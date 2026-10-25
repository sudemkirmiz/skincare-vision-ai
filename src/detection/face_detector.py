# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Sudem Kırmız
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from preprocessing.imaging import read_image, write_image


@dataclass(frozen=True)
class FaceDetectionResult:
    face_detected: bool
    confidence: float
    box: tuple[int, int, int, int] | None
    face_count: int = 0


class OpenCVFaceDetector:
    def __init__(self) -> None:
        cascade_dir = Path(cv2.data.haarcascades)
        self.detector = cv2.CascadeClassifier(str(cascade_dir / "haarcascade_frontalface_default.xml"))
        self.profile_detector = cv2.CascadeClassifier(str(cascade_dir / "haarcascade_profileface.xml"))

        if self.detector.empty():
            raise RuntimeError("OpenCV face cascade could not be loaded.")

    def detect(self, image: str | Path | np.ndarray) -> FaceDetectionResult:
        if not isinstance(image, np.ndarray):
            image = read_image(image)

        gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        min_side = max(60, int(min(gray_image.shape[:2]) * 0.08))
        faces = self._find_faces(gray_image, (min_side, min_side))

        if len(faces) == 0:
            return FaceDetectionResult(face_detected=False, confidence=0.0, box=None, face_count=0)

        largest_face = max(faces, key=lambda face: face[2] * face[3])
        x, y, width, height = [int(value) for value in largest_face]

        return FaceDetectionResult(
            face_detected=True,
            # Haar cascades give no calibrated probability; 1.0 only means "found".
            confidence=1.0,
            box=(x, y, width, height),
            face_count=len(faces),
        )

    def _find_faces(self, gray_image: np.ndarray, min_size: tuple[int, int]) -> list:
        """Strict frontal pass first, then progressively looser passes for close-ups and angled faces."""
        equalized = cv2.equalizeHist(gray_image)
        passes = [
            (self.detector, gray_image, 5, False),
            (self.detector, equalized, 4, False),
            (self.detector, equalized, 3, False),
            (self.profile_detector, equalized, 4, False),
            (self.profile_detector, equalized, 4, True),
        ]
        image_width = gray_image.shape[1]
        for cascade, source, min_neighbors, mirrored in passes:
            if cascade.empty():
                continue
            target = cv2.flip(source, 1) if mirrored else source
            faces = cascade.detectMultiScale(target, scaleFactor=1.1, minNeighbors=min_neighbors, minSize=min_size)
            if len(faces):
                if mirrored:
                    faces = [(image_width - x - w, y, w, h) for x, y, w, h in faces]
                return list(faces)
        return []

    def crop_face(
        self,
        image_path: str | Path,
        output_path: str | Path,
        padding_ratio: float = 0.15,
        detection: FaceDetectionResult | None = None,
    ) -> Path:
        image = read_image(image_path)
        if detection is None:
            detection = self.detect(image)
        if not detection.face_detected or detection.box is None:
            raise ValueError("No face was detected, so a crop cannot be created.")

        x, y, width, height = detection.box
        image_height, image_width = image.shape[:2]

        padding_x = int(width * padding_ratio)
        padding_y = int(height * padding_ratio)

        left = max(0, x - padding_x)
        top = max(0, y - padding_y)
        right = min(image_width, x + width + padding_x)
        bottom = min(image_height, y + height + padding_y)

        return write_image(image[top:bottom, left:right], output_path, quality=95)


if __name__ == "__main__":
    detector = OpenCVFaceDetector()
    detection_result = detector.detect("inputs/sample.jpg")
    print(detection_result)

    if detection_result.face_detected:
        crop_path = detector.crop_face("inputs/sample.jpg", "outputs/face_crop.jpg", detection=detection_result)
        print(f"Face crop saved: {crop_path}")
