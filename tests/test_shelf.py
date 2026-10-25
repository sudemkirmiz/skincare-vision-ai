# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Sudem Kırmız
from datetime import date

from recommendation.profile import SkinProfile
from recommendation.shelf import analyse_shelf, expiry

TODAY = date(2026, 10, 25)


def item(item_id, name, category, usage, inci="", opened_at=None, pao_months=None):
    return {"id": item_id, "name": name, "category": category, "usage": usage, "inci": inci,
            "opened_at": opened_at, "pao_months": pao_months, "created_at": "2026-10-01T00:00:00"}


RETINOL = item("a", "Gece Serumu", "serum", "pm", "Aqua, Glycerin, Retinol, Tocopherol")
GLYCOLIC = item("b", "Tonik", "exfoliant", "pm", "Aqua, Glycolic Acid, Glycerin")
SUNSCREEN = item("c", "SPF 50", "sunscreen", "am", "Aqua, Zinc Oxide, Glycerin")


def test_expiry_states():
    assert expiry(item("x", "K", "other", "am"), TODAY) is None
    assert expiry(item("x", "K", "other", "am", opened_at="2026-10-01", pao_months=12), TODAY)["status"] == "ok"
    assert expiry(item("x", "K", "other", "am", opened_at="2025-11-10", pao_months=12), TODAY)["status"] == "soon"
    assert expiry(item("x", "K", "other", "am", opened_at="2025-01-01", pao_months=6), TODAY)["status"] == "expired"


def test_evening_conflicts_and_missing_steps():
    result = analyse_shelf([RETINOL, GLYCOLIC], SkinProfile(skin_type="combination"), None, TODAY)
    assert any("Gece Serumu" in line and "Tonik" in line for line in result["conflicts"])
    assert any("güneş koruyucu yok" in gap for gap in result["gaps"])
    assert any("temizleyici" in gap for gap in result["gaps"]) and any("nemlendirici" in gap for gap in result["gaps"])
    by_id = {entry["id"]: entry for entry in result["items"]}
    assert "retinol" in by_id["a"]["actives"] and by_id["a"]["verdict"]["verdict"] in {"suitable", "caution"}


def test_same_active_twice_and_morning_conflict_ignored():
    morning_retinol = {**RETINOL, "id": "d", "usage": "am"}
    second_retinol = {**RETINOL, "id": "e", "name": "Göz Kremi"}
    result = analyse_shelf([RETINOL, second_retinol, morning_retinol, SUNSCREEN], SkinProfile(), None, TODAY)
    assert any("2 üründe" in line for line in result["conflicts"])
    assert not any("güneş koruyucu yok" in gap for gap in result["gaps"])


def test_profile_exclusions_and_routine_gaps():
    pregnant = SkinProfile(pregnant_or_breastfeeding=True)
    routine = {"actives": [{"id": "azelaic", "name": "Azelaik asit"}]}
    expired = {**SUNSCREEN, "opened_at": "2024-01-01", "pao_months": 6}
    result = analyse_shelf([RETINOL, expired], pregnant, routine, TODAY)
    assert result["items"][0]["verdict"]["verdict"] == "avoid"
    assert any("Gece Serumu" in note for note in result["notes"]) and any("süresi dolmuş" in note for note in result["notes"])
    assert any("Azelaik asit" in gap for gap in result["gaps"])


CLEANSER = item("f", "Jel Temizleyici", "cleanser", "both", "Aqua, Glycerin, Coco-Glucoside")
CREAM = item("g", "Bariyer Krem", "moisturizer", "both", "Aqua, Glycerin, Ceramide NP")
VITC = item("h", "C Serum", "serum", "am", "Aqua, Ascorbic Acid, Glycerin")
BHA = item("i", "BHA Tonik", "exfoliant", "pm", "Aqua, Salicylic Acid, Glycerin")


def _night_names(night):
    return [step["name"] for step in night["steps"]]


def test_plan_layers_products_and_ends_morning_with_sunscreen():
    plan = analyse_shelf([CREAM, SUNSCREEN, VITC, CLEANSER], SkinProfile(), None, TODAY)["plan"]
    assert [step["name"] for step in plan["morning"]] == ["Jel Temizleyici", "C Serum", "Bariyer Krem", "SPF 50"]
    assert all(_night_names(night) == ["Jel Temizleyici", "Bariyer Krem"] for night in plan["nights"])
    assert plan["active_nights"] == 0


def test_plan_never_puts_conflicting_actives_on_one_night():
    shelf = [CLEANSER, CREAM, RETINOL, GLYCOLIC, BHA]
    for profile in (SkinProfile(), SkinProfile(sensitivity="sometimes")):
        plan = analyse_shelf(shelf, profile, None, TODAY)["plan"]
        for night in plan["nights"]:
            names = set(_night_names(night))
            assert len(names & {"Gece Serumu", "Tonik", "BHA Tonik"}) <= 1, night
            assert night["steps"][0]["name"] == "Jel Temizleyici" and night["steps"][-1]["name"] == "Bariyer Krem"
        used = {name for night in plan["nights"] for name in _night_names(night)}
        assert {"Gece Serumu", "Tonik", "BHA Tonik"} <= used or profile.is_sensitive
    normal = analyse_shelf(shelf, SkinProfile(), None, TODAY)["plan"]
    sensitive = analyse_shelf(shelf, SkinProfile(sensitivity="sometimes"), None, TODAY)["plan"]
    assert normal["active_nights"] == 4 and sensitive["active_nights"] == 2
    assert [night["theme"] for night in normal["nights"]] == ["acid", "retinoid", "rest", "rest", "acid", "retinoid", "rest"]
    # The two acids take turns instead of sharing a night.
    assert "Tonik" in _night_names(normal["nights"][0]) and "BHA Tonik" in _night_names(normal["nights"][4])


def test_plan_skips_expired_and_moves_morning_retinol_to_evening():
    expired = item("j", "Eski Krem", "moisturizer", "both", "Aqua, Glycerin", opened_at="2025-01-01", pao_months=6)
    morning_retinol = {**RETINOL, "usage": "am"}
    plan = analyse_shelf([CLEANSER, expired, morning_retinol], SkinProfile(), None, TODAY)["plan"]
    assert plan["skipped"] == [{"name": "Eski Krem", "reason": "Kullanım süresi dolmuş"}]
    assert "Gece Serumu" not in [step["name"] for step in plan["morning"]]
    assert sum("Gece Serumu" in _night_names(night) for night in plan["nights"]) == 3
    assert any("akşam planına" in tip for tip in plan["tips"])


def test_zinc_serum_and_acid_cleanser_stay_daily():
    zinc_serum = item("k", "Niasinamid %10", "serum", "both", "Aqua, Niacinamide, Zinc PCA, Glycerin")
    bha_cleanser = item("l", "BHA Jel", "cleanser", "both", "Aqua, Salicylic Acid, Coco-Glucoside")
    plan = analyse_shelf([bha_cleanser, zinc_serum, CREAM], SkinProfile(), None, TODAY)["plan"]
    assert plan["active_nights"] == 0
    assert all(_night_names(night) == ["BHA Jel", "Niasinamid %10", "Bariyer Krem"] for night in plan["nights"])
