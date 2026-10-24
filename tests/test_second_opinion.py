import pytest

from analysis.second_opinion import apply_to_metrics, parse_gemini_boxes, reconcile
from vlm_engine import VLMEngine, VLMProviderError


def test_parse_converts_normalised_boxes_and_drops_bad_ones():
    spots = [
        {"box_2d": [100, 200, 120, 230]},  # ok
        {"box_2d": [500, 500, 400, 600]},  # inverted
        {"box_2d": [0, 0, 900, 900]},  # a whole region, not a spot
        {"box_2d": [10, 10, 11, 11]},  # sub-pixel
        {"box_2d": "nope"}, {"other": 1}, "x",
        {"box_2d": [-50, 990, 20, 1200]},  # clamped into range
    ]
    boxes = parse_gemini_boxes(spots, width=400, height=500)
    assert boxes[0] == [80, 50, 92, 60]
    assert len(boxes) == 2 and boxes[1] == [396, 0, 400, 10]


def test_reconcile_keeps_confirmed_colour_rejects_unconfirmed_and_adds_gemini_only():
    yolo = [[10, 10, 20, 20]]
    colour = [{"box_xyxy": [100, 100, 108, 108]}, {"box_xyxy": [300, 300, 306, 306]}]
    gemini = [[11, 11, 19, 19], [99, 99, 110, 110], [200, 200, 210, 210]]
    result = reconcile(yolo, colour, gemini)
    assert result["kept_colour"] == [colour[0]]
    assert result["gemini_only"] == [[200, 200, 210, 210]]
    assert result["stats"] == {"gemini_spots": 3, "colour_confirmed": 1, "colour_rejected": 1, "yolo_confirmed": 1, "gemini_only": 1}


def test_reconcile_with_no_gemini_spots_rejects_all_colour_candidates():
    result = reconcile([[1, 1, 5, 5]], [{"box_xyxy": [50, 50, 55, 55]}], [])
    assert result["kept_colour"] == [] and result["gemini_only"] == []


def test_apply_to_metrics_recomputes_spot_and_overall_scores():
    metrics = {
        "spot_counts": {"yolo": 3, "colour": 10, "total": 13},
        "raw": {"spots": 13.0},
        "scores": {"spots": 70, "redness": 60, "tone": 60, "texture": None, "shine": 80},
        "overall_score": 66,
    }
    apply_to_metrics(metrics, kept_colour=[{"box_xyxy": [0, 0, 4, 4]}] * 7, gemini_only=[[5, 5, 9, 9]] * 8)
    assert metrics["spot_counts"] == {"yolo": 3, "colour": 7, "gemini": 8, "total": 18}
    assert metrics["scores"]["spots"] < 70 and metrics["raw"]["spots"] == 18.0
    assert metrics["overall_score"] < 66 and len(metrics["gemini_spots"]) == 8


def test_detect_spots_is_gemini_only(tmp_path):
    with pytest.raises(VLMProviderError) as info:
        VLMEngine().detect_spots("Groq", tmp_path / "x.jpg", "key-123456")
    assert info.value.kind == "config"


@pytest.fixture(scope="module")
def service():
    from pathlib import Path

    from analysis.service import AnalysisService
    from config import get_settings
    from detection.face_detector import OpenCVFaceDetector
    from detection.face_landmarks import FaceLandmarkAnalyzer, mediapipe_available
    from detection.skin_finding_detector import SkinFindingDetector
    from preprocessing.quality_checker import ImageQualityChecker

    settings = get_settings()
    if not (mediapipe_available() and settings.face_landmarker_path.exists() and settings.yolo_model_path.exists()):
        pytest.skip("models not available")
    detector = SkinFindingDetector(settings.yolo_model_path)
    face = Path(__file__).parent / "fixtures" / "face_landmarks_478.npy"
    assert face.exists()
    landmarks = FaceLandmarkAnalyzer(settings.face_landmarker_path)
    yield AnalysisService(settings, OpenCVFaceDetector(), ImageQualityChecker(), lambda: detector, landmarks)
    landmarks.close()


def _face_image_bytes():
    """A sample photo if present (local only); otherwise skip."""
    from pathlib import Path

    sample = Path(__file__).resolve().parents[1] / "samples" / "01_frontal_lying.png"
    if not sample.exists():
        pytest.skip("sample photos are local-only")
    return sample.read_bytes()


def test_service_uses_second_opinion_and_survives_failures(service, monkeypatch):
    image = _face_image_bytes()
    calls = []

    def no_network(*_, **__):
        raise VLMProviderError("offline test", "network")

    # Tests must never reach a real provider: the AI comment call fails fast and offline.
    monkeypatch.setattr(service.router, "analyze", no_network)

    def fake(crop_path, crop_shape, api_key):
        calls.append(api_key)
        h, w = crop_shape[:2]
        return [[w // 2, h // 2, w // 2 + 8, h // 2 + 8]]

    monkeypatch.setattr(service, "_second_opinion", fake)
    payload = service.analyze(image, provider="Gemini", api_key="typed-key-1", use_vlm=True, second_opinion=True, fallback_keys={})
    # The VLM comment itself fails without a real key; the second opinion must still have run with the typed key.
    assert calls == ["typed-key-1"]
    assert payload["skin_metrics"]["second_opinion"]["status"] == "ok"
    assert payload["skin_metrics"]["spot_counts"]["total"] == payload["skin_metrics"]["spot_counts"]["yolo"] + \
        payload["skin_metrics"]["spot_counts"]["colour"] + payload["skin_metrics"]["spot_counts"]["gemini"]

    def failing(*_):
        raise VLMProviderError("quota", "quota")

    monkeypatch.setattr(service, "_second_opinion", failing)
    payload = service.analyze(image, provider="Gemini", api_key="typed-key-1", use_vlm=True, second_opinion=True, fallback_keys={})
    assert payload["skin_metrics"]["second_opinion"]["status"] == "skipped"
    assert any("ikinci görüşü" in note for note in payload["skin_metrics"]["notes"])

    calls.clear()
    monkeypatch.setattr(service, "_second_opinion", fake)
    service.analyze(image, provider="Gemini", api_key="k", use_vlm=False, second_opinion=True)
    assert calls == []  # no AI comments requested -> no extra call
