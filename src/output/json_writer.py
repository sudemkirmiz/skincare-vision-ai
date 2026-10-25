# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Sudem Kırmız
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class JsonWriter:
    def write(self, data: dict[str, Any], output_path: str | Path) -> Path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with output_path.open("w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)

        return output_path


if __name__ == "__main__":
    writer = JsonWriter()
    path = writer.write(
        {
            "status": "ok",
            "message": "JSON writer çalışıyor.",
        },
        "outputs/json_writer_test.json",
    )
    print(f"JSON saved: {path}")
