"""Automatic quality checks for VLM comments against the measured analysis.

Used for monitoring (warnings in logs), in the regression script and in tests whenever
the prompt changes. Checks are heuristic and Turkish-specific on purpose.
"""
from __future__ import annotations

import re
from typing import Any

from safety.safe_response_builder import contains_blocked_term, normalize_text

STRONG_WORDS = ("belirgin", "yogun", "ciddi", "siddetli", "cok sayida", "yaygin")
MILD_WORDS = ("hafif", "sinirli", "az sayida", "birkac", "minimal", "hafifce")
REGION_STEMS = {
    "forehead": ("alin",),
    "nose": ("burun",),
    # "sağ ve sol yanak", "sağ taraftaki yanak": side word up to three words before "yanak".
    "left_cheek": (r"sol(?:\s+\w+){0,3}\s+yanak",),
    "right_cheek": (r"sag(?:\s+\w+){0,3}\s+yanak",),
    "chin": ("cene",),
}
INGREDIENT_STEMS = {
    "Retinol": ("retinol", "retinal", "retinoid"),
    "Salisilik asit (BHA)": ("salisilik", "bha"),
    "Laktik / glikolik asit (AHA)": ("glikolik", "laktik", "aha "),
    "C vitamini": ("c vitamini", "askorbik"),
    "Alfa arbutin / traneksamik asit": ("arbutin", "traneksamik"),
    "Kil maskesi (kaolin / çinko)": ("kil maske",),
}


# Second-person plural endings after normalisation (ı->i, ü->u): cildiniz, kullanabilirsiniz, yüzünüz...
PLURAL_YOU = re.compile(r"\w+(?:iniz|unuz)\b")


def _has(text: str, stems: tuple[str, ...]) -> bool:
    """Stems are plain prefixes unless they contain regex syntax (the cheek patterns)."""
    return any(re.search(rf"\b{stem if '(' in stem else re.escape(stem)}", text) for stem in stems)


def check_vlm_output(
    vlm_output: dict[str, Any],
    skin_metrics: dict[str, Any] | None = None,
    region_summary: dict[str, Any] | None = None,
    routine: dict[str, Any] | None = None,
    personalization: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Each check: {"check", "ok", "detail"}. Missing context skips the related check."""
    observations = vlm_output.get("visible_observations", [])
    suggestions = vlm_output.get("care_suggestions", [])
    items = observations + suggestions
    observation_text = normalize_text(" ".join(observations))
    all_text = normalize_text(" ".join(items))
    checks: list[dict[str, Any]] = []

    blocked = [item for item in items if contains_blocked_term(item)]
    checks.append({"check": "safety", "ok": not blocked and not vlm_output.get("safety_removed_count"),
                   "detail": f"{vlm_output.get('safety_removed_count', 0)} cümle filtrelendi" if vlm_output.get("safety_removed_count") else "temiz"})

    checks.append({"check": "structure", "ok": 2 <= len(observations) <= 6 and 2 <= len(suggestions) <= 6 and all(len(i) <= 400 for i in items),
                   "detail": f"{len(observations)} gözlem, {len(suggestions)} öneri"})

    if skin_metrics and skin_metrics.get("available"):
        overall = skin_metrics["overall_score"]
        strong = sum(len(re.findall(rf"\b{word}", observation_text)) for word in STRONG_WORDS)
        mild = sum(len(re.findall(rf"\b{word}", observation_text)) for word in MILD_WORDS)
        if overall >= 75:
            ok, detail = strong <= 1, f"skor {overall}, güçlü ifade {strong}"
        elif overall < 40:
            ok, detail = strong >= 1, f"skor {overall}, güçlü ifade {strong}, hafif ifade {mild}"
        else:
            ok, detail = True, f"skor {overall}, güçlü {strong} / hafif {mild}"
        checks.append({"check": "severity", "ok": ok, "detail": detail})

    if region_summary:
        most = region_summary.get("most_affected")
        if most:
            mentioned = _has(observation_text, REGION_STEMS[most])
            checks.append({"check": "most_affected_region", "ok": mentioned, "detail": region_summary.get("most_affected_name")})
        invisible = [r for r in region_summary.get("regions", []) if not r["visible"]]
        claims = []
        for region in invisible:
            for sentence in observations:
                normalized = normalize_text(sentence)
                if _has(normalized, REGION_STEMS[region["key"]]) and "gorun" not in normalized and "kadraj" not in normalized:
                    claims.append(region["name"])
        checks.append({"check": "invisible_regions", "ok": not claims, "detail": ", ".join(sorted(set(claims))) or "yok"})

    if routine:
        excluded_names = {item["name"] for item in routine.get("excluded", [])}
        mentioned = [name for name in excluded_names if name in INGREDIENT_STEMS and _has(all_text, INGREDIENT_STEMS[name])]
        checks.append({"check": "routine_conflict", "ok": not mentioned, "detail": ", ".join(mentioned) or "yok"})

    if personalization and personalization.get("hitap_adi"):
        name = normalize_text(personalization["hitap_adi"]).split()[0]
        first = normalize_text(observations[0]) if observations else ""
        checks.append({"check": "name_used", "ok": bool(re.search(rf"\b{re.escape(name)}\b", first)), "detail": personalization["hitap_adi"]})
        plural = len(PLURAL_YOU.findall(all_text))
        form = personalization.get("hitap", "siz")
        ok = plural <= 1 if form == "sen" else plural >= 1
        checks.append({"check": "address_form", "ok": ok, "detail": f"{form}, çoğul ek {plural}"})

    return checks


def quality_score(checks: list[dict[str, Any]]) -> float:
    return round(sum(1 for c in checks if c["ok"]) / len(checks), 2) if checks else 1.0
