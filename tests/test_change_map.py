from pathlib import Path

import cv2
import numpy as np
import pytest

from analysis.change_map import ChangeMapError, build_change_map
from analysis.regions import build_region_map
from detection.face_landmarks import FaceLandmarkResult, HeadPose

FIXTURE = Path(__file__).parent / "fixtures" / "face_landmarks_478.npy"
SCALE = 1.6


class QueueLandmarks:
    """Returns prepared landmark results in call order (before, then after)."""

    def __init__(self, *results):
        self.results = list(results)

    def detect(self, _image):
        return self.results.pop(0)


def _result(points):
    x1, y1 = points.min(axis=0)
    x2, y2 = points.max(axis=0)
    return FaceLandmarkResult(points.astype(np.float32), (int(x1), int(y1), int(x2 - x1), int(y2 - y1)), HeadPose(0, 0, 0), 1)


def _encode(image):
    return cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 95])[1].tobytes()


def _blob(image, center, radius, bgr):
    overlay = image.copy()
    cv2.circle(overlay, (int(center[0]), int(center[1])), radius, bgr, -1)
    return cv2.GaussianBlur(overlay, (0, 0), 2)


@pytest.fixture(scope="module")
def scene():
    landmarks = np.load(FIXTURE) * SCALE
    height, width = int(198 * SCALE), int(172 * SCALE)
    rng = np.random.default_rng(0)
    skin = np.clip(np.array([150, 168, 205]) + rng.normal(0, 2, (height, width, 3)), 0, 255).astype(np.uint8)
    regions = build_region_map(landmarks, (height, width))
    left = np.argwhere(regions.mask("left_cheek")).mean(axis=0)[::-1]
    right = np.argwhere(regions.mask("right_cheek")).mean(axis=0)[::-1]
    red = (110, 110, 225)
    # A red patch on the left cheek fades; a new one appears on the right cheek.
    before = _blob(skin, left, 14, red)
    changed = _blob(skin, right, 14, red)
    # The later photo is taken slightly closer, rotated and off-centre.
    matrix = cv2.getRotationMatrix2D((width / 2, height / 2), 4, 1.06)
    matrix[:, 2] += (6, -4)
    after = cv2.warpAffine(changed, matrix, (width, height), borderMode=cv2.BORDER_REFLECT)
    after_landmarks = cv2.transform(landmarks[None].astype(np.float32), matrix)[0]
    return before, after, landmarks, after_landmarks


def test_change_map_finds_faded_and_new_redness(scene):
    before, after, before_points, after_points = scene
    result = build_change_map(_encode(before), _encode(after), QueueLandmarks(_result(before_points), _result(after_points)))
    assert result["alignment_error"] < 0.01
    assert result["stats"]["redness"]["better"] > 1 and result["stats"]["redness"]["worse"] > 1
    by_key = {region["key"]: region for region in result["regions"]}
    assert by_key["left_cheek"]["redness_better"] > by_key["left_cheek"]["redness_worse"]
    assert by_key["right_cheek"]["redness_worse"] > by_key["right_cheek"]["redness_better"]
    assert by_key["forehead"]["redness_worse"] < 1
    assert "En belirgin sakinleşme: Sol yanak." in result["summary"]
    # The new patch also reaches the narrow nose region, which is then the highest share.
    assert any(line.startswith("Kızarıklığın arttığı bölge:") for line in result["summary"])
    for key in ("before_uri", "after_uri", "redness_uri", "tone_uri"):
        assert result[key].startswith("data:image/jpeg;base64,")


def test_change_map_ignores_global_lighting(scene):
    before, _, points, _ = scene
    brighter = cv2.convertScaleAbs(before, alpha=1.0, beta=25)
    result = build_change_map(_encode(before), _encode(brighter), QueueLandmarks(_result(points), _result(points)))
    assert result["stats"]["redness"]["worse"] < 1 and result["stats"]["tone"]["worse"] < 1


def test_change_map_warns_about_pose_and_reports_missing_face(scene):
    before, after, before_points, after_points = scene
    result = build_change_map(_encode(before), _encode(after), QueueLandmarks(_result(before_points), _result(after_points)), before_yaw=2, after_yaw=25)
    assert any("Baş açıları" in note for note in result["notes"])
    with pytest.raises(ChangeMapError, match="yüz bulunamadı"):
        build_change_map(_encode(before), _encode(after), QueueLandmarks(_result(before_points), None))
    with pytest.raises(ChangeMapError):
        build_change_map(_encode(before), _encode(after), None)
