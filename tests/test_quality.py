import numpy as np

from preprocessing.quality_checker import ImageQualityChecker


def test_dark_small_flat_image_needs_review():
    image = np.full((200, 200, 3), 10, dtype=np.uint8)
    result = ImageQualityChecker().check(image)
    assert result.status == "needs_review"
    assert "karanlık" in result.notes
    assert "bulanık" in result.notes


def test_sharp_bright_image_is_good():
    rng = np.random.default_rng(0)
    image = rng.integers(60, 200, size=(600, 600, 3), dtype=np.uint8)
    result = ImageQualityChecker().check(image)
    assert result.status == "good"
