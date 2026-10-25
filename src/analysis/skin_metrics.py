# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Sudem Kırmız
"""Explainable, model-free skin appearance metrics.

Everything here is classical image processing on a scale-normalised face crop, so it
works regardless of how well the YOLO model performs. Values are *visual indices* for
cosmetic tracking, not clinical measurements, and they depend on lighting.

Thresholds were calibrated on the local sample set (samples/) and are kept in one place
(`CALIBRATION`) so they can be re-tuned when more labelled photos are available.
"""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from analysis.regions import REGIONS, RegionMap

LEFT_IRIS_CENTER = 473
RIGHT_IRIS_CENTER = 468
NORMALISED_EYE_DISTANCE = 140.0  # px between pupils after rescaling
FALLBACK_SHORT_SIDE = 420.0  # used when no landmarks are available
MIN_REGION_PIXELS = 400
UPSCALE_TEXTURE_LIMIT = 1.6
SPOT_THRESHOLD = 5.0  # local a* excess; 4.0 caught nostril creases, 6.0 missed faint spots
SPOT_THRESHOLD_STRICT = 7.5  # texture is unreliable when the crop had to be enlarged this much

# score = 100 at `good`, 0 at `bad` (linear, clamped). Higher is always better for the user.
CALIBRATION = {
    "redness_p90": (17.0, 30.0),  # 90th percentile a* (CIELAB) of skin
    "redness_hot": (1.0, 15.0),  # % of skin noticeably redder than its surroundings
    "spots": (3.0, 35.0),  # merged spot count over the visible face
    "tone": (3.5, 11.0),  # robust std of illumination-free lightness (band-pass L*)
    "shine": (0.5, 10.0),  # % of skin covered by specular highlights
    "texture": (0.38, 0.95),  # mean high-frequency lightness energy
}
WEIGHTS = {"spots": 0.35, "redness": 0.25, "tone": 0.15, "texture": 0.15, "shine": 0.10}
SCORE_LABELS = {
    "spots": "Nokta yoğunluğu",
    "redness": "Kızarıklık dengesi",
    "tone": "Ton eşitliği",
    "texture": "Doku pürüzsüzlüğü",
    "shine": "Parlama kontrolü",
}
ITA_CATEGORIES = [(55, "Çok açık"), (41, "Açık"), (28, "Orta"), (10, "Buğday"), (-30, "Esmer"), (-90, "Koyu")]


@dataclass
class SpotCandidate:
    box_xyxy: list[int]  # in the original (un-normalised) crop coordinates
    strength: float  # local a* excess


def _score(value: float, key: str) -> int:
    good, bad = CALIBRATION[key]
    fraction = (value - good) / (bad - good)
    return int(round(100 * (1 - min(1.0, max(0.0, fraction)))))


def _skin_colour_mask(image_bgr: np.ndarray) -> np.ndarray:
    ycrcb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2YCrCb)
    cr, cb = ycrcb[..., 1], ycrcb[..., 2]
    luma = ycrcb[..., 0]
    return (cr >= 133) & (cr <= 180) & (cb >= 77) & (cb <= 135) & (luma >= 40)


def masked_blur(values: np.ndarray, mask: np.ndarray, sigma: float) -> np.ndarray:
    """Gaussian blur that only averages pixels inside `mask`.

    A plain blur mixes in eyes, brows, hair and background, which creates fake contrast
    along every region border and inflates redness, tone and shine measurements.
    """
    weights = mask.astype(np.float32)
    blurred = cv2.GaussianBlur(values * weights, (0, 0), sigma)
    norm = cv2.GaussianBlur(weights, (0, 0), sigma)
    return np.where(norm > 1e-3, blurred / np.maximum(norm, 1e-3), values)


def robust_std(values: np.ndarray) -> float:
    low, high = np.percentile(values, [2, 98])
    return float(np.clip(values, low, high).std())


def ita_category(ita: float) -> str:
    return next(name for threshold, name in ITA_CATEGORIES if ita > threshold)


def _normalise(image: np.ndarray, landmarks: np.ndarray | None) -> tuple[float, np.ndarray]:
    if landmarks is not None and len(landmarks) > LEFT_IRIS_CENTER:
        eye_distance = float(np.linalg.norm(landmarks[LEFT_IRIS_CENTER] - landmarks[RIGHT_IRIS_CENTER]))
        scale = NORMALISED_EYE_DISTANCE / max(eye_distance, 1.0)
    else:
        scale = FALLBACK_SHORT_SIDE / max(1, min(image.shape[:2]))
    interpolation = cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC
    return scale, cv2.resize(image, None, fx=scale, fy=scale, interpolation=interpolation)


def find_spot_candidates(
    lab_a: np.ndarray, skin: np.ndarray, reference: float, strict: np.ndarray | None = None
) -> list[tuple[list[int], float]]:
    """Small blobs that are redder than their immediate surroundings (normalised-scale coordinates).

    `strict` marks naturally reddish areas (nose wings, nostril creases) that need a higher threshold.
    """
    local_excess = lab_a - masked_blur(lab_a, skin, reference * 0.12)
    threshold = np.full(lab_a.shape, SPOT_THRESHOLD, dtype=np.float32)
    if strict is not None:
        threshold[strict] = SPOT_THRESHOLD_STRICT
    blobs = ((local_excess > threshold) & skin).astype(np.uint8)
    blobs = cv2.morphologyEx(blobs, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    count, labels, stats, _ = cv2.connectedComponentsWithStats(blobs)
    min_area, max_area = (reference * 0.03) ** 2, (reference * 0.22) ** 2
    candidates = []
    for index in range(1, count):
        x, y, width, height, area = stats[index]
        aspect = max(width, height) / max(1, min(width, height))
        # Large or elongated red areas are diffuse redness / edges, not spots; they count towards redness instead.
        if not (min_area <= area <= max_area) or aspect > 3.0:
            continue
        strength = float(local_excess[labels == index].mean())
        candidates.append(([int(x), int(y), int(x + width), int(y + height)], round(strength, 2)))
    return candidates


def _box_overlaps(candidate: list[int], boxes: list[list[int]], margin: float = 0.3) -> bool:
    cx, cy = (candidate[0] + candidate[2]) / 2, (candidate[1] + candidate[3]) / 2
    for x1, y1, x2, y2 in boxes:
        pad_x, pad_y = (x2 - x1) * margin, (y2 - y1) * margin
        if x1 - pad_x <= cx <= x2 + pad_x and y1 - pad_y <= cy <= y2 + pad_y:
            return True
    return False


def compute_skin_metrics(
    crop_bgr: np.ndarray,
    landmarks: np.ndarray | None,
    region_map: RegionMap | None,
    yolo_boxes: list[list[int]],
) -> dict:
    """Metrics for one face crop. `yolo_boxes` and the returned candidate boxes use crop coordinates."""
    scale, image = _normalise(crop_bgr, landmarks)
    reference = NORMALISED_EYE_DISTANCE if landmarks is not None else FALLBACK_SHORT_SIDE / 3

    if region_map is not None:
        labels = cv2.resize(region_map.labels, (image.shape[1], image.shape[0]), interpolation=cv2.INTER_NEAREST)
        skin = (labels > 0) & _skin_colour_mask(image)
    else:
        labels = None
        skin = _skin_colour_mask(image)
    if skin.sum() < MIN_REGION_PIXELS:
        return {"available": False, "reason": "Yeterli cilt alanı bulunamadı."}

    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB).astype(np.float32)
    lightness = lab[..., 0] * (100.0 / 255.0)
    lab_a = lab[..., 1] - 128.0
    lab_b = lab[..., 2] - 128.0

    # Remove slow illumination changes (face curvature, shadows) before measuring unevenness.
    illumination = masked_blur(lightness, skin, reference * 0.4)
    band_pass = masked_blur(lightness, skin, 2.0) - illumination
    high_pass = np.abs(lightness - masked_blur(lightness, skin, 1.5))
    local_red = lab_a - masked_blur(lab_a, skin, reference * 0.4)
    # Statistics ignore a thin rim along mask borders, where even masked filters are least reliable.
    core = cv2.erode(skin.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)
    if core.sum() >= MIN_REGION_PIXELS:
        skin_stats = core
    else:
        skin_stats = skin
    chroma = np.hypot(lab_a, lab_b)
    highlights = (lightness - illumination > 9.0) & (lightness > 62.0) & (chroma < np.median(chroma[skin_stats]) * 0.85)

    # --- spots: YOLO findings + colour-based candidates that YOLO did not cover ---
    candidates = []
    strict = None
    if labels is not None:
        nose = (labels == 2).astype(np.uint8)
        strict = cv2.dilate(nose, np.ones((int(reference * 0.12) * 2 + 1,) * 2, np.uint8)).astype(bool)
    for box, strength in find_spot_candidates(lab_a, skin, reference, strict):
        original = [int(round(value / scale)) for value in box]
        if not _box_overlaps(original, yolo_boxes):
            candidates.append(SpotCandidate(original, strength))
    total_spots = len(yolo_boxes) + len(candidates)

    raw = {
        "redness_p90": float(np.percentile(lab_a[skin_stats], 90)),
        "redness_hot": float((local_red[skin_stats] > 5.0).mean() * 100),
        "redness_mean": float(lab_a[skin_stats].mean()),
        "spots": float(total_spots),
        "tone": robust_std(band_pass[skin_stats]),
        "shine": float(highlights[skin_stats].mean() * 100),
        "texture": float(high_pass[skin_stats].mean()),
    }
    texture_reliable = scale <= UPSCALE_TEXTURE_LIMIT
    scores = {
        "spots": _score(raw["spots"], "spots"),
        "redness": int(round((_score(raw["redness_p90"], "redness_p90") + _score(raw["redness_hot"], "redness_hot")) / 2)),
        "tone": _score(raw["tone"], "tone"),
        "shine": _score(raw["shine"], "shine"),
        "texture": _score(raw["texture"], "texture") if texture_reliable else None,
    }
    available = {key: value for key, value in scores.items() if value is not None}
    weight_sum = sum(WEIGHTS[key] for key in available)
    overall = int(round(sum(WEIGHTS[key] * value for key, value in available.items()) / weight_sum))

    ita = float(np.degrees(np.arctan2(np.median(lightness[skin]) - 50.0, np.median(lab_b[skin]))))
    regions = {}
    if labels is not None:
        for region_id, (key, name, _) in REGIONS.items():
            mask = skin_stats & (labels == region_id)
            if mask.sum() < MIN_REGION_PIXELS:
                continue
            region_hot = float((local_red[mask] > 5.0).mean() * 100)
            regions[key] = {
                "name": name,
                "redness": int(round((_score(float(np.percentile(lab_a[mask], 90)), "redness_p90") + _score(region_hot, "redness_hot")) / 2)),
                "tone": _score(robust_std(band_pass[mask]), "tone"),
                "shine": _score(float(highlights[mask].mean() * 100), "shine"),
            }

    notes = []
    if not texture_reliable:
        notes.append("Yüz fotoğrafta küçük olduğu için doku ölçülmedi.")
    if region_map is None:
        notes.append("Yüz haritası çıkarılamadığı için bölgesel metrik yok; değerler tüm cilt alanı içindir.")

    return {
        "available": True,
        "overall_score": overall,
        "scores": scores,
        "score_labels": SCORE_LABELS,
        "raw": {key: round(value, 2) for key, value in raw.items()},
        "regions": regions,
        "skin_tone": {"ita": round(ita, 1), "category": ita_category(ita)},
        "spot_counts": {"yolo": len(yolo_boxes), "colour": len(candidates), "total": total_spots},
        "spot_candidates": [{"box_xyxy": c.box_xyxy, "strength": c.strength} for c in candidates],
        "notes": notes,
    }


COLOUR_RING = (200, 70, 220)  # magenta: colour analysis
GEMINI_RING = (235, 170, 30)  # blue: Gemini second opinion


def draw_spot_candidates(image: np.ndarray, candidates: list[dict], color: tuple[int, int, int] = COLOUR_RING) -> np.ndarray:
    """Non-YOLO spots are drawn as rings, so they are distinguishable from YOLO boxes."""
    output = image.copy()
    thickness = max(1, round(min(output.shape[:2]) / 400))
    for candidate in candidates:
        x1, y1, x2, y2 = candidate["box_xyxy"]
        center = ((x1 + x2) // 2, (y1 + y2) // 2)
        radius = max(4, int(max(x2 - x1, y2 - y1) * 0.7))
        cv2.circle(output, center, radius, color, thickness, cv2.LINE_AA)
    return output
