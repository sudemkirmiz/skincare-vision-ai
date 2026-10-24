"""Gemini "second opinion" on spots, reconciled with YOLO and the colour-based candidates.

Three noisy detectors are combined without retraining:
- YOLO findings are kept (the trained model, weak recall but few false alarms);
- colour candidates are the noisiest source (nostril creases, flushed patches), so when a
  second opinion is available, a colour candidate only survives if Gemini also saw it;
- spots only Gemini found are added as their own source.
"""
from __future__ import annotations

from typing import Any

from analysis.skin_metrics import WEIGHTS, _score

MAX_SPOTS = 150
MAX_BOX_AREA = 0.05  # of the crop; larger boxes are patches/regions, not spots
MIN_BOX_SIDE = 3  # px


def parse_gemini_boxes(spots: list[Any], width: int, height: int) -> list[list[int]]:
    """Gemini box_2d is [ymin, xmin, ymax, xmax] normalised to 0-1000; returns crop-pixel xyxy."""
    boxes = []
    for spot in spots[:MAX_SPOTS]:
        coords = spot.get("box_2d") if isinstance(spot, dict) else None
        if not isinstance(coords, list) or len(coords) != 4 or not all(isinstance(v, (int, float)) for v in coords):
            continue
        y1, x1, y2, x2 = (max(0.0, min(1000.0, float(v))) for v in coords)
        if y2 <= y1 or x2 <= x1:
            continue
        box = [round(x1 * width / 1000), round(y1 * height / 1000), round(x2 * width / 1000), round(y2 * height / 1000)]
        box_width, box_height = box[2] - box[0], box[3] - box[1]
        if min(box_width, box_height) < MIN_BOX_SIDE or box_width * box_height > MAX_BOX_AREA * width * height:
            continue
        boxes.append(box)
    return boxes


def _center(box: list[int]) -> tuple[float, float]:
    return (box[0] + box[2]) / 2, (box[1] + box[3]) / 2


def _matches(a: list[int], b: list[int], margin: float = 0.5) -> bool:
    """Centre of `a` falls inside `b` grown by `margin` (spots are small; IoU is too strict)."""
    cx, cy = _center(a)
    pad_x, pad_y = (b[2] - b[0]) * margin + 2, (b[3] - b[1]) * margin + 2
    return b[0] - pad_x <= cx <= b[2] + pad_x and b[1] - pad_y <= cy <= b[3] + pad_y


def reconcile(yolo_boxes: list[list[int]], colour_candidates: list[dict], gemini_boxes: list[list[int]]) -> dict[str, Any]:
    """Returns kept colour candidates, Gemini-only boxes and agreement stats."""
    kept_colour = [c for c in colour_candidates if any(_matches(c["box_xyxy"], g) or _matches(g, c["box_xyxy"]) for g in gemini_boxes)]
    known = yolo_boxes + [c["box_xyxy"] for c in colour_candidates]
    gemini_only = [g for g in gemini_boxes if not any(_matches(g, k) or _matches(k, g) for k in known)]
    yolo_confirmed = sum(1 for y in yolo_boxes if any(_matches(y, g) or _matches(g, y) for g in gemini_boxes))
    return {
        "kept_colour": kept_colour,
        "gemini_only": gemini_only,
        "stats": {
            "gemini_spots": len(gemini_boxes),
            "colour_confirmed": len(kept_colour),
            "colour_rejected": len(colour_candidates) - len(kept_colour),
            "yolo_confirmed": yolo_confirmed,
            "gemini_only": len(gemini_only),
        },
    }


def apply_to_metrics(skin_metrics: dict[str, Any], kept_colour: list[dict], gemini_only: list[list[int]]) -> None:
    """Update counts, spot score and overall score in place after reconciliation."""
    counts = skin_metrics["spot_counts"]
    counts["colour"] = len(kept_colour)
    counts["gemini"] = len(gemini_only)
    counts["total"] = counts["yolo"] + counts["colour"] + counts["gemini"]
    skin_metrics["spot_candidates"] = kept_colour
    skin_metrics["gemini_spots"] = [{"box_xyxy": box} for box in gemini_only]
    skin_metrics["raw"]["spots"] = float(counts["total"])
    scores = skin_metrics["scores"]
    scores["spots"] = _score(float(counts["total"]), "spots")
    available = {k: v for k, v in scores.items() if v is not None}
    skin_metrics["overall_score"] = round(sum(WEIGHTS[k] * v for k, v in available.items()) / sum(WEIGHTS[k] for k in available))
