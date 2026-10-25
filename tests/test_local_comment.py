# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Sudem Kırmız
from analysis.local_comment import build_local_comment

LABELS = {"spots": "Nokta yoğunluğu", "redness": "Kızarıklık dengesi", "tone": "Ton eşitliği", "shine": "Parlama kontrolü", "texture": "Doku pürüzsüzlüğü"}


def metrics(**scores):
    base = {"spots": 80, "redness": 80, "tone": 80, "shine": 80, "texture": 80, **scores}
    return {
        "available": True, "overall_score": round(sum(base.values()) / 5), "scores": base, "score_labels": LABELS, "spot_counts": {"total": 29},
        "regions": {"forehead": {"name": "Alın", "tone": 70, "redness": 80}, "left_cheek": {"name": "Sol yanak", "tone": 20, "redness": 78},
                    "nose": {"name": "Burun", "tone": 72, "redness": 79}},
    }


REGIONS = {"most_affected_name": "Alın", "zones": {"t_zone": {"density": 3.7}, "u_zone": {"density": 1.1}}}
ROUTINE = {"actives": [{"name": "Azelaik asit", "strength": "%10 (kozmetik)", "frequency": "Akşamları, ilk hafta gün aşırı"}]}
BANNED = ("akne", "hastalık", "tedavi", "teşhis", "enfeksiyon", "ilaç")


def text_of(comment):
    return " ".join(comment["visible_observations"] + comment["care_suggestions"])


def test_weakest_scores_lead_with_name_region_zone_and_severity():
    comment = build_local_comment(metrics(spots=19, tone=30, redness=60), REGIONS, ROUTINE, {"hitap_adi": "Helin"}, {"status": "ok"})
    first, second = comment["visible_observations"][:2]
    assert first.startswith("Helin, ") and "29 nokta" in first and "T-bölgesinde" in first and ("belirgin" in first or "yoğun" in first)
    assert "(30/100)" in second
    assert "sol yanak" in second  # tone is worst on the left cheek, well below the face average
    assert any(line.startswith("Rutininizdeki Azelaik asit (%10, kozmetik)") for line in comment["care_suggestions"])
    assert any("dermatoloğa" in line for line in comment["care_suggestions"])  # spots in the priority band
    assert any("Noktalar iz" in line for line in comment["visible_observations"])  # spots + tone together


def test_severity_changes_the_wording():
    strong = build_local_comment(metrics(redness=20), REGIONS, None)["visible_observations"][0]
    medium = build_local_comment(metrics(redness=45), REGIONS, None)["visible_observations"][0]
    mild = build_local_comment(metrics(redness=65), REGIONS, None)["visible_observations"][0]
    assert "belirgin" in strong.lower() and "hafif" in mild.lower() and len({strong, medium, mild}) == 3


def test_same_analysis_same_text_different_faces_differ():
    a = build_local_comment(metrics(spots=40, shine=30), REGIONS, ROUTINE)
    assert a == build_local_comment(metrics(spots=40, shine=30), REGIONS, ROUTINE)
    texts = {text_of(build_local_comment(metrics(spots=s, shine=h), REGIONS, ROUTINE)) for s, h in ((40, 30), (41, 33), (20, 50), (50, 20))}
    assert len(texts) == 4


def test_progress_since_last_saved_analysis_comes_first():
    previous = {"overall_score": 50, "scores": {"spots": 30, "redness": 80, "tone": 80, "shine": 80, "texture": 80}, "created_at": "2026-10-01T09:00:00"}
    comment = build_local_comment(metrics(spots=55), REGIONS, None, {"hitap_adi": "Helin"}, previous=previous)
    first = comment["visible_observations"][0]
    assert first.startswith("Helin, 01.10 tarihli önceki analizinize göre") and "nokta yoğunluğu iyileşti (+25)" in first
    same = build_local_comment(metrics(spots=55), REGIONS, None, previous={**previous, "overall_score": 74, "scores": metrics(spots=55)["scores"]})
    assert "tablo benzer" in same["visible_observations"][0]
    # Without history it invites the user to track progress instead.
    assert any("geçmişe kaydedip" in line for line in build_local_comment(metrics(), REGIONS, None, image_quality={"status": "ok"})["care_suggestions"])


def test_goals_balanced_skin_photo_quality_and_missing_metrics():
    balanced = build_local_comment(metrics(), REGIONS, None, None, {"status": "needs_review", "notes": "Görsel boyutu düşük."}, concerns=["redness"])
    assert "iyi aralıkta" in balanced["visible_observations"][0]
    assert any("Hedeflerinizdeki kızarıklık dengesi için iyi haber" in line for line in balanced["visible_observations"])
    assert any(line.startswith("Görsel boyutu düşük. Daha isabetli") for line in balanced["care_suggestions"])
    assert build_local_comment({"available": False}, None, None) is None


def test_cosmetic_wording_limits_and_no_double_punctuation():
    for scores in ({"spots": 10, "redness": 10, "tone": 10, "shine": 10, "texture": 10}, {"spots": 50}, {}):
        comment = build_local_comment(metrics(**scores), REGIONS, ROUTINE, {"hitap_adi": "Helin"}, {"status": "needs_review"}, concerns=["spots"])
        text = text_of(comment).lower()
        assert not any(word in text for word in BANNED)
        assert len(comment["visible_observations"]) <= 4 and len(comment["care_suggestions"]) <= 5
        assert ".." not in text and ";" not in text.replace("; ", "")
        for line in comment["visible_observations"]:
            assert line.count(";") <= 1, line
    worst = build_local_comment(metrics(spots=10, redness=10, tone=10, shine=10, texture=10), REGIONS, ROUTINE, None, {"status": "needs_review"})
    assert any("dermatoloğa" in line for line in worst["care_suggestions"])  # never cut by the cap
