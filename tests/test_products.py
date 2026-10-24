import json
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PIL import Image

import vlm_engine
from recommendation.catalog import Catalog, Product, load_catalog, recommend_products, search_links
from recommendation.engine import build_routine
from recommendation.inci import analyse_inci, evaluate_product, parse_inci
from recommendation.profile import SkinProfile
from safety.safe_response_builder import contains_blocked_term
from vlm_engine import VLMEngine, VLMOptions, VLMProviderError

BHA_TONER = "Ingredients: Aqua, Salicylic Acid, Butylene Glycol, Niacinamide, Sodium Hydroxide, Parfum, Linalool."
SUNSCREEN = "Aqua, Homosalate, Ethylhexyl Salicylate, Butyl Methoxydibenzoylmethane, Octocrylene, Glycerin, Alcohol Denat., Phenoxyethanol"
RETINOL_SERUM = "Squalane, Caprylic/Capric Triglyceride, Retinol, Tocopherol"
CERAMIDE_CREAM = "Aqua, Glycerin, Ceramide NP, Ceramide AP, Cholesterol, Sodium Hyaluronate, Phenoxyethanol, CI 77891 (Titanium Dioxide)"
EXAMPLE_CATALOG = Path(__file__).resolve().parents[1] / "data" / "products.example.json"


def metrics(**scores):
    base = {"spots": 60, "redness": 60, "tone": 60, "shine": 60, "texture": 60}
    base.update(scores)
    return {"available": True, "scores": base, "score_labels": {k: k for k in base}}


def test_parse_inci_strips_headers_brackets_and_duplicates():
    names = parse_inci("İçindekiler: Aqua (Water), Glycerin, glycerin, CI 77891 [Titanium Dioxide], Parfum.")
    assert names == ["aqua", "glycerin", "ci 77891", "parfum"]


def test_analyse_detects_actives_flags_and_positions():
    analysis = analyse_inci(parse_inci(BHA_TONER))
    assert analysis.actives == {"bha": 2, "niacinamide": 4}
    assert analysis.fragrance == ["parfum", "linalool"]
    assert not analysis.fragrance_free


def test_uv_filter_salicylate_is_not_bha_and_phenoxyethanol_is_not_alcohol():
    analysis = analyse_inci(parse_inci(SUNSCREEN))
    assert analysis.is_sunscreen
    assert "bha" not in analysis.actives
    assert [name for name, _ in analysis.drying_alcohol] == ["alcohol denat"]


def test_pregnancy_makes_retinol_product_avoid():
    verdict = evaluate_product(analyse_inci(parse_inci(RETINOL_SERUM)), SkinProfile(pregnant_or_breastfeeding=True))
    assert verdict["verdict"] == "avoid"
    assert any("Retinol" in reason for reason in verdict["avoid"])


def test_sensitive_skin_and_fragrance_allergy():
    analysis = analyse_inci(parse_inci(BHA_TONER))
    assert evaluate_product(analysis, SkinProfile(sensitivity="sometimes"))["verdict"] == "caution"
    assert evaluate_product(analysis, SkinProfile(allergies=["fragrance"]))["verdict"] == "avoid"


def test_dry_skin_flags_alcohol_only_among_main_ingredients():
    toner = "Aqua, Alcohol Denat., Glycerin, Hamamelis Virginiana Water"
    verdict = evaluate_product(analyse_inci(parse_inci(toner)), SkinProfile(skin_type="dry"))
    assert verdict["verdict"] == "caution"
    assert any("alkol" in reason for reason in verdict["caution"])
    # 7th position in the sunscreen: not a main ingredient, no warning.
    assert evaluate_product(analyse_inci(parse_inci(SUNSCREEN)), SkinProfile(skin_type="dry"))["verdict"] == "suitable"


def test_routine_match_and_conflict_notes():
    profile = SkinProfile(current_actives=["retinol"])
    routine = build_routine(metrics(spots=10, shine=10), profile)
    verdict = evaluate_product(analyse_inci(parse_inci(BHA_TONER)), profile, routine)
    assert any("Retinol" in note for note in verdict["routine_notes"])
    good = evaluate_product(analyse_inci(parse_inci(CERAMIDE_CREAM)), SkinProfile())
    assert good["verdict"] == "suitable"
    assert any("Bariyer" in p for p in good["positives"])
    assert any("Parfüm" in p for p in good["positives"])


def test_all_inci_texts_pass_safety_filter():
    profiles = [SkinProfile(), SkinProfile(pregnant_or_breastfeeding=True, sensitivity="yes", allergies=["fragrance", "salicylates"], skin_type="dry")]
    for inci in (BHA_TONER, SUNSCREEN, RETINOL_SERUM, CERAMIDE_CREAM):
        for profile in profiles:
            verdict = evaluate_product(analyse_inci(parse_inci(inci)), profile, build_routine(metrics(), profile))
            for text in verdict["avoid"] + verdict["caution"] + verdict["positives"] + verdict["routine_notes"]:
                assert not contains_blocked_term(text), text


def test_example_catalog_loads_and_derives_from_inci():
    catalog = load_catalog(EXAMPLE_CATALOG)
    assert catalog.errors == []
    serum = next(p for p in catalog.products if p.category == "serum")
    assert serum.key_ingredients == ["hyaluronic", "niacinamide", "soothing"]
    assert serum.fragrance_free is True


def test_broken_catalog_entries_are_skipped(tmp_path):
    path = tmp_path / "products.json"
    path.write_text(json.dumps({"products": [
        {"id": "a", "name": "A", "brand": "B", "category": "toothpaste"},
        {"id": "b", "name": "B", "brand": "B", "category": "serum", "url": "http://insecure"},
        {"id": "c", "name": "C", "brand": "B", "category": "cleanser"},
    ]}), encoding="utf-8")
    catalog = load_catalog(path)
    assert [p.id for p in catalog.products] == ["c"]
    assert len(catalog.errors) == 2
    assert load_catalog(tmp_path / "missing.json").products == []
    (tmp_path / "bad.json").write_text("{not json", encoding="utf-8")
    assert load_catalog(tmp_path / "bad.json").errors


def test_recommend_products_filters_by_profile_and_falls_back_to_search():
    catalog = Catalog(
        products=[
            Product(id="t", name="BHA Tonik", brand="X", category="exfoliant", inci=BHA_TONER, price_tier="low"),
            Product(id="m", name="Seramid Krem", brand="X", category="moisturizer", inci=CERAMIDE_CREAM),
            Product(id="r", name="Retinol Serum", brand="X", category="serum", inci=RETINOL_SERUM, skin_types=["dry"]),
            Product(id="s", name="Bentonitli SPF", brand="X", category="sunscreen", key_ingredients=["clay_mask"]),
        ],
        search_providers=[{"name": "Shop", "url": "https://shop.example/s?q={q}"}],
    )
    profile = SkinProfile(skin_type="oily", sensitivity="sometimes")
    routine = build_routine(metrics(spots=5, shine=5, redness=95, tone=95, texture=95), profile)
    sections = {section["title"]: section for section in recommend_products(routine, profile, catalog)}
    assert [p["name"] for p in sections["Nemlendirme"]["products"]] == ["Seramid Krem"]
    assert sections["Temizleme"]["products"] == []
    assert sections["Temizleme"]["search_links"][0]["url"].startswith("https://shop.example/s?q=")
    assert "parf%C3%BCms%C3%BCz" in sections["Temizleme"]["search_links"][0]["url"]  # sensitive -> fragrance-free query
    # The BHA toner has fragrance: allowed only with a caution for "sometimes sensitive".
    bha_section = next((s for title, s in sections.items() if "BHA" in title), None)
    if bha_section and bha_section["products"]:
        assert bha_section["products"][0]["verdict"] == "caution"
    active_sections = [section for title, section in sections.items() if title not in {"Temizleme", "Nemlendirme", "Güneş koruma"}]
    assert all(product["name"] != "Bentonitli SPF" for section in active_sections for product in section["products"])


def test_search_links_encode_turkish_characters():
    (link,) = search_links("güneş kremi yağlı cilt", [{"name": "S", "url": "https://s.example/?q={q}"}])
    assert link["url"] == "https://s.example/?q=g%C3%BCne%C5%9F+kremi+ya%C4%9Fl%C4%B1+cilt"


def _label_bytes():
    buffer = BytesIO()
    Image.new("RGB", (2400, 1200), "white").save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture
def fake_session(monkeypatch):
    session = MagicMock()
    monkeypatch.setattr(vlm_engine.requests, "Session", lambda: session)
    monkeypatch.setattr(vlm_engine, "_backoff", lambda *_: None)
    return session


def _gemini_text(text):
    response = MagicMock(status_code=200, ok=True, headers={})
    response.json.return_value = {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": text}]}}]}
    return response


def test_label_ocr_uses_its_own_prompt_and_schema(fake_session):
    fake_session.post.return_value = _gemini_text(json.dumps({"ingredients_text": BHA_TONER, "product_name": "Tonik"}))
    result = VLMEngine(VLMOptions()).extract_ingredients("Gemini", _label_bytes(), "key-123456")
    payload = fake_session.post.call_args.kwargs["json"]
    assert "içerik listesini" in payload["contents"][0]["parts"][0]["text"]
    assert payload["generationConfig"]["responseSchema"]["required"] == ["ingredients_text"]
    assert result["ingredients_text"] == BHA_TONER and result["product_name"] == "Tonik"


def test_label_ocr_empty_or_garbage_raises(fake_session):
    fake_session.post.return_value = _gemini_text(json.dumps({"ingredients_text": ""}))
    with pytest.raises(VLMProviderError, match="içerik listesi bulunamadı"):
        VLMEngine().extract_ingredients("Gemini", _label_bytes(), "key-123456")
    fake_session.post.return_value = _gemini_text("not json at all")
    with pytest.raises(VLMProviderError, match="okunamadı"):
        VLMEngine().extract_ingredients("Gemini", _label_bytes(), "key-123456")


def test_search_links_carry_store_icon_file_name_only():
    (link,) = search_links("serum", [{"name": "S", "url": "https://s.example/?q={q}", "icon": "../../secret/evil.png"}])
    assert link["icon"] == "evil.png"
    default = load_catalog(Path("does-not-exist.json")).search_providers
    assert {p["icon"] for p in default} == {"trendyol.png", "hepsiburada.png", "google.png"}
