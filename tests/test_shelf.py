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
