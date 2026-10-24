from pathlib import Path

import cv2
import numpy as np
import pytest

from analysis.color_balance import SCLERA_REFERENCE_RATIO_BGR, apply_white_balance, estimate_white_balance, sclera_mask

FIXTURE = Path(__file__).parent / "fixtures" / "face_landmarks_478.npy"
SCALE = 4
SHAPE = (198 * SCALE, 172 * SCALE)
SKIN = (150, 172, 222)
SCLERA = tuple(int(200 * r) for r in SCLERA_REFERENCE_RATIO_BGR)  # typical warm-ish sclera under neutral light


@pytest.fixture(scope="module")
def landmarks():
    return np.load(FIXTURE) * SCALE


def face(landmarks, sclera=SCLERA):
    image = np.full((*SHAPE, 3), SKIN, dtype=np.uint8)
    image[sclera_mask(SHAPE, landmarks)] = sclera
    return image


def cast(image, gains):
    return np.clip(image.astype(np.float32) * np.array(gains, np.float32), 0, 255).astype(np.uint8)


def test_sclera_mask_excludes_iris(landmarks):
    mask = sclera_mask(SHAPE, landmarks)
    assert mask.sum() > 100
    x, y = np.round(landmarks[468]).astype(int)  # right iris centre
    assert not mask[y, x]


def test_neutral_photo_is_left_almost_unchanged(landmarks):
    balance = estimate_white_balance(face(landmarks), landmarks)
    assert balance.applied
    assert all(abs(g - 1) < 0.03 for g in balance.gains)


@pytest.mark.parametrize("gains", [(0.78, 0.95, 1.15), (1.15, 1.0, 0.85)])
def test_colour_cast_is_corrected(landmarks, gains):
    original = face(landmarks)
    balance = estimate_white_balance(cast(original, gains), landmarks)
    corrected = apply_white_balance(cast(original, gains), balance)
    skin_before = cast(original, gains)[5, 5].astype(float)
    skin_after = corrected[5, 5].astype(float)
    assert np.abs(skin_after - np.array(SKIN)).max() < np.abs(skin_before - np.array(SKIN)).max()
    assert np.abs(skin_after - np.array(SKIN)).max() <= 8


def test_bloodshot_eyes_are_not_used_as_reference(landmarks):
    balance = estimate_white_balance(face(landmarks, sclera=(90, 90, 210)), landmarks)
    assert not balance.applied and "kırmızımsı" in balance.reason
    image = face(landmarks, sclera=(90, 90, 210))
    assert apply_white_balance(image, balance) is image


def test_missing_landmarks_or_closed_eyes(landmarks):
    assert not estimate_white_balance(face(landmarks), None).applied
    tiny = cv2.resize(face(landmarks), (40, 46))
    assert not estimate_white_balance(tiny, landmarks / (SHAPE[1] / 40)).applied
