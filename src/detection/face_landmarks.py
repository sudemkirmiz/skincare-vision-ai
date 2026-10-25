# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Sudem Kırmız
from __future__ import annotations

import logging
import math
import threading
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

logger = logging.getLogger("skincare.landmarks")


@dataclass(frozen=True)
class HeadPose:
    yaw: float
    pitch: float
    roll: float

    def to_dict(self) -> dict[str, float]:
        return {"yaw": round(self.yaw, 1), "pitch": round(self.pitch, 1), "roll": round(self.roll, 1)}


@dataclass(frozen=True)
class FaceLandmarkResult:
    landmarks: np.ndarray  # (478, 2) pixel coordinates in the source image, may lie outside it
    box: tuple[int, int, int, int]  # x, y, w, h clipped to the image
    pose: HeadPose | None
    face_count: int


def mediapipe_available() -> bool:
    try:
        import mediapipe  # noqa: F401
        from mediapipe.tasks.python import vision  # noqa: F401
    except ImportError:
        return False
    return True


def pose_from_matrix(matrix: np.ndarray) -> HeadPose:
    rotation = np.asarray(matrix, dtype=float)[:3, :3]
    yaw = math.degrees(math.asin(max(-1.0, min(1.0, -rotation[2, 0]))))
    pitch = math.degrees(math.atan2(rotation[2, 1], rotation[2, 2]))
    roll = math.degrees(math.atan2(rotation[1, 0], rotation[0, 0]))
    return HeadPose(yaw=yaw, pitch=pitch, roll=roll)


class FaceLandmarkAnalyzer:
    """MediaPipe Face Landmarker (478 points). Far more robust than Haar on angled and close-up faces."""

    def __init__(self, model_path: str | Path, min_confidence: float = 0.3) -> None:
        from mediapipe.tasks.python import vision
        from mediapipe.tasks.python.core.base_options import BaseOptions

        model_path = Path(model_path)
        if not model_path.exists():
            raise FileNotFoundError(f"Face landmarker model not found: {model_path}")

        options = vision.FaceLandmarkerOptions(
            base_options=BaseOptions(model_asset_buffer=model_path.read_bytes()),
            num_faces=3,
            min_face_detection_confidence=min_confidence,
            min_face_presence_confidence=min_confidence,
            output_facial_transformation_matrixes=True,
        )
        self._landmarker = vision.FaceLandmarker.create_from_options(options)
        # One cached instance is shared across Streamlit sessions.
        self._lock = threading.Lock()

    def close(self) -> None:
        """Release MediaPipe's native graph; without this, short-lived processes can hang on exit."""
        with self._lock:
            self._landmarker.close()

    def detect(self, image_bgr: np.ndarray) -> FaceLandmarkResult | None:
        import mediapipe as mp

        height, width = image_bgr.shape[:2]
        rgb = np.ascontiguousarray(cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB))
        with self._lock:
            result = self._landmarker.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb))

        if not result.face_landmarks:
            return None

        faces = [np.array([[point.x * width, point.y * height] for point in face], dtype=np.float32) for face in result.face_landmarks]
        index = max(range(len(faces)), key=lambda i: float(np.ptp(faces[i][:, 0]) * np.ptp(faces[i][:, 1])))
        landmarks = faces[index]

        x1, y1 = np.floor(landmarks.min(axis=0)).astype(int)
        x2, y2 = np.ceil(landmarks.max(axis=0)).astype(int)
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(width, x2), min(height, y2)
        if x2 - x1 < 20 or y2 - y1 < 20:
            return None

        pose = None
        matrices = getattr(result, "facial_transformation_matrixes", None)
        if matrices and len(matrices) > index:
            pose = pose_from_matrix(np.array(matrices[index]))

        return FaceLandmarkResult(
            landmarks=landmarks,
            box=(int(x1), int(y1), int(x2 - x1), int(y2 - y1)),
            pose=pose,
            face_count=len(faces),
        )
