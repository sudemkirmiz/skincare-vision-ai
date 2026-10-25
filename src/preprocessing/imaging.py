# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Sudem Kırmız
from __future__ import annotations

import warnings
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


def validate_image_bytes(data: bytes, max_mb: int, max_pixels: int = 40_000_000) -> None:
    """Validate encoded size, decoded dimensions and image integrity before processing."""
    if len(data) > max_mb * 1024 * 1024:
        raise ValueError(f"Dosya çok büyük. En fazla {max_mb} MB yükleyebilirsiniz.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as image:
                width, height = image.size
                if width <= 0 or height <= 0 or width * height > max_pixels:
                    raise ValueError(f"Görsel çözünürlüğü çok yüksek. En fazla {max_pixels:,} piksel kullanabilirsiniz.")
                image.verify()
    except ValueError:
        raise
    except (UnidentifiedImageError, Image.DecompressionBombError, Image.DecompressionBombWarning, OSError, SyntaxError) as error:
        raise ValueError("Dosya geçerli bir görsel değil veya bozuk.") from error
