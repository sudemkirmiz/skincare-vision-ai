# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Sudem Kırmız
from pathlib import Path

import cv2
import numpy as np
import pytest

from analysis.regions import build_region_map
from analysis.skin_metrics import (
    _skin_colour_mask,
    compute_skin_metrics,
    draw_spot_candidates,
    ita_category,
    masked_blur,
)

SKIN_BGR = (150, 172, 222)  # light skin tone; passes the YCrCb skin filter
LANDMARKS = Path(__file__).parent / "fixtures" / "face_landmarks_478.npy"


def _skin_image(size=(420, 420), seed=0):
    rng = np.random.default_rng(seed)
    image = np.full((*size, 3), SKIN_BGR, dtype=np.float32)
    image += rng.normal(0, 1.5, image.shape)  # mild sensor noise
    return np.clip(image, 0, 255).astype(np.uint8)


def _add_red_spots(image, centers, radius=6):
    output = image.copy()
    for center in centers:
        cv2.circle(output, center, radius, (95, 105, 205), -1, cv2.LINE_AA)
    return output


def test_synthetic_skin_passes_colour_filter():
    assert _skin_colour_mask(_skin_image()).mean() > 0.99


def test_clean_skin_scores_high_and_red_spots_are_found():
    clean = compute_skin_metrics(_skin_image(), None, None, [])
    assert clean["available"]
    assert clean["spot_counts"]["total"] == 0
    assert clean["scores"]["spots"] == 100
    assert clean["overall_score"] >= 85

    spots = [(80, 80), (200, 120), (320, 300), (120, 330), (300, 90)]
    spotted = compute_skin_metrics(_add_red_spots(_skin_image(), spots), None, None, [])
    assert spotted["spot_counts"]["colour"] == len(spots)
    assert spotted["overall_score"] < clean["overall_score"]
    assert spotted["scores"]["redness"] <= clean["scores"]["redness"]


def test_spots_already_found_by_yolo_are_not_double_counted():
    spots = [(80, 80), (200, 120), (320, 300)]
    yolo_boxes = [[72, 72, 88, 88]]  # covers the first spot
    metrics = compute_skin_metrics(_add_red_spots(_skin_image(), spots), None, None, yolo_boxes)
    assert metrics["spot_counts"] == {"yolo": 1, "colour": 2, "total": 3}


def test_candidates_are_returned_in_crop_coordinates():
    image = _add_red_spots(_skin_image((840, 840)), [(600, 200)], radius=12)
    metrics = compute_skin_metrics(image, None, None, [])
    (candidate,) = metrics["spot_candidates"]
    x1, y1, x2, y2 = candidate["box_xyxy"]
    assert x1 <= 600 <= x2 and y1 <= 200 <= y2
    assert draw_spot_candidates(image, metrics["spot_candidates"]).shape == image.shape


def test_region_metrics_with_landmarks():
    landmarks = np.load(LANDMARKS) * 4  # fixture face is small; scale up to a realistic crop
    shape = (198 * 4, 172 * 4)
    image = _skin_image(shape)
    metrics = compute_skin_metrics(image, landmarks, build_region_map(landmarks, shape), [])
    assert metrics["available"]
    assert {"forehead", "nose", "chin"} <= set(metrics["regions"])
    assert all(0 <= region["redness"] <= 100 for region in metrics["regions"].values())


def test_tiny_upscaled_face_skips_texture():
    metrics = compute_skin_metrics(_skin_image((120, 120)), None, None, [])
    assert metrics["scores"]["texture"] is None
    assert any("doku" in note for note in metrics["notes"])


def test_no_skin_is_reported_not_crashed():
    blue = np.full((300, 300, 3), (200, 80, 20), dtype=np.uint8)
    assert compute_skin_metrics(blue, None, None, [])["available"] is False


def test_masked_blur_ignores_pixels_outside_mask():
    values = np.zeros((50, 50), dtype=np.float32)
    values[:, 25:] = 100.0
    mask = np.zeros((50, 50), dtype=bool)
    mask[:, :25] = True
    blurred = masked_blur(values, mask, 5.0)
    assert np.allclose(blurred[:, :25], 0.0, atol=1e-3)


@pytest.mark.parametrize(("ita", "category"), [(60, "Çok açık"), (45, "Açık"), (30, "Orta"), (15, "Buğday"), (0, "Esmer"), (-50, "Koyu")])
def test_ita_category(ita, category):
    assert ita_category(ita) == category
