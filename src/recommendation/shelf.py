"""The user's product shelf: per-product verdicts, opened-product expiry and shelf-wide checks.

Each product is judged with the same INCI checker as the Product Checker. On top of that the shelf
looks at the whole set: actives that should not share an evening, the same active twice in one
slot, essential steps that have no product, and products past their period-after-opening.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from recommendation.inci import active_name, analyse_inci, evaluate_product, parse_inci
from recommendation.ingredients import INGREDIENTS
from recommendation.profile import SkinProfile

CATEGORIES = {
    "cleanser": "Temizleyici",
    "moisturizer": "Nemlendirici",
    "sunscreen": "Güneş koruyucu",
    "serum": "Serum / aktif",
    "exfoliant": "Peeling / tonik",
    "other": "Diğer",
}
USAGES = {"am": "Sabah", "pm": "Akşam", "both": "Sabah ve akşam", "as_needed": "Gerektikçe"}
ESSENTIAL = ("cleanser", "moisturizer", "sunscreen")
EXPIRY_WARNING_DAYS = 30
AVERAGE_DAYS_PER_MONTH = 30.44


def _evening(item: dict[str, Any]) -> bool:
    return item["usage"] in {"pm", "both"}


def _morning(item: dict[str, Any]) -> bool:
    return item["usage"] in {"am", "both"}


def expiry(item: dict[str, Any], today: date) -> dict[str, Any] | None:
    """Days left of the period-after-opening (the jar symbol, e.g. 12M)."""
    if not item.get("opened_at") or not item.get("pao_months"):
        return None
    opened = date.fromisoformat(item["opened_at"])
    days_left = round(item["pao_months"] * AVERAGE_DAYS_PER_MONTH) - (today - opened).days
    status = "expired" if days_left < 0 else "soon" if days_left <= EXPIRY_WARNING_DAYS else "ok"
    return {"days_left": days_left, "status": status}


def analyse_item(item: dict[str, Any], profile: SkinProfile, routine: dict | None, today: date) -> dict[str, Any]:
    result = {**item, "category_label": CATEGORIES.get(item["category"], item["category"]), "usage_label": USAGES.get(item["usage"], item["usage"]),
              "expiry": expiry(item, today), "verdict": None, "actives": [], "is_sunscreen": item["category"] == "sunscreen"}
    ingredients = parse_inci(item.get("inci") or "")
    if ingredients:
        analysis = analyse_inci(ingredients)
        result["verdict"] = evaluate_product(analysis, profile, routine)
        result["actives"] = list(analysis.actives)
        result["is_sunscreen"] = result["is_sunscreen"] or analysis.is_sunscreen
    return result


def _conflicts(items: list[dict[str, Any]]) -> list[str]:
    """Evening actives on the shelf that should not be used on the same evening."""
    evening = [(item, active) for item in items if _evening(item) for active in item["actives"] if active in INGREDIENTS]
    warnings = []
    seen: set[frozenset[str]] = set()
    for index, (first, active_a) in enumerate(evening):
        for second, active_b in evening[index + 1:]:
            pair = frozenset({active_a, active_b})
            if first["id"] == second["id"] or pair in seen or len(pair) < 2:
                continue
            if active_b in INGREDIENTS[active_a].conflicts or active_a in INGREDIENTS[active_b].conflicts:
                seen.add(pair)
                warnings.append(f"“{first['name']}” ({active_name(active_a)}) ile “{second['name']}” ({active_name(active_b)}) "
                                "aynı akşam kullanılmamalı; farklı akşamlara ayırın.")
    return warnings


def _duplicates(items: list[dict[str, Any]]) -> list[str]:
    """The same active in two products of the same time slot: more irritation, rarely more benefit."""
    warnings = []
    for slot_name, in_slot in (("akşam", _evening), ("sabah", _morning)):
        owners: dict[str, list[str]] = {}
        for item in items:
            if in_slot(item):
                for active in item["actives"]:
                    owners.setdefault(active, []).append(item["name"])
        for active, names in owners.items():
            if len(names) > 1 and active in INGREDIENTS and active != "niacinamide":
                warnings.append(f"{active_name(active)} {slot_name} rutininizde {len(names)} üründe var ({', '.join(names)}); "
                                "tahriş riskini azaltmak için birini seçin.")
    return warnings


def _gaps(items: list[dict[str, Any]], routine: dict | None) -> list[str]:
    gaps = []
    has = {category: any(item["category"] == category or (category == "sunscreen" and item["is_sunscreen"]) for item in items) for category in ESSENTIAL}
    if not has["sunscreen"]:
        gaps.append("Rafınızda güneş koruyucu yok; sabah rutininin en önemli adımı.")
    elif not any(item["is_sunscreen"] and _morning(item) for item in items):
        gaps.append("Güneş koruyucunuz sabah kullanım olarak işaretli değil.")
    if not has["cleanser"]:
        gaps.append("Rafınızda yüz temizleyici yok.")
    if not has["moisturizer"]:
        gaps.append("Rafınızda nemlendirici yok.")
    owned = {active for item in items for active in item["actives"]}
    for active in (routine or {}).get("actives", []):
        if active["id"] not in owned:
            gaps.append(f"Rutininiz için önerilen {active['name']} rafınızdaki ürünlerde görünmüyor.")
    return gaps


def analyse_shelf(items: list[dict[str, Any]], profile: SkinProfile, routine: dict | None = None, today: date | None = None) -> dict[str, Any]:
    today = today or date.today()
    analysed = [analyse_item(item, profile, routine, today) for item in items]
    expired = [item["name"] for item in analysed if item["expiry"] and item["expiry"]["status"] == "expired"]
    avoid = [item["name"] for item in analysed if item["verdict"] and item["verdict"]["verdict"] == "avoid"]
    notes = []
    if avoid:
        notes.append(f"Profilinize göre önerilmeyen ürün: {', '.join(avoid)}.")
    if expired:
        notes.append(f"Açıldıktan sonraki kullanım süresi dolmuş: {', '.join(expired)}.")
    return {
        "items": analysed,
        "conflicts": _conflicts(analysed) + _duplicates(analysed),
        "gaps": _gaps(analysed, routine),
        "notes": notes,
        "categories": CATEGORIES,
        "usages": USAGES,
    }
