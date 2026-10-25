# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Sudem Kırmız
"""Analysis orchestration, independent of the UI.

The Streamlit app, the sample regression script and any future API all call
`AnalysisService.analyze`, so the pipeline behaves identically everywhere.
"""
from __future__ import annotations

import base64
import logging
import tempfile
import time
import uuid
from collections.abc import Callable
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageOps

from analysis.color_balance import apply_white_balance, estimate_white_balance
from analysis.local_comment import build_local_comment
from analysis.multiview import merge_views, primary_view_index
from analysis.pipeline import run_pipeline
from analysis.regions import REGION_NAMES, build_region_map, draw_region_overlay, summarize_regions
from analysis.second_opinion import apply_to_metrics, parse_gemini_boxes, reconcile
from analysis.skin_metrics import GEMINI_RING, compute_skin_metrics, draw_spot_candidates
from config import Settings
from detection.face_detector import OpenCVFaceDetector
from detection.face_landmarks import FaceLandmarkAnalyzer
from detection.skin_finding_detector import SkinFindingDetector, draw_finding_boxes
from preprocessing.imaging import read_image, write_image
from preprocessing.quality_checker import ImageQualityChecker
from recommendation.engine import build_routine, routine_summary_for_vlm
from recommendation.profile import SkinProfile
from vlm.engine import VLMEngine, VLMOptions, VLMProviderError
from vlm.quality import check_vlm_output, quality_score
from vlm.router import ProviderTarget, VLMRouter, describe_fallback

logger = logging.getLogger("skincare.service")

PROVIDER_ENV_KEYS = {"Gemini": "GEMINI_API_KEY", "OpenAI": "OPENAI_API_KEY", "Hugging Face": "HF_TOKEN", "Groq": "GROQ_API_KEY"}
PREVIEW_MAX_SIDE = 1000
THUMBNAIL_MAX_SIDE = 320
NOTICEABLE_CAST = 0.08  # channel gain deviation worth telling the user about  # stored in history; small on purpose


def save_uploaded_image(data: bytes, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(BytesIO(data)) as image:
        image = ImageOps.exif_transpose(image)
        if image.mode != "RGB":
            image = image.convert("RGB")
        # Re-encoding drops EXIF (GPS, device) metadata.
        image.save(output_path, format="JPEG", quality=95)
    return output_path


def image_to_data_uri(image_path: str | Path, max_side: int = PREVIEW_MAX_SIDE, quality: int = 88) -> str:
    with Image.open(image_path) as image:
        image = image.convert("RGB")
        image.thumbnail((max_side, max_side))
        buffer = BytesIO()
        image.save(buffer, format="JPEG", quality=quality)
    return "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def metrics_summary(skin_metrics: dict[str, Any]) -> dict[str, Any]:
    """The compact view of the metrics that the VLM receives."""
    return {
        "overall_score": skin_metrics["overall_score"],
        "scores": {skin_metrics["score_labels"][k]: v for k, v in skin_metrics["scores"].items() if v is not None},
        "skin_tone": skin_metrics["skin_tone"]["category"],
        "spot_counts": skin_metrics["spot_counts"],
        **({"views": skin_metrics["views"]} if skin_metrics.get("views") else {}),
    }


class AnalysisService:
    def __init__(
        self,
        settings: Settings,
        face_detector: OpenCVFaceDetector,
        quality_checker: ImageQualityChecker,
        skin_detector: Callable[[], SkinFindingDetector],
        landmark_analyzer: FaceLandmarkAnalyzer | None = None,
        router: VLMRouter | None = None,
    ) -> None:
        self.settings = settings
        # Shared across requests so provider health and the response cache persist.
        self.router = router or VLMRouter(VLMEngine(VLMOptions(
            gemini_model=settings.gemini_model,
            gemini_fallback_models=settings.gemini_fallback_models,
            groq_model=settings.groq_model,
            openai_model=settings.openai_model,
            timeout_seconds=settings.vlm_timeout_seconds,
            max_retries=settings.vlm_max_retries,
            trust_env_proxy=settings.vlm_trust_env_proxy,
        )))
        self.face_detector = face_detector
        self.quality_checker = quality_checker
        # Lazy so the YOLO model only loads when a face/region was actually found.
        self._skin_detector = skin_detector
        self.landmark_analyzer = landmark_analyzer

    def analyze(
        self,
        image_bytes: bytes,
        provider: str = "Gemini",
        hf_model: str | None = None,
        api_key: str = "",
        use_vlm: bool = True,
        profile: SkinProfile | None = None,
        fallback_keys: dict[str, str] | None = None,
        personalization: dict[str, str] | None = None,
        merged: dict[str, Any] | None = None,
        second_opinion: bool = False,
        previous: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Run the whole pipeline in a private temp dir so concurrent sessions never share files.

        Face photos are sensitive: nothing is kept on disk after the analysis finishes;
        only in-memory previews and JSON results are returned.
        """
        analysis_id = uuid.uuid4().hex[:12]
        started = time.perf_counter()
        with tempfile.TemporaryDirectory(prefix=f"skincare_{analysis_id}_") as work_dir:
            work = Path(work_dir)
            upload_path = save_uploaded_image(image_bytes, work / "upload.jpg")
            face_crop_path = work / "face_crop.jpg"
            annotated_path = work / "face_annotated.jpg"

            result = run_pipeline(
                input_image_path=upload_path,
                face_crop_path=face_crop_path,
                result_json_path=None,
                face_detector=self.face_detector,
                quality_checker=self.quality_checker,
                full_image_fallback=True,
                landmark_analyzer=self.landmark_analyzer,
            )
            result["detected_regions"].pop("face_crop_path", None)
            landmarks = result["detected_regions"].pop("landmarks", None)
            face_found = face_crop_path.exists()

            skin_findings_data = None
            region_summary = None
            skin_metrics = None
            if face_found:
                # Second opinion costs one Gemini call: single-photo analyses with AI comments only.
                typed_gemini_key = api_key.strip() if provider == "Gemini" else ""
                gemini_key = typed_gemini_key or (fallback_keys or {}).get("Gemini", "")
                opinion_key = gemini_key if second_opinion and use_vlm and not merged else ""
                skin_findings_data, region_summary, skin_metrics = self._detect_and_annotate(
                    face_crop_path, annotated_path, landmarks, opinion_key
                )
                if merged:
                    # Multi-angle: this photo supplies the crop for the AI; numbers come from all angles.
                    region_summary, skin_metrics = merged["region_summary"], merged["skin_metrics"]
                    skin_findings_data["region_summary"] = region_summary
                    skin_findings_data["skin_metrics_summary"] = metrics_summary(skin_metrics)

            routine = build_routine(skin_metrics, profile) if face_found else None
            if routine and skin_findings_data is not None:
                # The VLM sees the finished plan (and only VLM-safe profile fields) so its comments agree with it.
                skin_findings_data["routine_plan"] = routine_summary_for_vlm(routine, profile)
            if personalization and skin_findings_data is not None:
                # Only the display name and address form; never surname, age or health answers.
                skin_findings_data["user"] = {k: personalization[k] for k in ("hitap_adi", "hitap") if personalization.get(k)}

            chain = self._provider_chain(provider, api_key, hf_model, fallback_keys or {})
            vlm_output, vlm_error, vlm_attempts = self._run_vlm(
                analysis_id, face_found, face_crop_path, use_vlm, chain, skin_findings_data, result.get("image_quality"),
            )
            if vlm_output:
                vlm_output["quality_checks"] = check_vlm_output(vlm_output, skin_metrics, region_summary, routine, personalization)
                failed = [c["check"] for c in vlm_output["quality_checks"] if not c["ok"]]
                if failed:
                    # Monitoring signal for prompt regressions; the comment is still shown.
                    logger.warning("VLM quality checks failed analysis_id=%s provider=%s checks=%s", analysis_id, vlm_output["provider"], failed)
                vlm_output["quality_score"] = quality_score(vlm_output["quality_checks"])
                result["visible_observations"] = vlm_output["visible_observations"]
                result["care_suggestions"] = vlm_output["care_suggestions"]
                result["disclaimer"] = vlm_output["disclaimer"]
            comment_source = "ai" if vlm_output else None
            if not vlm_output and face_found:
                # No key, comment turned off or every provider failed: still explain the numbers, without AI.
                local = build_local_comment(skin_metrics, region_summary, routine, personalization, result.get("image_quality"),
                                            concerns=profile.concerns if profile else None, previous=previous)
                if local:
                    result.update(local)
                    comment_source = "local"

            original_uri = image_to_data_uri(upload_path)
            marked_source = annotated_path if annotated_path.exists() else face_crop_path
            marked_uri = image_to_data_uri(marked_source) if marked_source.exists() else None
            # Clean (unannotated) crop for history before/after views.
            face_thumbnail_uri = image_to_data_uri(face_crop_path, THUMBNAIL_MAX_SIDE, 80) if face_crop_path.exists() else None

        detections = int((skin_findings_data or {}).get("summary", {}).get("total_detections", 0))
        logger.info(
            "Analysis done analysis_id=%s method=%s detections=%s vlm=%s elapsed=%.2fs",
            analysis_id, result["detected_regions"].get("method"), detections, bool(vlm_output), time.perf_counter() - started,
        )
        return {
            "analysis_id": analysis_id,
            "result": result,
            "skin_findings": skin_findings_data,
            "vlm_output": vlm_output,
            "vlm_error": vlm_error,
            "comment_source": comment_source,
            "vlm_attempts": vlm_attempts,
            "vlm_note": describe_fallback(vlm_attempts, vlm_output["provider"]) if vlm_output and not vlm_output.get("cached") else None,
            "face_found": face_found,
            "region_summary": region_summary,
            "skin_metrics": skin_metrics,
            "routine": routine,
            "original_uri": original_uri,
            "marked_uri": marked_uri,
            "face_thumbnail_uri": face_thumbnail_uri,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }

    def analyze_views(self, images: list[bytes], **options: Any) -> dict[str, Any]:
        """1-3 photos of the same face. One VLM call (on the most frontal photo) with merged numbers."""
        if len(images) == 1:
            return self.analyze(images[0], **options)
        drafts = [self.analyze(image, **{**options, "use_vlm": False, "second_opinion": False}) for image in images]
        usable = [draft for draft in drafts if draft["face_found"]]
        if not usable:
            return drafts[0]
        primary = primary_view_index(usable)
        try:
            merged = merge_views(usable)
        except ValueError:
            logger.warning("Multi-view merge not possible; using the most frontal photo only")
            return self.analyze(images[drafts.index(usable[primary])], **options)
        final = self.analyze(images[drafts.index(usable[primary])], **options, merged=merged)
        final["views"] = [
            {
                "original_uri": draft["original_uri"],
                "marked_uri": draft["marked_uri"],
                "yaw": (draft["result"]["detected_regions"].get("head_pose") or {}).get("yaw"),
                "primary": index == primary,
            }
            for index, draft in enumerate(usable)
        ]
        final["provenance"] = merged["provenance"]
        final["skipped_views"] = len(drafts) - len(usable)
        return final

    def _second_opinion(self, crop_path: Path, crop_shape: tuple[int, ...], api_key: str) -> list[list[int]]:
        """Gemini spot boxes in crop pixels; raises VLMProviderError on any provider problem."""
        raw = self.router.engine.detect_spots("Gemini", crop_path, api_key)
        return parse_gemini_boxes(raw, crop_shape[1], crop_shape[0])

    def _detect_and_annotate(
        self, face_crop_path: Path, annotated_path: Path, landmarks: list | None, second_opinion_key: str = ""
    ) -> tuple[dict[str, Any], dict[str, Any] | None, dict[str, Any] | None]:
        skin_detector = self._skin_detector()
        skin_findings = skin_detector.detect(face_crop_path)
        skin_findings_data = skin_findings.to_dict()
        # Local temp paths are meaningless outside this function.
        skin_findings_data.pop("image_path", None)
        skin_findings_data["model_path"] = Path(skin_findings_data["model_path"]).name
        yolo_boxes = [finding.box_original_xyxy for finding in skin_findings.findings]

        crop_image = read_image(face_crop_path)
        landmark_array = np.asarray(landmarks, dtype=np.float32) if landmarks is not None else None
        region_map = build_region_map(landmark_array, crop_image.shape[:2]) if landmark_array is not None else None

        # Colour cast correction only for the colour metrics; YOLO already ran on the original crop.
        white_balance = estimate_white_balance(crop_image, landmark_array)
        try:
            skin_metrics = compute_skin_metrics(apply_white_balance(crop_image, white_balance), landmark_array, region_map, yolo_boxes)
            if skin_metrics.get("available"):
                skin_metrics["white_balance"] = white_balance.to_dict()
                if white_balance.applied and max(abs(g - 1) for g in white_balance.gains) > NOTICEABLE_CAST:
                    skin_metrics["notes"].append("Fotoğraftaki renk sapması (ör. sarı oda ışığı) göz akı referansıyla düzeltildi; skorlar buna göre hesaplandı.")
        except Exception:
            # Metrics are an enrichment; never let them break the core analysis.
            logger.exception("Skin metrics failed")
            skin_metrics = {"available": False, "reason": "Cilt metrikleri hesaplanamadı."}
        candidates = skin_metrics.get("spot_candidates", []) if skin_metrics.get("available") else []
        gemini_spots: list[dict] = []
        if second_opinion_key and skin_metrics.get("available"):
            try:
                gemini_boxes = self._second_opinion(face_crop_path, crop_image.shape, second_opinion_key)
                merged = reconcile(yolo_boxes, candidates, gemini_boxes)
                apply_to_metrics(skin_metrics, merged["kept_colour"], merged["gemini_only"])
                candidates, gemini_spots = skin_metrics["spot_candidates"], skin_metrics["gemini_spots"]
                skin_metrics["second_opinion"] = {"status": "ok", **merged["stats"]}
                logger.info("Second opinion stats=%s", merged["stats"])
            except VLMProviderError as error:
                # Never block the analysis: fall back to YOLO + colour analysis.
                logger.warning("Second opinion skipped kind=%s", error.kind)
                skin_metrics["second_opinion"] = {"status": "skipped", "reason": error.kind}
                skin_metrics["notes"].append("Gemini ikinci görüşü bu analizde kullanılamadı (kota, anahtar veya bağlantı); noktalar YOLO ve renk analiziyle sayıldı.")

        region_summary = None
        if region_map is not None:
            # Regions count YOLO findings, colour candidates and Gemini-only spots together.
            all_boxes = yolo_boxes + [candidate["box_xyxy"] for candidate in candidates] + [spot["box_xyxy"] for spot in gemini_spots]
            region_summary = summarize_regions(region_map, all_boxes)
            assigned = region_summary.pop("finding_regions")
            for finding, region_key in zip(skin_findings_data["findings"], assigned[: len(yolo_boxes)], strict=True):
                finding["region"] = region_key
            colour_end = len(yolo_boxes) + len(candidates)
            for candidate, region_key in zip(candidates, assigned[len(yolo_boxes):colour_end], strict=True):
                candidate["region"] = region_key
            for spot, region_key in zip(gemini_spots, assigned[colour_end:], strict=True):
                spot["region"] = region_key
            most_affected = region_summary["most_affected"]
            region_summary["most_affected_name"] = REGION_NAMES.get(most_affected) if most_affected else None
            skin_findings_data["region_summary"] = region_summary
            crop_image = draw_region_overlay(crop_image, region_map)

        if skin_metrics.get("available"):
            skin_findings_data["skin_metrics_summary"] = metrics_summary(skin_metrics)
        crop_image = draw_spot_candidates(crop_image, candidates)
        crop_image = draw_spot_candidates(crop_image, gemini_spots, GEMINI_RING)
        write_image(draw_finding_boxes(crop_image, skin_findings), annotated_path)
        return skin_findings_data, region_summary, skin_metrics

    def _provider_chain(
        self, provider: str, api_key: str, hf_model: str | None, fallback_keys: dict[str, str]
    ) -> list[ProviderTarget]:
        """Requested provider first, then the configured fallbacks that have a key."""
        chain = [ProviderTarget(provider, api_key, hf_model if provider == "Hugging Face" else None)]
        if not self.settings.vlm_fallback:
            return chain
        for name in self.settings.vlm_fallback_order:
            if name != provider and fallback_keys.get(name, "").strip():
                chain.append(ProviderTarget(name, fallback_keys[name], self.settings.hf_model if name == "Hugging Face" else None))
        return chain

    def _run_vlm(
        self,
        analysis_id: str,
        face_found: bool,
        face_crop_path: Path,
        use_vlm: bool,
        chain: list[ProviderTarget],
        skin_findings_data: dict[str, Any] | None,
        quality_data: dict[str, Any] | None,
    ) -> tuple[dict[str, Any] | None, str | None, list[dict[str, Any]]]:
        if not face_found:
            return None, "Fotoğraf analiz edilemedi. Yüzün net ve kadrajın büyük kısmını kapladığı bir fotoğraf deneyin.", []
        if not use_vlm:
            return None, "Yapay zekâ yorumu ayarlarda kapalı olduğu için üretilmedi.", []
        if not any(target.api_key.strip() for target in chain):
            provider = chain[0].provider
            return None, f"{PROVIDER_ENV_KEYS.get(provider, 'API anahtarı')} tanımlı değil. Anahtarı .env dosyasına ekleyin veya kenar çubuğuna girin.", []
        try:
            output, attempts = self.router.analyze(
                chain, face_crop_path, skin_findings_data, quality_data, hf_provider=self.settings.hf_provider,
            )
            return output, None, attempts
        except VLMProviderError as error:
            logger.warning("All VLM providers failed analysis_id=%s kind=%s", analysis_id, error.kind)
            return None, str(error), []
        except Exception:
            logger.exception("Unexpected VLM error analysis_id=%s", analysis_id)
            return None, f"Beklenmeyen VLM hatası (kayıt no: {analysis_id}).", []
