# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Sudem Kırmız
"""Aligned before/after change map from two saved face thumbnails.

The later face is warped onto the earlier one with a similarity transform fitted on rigid landmarks
(eye corners, nose, forehead, chin). Inside the shared skin area each photo is band-pass filtered:
a fine blur removes pixel noise and subtracting a wide blur removes lighting direction, shading and
white balance. The map therefore shows *local* change at spot and patch scale: red patches that faded
or appeared, and marks that got darker or lighter.
"""
from __future__ import annotations

import base64
from typing import TYPE_CHECKING, Any

import cv2
import numpy as np

from analysis.regions import LEFT_EYE, REGION_NAMES, REGIONS, RIGHT_EYE, build_region_map

if TYPE_CHECKING:
    from detection.face_landmarks import FaceLandmarkAnalyzer

# Landmarks that barely move with expression: eye corners, brow line centre, nose bridge/tip, chin.
RIGID_POINTS = [33, 133, 362, 263, 10, 151, 168, 6, 1, 4, 152, 199]
# Band-pass scales (share of the eye distance) and local change thresholds (CIELAB units).
FINE_SCALE = 0.03
WIDE_SCALE = 0.3
REDNESS_STEP = 3.0
TONE_STEP = 4.0
# Background pixels deviating by more than this many steps in the spot direction are skipped
# (tuned on synthetic spots plus a healed-spots / relit photo: no halos, no lighting artefacts).
SPOT_REJECT = 2.0
# Alignment quality and comparability limits.
MAX_RESIDUAL = 0.05  # mean landmark error / eye distance
MAX_YAW_GAP = 10.0
MAX_LIGHT_GAP = 12.0
MIN_REGION_SHARE = 0.03
# Overlay colours (BGR) from the status palette: improvement / worsening.
BETTER_BGR = np.array([12, 163, 12], dtype=np.float32)  # #0ca30c
WORSE_BGR = np.array([59, 59, 208], dtype=np.float32)  # #d03b3b
MAX_ALPHA = 0.7


class ChangeMapError(ValueError):
    """Raised with a Turkish, user-facing message."""


def _decode(data: bytes) -> np.ndarray:
    image = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ChangeMapError("Önizleme okunamadı.")
    return image


def _data_uri(image: np.ndarray) -> str:
    ok, buffer = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 88])
    if not ok:
        raise ChangeMapError("Görsel oluşturulamadı.")
    return "data:image/jpeg;base64," + base64.b64encode(buffer.tobytes()).decode("ascii")


def _masked_blur(values: np.ndarray, mask: np.ndarray, sigma: float) -> np.ndarray:
    weights = cv2.GaussianBlur(mask.astype(np.float32), (0, 0), sigma)
    blurred = cv2.GaussianBlur(values * mask, (0, 0), sigma)
    return np.where(weights > 1e-3, blurred / np.maximum(weights, 1e-3), 0.0)


def _band_pass(values: np.ndarray, mask: np.ndarray, fine: float, wide: float, spot_sign: int, step: float) -> np.ndarray:
    """Fine detail minus a background that skips spots (pixels deviating by `step` in `spot_sign` direction).

    A plain wide blur would let a large spot raise its own surroundings and paint a false opposite-sign
    ring around it. Only the spot direction is skipped, so ordinary shading still shapes the background.
    """
    detail = _masked_blur(values, mask, fine)
    background = _masked_blur(values, mask, wide)
    for _ in range(2):
        background = _masked_blur(values, mask & ((detail - background) * spot_sign < SPOT_REJECT * step), wide)
    return detail - background


def _local_lab(image: np.ndarray, mask: np.ndarray, fine: float, wide: float) -> tuple[np.ndarray, np.ndarray, float]:
    """Spot-scale lightness and redness with shading and colour cast removed."""
    lab = cv2.cvtColor(image.astype(np.float32) / 255.0, cv2.COLOR_BGR2Lab)
    lightness, redness = lab[..., 0], lab[..., 1]
    # Marks are darker (lower L*), red patches are redder (higher a*).
    return (_band_pass(lightness, mask, fine, wide, -1, TONE_STEP), _band_pass(redness, mask, fine, wide, 1, REDNESS_STEP),
            float(np.median(lightness[mask])))


def _overlay(base: np.ndarray, change: np.ndarray, mask: np.ndarray, step: float, worse_when_positive: bool) -> np.ndarray:
    """Tint pixels whose change passes `step`; stronger change, stronger tint."""
    signed = change if worse_when_positive else -change
    strength = np.clip((np.abs(signed) - step) / (2 * step), 0, 1) * MAX_ALPHA
    strength = np.where(mask & (np.abs(signed) >= step), strength + 0.15, 0.0)[..., None]
    colour = np.where((signed > 0)[..., None], WORSE_BGR, BETTER_BGR)
    # Desaturate the photo slightly so the tint reads clearly.
    gray = cv2.cvtColor(cv2.cvtColor(base, cv2.COLOR_BGR2GRAY), cv2.COLOR_GRAY2BGR).astype(np.float32)
    muted = base.astype(np.float32) * 0.55 + gray * 0.45
    return np.clip(muted * (1 - strength) + colour * strength, 0, 255).astype(np.uint8)


def _share(flags: np.ndarray, mask: np.ndarray) -> float:
    total = int(mask.sum())
    return round(100.0 * float((flags & mask).sum()) / total, 1) if total else 0.0


def build_change_map(before_jpeg: bytes, after_jpeg: bytes, landmarks: FaceLandmarkAnalyzer | None,
                     before_yaw: float | None = None, after_yaw: float | None = None) -> dict[str, Any]:
    if landmarks is None:
        raise ChangeMapError("Fark haritası için yüz haritası modeli gerekiyor.")
    before, after = _decode(before_jpeg), _decode(after_jpeg)
    face_before, face_after = landmarks.detect(before), landmarks.detect(after)
    if face_before is None or face_after is None:
        raise ChangeMapError("Önizlemelerden birinde yüz bulunamadı; bu iki kayıt için fark haritası çıkarılamıyor.")

    target = face_before.landmarks[RIGID_POINTS]
    source = face_after.landmarks[RIGID_POINTS]
    matrix, _ = cv2.estimateAffinePartial2D(source, target, method=cv2.LMEDS)
    if matrix is None:
        raise ChangeMapError("Yüzler hizalanamadı.")
    height, width = before.shape[:2]
    warped = cv2.warpAffine(after, matrix, (width, height), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    warped_landmarks = cv2.transform(face_after.landmarks[None], matrix)[0]

    eye_distance = float(np.linalg.norm(face_before.landmarks[LEFT_EYE].mean(axis=0) - face_before.landmarks[RIGHT_EYE].mean(axis=0))) or 1.0
    residual = float(np.linalg.norm(warped_landmarks[RIGID_POINTS] - target, axis=1).mean()) / eye_distance

    regions_before = build_region_map(face_before.landmarks, before.shape[:2])
    regions_after = build_region_map(warped_landmarks, before.shape[:2])
    inside = cv2.warpAffine(np.ones(after.shape[:2], np.uint8), matrix, (width, height), flags=cv2.INTER_NEAREST) > 0
    skin = (regions_before.labels > 0) & (regions_after.labels > 0) & inside
    if skin.sum() < 500:
        raise ChangeMapError("Karşılaştırılabilir cilt alanı çok küçük; benzer açıyla çekilmiş kayıtları seçin.")

    # Fine scale ~ a small spot, wide scale ~ a third of the eye distance (larger than any spot).
    fine, wide = max(1.0, eye_distance * FINE_SCALE), eye_distance * WIDE_SCALE
    light_before, red_before, median_before = _local_lab(before, skin, fine, wide)
    light_after, red_after, median_after = _local_lab(warped, skin, fine, wide)
    redness_change = red_after - red_before
    tone_change = light_after - light_before  # negative = darker mark

    redder, calmer = redness_change >= REDNESS_STEP, redness_change <= -REDNESS_STEP
    darker, lighter = tone_change <= -TONE_STEP, tone_change >= TONE_STEP
    stats = {
        "redness": {"better": _share(calmer, skin), "worse": _share(redder, skin)},
        "tone": {"better": _share(lighter, skin), "worse": _share(darker, skin)},
    }
    regions = []
    for region_id, (key, name, _) in REGIONS.items():
        mask = skin & (regions_before.labels == region_id)
        if mask.sum() < MIN_REGION_SHARE * skin.sum():
            continue
        regions.append({"key": key, "name": name, "redness_better": _share(calmer, mask), "redness_worse": _share(redder, mask),
                        "tone_better": _share(lighter, mask), "tone_worse": _share(darker, mask)})

    summary = []
    for label, values in (("Kızarıklık", stats["redness"]), ("Leke/ton", stats["tone"])):
        # "azalan alan %12" avoids Turkish suffixes that change with the number.
        summary.append(f"{label}: azalan alan %{values['better']:g}, artan alan %{values['worse']:g}.")
    if regions:
        best = max(regions, key=lambda region: region["redness_better"] - region["redness_worse"])
        worst = min(regions, key=lambda region: region["redness_better"] - region["redness_worse"])
        if best["redness_better"] - best["redness_worse"] >= 3:
            summary.append(f"En belirgin sakinleşme: {REGION_NAMES[best['key']]}.")
        if worst["redness_worse"] - worst["redness_better"] >= 3:
            summary.append(f"Kızarıklığın arttığı bölge: {REGION_NAMES[worst['key']]}.")

    notes = []
    if residual > MAX_RESIDUAL:
        notes.append("Yüzler tam hizalanamadı (ifade veya açı farkı); harita kaba bir göstergedir.")
    if before_yaw is not None and after_yaw is not None and abs(before_yaw - after_yaw) > MAX_YAW_GAP:
        notes.append(f"Baş açıları farklı ({abs(before_yaw - after_yaw):.0f}°); yanağın biri daha az görünür olabilir.")
    if abs(median_before - median_after) > MAX_LIGHT_GAP:
        notes.append("Işık koşulları belirgin farklı; genel ışık farkı dengelendi ama sonuçlar etkilenebilir.")
    notes.append("Harita nokta ve leke ölçeğindeki değişimi gösterir; ışık yönü, gölge ve genel ton farkı ayıklanır.")

    return {
        "before_uri": _data_uri(before),
        "after_uri": _data_uri(warped),
        "redness_uri": _data_uri(_overlay(warped, redness_change, skin, REDNESS_STEP, worse_when_positive=True)),
        "tone_uri": _data_uri(_overlay(warped, tone_change, skin, TONE_STEP, worse_when_positive=False)),
        "stats": stats,
        "regions": regions,
        "summary": summary,
        "notes": notes,
        "alignment_error": round(residual, 3),
    }
