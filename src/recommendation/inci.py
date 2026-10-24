"""INCI (ingredient list) parsing and compatibility checks against a skin profile and routine.

Matching is substring-based on normalised INCI names, which is robust to the small
spelling and spacing differences that OCR and packaging introduce. Concentrations are
not on labels, so only the position (first ~5 = main ingredients) is used as a hint.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from recommendation.engine import exclusion_reason
from recommendation.ingredients import INGREDIENTS
from recommendation.profile import CURRENT_ACTIVES, SkinProfile

# INCI fragments -> ingredient id from the knowledge base (or a profile active id).
ACTIVE_PATTERNS: dict[str, tuple[str, ...]] = {
    "niacinamide": ("niacinamide",),
    "bha": ("salicylic acid", "betaine salicylate", "capryloyl salicylic acid"),
    "azelaic": ("azelaic acid", "azeloyl"),
    "retinol": ("retinol", "retinal", "retinyl", "hydroxypinacolone retinoate"),
    "aha": ("glycolic acid", "lactic acid", "mandelic acid", "gluconolactone"),
    "vitamin_c": ("ascorbic acid", "ascorbyl", "ascorbate"),
    "soothing": ("centella asiatica", "madecassoside", "asiaticoside", "panthenol", "allantoin", "bisabolol"),
    "tone_brightener": ("alpha-arbutin", "alpha arbutin", "tranexamic acid"),
    "hyaluronic": ("hyaluronic acid", "sodium hyaluronate", "hydrolyzed hyaluronic"),
    "clay_mask": ("kaolin", "bentonite", "zinc pca"),
    "benzoyl": ("benzoyl peroxide",),
}
BARRIER_PATTERNS = ("ceramide", "cholesterol", "squalane", "phytosphingosine")
SUNSCREEN_PATTERNS = (
    "zinc oxide", "titanium dioxide", "ethylhexyl methoxycinnamate", "octocrylene", "avobenzone",
    "butyl methoxydibenzoylmethane", "bis-ethylhexyloxyphenol", "tinosorb", "uvinul", "homosalate",
    "ethylhexyl salicylate", "ethylhexyl triazone", "diethylamino hydroxybenzoyl",
)
FRAGRANCE_PATTERNS = (
    "parfum", "fragrance", "aroma", "linalool", "limonene", "citronellol", "geraniol", "citral",
    "eugenol", "coumarin", "hexyl cinnamal", "benzyl salicylate", "benzyl alcohol", "farnesol",
    "isoeugenol", "cinnamal", "amyl cinnamal", "alpha-isomethyl ionone", "hydroxycitronellal",
)
ESSENTIAL_OIL_PATTERNS = (
    "lavandula", "citrus aurantium", "citrus limon", "citrus sinensis", "mentha", "eucalyptus",
    "melaleuca", "rosmarinus", "pelargonium", "cymbopogon", "peppermint", "tea tree",
)
# Exact names only: substring "ethanol" would also flag phenoxyethanol, a harmless preservative.
DRYING_ALCOHOLS = {"alcohol", "alcohol denat", "ethanol", "isopropyl alcohol", "sd alcohol", "sd alcohol 40", "sd alcohol 40-b"}
PORE_CLOGGING_PATTERNS = (
    "cocos nucifera oil", "coconut oil", "isopropyl myristate", "isopropyl palmitate",
    "myristyl myristate", "laureth-4", "acetylated lanolin", "algae extract",
)
SALICYLATE_PATTERNS = ("salicylic acid", "salicylate", "salix alba", "willow bark")
MAIN_POSITION = 5  # first N ingredients are usually the bulk of the formula


@dataclass
class InciAnalysis:
    ingredients: list[str]
    actives: dict[str, int] = field(default_factory=dict)  # id -> position (1-based)
    barrier: list[str] = field(default_factory=list)
    is_sunscreen: bool = False
    fragrance: list[str] = field(default_factory=list)
    essential_oils: list[str] = field(default_factory=list)
    drying_alcohol: list[tuple[str, int]] = field(default_factory=list)
    pore_clogging: list[str] = field(default_factory=list)
    salicylates: list[str] = field(default_factory=list)

    @property
    def fragrance_free(self) -> bool:
        return not self.fragrance and not self.essential_oils


def normalise_inci(name: str) -> str:
    text = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii").lower()
    text = re.sub(r"\(.*?\)|\[.*?\]", " ", text)  # drop CI numbers, "(and)", translations
    text = re.sub(r"[^a-z0-9\- /]", " ", text)
    return re.sub(r"\s+", " ", text).strip(" -/")


def parse_inci(text: str) -> list[str]:
    """Split a pasted or OCR'd ingredient list into normalised INCI names."""
    text = re.sub(r"(?i)^\s*(ingredients?|i[çc]indekiler|inci|composition)\s*[:\-]", "", text.strip())
    text = re.sub(r"(?i)\bmay contain\b.*$|\+/-.*$", "", text, flags=re.DOTALL)
    parts = re.split(r"[,;\n•·]|\s{2,}|\.\s", text)
    seen: dict[str, None] = {}
    for part in parts:
        name = normalise_inci(part)
        if len(name) >= 3 and name not in seen:
            seen[name] = None
    return list(seen)


def _matches(name: str, patterns: tuple[str, ...]) -> bool:
    return any(pattern in name for pattern in patterns)


def analyse_inci(ingredients: list[str]) -> InciAnalysis:
    analysis = InciAnalysis(ingredients=ingredients)
    for position, name in enumerate(ingredients, start=1):
        for active_id, patterns in ACTIVE_PATTERNS.items():
            # Salicylate-based UV filters are not exfoliating BHA.
            if active_id == "bha" and "ethylhexyl salicylate" in name:
                continue
            if _matches(name, patterns) and active_id not in analysis.actives:
                analysis.actives[active_id] = position
        if _matches(name, BARRIER_PATTERNS):
            analysis.barrier.append(name)
        if _matches(name, SUNSCREEN_PATTERNS):
            analysis.is_sunscreen = True
        if _matches(name, FRAGRANCE_PATTERNS):
            analysis.fragrance.append(name)
        if _matches(name, ESSENTIAL_OIL_PATTERNS) and ("oil" in name or "extract" not in name):
            analysis.essential_oils.append(name)
        if name in DRYING_ALCOHOLS or name.startswith("alcohol denat"):
            analysis.drying_alcohol.append((name, position))
        if _matches(name, PORE_CLOGGING_PATTERNS):
            analysis.pore_clogging.append(name)
        if _matches(name, SALICYLATE_PATTERNS):
            analysis.salicylates.append(name)
    return analysis


def active_name(active_id: str) -> str:
    if active_id in INGREDIENTS:
        return INGREDIENTS[active_id].name
    return CURRENT_ACTIVES.get(active_id, active_id)


def evaluate_product(analysis: InciAnalysis, profile: SkinProfile, routine: dict | None = None) -> dict:
    """Verdict ('suitable' / 'caution' / 'avoid') with reasons, positives and routine notes."""
    avoid: list[str] = []
    caution: list[str] = []
    positives: list[str] = []
    routine_notes: list[str] = []

    for active_id in analysis.actives:
        if active_id in INGREDIENTS:
            reason = exclusion_reason(INGREDIENTS[active_id], profile)
            if reason:
                avoid.append(f"{active_name(active_id)} içeriyor; {reason}.")
    if "benzoyl" in analysis.actives:
        caution.append("Benzoil peroksit içeriyor; kumaşları ağartabilir ve kurutabilir, eczacınıza danışarak kullanın.")
    if "salicylates" in profile.allergies and analysis.salicylates:
        avoid.append("Salisilat içeriyor; salisilat hassasiyeti belirttiniz.")

    fragrance_sensitive = profile.is_sensitive or "fragrance" in profile.allergies
    if analysis.fragrance and fragrance_sensitive:
        target = avoid if "fragrance" in profile.allergies else caution
        target.append(f"Parfüm/koku alerjeni içeriyor ({', '.join(analysis.fragrance[:3])}).")
    if analysis.essential_oils and (profile.is_sensitive or "essential_oils" in profile.allergies):
        target = avoid if "essential_oils" in profile.allergies else caution
        target.append(f"Uçucu yağ içeriyor ({', '.join(analysis.essential_oils[:2])}).")
    early_alcohol = [name for name, position in analysis.drying_alcohol if position <= MAIN_POSITION]
    if early_alcohol and (profile.skin_type == "dry" or profile.is_sensitive):
        caution.append("Kurutucu alkol listenin başlarında; kuru veya hassas ciltte gerginlik yapabilir.")
    if analysis.pore_clogging and (profile.skin_type in {"oily", "combination"} or "spots" in profile.concerns):
        caution.append(f"Bazı kişilerde gözenek tıkayabilen bileşen içeriyor ({', '.join(analysis.pore_clogging[:2])}).")

    recommended = {item["id"] for item in (routine or {}).get("actives", [])}
    for active_id, position in analysis.actives.items():
        name = active_name(active_id)
        where = "ana bileşenlerden" if position <= MAIN_POSITION else f"listede {position}. sırada"
        if active_id in recommended:
            positives.append(f"{name} içeriyor ({where}); rutininiz için önerilen içeriklerden.")
        elif active_id in INGREDIENTS and not exclusion_reason(INGREDIENTS[active_id], profile):
            positives.append(f"{name} içeriyor ({where}).")
    if analysis.barrier:
        positives.append("Bariyer destekleyici bileşenler (seramid, skualan vb.) içeriyor.")
    if analysis.is_sunscreen:
        positives.append("UV filtresi içeriyor; güneş koruma adımında kullanılabilir.")
    if analysis.fragrance_free:
        positives.append("Parfüm ve uçucu yağ içermiyor.")

    in_use = set(profile.current_actives) | recommended
    for active_id in analysis.actives:
        if active_id not in INGREDIENTS:
            continue
        clashes = [active_name(other) for other in in_use if other != active_id and (other in INGREDIENTS[active_id].conflicts)]
        if clashes:
            routine_notes.append(f"{active_name(active_id)} ile {', '.join(sorted(set(clashes)))} aynı akşam kullanılmamalı.")

    verdict = "avoid" if avoid else "caution" if caution else "suitable"
    return {
        "verdict": verdict,
        "verdict_label": {"avoid": "Önerilmez", "caution": "Dikkatli kullanın", "suitable": "Uygun görünüyor"}[verdict],
        "avoid": avoid,
        "caution": caution,
        "positives": positives,
        "routine_notes": routine_notes,
        "detected_actives": [active_name(a) for a in analysis.actives],
        "ingredient_count": len(analysis.ingredients),
    }
