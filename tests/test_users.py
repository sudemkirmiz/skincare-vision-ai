import sqlite3

import pytest

from history.store import MIGRATIONS, HistoryStore, record_from_payload
from recommendation.engine import build_routine
from recommendation.profile import SkinProfile
from users.profile import UserProfile, clean_name, completeness, infer_skin_type, profile_photo_mismatches, validate_required
from vlm_quality import check_vlm_output


def test_clean_name_keeps_turkish_letters_and_strips_noise():
    assert clean_name("  Ayşe   Gül<script>1 ") == "Ayşe Gülscript"
    assert clean_name("O'Neil-Çakır") == "O'Neil-Çakır"
    assert clean_name("x" * 80) == "x" * 40


def test_required_validation():
    assert validate_required("Ayşe", "18_29", "oily", "no", "no", True, "female") == []
    assert len(validate_required("A", None, None, None, None, False, None)) == 6  # pregnancy skipped until gender known
    assert len(validate_required("A", None, None, None, None, False, "other")) == 6


def test_pregnancy_question_only_when_relevant():
    from users.profile import pregnancy_question_applies

    assert validate_required("Can", "18_29", "oily", "no", None, True, "male") == []
    assert any("Hamilelik" in e for e in validate_required("Ayşe", "18_29", "oily", "no", None, True, "female"))
    assert any("Hamilelik" in e for e in validate_required("Deniz", "18_29", "oily", "no", None, True, "other"))
    assert not pregnancy_question_applies("male") and pregnancy_question_applies("female") and pregnancy_question_applies("other")
    assert UserProfile(display_name="Can", gender="xyz").gender == "other"
    assert "gender" not in UserProfile(display_name="Can", gender="male").vlm_personalization()


@pytest.mark.parametrize(("t_zone", "cheeks", "blotting", "expected"), [
    ("oily", "oily", "often", "oily"),
    ("oily", "normal", "sometimes", "combination"),
    ("oily", "dry", "never", "combination"),
    ("normal", "dry", "never", "dry"),
    ("normal", "dry", "often", "combination"),
    ("dry", "dry", "often", "dry"),
    ("normal", "normal", "never", "normal"),
    ("normal", "normal", "often", "combination"),
    ("normal", None, "never", None),
])
def test_skin_type_quiz(t_zone, cheeks, blotting, expected):
    assert infer_skin_type(t_zone, cheeks, blotting) == expected


def test_profile_roundtrip_and_personalization():
    profile = UserProfile(display_name="Ayşe", last_name="Yılmaz", address_form="siz",
                          skin=SkinProfile(skin_type="dry", pregnancy_disclosed=False), answered=["last_name", "bogus"])
    restored = UserProfile.from_dict({**profile.to_dict(), "unknown_future_field": 1})
    assert restored.skin.skin_type == "dry" and restored.skin.pregnancy_status == "undisclosed"
    assert restored.answered == ["last_name"]
    assert restored.vlm_personalization() == {"hitap_adi": "Ayşe", "hitap": "siz"}
    assert "Yılmaz" not in str(restored.vlm_personalization())


def test_completeness_counts_answered_optional_fields():
    base = UserProfile(display_name="Ali")
    full = UserProfile(display_name="Ali", answered=["last_name", "address_form", "concerns", "current_actives", "allergies",
                                                      "budget", "routine_size", "makeup", "sun_exposure"])
    assert 0.3 < completeness(base) < 0.5
    assert completeness(full) == 1.0


def _metrics(shine=80, redness=80, forehead_shine=90, nose_shine=90):
    return {"available": True, "scores": {"shine": shine, "redness": redness},
            "regions": {"forehead": {"shine": forehead_shine}, "nose": {"shine": nose_shine}}}


def test_mismatch_hints():
    assert profile_photo_mismatches(SkinProfile(skin_type="dry"), _metrics(shine=40))
    assert profile_photo_mismatches(SkinProfile(skin_type="normal"), _metrics(shine=70, nose_shine=20))
    assert profile_photo_mismatches(SkinProfile(skin_type="oily"), _metrics(shine=96, forehead_shine=95, nose_shine=99))
    assert profile_photo_mismatches(SkinProfile(sensitivity="no"), _metrics(redness=20))
    assert profile_photo_mismatches(SkinProfile(skin_type="oily", sensitivity="yes"), _metrics(shine=40, redness=20)) == []
    assert profile_photo_mismatches(SkinProfile(), None) == []


def test_undisclosed_pregnancy_is_handled_conservatively():
    metrics = {"available": True, "scores": {"spots": 10, "redness": 90, "tone": 10, "texture": 0, "shine": 90}, "score_labels": {}}
    routine = build_routine(metrics, SkinProfile(pregnancy_disclosed=False, current_actives=["niacinamide"]))
    assert "retinol" not in {a["id"] for a in routine["actives"]}
    assert any("belirtmediğin" in w for w in routine["warnings"])


def test_makeup_and_sun_answers_change_routine_text():
    daily = build_routine(None, SkinProfile(makeup="daily", sun_exposure="high"))
    assert "çift temizleme" in daily["pm"][0]["product"]
    assert "terledikten" in daily["am"][-1]["product"]
    none = build_routine(None, SkinProfile(makeup="none", sun_exposure="low"))
    assert "yağ bazlı" not in none["pm"][0]["product"]


def test_profile_store_and_adoption_of_legacy_history(tmp_path):
    store = HistoryStore(tmp_path / "h.db")
    store.save(record_from_payload({"analysis_id": "old", "result": {}}, "Ben"))
    first = UserProfile(display_name="Ayşe")
    store.save_profile(first.to_dict())
    assert [r.id for r in store.list(first.id)] == ["old"]  # legacy "Ben" history adopted
    second = UserProfile(display_name="Can")
    store.save_profile(second.to_dict())
    store.touch_profile(first.id)
    assert [p["display_name"] for p in store.list_profiles()] == ["Ayşe", "Can"]
    store.delete_profile(first.id)
    assert store.get_profile(first.id) is None and store.list(first.id) == []
    assert store.get_profile(second.id)["display_name"] == "Can"


def test_v1_database_is_migrated(tmp_path):
    path = tmp_path / "v1.db"
    with sqlite3.connect(path) as connection:
        for statement in MIGRATIONS[1]:
            connection.execute(statement)
        connection.execute("PRAGMA user_version = 1")
    store = HistoryStore(path)
    store.save_profile(UserProfile(display_name="Ayşe").to_dict())
    assert len(store.list_profiles()) == 1


def test_quality_checks_name_and_address_form():
    personal = {"hitap_adi": "Ayşe", "hitap": "sen"}
    good = {"visible_observations": ["Ayşe, sol yanağında hafif kızarıklık var.", "Cildin genel olarak dengeli."],
            "care_suggestions": ["Nazik bir temizleyici kullanabilirsin.", "Güneş koruyucunu ihmal etme."]}
    checks = {c["check"]: c["ok"] for c in check_vlm_output(good, personalization=personal)}
    assert checks["name_used"] and checks["address_form"]
    formal = {"visible_observations": ["Sol yanağınızda kızarıklık var.", "Cildiniz dengeli."],
              "care_suggestions": ["Nemlendirici kullanabilirsiniz.", "Güneş koruyucunuzu sürün."]}
    checks = {c["check"]: c["ok"] for c in check_vlm_output(formal, personalization=personal)}
    assert not checks["name_used"] and not checks["address_form"]
    checks = {c["check"]: c["ok"] for c in check_vlm_output(formal, personalization={"hitap_adi": "Ayşe", "hitap": "siz"})}
    assert checks["address_form"]
