from __future__ import annotations

from io import BytesIO
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, UnidentifiedImageError


def read_image(image_path: str | Path) -> np.ndarray:
    """cv2.imread fails silently on non-ASCII Windows paths; decode from bytes instead."""
    image_path = Path(image_path)
    try:
        buffer = np.fromfile(str(image_path), dtype=np.uint8)
    except OSError as error:
        raise FileNotFoundError(f"Image could not be read: {image_path}") from error
    image = cv2.imdecode(buffer, cv2.IMREAD_COLOR) if buffer.size else None
    if image is None:
        raise FileNotFoundError(f"Image could not be read: {image_path}")
    return image


def write_image(image: np.ndarray, output_path: str | Path, quality: int = 92) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    extension = output_path.suffix.lower() or ".jpg"
    params = [cv2.IMWRITE_JPEG_QUALITY, quality] if extension in {".jpg", ".jpeg"} else []
    ok, encoded = cv2.imencode(extension, image, params)
    if not ok:
        raise RuntimeError(f"Image could not be saved: {output_path}")
    encoded.tofile(str(output_path))
    return output_path


def validate_image_bytes(data: bytes, max_mb: int) -> None:
    """Size limit + real image check (Pillow verify also catches decompression bombs)."""
    if len(data) > max_mb * 1024 * 1024:
        raise ValueError(f"Dosya çok büyük. En fazla {max_mb} MB yükleyebilirsiniz.")
    try:
        with Image.open(BytesIO(data)) as image:
            image.verify()
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, SyntaxError) as error:
        raise ValueError("Dosya geçerli bir görsel değil veya bozuk.") from error
