"""Run the full analysis pipeline over every image in samples/ and summarise the results.

Usage:
    python scripts/evaluate_samples.py                 # pipeline only, no external API calls
    python scripts/evaluate_samples.py --vlm Gemini    # also call the VLM with the .env key

Annotated images and summary.json are written to outputs/samples/ (git-ignored).
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from analysis.service import PROVIDER_ENV_KEYS, AnalysisService  # noqa: E402
from config import configure_logging, get_settings, load_env_file  # noqa: E402
from detection.face_detector import OpenCVFaceDetector  # noqa: E402
from detection.face_landmarks import FaceLandmarkAnalyzer, mediapipe_available  # noqa: E402
from detection.skin_finding_detector import SkinFindingDetector  # noqa: E402
from preprocessing.quality_checker import ImageQualityChecker  # noqa: E402

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def build_service() -> AnalysisService:
    settings = get_settings()
    detector = SkinFindingDetector(settings.yolo_model_path, settings.yolo_image_size, settings.yolo_confidence)
    landmarks = None
    if mediapipe_available() and settings.face_landmarker_path.exists():
        landmarks = FaceLandmarkAnalyzer(settings.face_landmarker_path)
    return AnalysisService(settings, OpenCVFaceDetector(), ImageQualityChecker(), lambda: detector, landmarks)


def summarise(name: str, payload: dict, elapsed: float) -> dict:
    result = payload["result"]
    regions = result["detected_regions"]
    findings = payload.get("skin_findings") or {}
    region_summary = payload.get("region_summary") or {}
    confidences = [f["confidence"] for f in findings.get("findings", [])]
    return {
        "image": name,
        "method": regions.get("method"),
        "pose": regions.get("head_pose"),
        "quality": (result.get("image_quality") or {}).get("status"),
        "detections": findings.get("summary", {}).get("total_detections", 0),
        "mean_confidence": round(sum(confidences) / len(confidences), 3) if confidences else None,
        "regions": {r["key"]: r["count"] if r["visible"] else None for r in region_summary.get("regions", [])},
        "most_affected": region_summary.get("most_affected_name"),
        "skin_metrics": payload.get("skin_metrics"),
        "vlm_ok": payload.get("vlm_output") is not None,
        "vlm_provider": (payload.get("vlm_output") or {}).get("provider"),
        "vlm_attempts": payload.get("vlm_attempts"),
        "quality_score": (payload.get("vlm_output") or {}).get("quality_score"),
        "quality_checks": (payload.get("vlm_output") or {}).get("quality_checks"),
        "vlm_error": (payload.get("vlm_error") or "")[:200] or None,
        "observations": result.get("visible_observations", []),
        "suggestions": result.get("care_suggestions", []),
        "seconds": round(elapsed, 2),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--samples", type=Path, default=PROJECT_ROOT / "samples")
    parser.add_argument("--out", type=Path, default=PROJECT_ROOT / "outputs" / "samples")
    parser.add_argument("--vlm", choices=list(PROVIDER_ENV_KEYS), help="also run the VLM with this provider")
    args = parser.parse_args()

    load_env_file(PROJECT_ROOT / ".env")
    configure_logging("WARNING")
    images = sorted(p for p in args.samples.iterdir() if p.suffix.lower() in IMAGE_SUFFIXES)
    if not images:
        print(f"No images in {args.samples}")
        return 1

    service = build_service()
    api_key = os.getenv(PROVIDER_ENV_KEYS[args.vlm], "") if args.vlm else ""
    fallback_keys = {name: os.getenv(env, "") for name, env in PROVIDER_ENV_KEYS.items()}
    args.out.mkdir(parents=True, exist_ok=True)
    rows = []
    for image_path in images:
        started = time.perf_counter()
        payload = service.analyze(
            image_path.read_bytes(), provider=args.vlm or "Gemini", api_key=api_key, use_vlm=bool(args.vlm), fallback_keys=fallback_keys
        )
        row = summarise(image_path.name, payload, time.perf_counter() - started)
        rows.append(row)
        if payload.get("marked_uri"):
            (args.out / f"{image_path.stem}_annotated.jpg").write_bytes(base64.b64decode(payload["marked_uri"].split(",", 1)[1]))

        pose = row["pose"] or {}
        print(f"\n{row['image']}  [{row['method']}]  quality={row['quality']}  yaw={pose.get('yaw')} pitch={pose.get('pitch')}  {row['seconds']}s")
        print(f"  YOLO: {row['detections']} spots, mean conf {row['mean_confidence']}  |  most affected: {row['most_affected']}")
        print(f"  regions: {row['regions']}")
        if row["skin_metrics"]:
            print(f"  skin score: {row['skin_metrics'].get('overall_score')}  sub-scores: {row['skin_metrics'].get('scores')}")
        if args.vlm:
            attempts = " -> ".join(f"{a['provider']}:{a['status']}" + (f"({a['kind']})" if a.get("kind") else "") for a in row["vlm_attempts"] or [])
            print(f"  VLM: {'ok via ' + row['vlm_provider'] if row['vlm_ok'] else row['vlm_error']}  [{attempts}]")
            if row["quality_checks"]:
                failed = [f"{c['check']} ({c['detail']})" for c in row["quality_checks"] if not c["ok"]]
                print(f"  quality: {row['quality_score']}" + (f"  FAILED: {failed}" if failed else "  all checks passed"))
            for line in row["observations"][:3]:
                print(f"    - {line}")

    if args.vlm:
        scores = [r["quality_score"] for r in rows if r["quality_score"] is not None]
        if scores:
            print(f"\nMean VLM quality score: {sum(scores) / len(scores):.2f} over {len(scores)} images")
    (args.out / "summary.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nWrote {len(rows)} results to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
