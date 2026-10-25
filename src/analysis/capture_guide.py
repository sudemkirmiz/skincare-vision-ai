# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Sudem Kırmız
"""Live guidance for camera capture: checks one small preview frame and says what to fix first.

Frames are analysed in memory and never stored. The checks mirror what makes an analysis reliable:
one face, close enough, centred, steady, evenly lit and facing the camera (or turned for a side view).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import cv2
import numpy as np

if TYPE_CHECKING:
    from detection.face_landmarks import FaceLandmarkAnalyzer

# Face width as a share of the frame width.
MIN_FACE_WIDTH = 0.30
MAX_FACE_WIDTH = 0.72
# Face centre offset from the frame centre, as a share of the frame size.
MAX_CENTER_OFFSET = 0.13
# Mean face lightness (0-255) and share of blown-out pixels.
MIN_BRIGHTNESS = 75
MAX_BRIGHTNESS = 215
MAX_CLIPPED_SHARE = 0.08
# Laplacian variance of the face crop resized to 160 px wide.
MIN_SHARPNESS = 22.0
# Head pose (degrees).
FRONT_MAX_YAW = 10.0
FRONT_MAX_PITCH = 14.0
MAX_ROLL = 9.0
SIDE_MIN_YAW = 18.0
SIDE_MAX_YAW = 42.0
TARGETS = ("front", "side")


@dataclass
class Check:
    key: str
    ok: bool
    message: str


def _sharpness(gray_face: np.ndarray) -> float:
    height, width = gray_face.shape[:2]
    if width < 8 or height < 8:
        return 0.0
    scale = 160 / width
    resized = cv2.resize(gray_face, (160, max(8, int(height * scale))), interpolation=cv2.INTER_AREA)
    return float(cv2.Laplacian(resized, cv2.CV_64F).var())


def _pose_check(target: str, pose: Any, avoid_sign: int) -> Check:
    if pose is None:
        return Check("pose", True, "")
    yaw, pitch, roll = pose.yaw, pose.pitch, pose.roll
    if abs(roll) > MAX_ROLL:
        return Check("pose", False, "Başınızı dik tutun; yana eğmeyin.")
    if target == "front":
        if abs(yaw) > FRONT_MAX_YAW:
            return Check("pose", False, "Doğrudan kameraya bakın.")
        if abs(pitch) > FRONT_MAX_PITCH:
            # The pitch sign depends on the camera model, so the hint does not name a direction.
            return Check("pose", False, "Kamerayı göz hizasında tutun; başınızı yukarı veya aşağı eğmeyin.")
        return Check("pose", True, "")
    # Side view: a clear turn, but not so far that the far cheek disappears.
    if avoid_sign and np.sign(yaw) == avoid_sign and abs(yaw) >= SIDE_MIN_YAW / 2:
        return Check("pose", False, "Bu kez başınızı diğer yana çevirin.")
    if abs(yaw) < SIDE_MIN_YAW:
        return Check("pose", False, "Başınızı yavaşça bir yana çevirin.")
    if abs(yaw) > SIDE_MAX_YAW:
        return Check("pose", False, "Biraz fazla döndünüz; kameraya doğru hafifçe geri dönün.")
    return Check("pose", True, "")


def assess_frame(image_bgr: np.ndarray, landmarks: FaceLandmarkAnalyzer | None, target: str = "front", avoid_sign: int = 0) -> dict[str, Any]:
    """Return ok, the first thing to fix (Turkish), every check and the face box (0-1 coordinates)."""
    if target not in TARGETS:
        raise ValueError(f"Unknown capture target: {target}")
    height, width = image_bgr.shape[:2]
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)

    if landmarks is None:
        # No face model: only lighting can be checked; never block the user.
        mean = float(gray.mean())
        message = "Ortam karanlık; ışığa dönün." if mean < MIN_BRIGHTNESS else ""
        return {"guide_available": False, "ok": not message, "face": None, "message": message or "Hazır olduğunuzda çekin.", "checks": [], "box": None, "pose": None}

    face = landmarks.detect(image_bgr)
    if face is None:
        return {"guide_available": True, "ok": False, "face": False, "message": "Yüzünüzü çerçevenin içine getirin.", "checks": [], "box": None, "pose": None}

    x, y, w, h = face.box
    face_gray = gray[y:y + h, x:x + w]
    center_x = (x + w / 2) / width
    center_y = (y + h / 2) / height
    face_share = w / width
    clipped = float((face_gray >= 250).mean()) if face_gray.size else 0.0
    brightness = float(face_gray.mean()) if face_gray.size else 0.0

    checks = [
        Check("single_face", face.face_count == 1, "Kadrajda yalnızca bir yüz olsun."),
        Check("distance", face_share >= MIN_FACE_WIDTH, "Biraz yaklaşın."),
        Check("distance_far", face_share <= MAX_FACE_WIDTH, "Biraz uzaklaşın; yüzünüzün tamamı görünsün."),
        Check("centered", abs(center_x - 0.5) <= MAX_CENTER_OFFSET and abs(center_y - 0.5) <= MAX_CENTER_OFFSET * 1.3, "Yüzünüzü oval çerçevenin ortasına getirin."),
        _pose_check(target, face.pose, avoid_sign),
        Check("dark", brightness >= MIN_BRIGHTNESS, "Ortam karanlık; pencereye veya ışığa dönün."),
        Check("bright", brightness <= MAX_BRIGHTNESS and clipped <= MAX_CLIPPED_SHARE, "Işık çok sert; doğrudan ışıktan biraz uzaklaşın."),
        Check("sharp", _sharpness(face_gray) >= MIN_SHARPNESS, "Görüntü bulanık; telefonu sabit tutun."),
    ]
    failed = next((check for check in checks if not check.ok), None)
    return {
        "guide_available": True,
        "ok": failed is None,
        "face": True,
        "message": failed.message if failed else "Harika, sabit durun…",
        "checks": [{"key": check.key, "ok": check.ok} for check in checks],
        "box": [round(x / width, 4), round(y / height, 4), round(w / width, 4), round(h / height, 4)],
        "pose": face.pose.to_dict() if face.pose else None,
    }
