# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Sudem Kırmız
"""Plain-text and JSON exports of an analysis (shared by the Streamlit app and the API)."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from safety.safe_response_builder import DISCLAIMER


def total_spot_count(payload: dict[str, Any]) -> int:
    metrics = payload.get("skin_metrics") or {}
    if metrics.get("available"):
        return int(metrics["spot_counts"]["total"])
    return int((payload.get("skin_findings") or {}).get("summary", {}).get("total_detections", 0))


def quality_label(quality_data: dict[str, Any] | None) -> str:
    if not quality_data:
        return "Hazırlanamadı"
    return "Uygun" if quality_data.get("status") == "good" else "Kontrol gerekli"


def routine_report_lines(routine: dict[str, Any] | None) -> list[str]:
    if not routine:
        return []
    lines = ["Kişisel rutin:", "  Sabah:"]
    lines += [f"    {index}. {step['step']}: {step['product']}" for index, step in enumerate(routine["am"], 1)]
    lines += ["  Akşam:"]
    lines += [f"    {index}. {step['step']}: {step['product']}" for index, step in enumerate(routine["pm"], 1)]
    if routine["actives"]:
        lines += ["  Önerilen içerikler:"]
        lines += [f"    - {item['name']} ({item['strength']}): {item['frequency']}" for item in routine["actives"]]
    lines += [f"  ! {warning}" for warning in routine["warnings"]]
    return [*lines, ""]


def build_report_text(payload: dict[str, Any]) -> str:
    result = payload["result"]
    quality_data = result.get("image_quality") or {}
    vlm_output = payload.get("vlm_output") or {}
    metrics = payload.get("skin_metrics") or {}
    observations = result.get("visible_observations", [])
    suggestions = result.get("care_suggestions", [])
    created_at = payload.get("created_at", datetime.now().strftime("%Y-%m-%d %H:%M"))
    model_line = f"{vlm_output.get('provider')} / {vlm_output.get('model')}" if vlm_output else "-"
    lines = [
        "SkinCare Vision AI - Bakım Ön Değerlendirme Raporu",
        f"Tarih: {created_at}",
        f"Yorum modeli: {model_line}",
        "",
        f"Akne benzeri nokta sayısı: {total_spot_count(payload)}",
        *([f"Cilt Skoru: {metrics['overall_score']}/100", *[f"  {metrics['score_labels'][k]}: {v}" for k, v in metrics["scores"].items() if v is not None]] if metrics.get("available") else []),
        f"Fotoğraf kalitesi: {quality_label(quality_data)}",
        f"Kalite notu: {quality_data.get('notes', '-')}",
        "",
        "Gözlemler:",
        *[f"- {item}" for item in observations],
        "",
        "Bakım önerileri:",
        *[f"- {item}" for item in suggestions],
        "",
        *routine_report_lines(payload.get("routine")),
        result.get("disclaimer", DISCLAIMER),
    ]
    return "\n".join(lines)


def build_report_json(payload: dict[str, Any]) -> str:
    export = {
        "created_at": payload.get("created_at"),
        "result": payload.get("result"),
        "skin_findings": payload.get("skin_findings"),
        "vlm_output": payload.get("vlm_output"),
        "skin_metrics": {k: v for k, v in (payload.get("skin_metrics") or {}).items() if k != "spot_candidates"},
        "routine": payload.get("routine"),
    }
    return json.dumps(export, ensure_ascii=False, indent=2)
