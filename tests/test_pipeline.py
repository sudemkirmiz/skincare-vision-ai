from pathlib import Path

import numpy as np
import pytest

from imaging import read_image, write_image
from main import run_pipeline

MODEL_PATH = Path(__file__).resolve().parents[1] / "models" / "acne_like_spot.pt"


def test_unicode_path_round_trip(tmp_path):
    path = tmp_path / "çğüşıö yüz.jpg"
    write_image(np.full((50, 60, 3), 128, dtype=np.uint8), path)
    assert read_image(path).shape == (50, 60, 3)


def test_pipeline_without_face_returns_safe_result(tmp_path):
    image_path = write_image(np.full((480, 640, 3), 127, dtype=np.uint8), tmp_path / "blank.jpg")
    result = run_pipeline(image_path, tmp_path / "crop.jpg", result_json_path=None)
    assert result["detected_regions"]["face_detected"] is False
    assert result["image_quality"] is None
    assert not (tmp_path / "crop.jpg").exists()


@pytest.mark.skipif(not MODEL_PATH.exists(), reason="YOLO weights not present")
def test_yolo_detector_runs_on_blank_image(tmp_path):
    from detection.skin_finding_detector import SkinFindingDetector

    image_path = write_image(np.full((400, 300, 3), 180, dtype=np.uint8), tmp_path / "face.jpg")
    detector = SkinFindingDetector(model_path=MODEL_PATH)
    result = detector.detect(image_path)
    assert result.summary["total_detections"] == len(result.findings)
    detector.draw_findings(image_path, result, tmp_path / "annotated.jpg")
    assert (tmp_path / "annotated.jpg").exists()


def test_pipeline_full_image_fallback_when_no_face(tmp_path):
    rng = np.random.default_rng(1)
    image_path = write_image(rng.integers(60, 200, size=(500, 500, 3), dtype=np.uint8), tmp_path / "closeup.jpg")
    result = run_pipeline(image_path, tmp_path / "crop.jpg", result_json_path=None, full_image_fallback=True)
    assert result["detected_regions"]["analysis_region"] == "full_image"
    assert result["image_quality"] is not None
    assert read_image(tmp_path / "crop.jpg").shape[:2] == (500, 500)
