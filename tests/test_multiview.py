import pytest

from analysis.multiview import merge_views, primary_view_index

KEYS = ["forehead", "nose", "left_cheek", "right_cheek", "chin"]
NAMES = {"forehead": "Alın", "nose": "Burun", "left_cheek": "Sol yanak", "right_cheek": "Sağ yanak", "chin": "Çene"}


def view(yaw, regions, scores=None, ita=45.0, yolo_regions=(), colour_regions=()):
    """regions: key -> (count, area_ratio) for visible regions; others invisible."""
    summary = []
    for key in KEYS:
        if key in regions:
            count, area = regions[key]
            summary.append({"key": key, "name": NAMES[key], "count": count, "area_ratio": area, "density": round(count / (area * 10), 2), "visible": True})
        else:
            summary.append({"key": key, "name": NAMES[key], "count": 0, "area_ratio": 0.01, "density": None, "visible": False})
    return {
        "result": {"detected_regions": {"head_pose": {"yaw": yaw}}},
        "region_summary": {"regions": summary},
        "skin_findings": {"findings": [{"region": key} for key in yolo_regions]},
        "skin_metrics": {
            "available": True,
            "scores": scores or {"spots": 50, "redness": 60, "tone": 70, "shine": 80, "texture": 90},
            "skin_tone": {"ita": ita, "category": "Açık"},
            "spot_candidates": [{"region": key} for key in colour_regions],
            "regions": {key: {"name": NAMES[key], "redness": 50} for key in regions},
            "notes": [],
        },
    }


FRONT = view(-2, {"forehead": (4, 0.25), "nose": (1, 0.1), "left_cheek": (2, 0.2), "right_cheek": (2, 0.2), "chin": (1, 0.1)},
             yolo_regions=["forehead", "forehead", "left_cheek"], colour_regions=["forehead", "forehead", "nose", "left_cheek"])
TURNED_RIGHT = view(28, {"left_cheek": (9, 0.6), "chin": (2, 0.15), "nose": (1, 0.08)},
                    yolo_regions=["left_cheek"] * 4, colour_regions=["left_cheek"] * 5 + ["chin", "chin"])


def test_primary_is_most_frontal():
    assert primary_view_index([TURNED_RIGHT, FRONT]) == 1


def test_each_region_comes_from_its_best_view_without_double_counting():
    merged = merge_views([FRONT, TURNED_RIGHT])
    assert merged["provenance"] == {"forehead": 0, "nose": 0, "left_cheek": 1, "right_cheek": 0, "chin": 1}
    counts = {r["key"]: r["count"] for r in merged["region_summary"]["regions"]}
    assert counts == {"forehead": 4, "nose": 1, "left_cheek": 9, "right_cheek": 2, "chin": 2}
    metrics = merged["skin_metrics"]
    assert metrics["spot_counts"]["total"] == 18
    # forehead 2+2 and nose 0+1 from FRONT, right cheek 0, left cheek 4+5 and chin 0+2 from TURNED_RIGHT
    assert metrics["spot_counts"]["yolo"] == 2 + 4 and metrics["spot_counts"]["colour"] == 3 + 7
    assert merged["region_summary"]["most_affected"] == "forehead"  # 4 spots on 25% area: density 1.6 beats 1.5 and 1.33
    assert metrics["views"] == 2 and "2 açıdan" in metrics["notes"][0]


def test_scores_are_recomputed_from_merged_counts_and_averaged_colour_metrics():
    other = view(30, {"left_cheek": (0, 0.6)}, scores={"spots": 90, "redness": 80, "tone": 50, "shine": 60, "texture": None})
    metrics = merge_views([FRONT, other])["skin_metrics"]
    assert metrics["scores"]["redness"] == 70 and metrics["scores"]["tone"] == 60 and metrics["scores"]["texture"] == 90
    assert 0 <= metrics["overall_score"] <= 100


def test_region_hidden_everywhere_stays_invisible():
    merged = merge_views([TURNED_RIGHT, view(25, {"chin": (1, 0.2)})])
    forehead = next(r for r in merged["region_summary"]["regions"] if r["key"] == "forehead")
    assert forehead["visible"] is False and "forehead" not in merged["provenance"]


def test_large_skin_tone_spread_adds_a_hint():
    notes = merge_views([FRONT, view(25, {"chin": (1, 0.2)}, ita=10.0)])["skin_metrics"]["notes"]
    assert any("farklı kişilere" in note for note in notes)
    assert not any("farklı kişilere" in note for note in merge_views([FRONT, TURNED_RIGHT])["skin_metrics"]["notes"])


def test_no_usable_view_raises():
    broken = {**FRONT, "skin_metrics": {"available": False}}
    with pytest.raises(ValueError):
        merge_views([broken])
