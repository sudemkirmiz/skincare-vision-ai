# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Sudem Kırmız
"""Merge 1-3 photos of the same face (front, left, right) into one analysis.

Each region is measured in the photo where it is seen best (largest visible share), so
cheeks hidden by a turned head are covered by another angle and no spot is counted twice:
a region's count always comes from exactly one photo.
"""
from __future__ import annotations

from typing import Any

from analysis.regions import MIN_VISIBLE_RATIO, REGION_NAMES, ZONES
from analysis.skin_metrics import SCORE_LABELS, WEIGHTS, _score

ITA_SPREAD_WARNING = 15.0


def primary_view_index(views: list[dict[str, Any]]) -> int:
    """The most frontal photo (smallest |yaw|) carries the AI comment and the thumbnail."""
    def yaw(view: dict[str, Any]) -> float:
        pose = view.get("result", {}).get("detected_regions", {}).get("head_pose") or {}
        return abs(pose.get("yaw", 90.0))
    return min(range(len(views)), key=lambda index: yaw(views[index]))


def _region_sources(view: dict[str, Any], key: str) -> tuple[int, int]:
    """(yolo, colour) spots of one region in one view."""
    yolo = sum(1 for f in (view.get("skin_findings") or {}).get("findings", []) if f.get("region") == key)
    metrics = view.get("skin_metrics") or {}
    colour = sum(1 for c in metrics.get("spot_candidates", []) + metrics.get("gemini_spots", []) if c.get("region") == key)
    return yolo, colour


def merge_views(views: list[dict[str, Any]]) -> dict[str, Any]:
    """Returns merged {"region_summary", "skin_metrics", "provenance"} from per-view payloads."""
    usable = [i for i, v in enumerate(views) if v.get("region_summary") and (v.get("skin_metrics") or {}).get("available")]
    if not usable:
        raise ValueError("no view with regions and metrics")

    regions, provenance = [], {}
    yolo_total = colour_total = 0
    for key in REGION_NAMES:
        best_index, best_region = None, None
        for index in usable:
            region = next(r for r in views[index]["region_summary"]["regions"] if r["key"] == key)
            if region["visible"] and (best_region is None or region["area_ratio"] > best_region["area_ratio"]):
                best_index, best_region = index, region
        if best_region is None:
            fallback = next(r for r in views[usable[0]]["region_summary"]["regions"] if r["key"] == key)
            regions.append({**fallback, "view": None})
            continue
        provenance[key] = best_index
        yolo, colour = _region_sources(views[best_index], key)
        yolo_total += yolo
        colour_total += colour
        regions.append({**best_region, "view": best_index})

    zones = {}
    by_key = {r["key"]: r for r in regions}
    for zone_key, (zone_name, members) in ZONES.items():
        visible = [by_key[m] for m in members if by_key[m]["visible"]]
        count = sum(r["count"] for r in visible)
        area = sum(r["area_ratio"] for r in visible)
        zones[zone_key] = {"name": zone_name, "count": count, "density": round(count / (area * 10), 2) if area >= MIN_VISIBLE_RATIO else None}
    ranked = sorted((r for r in regions if r["visible"] and r["count"] > 0), key=lambda r: (r["density"] or 0, r["count"]), reverse=True)
    most = ranked[0]["key"] if ranked else None
    region_summary = {
        "regions": regions,
        "zones": zones,
        "unassigned": 0,
        "most_affected": most,
        "most_affected_name": REGION_NAMES.get(most) if most else None,
        "views": len(views),
    }

    metrics_list = [views[i]["skin_metrics"] for i in usable]
    total = sum(r["count"] for r in regions if r["visible"])
    scores: dict[str, int | None] = {"spots": _score(float(total), "spots")}
    for key in ("redness", "tone", "shine", "texture"):
        values = [m["scores"][key] for m in metrics_list if m["scores"].get(key) is not None]
        scores[key] = round(sum(values) / len(values)) if values else None
    available = {k: v for k, v in scores.items() if v is not None}
    overall = round(sum(WEIGHTS[k] * v for k, v in available.items()) / sum(WEIGHTS[k] for k in available))

    region_metrics = {}
    for key, index in provenance.items():
        metrics_regions = views[index]["skin_metrics"].get("regions", {})
        if key in metrics_regions:
            region_metrics[key] = metrics_regions[key]

    primary = views[primary_view_index(views)]["skin_metrics"]
    notes = list(dict.fromkeys(note for m in metrics_list for note in m.get("notes", [])))
    notes.insert(0, f"{len(views)} açıdan analiz edildi; her bölge en iyi göründüğü fotoğraftan ölçüldü.")
    itas = [m["skin_tone"]["ita"] for m in metrics_list]
    if max(itas) - min(itas) > ITA_SPREAD_WARNING:
        # Not an identity check (that would need a face-recognition model); only a coarse sanity hint.
        notes.insert(1, "Fotoğraflar arasında cilt tonu belirgin farklı: ışık çok farklı olabilir ya da fotoğraflar farklı kişilere ait olabilir.")
    skin_metrics = {
        "available": True,
        "overall_score": overall,
        "scores": scores,
        "score_labels": SCORE_LABELS,
        "regions": region_metrics,
        "skin_tone": primary["skin_tone"],
        "spot_counts": {"yolo": yolo_total, "colour": colour_total, "total": total},
        "spot_candidates": [],
        "notes": notes,
        "views": len(views),
        "white_balance": primary.get("white_balance"),
    }
    return {"region_summary": region_summary, "skin_metrics": skin_metrics, "provenance": provenance}
