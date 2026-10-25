# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Sudem Kırmız
import itertools

import pytest

from recommendation.engine import build_routine, compute_needs, routine_summary_for_vlm
from recommendation.ingredients import INGREDIENTS
from recommendation.profile import SkinProfile
from safety.safe_response_builder import contains_blocked_term


def metrics(spots=60, redness=60, tone=60, shine=60, texture=60):
    return {
        "available": True,
        "scores": {"spots": spots, "redness": redness, "tone": tone, "shine": shine, "texture": texture},
        "score_labels": {"spots": "Nokta yoğunluğu", "redness": "Kızarıklık dengesi", "tone": "Ton eşitliği", "shine": "Parlama kontrolü", "texture": "Doku pürüzsüzlüğü"},
    }


def chosen(routine):
    return {item["id"] for item in routine["actives"]}


def excluded(routine):
    return {item["name"] for item in routine["excluded"]}


def test_needs_follow_metrics_and_profile():
    needs = compute_needs(metrics(spots=20, redness=90), SkinProfile(concerns=["redness"], skin_type="dry"))
    assert needs["spots"] == 0.8
    assert needs["redness"] == pytest.approx(0.4)  # 0.1 from metrics + 0.3 stated concern
    assert needs["dryness"] == 0.5


def test_pregnancy_excludes_retinoids_bha_and_arbutin():
    routine = build_routine(metrics(spots=10, texture=10, tone=10), SkinProfile(pregnant_or_breastfeeding=True, current_actives=["niacinamide"]))
    assert not chosen(routine) & {"retinol", "bha", "tone_brightener"}
    assert any("Hamilelik" in warning for warning in routine["warnings"])


def test_minor_and_sensitive_exclusions():
    minor = build_routine(metrics(texture=0, tone=0), SkinProfile(age_group="under_18", current_actives=["bha"]))
    assert not chosen(minor) & {"retinol", "aha"}
    assert any("18 yaş" in warning for warning in minor["warnings"])

    sensitive = build_routine(metrics(spots=0, texture=0, tone=0), SkinProfile(sensitivity="yes"))
    assert not chosen(sensitive) & {"retinol", "aha", "bha", "vitamin_c"}
    assert "Salisilik asit (BHA)" in excluded(sensitive)


def test_allergy_and_dry_skin_exclusions():
    routine = build_routine(metrics(spots=0, shine=0), SkinProfile(allergies=["salicylates"], skin_type="dry"))
    assert "bha" not in chosen(routine)
    assert "clay_mask" not in chosen(routine)


def test_routine_size_limits_actives():
    assert len(build_routine(metrics(10, 10, 10, 10, 10), SkinProfile(routine_size="minimal"))["actives"]) == 1
    assert len(build_routine(metrics(10, 10, 10, 10, 10), SkinProfile(routine_size="standard"))["actives"]) == 2


def test_healthy_skin_gets_basics_only():
    routine = build_routine(metrics(95, 95, 95, 95, 95), SkinProfile(skin_type="normal"))
    assert routine["actives"] == []
    assert [step["step"] for step in routine["am"]] == ["Temizleme", "Nemlendirme", "Güneş koruma"]


def test_sunscreen_always_in_morning():
    for profile in (SkinProfile(), SkinProfile(skin_type="dry"), SkinProfile(sensitivity="yes")):
        assert build_routine(metrics(), profile)["am"][-1]["step"] == "Güneş koruma"


def test_conflicting_actives_never_share_a_night():
    profile = SkinProfile(current_actives=["vitamin_c"], concerns=["texture", "spots"], skin_type="oily")
    routine = build_routine(metrics(spots=5, texture=0, tone=90, redness=95, shine=90), profile)
    names = {INGREDIENTS[i].name: i for i in INGREDIENTS}
    for night in routine["weekly"]:
        ids = {names[name] for name in night["actives"] if name in names}
        for active in ids:
            assert not ids & INGREDIENTS[active].conflicts, night


def test_current_retinol_moves_to_free_nights_and_warns():
    profile = SkinProfile(current_actives=["retinol"], concerns=["spots"], skin_type="oily", sensitivity="no")
    routine = build_routine(metrics(spots=0, shine=0, texture=95, tone=95, redness=95), profile)
    assert "bha" in chosen(routine)
    assert any("aynı akşam kullanılmamalı" in warning for warning in routine["warnings"])
    for night in routine["weekly"]:
        assert not ("Salisilik asit (BHA)" in night["actives"] and any("Retinol" in a for a in night["actives"]))


def test_referral_when_scores_are_very_low():
    routine = build_routine(metrics(spots=10), SkinProfile())
    assert any("dermatoloğa" in warning for warning in routine["warnings"])
    assert not any("dermatoloğa" in w for w in build_routine(metrics(spots=60), SkinProfile())["warnings"])


def test_works_without_metrics():
    routine = build_routine(None, SkinProfile(concerns=["redness"]))
    assert "soothing" in chosen(routine) or "azelaic" in chosen(routine)


def test_vlm_summary_hides_health_data():
    profile = SkinProfile(pregnant_or_breastfeeding=True, allergies=["fragrance"], age_group="under_18")
    summary = routine_summary_for_vlm(build_routine(metrics(), profile), profile)
    text = str(summary).lower()
    assert "hamile" not in text and "pregnan" not in text and "alerj" not in text and "18" not in text


def _all_texts(routine):
    yield from routine["focus"]
    for item in routine["actives"]:
        yield from (item["why"], item["frequency"], *item["cautions"])
    for step in routine["am"] + routine["pm"]:
        yield from (step["step"], step["product"])
    for night in routine["weekly"]:
        yield from night["actives"]
    yield from routine["warnings"]
    yield from routine["tips"]
    for item in routine["excluded"]:
        yield item["reason"]


def test_every_generated_text_passes_the_safety_filter():
    profiles = [
        SkinProfile(skin_type=t, sensitivity=s, pregnant_or_breastfeeding=p, age_group=a, current_actives=c, concerns=["spots", "redness"])
        for t, s, p, a, c in itertools.product(
            ["oily", "dry", "unknown"], ["no", "yes"], [False, True], ["under_18", "30_44"], [[], ["retinol", "bha"], ["benzoyl"]]
        )
    ]
    for profile, score_set in itertools.product(profiles, [metrics(10, 10, 10, 10, 10), metrics(90, 30, 50, 70, 20)]):
        for text in _all_texts(build_routine(score_set, profile)):
            assert not contains_blocked_term(text), text
