# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Sudem Kırmız
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from config import PROJECT_ROOT
from detection.face_detector import FaceDetectionResult, OpenCVFaceDetector
from output.json_writer import JsonWriter
from preprocessing.imaging import read_image, write_image
from preprocessing.quality_checker import ImageQualityChecker, ImageQualityResult
from safety.safe_response_builder import DISCLAIMER

if TYPE_CHECKING:
    from detection.face_landmarks import FaceLandmarkAnalyzer, HeadPose

INPUT_IMAGE_PATH = PROJECT_ROOT / "inputs" / "sample.jpg"
FACE_CROP_PATH = PROJECT_ROOT / "outputs" / "face_crop.jpg"
RESULT_JSON_PATH = PROJECT_ROOT / "outputs" / "result.json"

MAX_YAW_DEGREES = 30.0
MAX_PITCH_DEGREES = 25.0
LANDMARK_CROP_PADDING = 0.06
# Landmarks end below the hairline; keep the upper forehead in the crop.
LANDMARK_CROP_TOP_EXTRA = 0.15


def run_pipeline(
    input_image_path: str | Path = INPUT_IMAGE_PATH,
    face_crop_path: str | Path = FACE_CROP_PATH,
    result_json_path: str | Path | None = RESULT_JSON_PATH,
    face_detector: OpenCVFaceDetector | None = None,
    quality_checker: ImageQualityChecker | None = None,
    full_image_fallback: bool = False,
    landmark_analyzer: FaceLandmarkAnalyzer | None = None,
) -> dict:
    """Face localisation cascade: MediaPipe landmarks -> Haar cascade -> (optional) whole image.

    When landmarks are found, `detected_regions["landmarks"]` holds them in crop coordinates
    for region analysis; callers should pop it before serialising the result.
    """
    input_image_path = Path(input_image_path)
    face_crop_path = Path(face_crop_path)
    quality_checker = quality_checker or ImageQualityChecker()
    image = read_image(input_image_path)

    if landmark_analyzer is not None:
        landmark_result = landmark_analyzer.detect(image)
        if landmark_result is not None:
            left, top, right, bottom = _padded_box(landmark_result.box, image.shape, LANDMARK_CROP_PADDING, top_extra=LANDMARK_CROP_TOP_EXTRA)
            crop = image[top:bottom, left:right]
            write_image(crop, face_crop_path, quality=95)
            quality_result = _with_pose_check(quality_checker.check(crop), landmark_result.pose)
            detection = FaceDetectionResult(True, 1.0, landmark_result.box, landmark_result.face_count)
            result = _build_result(quality_result, detection, face_crop_path, "face", method="mediapipe")
            result["detected_regions"]["head_pose"] = landmark_result.pose.to_dict() if landmark_result.pose else None
            result["detected_regions"]["landmarks"] = (landmark_result.landmarks - np.array([left, top], dtype=np.float32)).tolist()
            _write(result, result_json_path)
            return result

    detector = face_detector or OpenCVFaceDetector()
    detection_result = detector.detect(image)

    if detection_result.face_detected:
        detector.crop_face(input_image_path, face_crop_path, detection=detection_result)
        quality_result = quality_checker.check(face_crop_path)
        result = _build_result(quality_result, detection_result, face_crop_path, "face", method="haar")
        _write(result, result_json_path)
        return result

    if full_image_fallback:
        # Close-up skin photos often have no detectable face; analyse the whole frame instead.
        write_image(image, face_crop_path, quality=95)
        quality_result = quality_checker.check(image)
        result = _build_result(quality_result, detection_result, face_crop_path, "full_image", method="full_image")
        _write(result, result_json_path)
        return result

    result = {
        "image_quality": None,
        "detected_regions": {
            "face_detected": False,
            "face_confidence": 0.0,
            "face_count": 0,
            "face_crop_path": None,
            "analysis_region": None,
            "method": None,
        },
        "visible_observations": [],
        "care_suggestions": [],
        "disclaimer": DISCLAIMER,
    }
    _write(result, result_json_path)
    return result


def _padded_box(
    box: tuple[int, int, int, int], shape: tuple[int, ...], padding: float, top_extra: float = 0.0
) -> tuple[int, int, int, int]:
    x, y, width, height = box
    image_height, image_width = shape[:2]
    pad_x, pad_y = int(width * padding), int(height * padding)
    pad_top = pad_y + int(height * top_extra)
    return max(0, x - pad_x), max(0, y - pad_top), min(image_width, x + width + pad_x), min(image_height, y + height + pad_y)


def _with_pose_check(quality: ImageQualityResult, pose: HeadPose | None) -> ImageQualityResult:
    if pose is None or (abs(pose.yaw) <= MAX_YAW_DEGREES and abs(pose.pitch) <= MAX_PITCH_DEGREES):
        return quality
    note = "Yüz belirgin şekilde yana veya yukarı/aşağı dönük; karşıdan çekilmiş bir fotoğraf daha dengeli sonuç verir."
    notes = note if quality.status == "good" else f"{quality.notes} {note}"
    return ImageQualityResult("needs_review", notes, quality.width, quality.height, quality.brightness, quality.blur_score)


def _build_result(
    quality_result: ImageQualityResult,
    detection_result: FaceDetectionResult,
    face_crop_path: Path,
    analysis_region: str,
    method: str,
) -> dict:
    return {
        "image_quality": {
            "status": quality_result.status,
            "notes": quality_result.notes,
            "width": quality_result.width,
            "height": quality_result.height,
            "brightness": quality_result.brightness,
            "blur_score": quality_result.blur_score,
        },
        "detected_regions": {
            "face_detected": detection_result.face_detected,
            "face_confidence": detection_result.confidence,
            "face_count": detection_result.face_count,
            "face_box": detection_result.box,
            "face_crop_path": str(face_crop_path),
            "analysis_region": analysis_region,
            "method": method,
        },
        "visible_observations": [],
        "care_suggestions": [],
        "disclaimer": DISCLAIMER,
    }


def _write(result: dict, result_json_path: str | Path | None) -> None:
    if result_json_path is None:
        return
    serialisable = {**result, "detected_regions": {k: v for k, v in result["detected_regions"].items() if k != "landmarks"}}
    JsonWriter().write(serialisable, result_json_path)


if __name__ == "__main__":
    pipeline_result = run_pipeline()
    print(pipeline_result)
