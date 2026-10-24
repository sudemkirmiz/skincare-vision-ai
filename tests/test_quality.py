import numpy as np
import pytest
from PIL import Image

from imaging import validate_image_bytes
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


def test_upload_pixel_limit_is_enforced(tmp_path):
    path = tmp_path / "large.png"
    Image.new("RGB", (101, 100)).save(path)
    with pytest.raises(ValueError, match="çözünürlüğü"):
        validate_image_bytes(path.read_bytes(), max_mb=1, max_pixels=10_000)
