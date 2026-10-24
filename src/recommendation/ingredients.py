"""Cosmetic (non-prescription) ingredient knowledge base.

Deliberately conservative: anything with prescription status in Türkiye or unclear
safety in pregnancy is either left out or excluded for that profile. Texts must pass
the safety filter (no disease names, no "treatment" claims) - a test enforces this.
"""
from __future__ import annotations

from dataclasses import dataclass

# Exclusion conditions an ingredient can declare.
PREGNANT = "pregnant"
MINOR = "minor"
SENSITIVE = "sensitive"  # excluded only for "yes", not "sometimes"
SALICYLATE_ALLERGY = "salicylates"
DRY_SKIN = "dry"

EXCLUSION_REASONS = {
    PREGNANT: "hamilelik/emzirme döneminde ihtiyatlı olarak önerilmiyor",
    MINOR: "18 yaş altı için önerilmiyor",
    SENSITIVE: "hassas ciltte tahriş riski nedeniyle önerilmiyor",
    SALICYLATE_ALLERGY: "salisilat hassasiyeti belirttiğiniz için önerilmiyor",
    DRY_SKIN: "kuru ciltte kurutucu olabileceği için önerilmiyor",
}


@dataclass(frozen=True)
class Ingredient:
    id: str
    name: str
    form: str  # typical product format
    strength: str  # cosmetic concentration range
    targets: dict[str, float]  # concern -> relevance 0..1
    slot: str  # "am", "pm" or "both"
    frequency: str
    benefit: str  # what it does, cosmetic wording
    cautions: tuple[str, ...] = ()
    excluded_if: frozenset[str] = frozenset()
    conflicts: frozenset[str] = frozenset()  # not on the same evening
    group: str = ""  # at most one ingredient per group is chosen
    sensitive_friendly: bool = False
    budget: str = "low"  # cheapest typical tier: low / mid / high


INGREDIENTS: dict[str, Ingredient] = {
    item.id: item
    for item in [
        Ingredient(
            id="niacinamide",
            name="Niasinamid",
            form="serum",
            strength="%4-5",
            targets={"spots": 0.6, "shine": 0.8, "redness": 0.5, "tone": 0.6, "texture": 0.3},
            slot="both",
            frequency="Her gün, sabah ve/veya akşam",
            benefit="Yağ dengesini ve gözenek görünümünü destekler, ton eşitsizliği ile kızarıklık görünümünü azaltmaya yardımcı olur.",
            cautions=("Hassas ciltte %2-4 ile başlamak daha konforludur.",),
            sensitive_friendly=True,
        ),
        Ingredient(
            id="bha",
            name="Salisilik asit (BHA)",
            form="tonik veya serum",
            strength="%0,5-2",
            targets={"spots": 1.0, "shine": 0.7, "texture": 0.7},
            slot="pm",
            frequency="Haftada 2-3 akşam ile başlayın, cilt alışınca gün aşırı",
            benefit="Gözenek içine işleyerek siyah nokta ve tıkanıklık görünümünü azaltmaya yardımcı olur.",
            cautions=("Kullandığınız dönemde güneş koruyucu şart.", "Kuruluk olursa sıklığı azaltın."),
            excluded_if=frozenset({PREGNANT, SALICYLATE_ALLERGY, SENSITIVE}),
            conflicts=frozenset({"retinol", "aha"}),
            group="exfoliant",
        ),
        Ingredient(
            id="azelaic",
            name="Azelaik asit",
            form="krem veya jel",
            strength="%10 (kozmetik)",
            targets={"spots": 0.8, "redness": 0.9, "tone": 0.8},
            slot="pm",
            frequency="Akşamları, ilk hafta gün aşırı",
            benefit="Kızarıklık, nokta ve leke görünümünü dengelemeye yardımcı olur; hassas ciltte genelde iyi tolere edilir.",
            cautions=("İlk günlerde hafif karıncalanma normaldir; yanma olursa ara verin.",),
            sensitive_friendly=True,
            budget="mid",
        ),
        Ingredient(
            id="retinol",
            name="Retinol",
            form="serum veya krem",
            strength="%0,1-0,3 ile başlayın",
            targets={"texture": 1.0, "tone": 0.7, "spots": 0.6},
            slot="pm",
            frequency="Haftada 2 akşam ile başlayın, 2-3 haftada bir artırın",
            benefit="Hücre yenilenmesini destekleyerek doku, ton ve gözenek görünümünü düzgünleştirmeye yardımcı olur.",
            cautions=("Güneş hassasiyetini artırabilir; sabah güneş koruyucu şart.", "Pul pul dökülme olursa sıklığı azaltın."),
            excluded_if=frozenset({PREGNANT, MINOR, SENSITIVE}),
            conflicts=frozenset({"bha", "aha"}),
            budget="mid",
        ),
        Ingredient(
            id="aha",
            name="Laktik / glikolik asit (AHA)",
            form="tonik veya serum",
            strength="%5-10",
            targets={"texture": 0.9, "tone": 0.6},
            slot="pm",
            frequency="Haftada 1-2 akşam",
            benefit="Yüzeydeki ölü hücreleri nazikçe uzaklaştırarak pürüzsüzlük ve ışıltı görünümünü destekler.",
            cautions=("Kullandığınız dönemde güneş koruyucu şart.",),
            excluded_if=frozenset({MINOR, SENSITIVE}),
            conflicts=frozenset({"retinol", "bha"}),
            group="exfoliant",
        ),
        Ingredient(
            id="vitamin_c",
            name="C vitamini",
            form="serum",
            strength="%10-15",
            targets={"tone": 0.9, "texture": 0.2},
            slot="am",
            frequency="Her sabah, güneş koruyucudan önce",
            benefit="Işıltı ve ton eşitliği görünümünü destekler, güneş koruyucunun yanında antioksidan destek sağlar.",
            cautions=("Hassas ciltte daha düşük oranlı veya türev formlarla başlayın.",),
            excluded_if=frozenset({SENSITIVE}),
            budget="mid",
        ),
        Ingredient(
            id="soothing",
            name="Centella / panthenol",
            form="serum veya krem",
            strength="-",
            targets={"redness": 1.0, "dryness": 0.4},
            slot="both",
            frequency="Her gün",
            benefit="Cildi yatıştırarak kızarıklık ve gerginlik hissini azaltmaya yardımcı olur, bariyeri destekler.",
            sensitive_friendly=True,
        ),
        Ingredient(
            id="tone_brightener",
            name="Alfa arbutin / traneksamik asit",
            form="serum",
            strength="%2-3",
            targets={"tone": 0.9},
            slot="both",
            frequency="Her gün, akşam veya sabah",
            benefit="Koyu leke ve iz görünümünü açmaya yardımcı olur.",
            excluded_if=frozenset({PREGNANT}),
            sensitive_friendly=True,
            budget="mid",
        ),
        Ingredient(
            id="hyaluronic",
            name="Hyaluronik asit",
            form="serum",
            strength="-",
            targets={"dryness": 1.0, "texture": 0.2},
            slot="both",
            frequency="Her gün, nemli cilde",
            benefit="Cildin nem tutmasına yardımcı olur, gerginlik hissini azaltır.",
            sensitive_friendly=True,
        ),
        Ingredient(
            id="clay_mask",
            name="Kil maskesi (kaolin / çinko)",
            form="maske",
            strength="-",
            targets={"shine": 0.9, "spots": 0.3},
            slot="pm",
            frequency="Haftada 1-2 kez, sadece T-bölgesine",
            benefit="Fazla yağı emerek parlama görünümünü azaltır.",
            excluded_if=frozenset({DRY_SKIN}),
            group="mask",
        ),
    ]
}

# Basic steps every routine has; the product advice depends on skin type.
CLEANSER_BY_TYPE = {
    "oily": "Jel veya köpük yapılı, sülfatsız nazik temizleyici",
    "combination": "Jel yapılı nazik temizleyici",
    "normal": "Nazik, pH dengeli temizleyici",
    "dry": "Krem veya süt yapılı, köpürmeyen temizleyici",
    "unknown": "Nazik, pH dengeli temizleyici",
}
MOISTURIZER_BY_TYPE = {
    "oily": "Hafif, yağsız jel nemlendirici (komedojenik olmayan)",
    "combination": "Hafif losyon nemlendirici; kuru bölgelere biraz daha",
    "normal": "Seramidli hafif krem nemlendirici",
    "dry": "Seramid ve yağ asitleri içeren zengin krem nemlendirici",
    "unknown": "Seramidli hafif nemlendirici",
}
SUNSCREEN_BY_TYPE = {
    "oily": "SPF 50, geniş spektrumlu, mat bitişli akışkan güneş koruyucu",
    "combination": "SPF 50, geniş spektrumlu, hafif dokulu güneş koruyucu",
    "normal": "SPF 50, geniş spektrumlu güneş koruyucu",
    "dry": "SPF 50, geniş spektrumlu, nemlendirici dokulu güneş koruyucu",
    "unknown": "SPF 50, geniş spektrumlu güneş koruyucu",
}
