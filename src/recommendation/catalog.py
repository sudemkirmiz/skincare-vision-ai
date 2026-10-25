# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Sudem Kırmız
"""Editable product catalog (data/products.json) matched against the routine.

The starter catalog contains a deliberately small set verified against manufacturers'
official Turkish pages. When nothing in the catalog fits a routine step, store search
links built from that step are shown instead. Users are always told to verify the label.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import quote_plus

from recommendation.engine import exclusion_reason
from recommendation.inci import analyse_inci, evaluate_product, parse_inci
from recommendation.ingredients import INGREDIENTS
from recommendation.profile import SkinProfile

logger = logging.getLogger("skincare.catalog")

CATEGORIES = {
    "cleanser": "Temizleyici",
    "moisturizer": "Nemlendirici",
    "sunscreen": "Güneş koruyucu",
    "serum": "Serum",
    "exfoliant": "Tonik / peeling",
    "mask": "Maske",
}
STEP_CATEGORIES = {"Temizleme": "cleanser", "Nemlendirme": "moisturizer", "Güneş koruma": "sunscreen"}
BUDGET_ORDER = {"low": 0, "mid": 1, "high": 2}
SKIN_TYPE_QUERY = {"oily": "yağlı cilt", "combination": "karma cilt", "dry": "kuru cilt", "normal": "", "unknown": ""}
STEP_QUERY = {"cleanser": "yüz temizleme jeli", "moisturizer": "nemlendirici krem", "sunscreen": "spf 50 yüz güneş kremi"}
ACTIVE_QUERY = {
    "niacinamide": "niasinamid serum",
    "bha": "salisilik asit tonik",
    "azelaic": "azelaik asit krem",
    "retinol": "retinol serum",
    "aha": "laktik asit tonik",
    "vitamin_c": "c vitamini serum",
    "soothing": "centella krem",
    "tone_brightener": "alfa arbutin serum",
    "hyaluronic": "hyaluronik asit serum",
    "clay_mask": "kil maskesi",
}
ACTIVE_CATEGORIES = {
    "clay_mask": {"mask"},
    "aha": {"exfoliant", "serum"},
    "bha": {"exfoliant", "serum"},
    "retinol": {"serum"},
    "azelaic": {"serum"},
    "vitamin_c": {"serum"},
    "niacinamide": {"serum"},
    "hyaluronic": {"serum"},
    "soothing": {"serum"},
    "tone_brightener": {"serum"},
}
# `icon` names a file bundled in frontend/public/stores, avoiding third-party requests from the browser.
DEFAULT_SEARCH_PROVIDERS = [
    {"name": "Trendyol", "url": "https://www.trendyol.com/sr?q={q}", "icon": "trendyol.png"},
    {"name": "Hepsiburada", "url": "https://www.hepsiburada.com/ara?q={q}", "icon": "hepsiburada.png"},
    {"name": "Google Alışveriş", "url": "https://www.google.com/search?tbm=shop&q={q}", "icon": "google.png"},
]
MAX_PRODUCTS_PER_STEP = 3


@dataclass
class Product:
    id: str
    name: str
    brand: str
    category: str
    skin_types: list[str] = field(default_factory=lambda: ["all"])
    price_tier: str = "mid"
    inci: str = ""
    key_ingredients: list[str] = field(default_factory=list)
    fragrance_free: bool | None = None
    url: str = ""
    notes: str = ""

    def __post_init__(self) -> None:
        if self.category not in CATEGORIES:
            raise ValueError(f"unknown category {self.category!r}")
        if self.price_tier not in BUDGET_ORDER:
            raise ValueError(f"unknown price_tier {self.price_tier!r}")
        if self.url and not self.url.startswith("https://"):
            raise ValueError("url must start with https://")
        unknown = [k for k in self.key_ingredients if k not in INGREDIENTS]
        if unknown:
            raise ValueError(f"unknown key_ingredients {unknown}")
        if self.inci:
            # A real ingredient list is the source of truth for actives and fragrance.
            analysis = analyse_inci(parse_inci(self.inci))
            self.key_ingredients = sorted(set(self.key_ingredients) | {a for a in analysis.actives if a in INGREDIENTS})
            self.fragrance_free = analysis.fragrance_free

    def fits_skin_type(self, skin_type: str) -> bool:
        return "all" in self.skin_types or skin_type == "unknown" or skin_type in self.skin_types


@dataclass
class Catalog:
    products: list[Product]
    search_providers: list[dict[str, str]]
    errors: list[str] = field(default_factory=list)


def load_catalog(path: Path) -> Catalog:
    """Invalid entries are skipped and reported, never fatal: the app must start with a broken catalog."""
    if not path.exists():
        return Catalog([], DEFAULT_SEARCH_PROVIDERS, [])
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        logger.error("Catalog unreadable: %s", error)
        return Catalog([], DEFAULT_SEARCH_PROVIDERS, [f"Katalog okunamadı: {error}"])

    products, errors = [], []
    for index, entry in enumerate(raw.get("products", [])):
        try:
            products.append(Product(**entry))
        except (TypeError, ValueError) as error:
            errors.append(f"Ürün #{index + 1} ({entry.get('name', '?') if isinstance(entry, dict) else '?'}): {error}")
    providers = [p for p in raw.get("search_providers", DEFAULT_SEARCH_PROVIDERS) if "{q}" in p.get("url", "") and p.get("url", "").startswith("https://")]
    for error in errors:
        logger.warning("Catalog entry skipped: %s", error)
    return Catalog(products, providers or DEFAULT_SEARCH_PROVIDERS, errors)


def search_links(query: str, providers: list[dict[str, str]]) -> list[dict[str, str]]:
    return [{"name": p["name"], "url": p["url"].replace("{q}", quote_plus(query)), "icon": Path(p.get("icon", "")).name} for p in providers]


def _query(base: str, profile: SkinProfile) -> str:
    parts = [base, SKIN_TYPE_QUERY.get(profile.skin_type, "")]
    if profile.is_sensitive or "fragrance" in profile.allergies:
        parts.append("parfümsüz")
    return " ".join(part for part in parts if part)


def _rank_products(candidates: list[Product], profile: SkinProfile, routine: dict, active_id: str | None) -> list[dict]:
    ranked = []
    for product in candidates:
        if not product.fits_skin_type(profile.skin_type):
            continue
        reasons, cautions = [], []
        verdict = "suitable"
        if product.inci:
            evaluation = evaluate_product(analyse_inci(parse_inci(product.inci)), profile, routine)
            if evaluation["verdict"] == "avoid":
                continue
            verdict = evaluation["verdict"]
            reasons += evaluation["positives"][:2]
            cautions += evaluation["caution"]
        else:
            if any(exclusion_reason(INGREDIENTS[k], profile) for k in product.key_ingredients):
                continue
            cautions.append("İçerik listesi katalogda yok; satın almadan önce etiketi kontrol edin.")
        if (profile.is_sensitive or "fragrance" in profile.allergies) and product.fragrance_free is False:
            continue
        if active_id and active_id not in product.key_ingredients:
            continue
        if "all" not in product.skin_types and profile.skin_type in product.skin_types:
            reasons.insert(0, "Cilt tipinize uygun olarak işaretli.")
        over_budget = BUDGET_ORDER[product.price_tier] > BUDGET_ORDER[profile.budget]
        score = (2 if verdict == "suitable" else 1) - (0.5 if over_budget else 0) + 0.1 * len(product.key_ingredients)
        ranked.append({
            "name": product.name,
            "brand": product.brand,
            "category": CATEGORIES[product.category],
            "price_tier": product.price_tier,
            "url": product.url,
            "verdict": verdict,
            "reasons": reasons or ["Rutin adımına uygun."],
            "cautions": cautions + (["Bütçenizin üzerinde."] if over_budget else []),
            "_score": score,
        })
    ranked.sort(key=lambda item: item["_score"], reverse=True)
    for item in ranked:
        item.pop("_score")
    return ranked[:MAX_PRODUCTS_PER_STEP]


def recommend_products(routine: dict, profile: SkinProfile, catalog: Catalog) -> list[dict]:
    """One entry per routine need: basic steps first, then each chosen active."""
    sections = []
    for step, category in STEP_CATEGORIES.items():
        products = _rank_products([p for p in catalog.products if p.category == category], profile, routine, None)
        sections.append({
            "title": step,
            "products": products,
            "search_links": search_links(_query(STEP_QUERY[category], profile), catalog.search_providers),
        })
    for active in routine.get("actives", []):
        if active.get("already_using"):
            continue
        allowed_categories = ACTIVE_CATEGORIES.get(active["id"], {"serum", "exfoliant", "mask"})
        candidates = [product for product in catalog.products if product.category in allowed_categories]
        products = _rank_products(candidates, profile, routine, active["id"])
        sections.append({
            "title": active["name"],
            "products": products,
            "search_links": search_links(_query(ACTIVE_QUERY.get(active["id"], active["name"]), profile), catalog.search_providers),
        })
    return sections
