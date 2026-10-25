# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Sudem Kırmız
from pathlib import Path

import numpy as np
import pytest

from analysis.regions import LEFT_EYE, LIPS, NOSE, RIGHT_EYE, build_region_map, draw_region_overlay, summarize_regions
from detection.face_landmarks import pose_from_matrix

FIXTURE = Path(__file__).parent / "fixtures" / "face_landmarks_478.npy"
SHAPE = (198, 172)


@pytest.fixture(scope="module")
def landmarks():
    return np.load(FIXTURE)


@pytest.fixture(scope="module")
def region_map(landmarks):
    return build_region_map(landmarks, SHAPE)


def _centroid(landmarks, indices):
    x, y = landmarks[indices].mean(axis=0)
    return float(x), float(y)


def test_eyes_and_lips_are_excluded(landmarks, region_map):
    for indices in (LEFT_EYE, RIGHT_EYE, LIPS):
        x, y = _centroid(landmarks, indices)
        assert region_map.labels[int(y), int(x)] == 0


def test_key_points_land_in_expected_regions(landmarks, region_map):
    nose_x, nose_y = landmarks[4]  # nose tip area
    assert region_map.region_at(nose_x, nose_y) == "nose"
    chin_x, chin_y = landmarks[152] + np.array([0, -6])  # just above the chin tip
    assert region_map.region_at(chin_x, chin_y) == "chin"
    forehead_x, forehead_y = landmarks[10] + np.array([0, 6])  # just below the hairline point
    assert region_map.region_at(forehead_x, forehead_y) == "forehead"
    # cheeks sit below the eyes, on either side of the nose
    eye_x, eye_y = _centroid(landmarks, RIGHT_EYE)
    image_left_cheek = region_map.region_at(eye_x, eye_y + 22)
    eye_x, eye_y = _centroid(landmarks, LEFT_EYE)
    image_right_cheek = region_map.region_at(eye_x, eye_y + 22)
    assert {image_left_cheek, image_right_cheek} == {"left_cheek", "right_cheek"}


def test_summary_counts_and_density(landmarks, region_map):
    nose_x, nose_y = landmarks[NOSE].mean(axis=0)
    nose_box = [int(nose_x) - 2, int(nose_y) - 2, int(nose_x) + 2, int(nose_y) + 2]
    outside = [0, 0, 3, 3]
    summary = summarize_regions(region_map, [nose_box, nose_box, outside])
    by_key = {region["key"]: region for region in summary["regions"]}
    assert by_key["nose"]["count"] == 2
    assert summary["unassigned"] == 1
    assert summary["most_affected"] == "nose"
    assert summary["zones"]["t_zone"]["count"] == 2
    assert summary["finding_regions"] == ["nose", "nose", None]
    assert abs(sum(region["area_ratio"] for region in summary["regions"]) - 1.0) < 0.01


def test_overlay_keeps_shape(region_map):
    image = np.full((*SHAPE, 3), 128, dtype=np.uint8)
    overlay = draw_region_overlay(image, region_map)
    assert overlay.shape == image.shape
    assert not np.array_equal(overlay, image)


def test_pose_from_matrix():
    yaw = np.radians(20)
    rotation = np.eye(4)
    rotation[:3, :3] = [[np.cos(yaw), 0, np.sin(yaw)], [0, 1, 0], [-np.sin(yaw), 0, np.cos(yaw)]]
    pose = pose_from_matrix(rotation)
    assert round(pose.yaw) == 20 and round(pose.pitch) == 0 and round(pose.roll) == 0
