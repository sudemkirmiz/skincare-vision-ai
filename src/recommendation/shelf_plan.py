# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Sudem Kırmız
"""Turns the user's own shelf into a concrete plan: the order to apply products and a 7-night cycle.

Layering follows the usual thin-to-thick rule (cleanser → toner/exfoliant → serums → moisturiser →
sunscreen last in the morning). Strong evening actives are not stacked: retinoids and acids get their
own nights with recovery nights in between ("skin cycling"), so conflicting actives from the shelf
check never meet on the same evening. Sensitive skin gets fewer active nights.
"""
from __future__ import annotations

from typing import Any

from recommendation.ingredients import INGREDIENTS
from recommendation.profile import SkinProfile

WEEKDAYS = ("Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz")
# Thin to thick; sunscreen is always the last morning step.
LAYER_ORDER = {"cleanser": 0, "exfoliant": 1, "serum": 2, "other": 3, "moisturizer": 4, "sunscreen": 5}
STRONG = {"retinol": "retinoid", "aha": "acid", "bha": "acid", "clay_mask": "mask"}
THEMES = {
    "retinoid": "Retinol gecesi",
    "acid": "Peeling gecesi",
    "mask": "Maske gecesi",
    "rest": "Onarım gecesi",
}
# Night index 0 = Monday. Classic cycle: acid → retinoid → two recovery nights, repeated.
SCHEDULE = {
    False: {"acid": (0, 4), "retinoid": (1, 5), "acid_only": (1, 4), "retinoid_only": (0, 2, 4), "mask": (2,)},
    True: {"acid": (0,), "retinoid": (3,), "acid_only": (2,), "retinoid_only": (0, 3), "mask": (5,)},
}
TIPS = {
    "cleanser": "Nemli cilde 30-60 saniye masaj yapıp ılık suyla durulayın.",
    "exfoliant": "Pamukla ya da avuçla ince bir kat; göz çevresinden uzak tutun.",
    "serum": "Birkaç damla yeterli; bir sonraki adımdan önce 1 dakika emilmesini bekleyin.",
    "moisturizer": "Cilt hâlâ hafif nemliyken uygulayın.",
    "sunscreen": "Yüz ve boyun için iki parmak boyu; dışarıdaysanız 2 saatte bir yenileyin.",
    "other": "",
}
ACTIVE_TIPS = {
    "retinol": "Kuru cilde bezelye büyüklüğünde; ilk haftalarda nemlendiriciyle 'sandviç' yapabilirsiniz.",
    "vitamin_c": "Temizlemeden hemen sonra, güneş koruyucunun altına.",
    "aha": "Kuru cilde ince bir kat; ertesi sabah güneş koruyucu şart.",
    "bha": "Yağlı bölgelere odaklanın; ertesi sabah güneş koruyucu şart.",
    "clay_mask": "Tamamen kurumadan (10 dk) ılık suyla yıkayın.",
}


def _step(item: dict[str, Any]) -> dict[str, Any]:
    tip = next((ACTIVE_TIPS[active] for active in item["actives"] if active in ACTIVE_TIPS), TIPS.get(item["category"], ""))
    return {"id": item["id"], "name": item["name"], "category": item["category"], "category_label": item["category_label"],
            "actives": [INGREDIENTS[active].name for active in item["actives"] if active in INGREDIENTS], "tip": tip}


def _order(items: list[dict[str, Any]], morning: bool) -> list[dict[str, Any]]:
    def key(item: dict[str, Any]) -> tuple[int, int]:
        rank = LAYER_ORDER.get("sunscreen" if item["is_sunscreen"] else item["category"], 3)
        # Vitamin C goes first among morning serums.
        first = 0 if morning and "vitamin_c" in item["actives"] else 1
        return rank, first
    return [_step(item) for item in sorted(items, key=key)]


def _strength(item: dict[str, Any]) -> str | None:
    # Rinse-off cleansers with an acid are fine daily; zinc or kaolin only make a mask when the product is one
    # (a niacinamide + zinc serum is a daily serum).
    if item["category"] == "cleanser":
        return None
    kinds = {STRONG[active] for active in item["actives"] if active in STRONG and (active != "clay_mask" or item["category"] == "other")}
    for kind in ("retinoid", "acid", "mask"):
        if kind in kinds:
            return kind
    return None


def plan_shelf(analysed: list[dict[str, Any]], profile: SkinProfile) -> dict[str, Any]:
    """Morning steps, the every-evening base and seven themed nights built only from the user's products."""
    skipped, usable = [], []
    for item in analysed:
        if item["expiry"] and item["expiry"]["status"] == "expired":
            skipped.append({"name": item["name"], "reason": "Kullanım süresi dolmuş"})
        elif item["verdict"] and item["verdict"]["verdict"] == "avoid":
            skipped.append({"name": item["name"], "reason": "Profilinize göre önerilmiyor"})
        else:
            usable.append(item)
    as_needed = [item["name"] for item in usable if item["usage"] == "as_needed"]
    usable = [item for item in usable if item["usage"] != "as_needed"]

    # Strong actives never go in the morning, even when the product is marked "both".
    morning = [item for item in usable if item["usage"] in {"am", "both"} and not _strength(item)]
    moved = [item for item in usable if item["usage"] == "am" and _strength(item)]
    evening = [item for item in usable if (item["usage"] in {"pm", "both"} or item in moved) and not item["is_sunscreen"]]
    base = [item for item in evening if not _strength(item)]
    strong = {kind: [item for item in evening if _strength(item) == kind] for kind in ("retinoid", "acid", "mask")}

    sensitive = profile.is_sensitive
    slots = SCHEDULE[sensitive]
    nights: list[list[dict[str, Any]]] = [[] for _ in WEEKDAYS]
    themes = ["rest"] * len(WEEKDAYS)
    both = bool(strong["retinoid"]) and bool(strong["acid"])
    for kind in ("acid", "retinoid"):
        if not strong[kind]:
            continue
        days = slots[kind] if both else slots[f"{kind}_only"]
        for turn, day in enumerate(days):
            # Several acid products (AHA and BHA) take turns instead of sharing a night.
            nights[day].append(strong[kind][turn % len(strong[kind])])
            themes[day] = kind
    if strong["mask"]:
        free = [day for day in slots["mask"] if themes[day] == "rest"] or [day for day, theme in enumerate(themes) if theme == "rest"]
        if free:
            nights[free[0]].extend(strong["mask"])
            themes[free[0]] = "mask"

    plan_nights = []
    for index, name in enumerate(WEEKDAYS):
        plan_nights.append({"day": name, "theme": themes[index], "theme_label": THEMES[themes[index]], "steps": _order(base + nights[index], morning=False)})

    tips = []
    if not any(item["is_sunscreen"] for item in morning):
        tips.append("Sabah rutininizde güneş koruyucu yok; aktif kullanılan dönemde en önemli adım.")
    for item in moved:
        tips.append(f"“{item['name']}” güneşe duyarlılık yaratabilen bir aktif içeriyor; sabah yerine akşam planına aldık.")
    if strong["retinoid"] or strong["acid"]:
        tips.append("Onarım gecelerinde yalnızca temizleyici ve nemlendirici kullanın; cilt bariyeri bu gecelerde toparlanır.")
        if sensitive:
            tips.append("Hassas cilt: aktif gecelerini azalttık. 3-4 hafta sorun olmazsa haftada bir gece ekleyebilirsiniz.")
    if not usable:
        tips.append("Plan için rafınıza en az bir ürün ekleyin.")
    return {
        "morning": _order(morning, morning=True),
        "nights": plan_nights,
        "as_needed": as_needed,
        "skipped": skipped,
        "tips": tips,
        "active_nights": sum(theme != "rest" for theme in themes),
    }
