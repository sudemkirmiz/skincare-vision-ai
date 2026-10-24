"""Human-readable, portable download file names (e.g. Cilt_Raporu_Ayse_Yilmaz_24-10-2026.pdf).

Turkish letters are transliterated: some mail clients, older Windows tools and zip
programs still mangle non-ASCII file names.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime

TURKISH_ASCII = str.maketrans({"ı": "i", "İ": "I", "ş": "s", "Ş": "S", "ğ": "g", "Ğ": "G", "ç": "c", "Ç": "C", "ö": "o", "Ö": "O", "ü": "u", "Ü": "U"})
MAX_PART_LENGTH = 40


def safe_part(text: str) -> str:
    text = (text or "").translate(TURKISH_ASCII)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_")
    return text[:MAX_PART_LENGTH].rstrip("_")


def _date_part(created_at: str | None) -> str:
    for parse in (datetime.fromisoformat, lambda value: datetime.strptime(value, "%Y-%m-%d %H:%M")):
        try:
            return parse(created_at).strftime("%d-%m-%Y")  # type: ignore[arg-type]
        except (TypeError, ValueError):
            continue
    return datetime.now().strftime("%d-%m-%Y")


def report_filename(full_name: str | None, created_at: str | None, extension: str, prefix: str = "Cilt_Raporu") -> str:
    parts = [prefix, safe_part(full_name or ""), _date_part(created_at)]
    return "_".join(part for part in parts if part) + f".{extension.lstrip('.')}"
