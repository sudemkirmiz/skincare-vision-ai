"""Rule-based routine engine: analysis metrics + skin profile -> explained AM/PM routine.

Deterministic on purpose: every suggestion can be traced to a metric or an answer,
and the whole thing is unit-testable. The VLM only receives the finished plan.
"""
from __future__ import annotations

from typing import Any

from recommendation.ingredients import (
    CLEANSER_BY_TYPE,
    DRY_SKIN,
    EXCLUSION_REASONS,
    INGREDIENTS,
    MINOR,
    MOISTURIZER_BY_TYPE,
    PREGNANT,
    SALICYLATE_ALLERGY,
    SENSITIVE,
    SUNSCREEN_BY_TYPE,
    Ingredient,
)
from recommendation.profile import CONCERNS, CURRENT_ACTIVES, SkinProfile

METRIC_CONCERNS = ("spots", "redness", "tone", "shine", "texture")
PROFILE_CONCERN_BOOST = 0.3
MAX_ACTIVES = {"minimal": 1, "standard": 2}
MIN_NEED = 0.15  # below this a concern is not worth an extra product
REFERRAL_SCORES = {"spots": 20, "redness": 25}
WEEKDAYS = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]
# Conflicting evening actives get fixed, non-adjacent nights when introduced.
EVENING_PATTERNS = [[0, 3], [1, 5], [2, 6]]
BUDGET_ORDER = {"low": 0, "mid": 1, "high": 2}
STRONG_ACTIVES = {"retinol", "aha"}
FIRST_TIMER_FACTOR = 0.75  # people new to actives start with gentler options
SUN_ADVICE = {
    "unknown": "; dışarıdaysanız 2-3 saatte bir yenileyin",
    "low": "; içerideyseniz sabah bir kat yeterli, dışarı çıkarken yenileyin",
    "medium": "; dışarıdaysanız 2-3 saatte bir yenileyin",
    "high": "; 2 saatte bir ve terledikten sonra yenileyin, şapka ve gölge de kullanın",
}
MAKEUP_CLEANSE = {
    "unknown": "; makyaj varsa önce yağ bazlı temizleyici kullanın",
    "none": "",
    "sometimes": "; makyajlı günlerde önce yağ bazlı temizleyici (çift temizleme)",
    "daily": "; her akşam önce yağ bazlı temizleyici ile makyajı çözün (çift temizleme)",
}


def compute_needs(skin_metrics: dict[str, Any] | None, profile: SkinProfile) -> dict[str, float]:
    """0..1 need per concern: low metric score and stated concerns both raise it."""
    needs = {concern: 0.0 for concern in CONCERNS}
    scores = (skin_metrics or {}).get("scores", {}) if (skin_metrics or {}).get("available") else {}
    for concern in METRIC_CONCERNS:
        score = scores.get(concern)
        if score is not None:
            needs[concern] = (100 - score) / 100
    for concern in profile.concerns:
        needs[concern] = min(1.0, needs[concern] + PROFILE_CONCERN_BOOST)
    if profile.skin_type == "oily":
        needs["shine"] = min(1.0, needs["shine"] + 0.2)
    elif profile.skin_type == "dry":
        needs["dryness"] = min(1.0, needs["dryness"] + 0.5)
        needs["shine"] *= 0.5
    return {concern: round(value, 2) for concern, value in needs.items()}


def exclusion_reason(ingredient: Ingredient, profile: SkinProfile) -> str | None:
    checks = {
        PREGNANT: profile.pregnancy_caution,
        MINOR: profile.is_minor,
        SENSITIVE: profile.sensitivity == "yes",
        SALICYLATE_ALLERGY: "salicylates" in profile.allergies,
        DRY_SKIN: profile.skin_type == "dry",
    }
    for condition in sorted(ingredient.excluded_if):
        if checks.get(condition):
            return EXCLUSION_REASONS[condition]
    return None


def _relevance(ingredient: Ingredient, needs: dict[str, float], profile: SkinProfile) -> float:
    score = sum(weight * needs.get(concern, 0.0) for concern, weight in ingredient.targets.items())
    if profile.is_sensitive and ingredient.sensitive_friendly:
        score *= 1.15
    if BUDGET_ORDER[ingredient.budget] > BUDGET_ORDER[profile.budget]:
        score *= 0.85
    if ingredient.id in STRONG_ACTIVES and not profile.current_actives:
        score *= FIRST_TIMER_FACTOR
    return score


def _why(ingredient: Ingredient, needs: dict[str, float], skin_metrics: dict[str, Any] | None, profile: SkinProfile) -> str:
    main = max(ingredient.targets, key=lambda concern: ingredient.targets[concern] * needs.get(concern, 0.0))
    reasons = []
    score = ((skin_metrics or {}).get("scores") or {}).get(main)
    if score is not None and score < 75:
        label = (skin_metrics or {}).get("score_labels", {}).get(main, CONCERNS[main])
        reasons.append(f"{label} skorunuz {score}/100")
    if main in profile.concerns:
        reasons.append(f"hedefleriniz arasında “{CONCERNS[main].lower()}” var")
    prefix = (" ve ".join(reasons) + ". ") if reasons else ""
    return f"{prefix}{ingredient.benefit}"


def select_actives(needs: dict[str, float], profile: SkinProfile) -> tuple[list[Ingredient], list[dict[str, str]]]:
    ranked = sorted(INGREDIENTS.values(), key=lambda item: _relevance(item, needs, profile), reverse=True)
    selected: list[Ingredient] = []
    excluded: list[dict[str, str]] = []
    used_groups: set[str] = set()
    limit = MAX_ACTIVES[profile.routine_size]
    for ingredient in ranked:
        relevance = _relevance(ingredient, needs, profile)
        if relevance < MIN_NEED:
            break
        reason = exclusion_reason(ingredient, profile)
        if reason:
            excluded.append({"name": ingredient.name, "reason": reason})
            continue
        if len(selected) >= limit:
            continue
        if ingredient.group and ingredient.group in used_groups:
            continue
        if profile.is_sensitive and any(ingredient.id in item.conflicts for item in selected):
            # Sensitive skin: never stack two strong evening actives, even on alternate nights.
            continue
        selected.append(ingredient)
        if ingredient.group:
            used_groups.add(ingredient.group)
    return selected, excluded


def _evening_schedule(actives: list[Ingredient], current: list[str]) -> list[dict[str, Any]]:
    """Weekly evening plan: conflicting actives never share a night; rest nights stay plain.

    `current` are actives the user already uses that were not re-selected; when they clash
    with a new active they are moved to the free nights.
    """
    evening = [item for item in actives if item.slot in {"pm", "both"}]
    scheduled = [item for item in evening if item.conflicts or item.id in {"azelaic", "clay_mask"}]
    nightly = [item.name for item in evening if item not in scheduled]
    nights: list[list[str]] = [list(nightly) for _ in WEEKDAYS]
    night_ids: list[set[str]] = [set() for _ in WEEKDAYS]

    pattern_index = 0
    for item in scheduled:
        if item.id == "azelaic":
            days = [0, 2, 4, 6]  # every other night in the first weeks
        elif item.id == "clay_mask":
            days = [5]
        else:
            days = EVENING_PATTERNS[pattern_index % len(EVENING_PATTERNS)]
            pattern_index += 1
        for day in days:
            nights[day].append(item.name)
            night_ids[day].add(item.id)

    for active_id in current:
        conflicts = INGREDIENTS[active_id].conflicts if active_id in INGREDIENTS else frozenset()
        clashing = {item.id for item in scheduled if active_id in item.conflicts or item.id in conflicts}
        if not clashing:
            continue
        free = [day for day in range(len(WEEKDAYS)) if not night_ids[day] & clashing]
        for day in free[:3]:
            nights[day].append(f"{CURRENT_ACTIVES[active_id]} (mevcut rutininiz)")
            night_ids[day].add(active_id)

    return [{"day": day, "actives": nights[index] or ["Dinlenme: sadece temizleme + nemlendirme"]} for index, day in enumerate(WEEKDAYS)]


def build_routine(skin_metrics: dict[str, Any] | None, profile: SkinProfile | None = None) -> dict[str, Any]:
    profile = profile or SkinProfile()
    needs = compute_needs(skin_metrics, profile)
    actives, excluded = select_actives(needs, profile)
    current = profile.current_actives
    skin_type = profile.skin_type
    fragrance_note = " (parfümsüz)" if profile.is_sensitive or "fragrance" in profile.allergies else ""

    active_cards = []
    for item in actives:
        already = item.id in current
        active_cards.append({
            "id": item.id,
            "name": item.name,
            "form": item.form,
            "strength": item.strength,
            "slot": item.slot,
            "frequency": "Zaten kullanıyorsunuz; mevcut sıklığınıza devam edin." if already else item.frequency,
            "why": _why(item, needs, skin_metrics, profile),
            "cautions": list(item.cautions),
            "already_using": already,
        })

    am = [{"step": "Temizleme", "product": CLEANSER_BY_TYPE[skin_type] + fragrance_note}]
    am += [{"step": item.name, "product": f"{item.form}, {item.strength}"} for item in actives if item.slot in {"am", "both"}]
    am += [
        {"step": "Nemlendirme", "product": MOISTURIZER_BY_TYPE[skin_type] + fragrance_note},
        {"step": "Güneş koruma", "product": SUNSCREEN_BY_TYPE[skin_type] + SUN_ADVICE[profile.sun_exposure]},
    ]
    pm = [{"step": "Temizleme", "product": CLEANSER_BY_TYPE[skin_type] + fragrance_note + MAKEUP_CLEANSE[profile.makeup]}]
    pm += [{"step": item.name, "product": f"{item.form}, {item.strength} - {item.frequency.lower()}"} for item in actives if item.slot in {"pm", "both"}]
    pm += [{"step": "Nemlendirme", "product": MOISTURIZER_BY_TYPE[skin_type] + fragrance_note}]

    warnings = _conflict_warnings(actives, current)
    if skin_metrics and skin_metrics.get("available"):
        scores = skin_metrics["scores"]
        if any(scores.get(key) is not None and scores[key] < limit for key, limit in REFERRAL_SCORES.items()):
            warnings.append("Görünüm yaygın ve belirgin. Bu rutin destekleyicidir; bir dermatoloğa görünmek en doğru başlangıç olur.")
    if profile.is_minor:
        warnings.append("18 yaş altında yeni bir aktife başlamadan önce ebeveyniniz ve bir uzmanla konuşmanız önerilir.")
    if profile.pregnant_or_breastfeeding:
        warnings.append("Hamilelik/emzirme döneminde her yeni ürünü doktorunuz veya eczacınızla teyit edin.")
    elif not profile.pregnancy_disclosed:
        warnings.append("Hamilelik/emzirme durumunuzu belirtmediğiniz için bazı içerikler ihtiyatlı olarak önerilmedi.")

    selected_ids = {item.id for item in actives}
    clashing_current = {a for a in current for item in actives if a in item.conflicts or (a in INGREDIENTS and item.id in INGREDIENTS[a].conflicts)}
    keep_using = [CURRENT_ACTIVES[a] for a in current if a not in selected_ids and a not in clashing_current]
    tips = [
        *([f"Mevcut {', '.join(keep_using)} kullanımınıza devam edebilirsiniz; önerilen içeriklerle çakışmaz."] if keep_using else []),
        "Yeni ürünleri tek tek ekleyin; ikisini aynı hafta başlatmayın.",
        "Her yeni ürünü önce kulak arkasına veya çene altına 2-3 gün sürerek yama testi yapın.",
        "Etkiyi görmek için en az 6-8 hafta düzenli kullanın.",
        "Sivilceleri sıkmayın; iz ve kızarıklık görünümünü uzatabilir.",
    ]
    focus = [CONCERNS[c] for c, v in sorted(needs.items(), key=lambda kv: kv[1], reverse=True) if v >= MIN_NEED][:3]
    return {
        "needs": needs,
        "focus": focus,
        "actives": active_cards,
        "excluded": excluded,
        "am": am,
        "pm": pm,
        "weekly": _evening_schedule(actives, [a for a in current if a not in {item.id for item in actives}]),
        "warnings": warnings,
        "tips": tips,
    }


def _conflict_warnings(actives: list[Ingredient], current: list[str]) -> list[str]:
    warnings = []
    for item in actives:
        clashes = [CURRENT_ACTIVES[a] for a in current if a in item.conflicts or (a in INGREDIENTS and item.id in INGREDIENTS[a].conflicts)]
        if clashes and item.id not in current:
            warnings.append(f"{item.name} ile {', '.join(clashes)} aynı akşam kullanılmamalı; haftalık planda ayrı akşamlara konuldu.")
    if "benzoyl" in current and any(item.id == "retinol" for item in actives):
        warnings.append("Benzoil peroksit ve retinolü aynı anda sürmeyin; birini sabah, diğerini akşam ya da farklı günlerde kullanın.")
    return warnings


def routine_summary_for_vlm(routine: dict[str, Any], profile: SkinProfile | None) -> dict[str, Any]:
    """What the VLM sees: the chosen plan and safe profile fields only."""
    return {
        "odak": routine["focus"],
        "secilen_icerikler": [item["name"] for item in routine["actives"]],
        "profil": (profile or SkinProfile()).vlm_safe_dict(),
    }
