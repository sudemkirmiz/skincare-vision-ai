# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Sudem Kırmız
"""Before/after comparison and trend series built from stored history records."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from analysis.regions import REGION_NAMES
from analysis.skin_metrics import SCORE_LABELS
from history.store import HistoryRecord, HistoryStore, record_from_payload

MEANINGFUL_SCORE_CHANGE = 5  # sub-score points; smaller moves are within lighting/camera noise


def _direction(delta: float | None, higher_is_better: bool) -> str:
    if delta is None:
        return "unknown"
    # Scores move a few points with lighting alone; counts are exact, so any change counts.
    threshold = MEANINGFUL_SCORE_CHANGE if higher_is_better else 1
    if abs(delta) < threshold:
        return "same"
    improved = delta > 0 if higher_is_better else delta < 0
    return "better" if improved else "worse"


def compare_records(before: HistoryRecord, after: HistoryRecord) -> dict[str, Any]:
    """Deltas between two analyses. Scores: higher is better. Spot counts: lower is better."""
    def delta(a: float | None, b: float | None) -> float | None:
        return None if a is None or b is None else b - a

    overall = delta(before.overall_score, after.overall_score)
    scores = []
    for key, label in SCORE_LABELS.items():
        change = delta(before.scores.get(key), after.scores.get(key))
        scores.append({"key": key, "label": label, "before": before.scores.get(key), "after": after.scores.get(key),
                       "delta": change, "direction": _direction(change, True)})
    regions = []
    for key, name in REGION_NAMES.items():
        change = delta(before.regions.get(key), after.regions.get(key))
        regions.append({"key": key, "name": name, "before": before.regions.get(key), "after": after.regions.get(key),
                        "delta": change, "direction": _direction(change, False)})
    spots = delta(before.spot_counts.get("total"), after.spot_counts.get("total"))
    better = [s["label"] for s in scores if s["direction"] == "better"]
    worse = [s["label"] for s in scores if s["direction"] == "worse"]

    summary = []
    if overall is not None:
        if abs(overall) < MEANINGFUL_SCORE_CHANGE:
            summary.append(f"Genel skor benzer kaldı ({before.overall_score} → {after.overall_score}).")
        else:
            verb = "yükseldi" if overall > 0 else "düştü"
            summary.append(f"Genel skor {abs(overall)} puan {verb} ({before.overall_score} → {after.overall_score}).")
    if better:
        summary.append(f"İyileşen alanlar: {', '.join(better)}.")
    if worse:
        summary.append(f"Geriye giden alanlar: {', '.join(worse)}.")
    if spots is not None and before.spot_counts.get("total"):
        percent = round(100 * spots / before.spot_counts["total"])
        summary.append(f"Nokta sayısı %{abs(percent)} {'azaldı' if spots < 0 else 'arttı' if spots > 0 else 'değişmedi'}.")
    comparable = _comparable(before, after)
    return {
        "overall_delta": overall,
        "scores": scores,
        "regions": regions,
        "spot_delta": spots,
        "summary": summary,
        "comparability_notes": comparable,
    }


def _comparable(before: HistoryRecord, after: HistoryRecord) -> list[str]:
    """Warn when two photos differ in ways that move the scores regardless of the skin."""
    notes = []
    if before.method != after.method:
        notes.append("Fotoğraflar farklı yöntemle analiz edildi (yüz haritası/tüm görüntü); karşılaştırma yaklaşık.")
    pose_a, pose_b = before.head_pose or {}, after.head_pose or {}
    if pose_a and pose_b and abs(abs(pose_a.get("yaw", 0)) - abs(pose_b.get("yaw", 0))) > 15:
        notes.append("Baş açıları belirgin farklı; farklı bölgeler görünüyor olabilir.")
    if "needs_review" in {before.quality_status, after.quality_status}:
        notes.append("Fotoğraflardan birinin kalitesi ideal değil.")
    notes.append("En doğru takip için benzer ışıkta, aynı açıdan ve makyajsız çekim önerilir.")
    return notes


def trend_rows(records: list[HistoryRecord]) -> list[dict[str, Any]]:
    """Long-format rows (one per record × series) for charting."""
    rows = []
    for record in records:
        if record.overall_score is not None:
            rows.append({"tarih": record.created_at, "seri": "Genel skor", "değer": record.overall_score, "id": record.id})
        for key, label in SCORE_LABELS.items():
            value = record.scores.get(key)
            if value is not None:
                rows.append({"tarih": record.created_at, "seri": label, "değer": value, "id": record.id})
    return rows


def previous_record_comparison(store: HistoryStore, payload: dict[str, Any], person: str) -> tuple[dict[str, Any] | None, str | None]:
    """Compare an analysis with the latest saved record of the same person before it."""
    previous = [record for record in store.list(person) if record.id != payload["analysis_id"] and record.overall_score is not None]
    if not previous or not (payload.get("skin_metrics") or {}).get("available"):
        return None, None
    current = HistoryRecord(**record_from_payload(payload, person))
    before = previous[-1]
    return compare_records(before, current), datetime.fromisoformat(before.created_at).strftime("%d.%m.%Y %H:%M")
