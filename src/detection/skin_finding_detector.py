# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Sudem Kırmız
from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from ultralytics import YOLO

from preprocessing.imaging import read_image, write_image


@dataclass(frozen=True)
class LetterboxInfo:
    original_width: int
    original_height: int
    target_width: int
    target_height: int
    resized_width: int
    resized_height: int
    scale: float
    pad_left: int
    pad_top: int


@dataclass(frozen=True)
class SkinFinding:
    label: str
    confidence: float
    box_640_xyxy: list[int]
    box_640_xywh: list[int]
    box_original_xyxy: list[int]
    box_original_xywh: list[int]


@dataclass(frozen=True)
class SkinFindingResult:
    image_path: str
    model_path: str
    confidence_threshold: float
    letterbox: LetterboxInfo
    findings: list[SkinFinding]
    summary: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SkinFindingDetector:
    def __init__(
        self,
        model_path: str | Path = "models/acne_like_spot.pt",
        target_size: int = 640,
        confidence_threshold: float = 0.10,
        iou_threshold: float = 0.5,
    ) -> None:
        self.model_path = Path(model_path)
        self.target_size = target_size
        self.confidence_threshold = confidence_threshold
        # Lower than Ultralytics' 0.7 default: nested duplicate boxes on the same spot were common.
        self.iou_threshold = iou_threshold

        if not self.model_path.exists():
            raise FileNotFoundError(f"YOLO model file not found: {self.model_path}")

        self.model = YOLO(str(self.model_path))
        # One cached instance is shared across Streamlit sessions; predict() is not thread-safe.
        self._predict_lock = threading.Lock()

    def detect(
        self,
        image_path: str | Path,
        output_json_path: str | Path | None = None,
    ) -> SkinFindingResult:
        image_path = Path(image_path)
        image = read_image(image_path)

        letterboxed_image, letterbox_info = letterbox_image(
            image=image,
            target_size=self.target_size,
        )

        with self._predict_lock:
            predictions = self.model.predict(
                source=letterboxed_image,
                imgsz=self.target_size,
                conf=self.confidence_threshold,
                iou=self.iou_threshold,
                verbose=False,
            )

        findings = self._parse_predictions(predictions, letterbox_info)
        result = SkinFindingResult(
            image_path=str(image_path),
            model_path=str(self.model_path),
            confidence_threshold=self.confidence_threshold,
            letterbox=letterbox_info,
            findings=findings,
            summary={
                "total_detections": len(findings),
                "class_counts": {"acne_like_spot": len(findings)},
            },
        )

        if output_json_path is not None:
            self.write_json(result, output_json_path)

        return result

    def write_json(
        self,
        result: SkinFindingResult,
        output_json_path: str | Path,
    ) -> Path:
        output_json_path = Path(output_json_path)
        output_json_path.parent.mkdir(parents=True, exist_ok=True)

        with output_json_path.open("w", encoding="utf-8") as file:
            json.dump(result.to_dict(), file, ensure_ascii=False, indent=2)

        return output_json_path

    def draw_findings(
        self,
        image_path: str | Path,
        result: SkinFindingResult,
        output_image_path: str | Path,
    ) -> Path:
        return draw_findings_on_image(image_path, result, output_image_path)

    def _parse_predictions(
        self,
        predictions: list[Any],
        letterbox_info: LetterboxInfo,
    ) -> list[SkinFinding]:
        if not predictions:
            return []

        result = predictions[0]
        boxes = result.boxes
        if boxes is None or len(boxes) == 0:
            return []

        findings: list[SkinFinding] = []

        for box in boxes:
            xyxy = box.xyxy[0].detach().cpu().numpy().tolist()
            confidence = float(box.conf[0].detach().cpu().item())

            box_640_xyxy = [int(round(value)) for value in xyxy]
            box_original_xyxy = map_letterbox_box_to_original(
                box_640_xyxy,
                letterbox_info,
            )

            findings.append(
                SkinFinding(
                    label="acne_like_spot",
                    confidence=round(confidence, 4),
                    box_640_xyxy=box_640_xyxy,
                    box_640_xywh=xyxy_to_xywh(box_640_xyxy),
                    box_original_xyxy=box_original_xyxy,
                    box_original_xywh=xyxy_to_xywh(box_original_xyxy),
                )
            )

        return findings


def letterbox_image(
    image: np.ndarray,
    target_size: int = 640,
    color: tuple[int, int, int] = (0, 0, 0),
) -> tuple[np.ndarray, LetterboxInfo]:
    original_height, original_width = image.shape[:2]
    target_width = target_size
    target_height = target_size

    scale = min(target_width / original_width, target_height / original_height)
    resized_width = int(round(original_width * scale))
    resized_height = int(round(original_height * scale))

    resized_image = cv2.resize(
        image,
        (resized_width, resized_height),
        interpolation=cv2.INTER_LINEAR,
    )

    pad_left = (target_width - resized_width) // 2
    pad_right = target_width - resized_width - pad_left
    pad_top = (target_height - resized_height) // 2
    pad_bottom = target_height - resized_height - pad_top

    letterboxed_image = cv2.copyMakeBorder(
        resized_image,
        pad_top,
        pad_bottom,
        pad_left,
        pad_right,
        borderType=cv2.BORDER_CONSTANT,
        value=color,
    )

    info = LetterboxInfo(
        original_width=original_width,
        original_height=original_height,
        target_width=target_width,
        target_height=target_height,
        resized_width=resized_width,
        resized_height=resized_height,
        scale=scale,
        pad_left=pad_left,
        pad_top=pad_top,
    )

    return letterboxed_image, info


def map_letterbox_box_to_original(
    box_xyxy: list[int],
    letterbox_info: LetterboxInfo,
) -> list[int]:
    x1, y1, x2, y2 = box_xyxy

    mapped_x1 = int(round((x1 - letterbox_info.pad_left) / letterbox_info.scale))
    mapped_y1 = int(round((y1 - letterbox_info.pad_top) / letterbox_info.scale))
    mapped_x2 = int(round((x2 - letterbox_info.pad_left) / letterbox_info.scale))
    mapped_y2 = int(round((y2 - letterbox_info.pad_top) / letterbox_info.scale))

    mapped_x1 = clamp(mapped_x1, 0, letterbox_info.original_width)
    mapped_y1 = clamp(mapped_y1, 0, letterbox_info.original_height)
    mapped_x2 = clamp(mapped_x2, 0, letterbox_info.original_width)
    mapped_y2 = clamp(mapped_y2, 0, letterbox_info.original_height)

    return [mapped_x1, mapped_y1, mapped_x2, mapped_y2]


def xyxy_to_xywh(box_xyxy: list[int]) -> list[int]:
    x1, y1, x2, y2 = box_xyxy
    return [x1, y1, max(0, x2 - x1), max(0, y2 - y1)]


def clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(value, maximum))


def confidence_color(confidence: float) -> tuple[int, int, int]:
    if confidence >= 0.5:
        return (40, 40, 230)
    if confidence >= 0.25:
        return (0, 120, 255)
    return (0, 200, 255)


def draw_finding_boxes(image: np.ndarray, result: SkinFindingResult) -> np.ndarray:
    output = image.copy()
    thickness = max(1, round(min(output.shape[:2]) / 400))

    # No per-box text: labels overlapped on dense areas. Colour encodes confidence instead
    # (amber = low, orange = medium, red = high); exact values live in the JSON output.
    for finding in result.findings:
        x1, y1, x2, y2 = finding.box_original_xyxy
        cv2.rectangle(output, (x1, y1), (x2, y2), color=confidence_color(finding.confidence), thickness=thickness)
    return output


def draw_findings_on_image(
    image_path: str | Path,
    result: SkinFindingResult,
    output_image_path: str | Path,
) -> Path:
    return write_image(draw_finding_boxes(read_image(image_path), result), output_image_path)


if __name__ == "__main__":
    detector = SkinFindingDetector()
    detection_result = detector.detect(
        "outputs/face_crop.jpg",
        output_json_path="outputs/skin_findings.json",
    )
    detector.draw_findings(
        "outputs/face_crop.jpg",
        detection_result,
        "outputs/skin_findings_annotated.jpg",
    )
    print(json.dumps(detection_result.to_dict(), ensure_ascii=False, indent=2))
