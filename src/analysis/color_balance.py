# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Sudem Kırmız
"""White balance using the eye whites (sclera) as a natural colour reference.

Warm indoor light or a phone's auto white balance shifts skin colour, which moves the
redness and tone metrics between photos of the same face. The sclera has a stable,
slightly warm colour, so scaling the channels until it matches that reference removes most
of the cast. Used only for the metrics; YOLO and the displayed image keep the original pixels.
"""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from analysis.regions import LEFT_EYE, RIGHT_EYE

LEFT_IRIS = [474, 475, 476, 477]
RIGHT_IRIS = [469, 470, 471, 472]
LEFT_IRIS_CENTER = 473
RIGHT_IRIS_CENTER = 468
MIN_SCLERA_PIXELS = 60
GAIN_LIMITS = (0.75, 1.35)
# Bloodshot eyes are not a usable reference. A warm light cast raises a* *and* b* together
# (orange), while irritation raises a* well above b* (red), so both conditions are required.
MAX_SCLERA_REDNESS = 18.0  # CIELAB a*
MAX_SCLERA_RED_OVER_YELLOW = 8.0  # a* - b*
MIN_SCLERA_LIGHTNESS = 45.0  # dark sclera = shadowed eyes, unreliable
# Healthy sclera is not pure white but slightly warm. Measured on the sample photos under
# neutral light (BGR channel / mean; spread +-0.02). Balancing to this instead of grey keeps
# neutral photos almost unchanged, so the metric calibration stays valid.
SCLERA_REFERENCE_RATIO_BGR = (0.938, 0.966, 1.097)


@dataclass(frozen=True)
class WhiteBalance:
    applied: bool
    reason: str
    gains: tuple[float, float, float] = (1.0, 1.0, 1.0)  # B, G, R
    sclera_pixels: int = 0

    def to_dict(self) -> dict:
        return {"applied": self.applied, "reason": self.reason, "gains_bgr": [round(g, 3) for g in self.gains], "sclera_pixels": self.sclera_pixels}


def sclera_mask(image_shape: tuple[int, int], landmarks: np.ndarray) -> np.ndarray:
    """Eye opening minus a slightly enlarged iris disc."""
    height, width = image_shape[:2]
    mask = np.zeros((height, width), dtype=np.uint8)
    for eye, iris, center in ((LEFT_EYE, LEFT_IRIS, LEFT_IRIS_CENTER), (RIGHT_EYE, RIGHT_IRIS, RIGHT_IRIS_CENTER)):
        eye_mask = np.zeros_like(mask)
        cv2.fillConvexPoly(eye_mask, cv2.convexHull(np.round(landmarks[eye]).astype(np.int32)), 1)
        iris_points = landmarks[iris]
        radius = float(np.linalg.norm(iris_points - landmarks[center], axis=1).mean()) * 1.25
        cv2.circle(eye_mask, tuple(np.round(landmarks[center]).astype(int)), max(1, int(round(radius))), 0, -1)
        # Shrink away from eyelids and lashes.
        eye_mask = cv2.erode(eye_mask, np.ones((3, 3), np.uint8))
        mask |= eye_mask
    return mask.astype(bool)


def estimate_white_balance(image_bgr: np.ndarray, landmarks: np.ndarray | None) -> WhiteBalance:
    if landmarks is None or len(landmarks) <= LEFT_IRIS_CENTER:
        return WhiteBalance(False, "Yüz haritası yok")
    mask = sclera_mask(image_bgr.shape, landmarks)
    if mask.sum() < MIN_SCLERA_PIXELS:
        return WhiteBalance(False, "Göz akı yeterince görünmüyor", sclera_pixels=int(mask.sum()))

    lab = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
    lightness = lab[..., 0][mask] * 100 / 255
    # Brightest half of the eye opening: sclera, not lashes/shadow/veins.
    bright = lightness >= np.percentile(lightness, 50)
    pixels = image_bgr[mask][bright].astype(np.float32)
    if len(pixels) < MIN_SCLERA_PIXELS // 2:
        return WhiteBalance(False, "Göz akı yeterince görünmüyor", sclera_pixels=len(pixels))
    redness = float(np.median(lab[..., 1][mask][bright] - 128))
    yellowness = float(np.median(lab[..., 2][mask][bright] - 128))
    if redness > MAX_SCLERA_REDNESS and redness - yellowness > MAX_SCLERA_RED_OVER_YELLOW:
        return WhiteBalance(False, "Göz akı kırmızımsı; referans olarak kullanılmadı", sclera_pixels=len(pixels))
    if float(np.median(lightness[bright])) < MIN_SCLERA_LIGHTNESS:
        return WhiteBalance(False, "Gözler gölgede; referans olarak kullanılmadı", sclera_pixels=len(pixels))

    reference = np.median(pixels, axis=0)  # B, G, R
    target = float(reference.mean()) * np.array(SCLERA_REFERENCE_RATIO_BGR, dtype=np.float32)
    gains = np.clip(target / np.maximum(reference, 1.0), *GAIN_LIMITS)
    return WhiteBalance(True, "Göz akı referansıyla renk dengelendi", tuple(float(g) for g in gains), len(pixels))


def apply_white_balance(image_bgr: np.ndarray, balance: WhiteBalance) -> np.ndarray:
    if not balance.applied:
        return image_bgr
    balanced = image_bgr.astype(np.float32) * np.array(balance.gains, dtype=np.float32)
    return np.clip(balanced, 0, 255).astype(np.uint8)
