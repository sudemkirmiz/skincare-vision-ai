from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from imaging import read_image


@dataclass(frozen=True)
class ImageQualityResult:
    status: str
    notes: str
    width: int
    height: int
    brightness: float
    blur_score: float


class ImageQualityChecker:
    def __init__(
        self,
        min_size: int = 400,
        min_brightness: float = 45.0,
        max_brightness: float = 220.0,
        min_blur_score: float = 80.0,
    ) -> None:
        self.min_size = min_size
        self.min_brightness = min_brightness
        self.max_brightness = max_brightness
        self.min_blur_score = min_blur_score

    def check(self, image: str | Path | np.ndarray) -> ImageQualityResult:
        if not isinstance(image, np.ndarray):
            image = read_image(image)

        height, width = image.shape[:2]
        gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        brightness = float(gray_image.mean())
        blur_score = float(cv2.Laplacian(gray_image, cv2.CV_64F).var())

        warnings: list[str] = []

        if width < self.min_size or height < self.min_size:
            warnings.append("Görsel boyutu düşük; daha yüksek çözünürlüklü bir fotoğraf tercih edilebilir.")

        if brightness < self.min_brightness:
            warnings.append("Fotoğraf karanlık görünüyor; daha iyi aydınlatılmış bir fotoğraf tercih edilebilir.")
        elif brightness > self.max_brightness:
            warnings.append("Fotoğraf çok parlak görünüyor; ışık patlaması analizi zorlaştırabilir.")

        if blur_score < self.min_blur_score:
            warnings.append("Fotoğrafta bulanıklık olabilir; daha net bir fotoğraf tercih edilebilir.")

        if warnings:
            status = "needs_review"
            notes = " ".join(warnings)
        else:
            status = "good"
            notes = "Fotoğraf boyutu, ışık ve netlik temel analiz için uygun görünüyor."

        return ImageQualityResult(
            status=status,
            notes=notes,
            width=width,
            height=height,
            brightness=round(brightness, 2),
            blur_score=round(blur_score, 2),
        )


if __name__ == "__main__":
    checker = ImageQualityChecker()
    result = checker.check("outputs/face_crop.jpg")
    print(result)
