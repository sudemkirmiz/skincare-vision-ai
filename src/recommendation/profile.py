# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Sudem Kırmız
"""User skin profile collected by the questionnaire.

Pregnancy and allergy answers are health data: they only filter the routine locally,
are never sent to a VLM and never logged.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

SKIN_TYPES = {
    "unknown": "Bilmiyorum",
    "oily": "Yağlı",
    "combination": "Karma (T-bölgesi yağlı)",
    "normal": "Normal",
    "dry": "Kuru",
}
# Short hints shown inside the dropdown (also readable on touch screens, where tooltips don't work).
SKIN_TYPE_HINTS = {
    "unknown": "3 kısa soruyla birlikte bulalım",
    "oily": "yüzün tamamı gün içinde parlar",
    "combination": "alın ve burun parlak, yanaklar normal/kuru",
    "normal": "ne parlama ne gerginlik, dengeli",
    "dry": "yıkadıktan sonra gerginlik, yer yer pul pul",
}
SKIN_TYPE_HELP = (
    "**Cilt tipinizi nasıl anlarsınız?** Yüzünüzü yıkayıp hiçbir ürün sürmeden 2-3 saat bekleyin:\n\n"
    "- **Yağlı:** Yüzün tamamı parlar, gözenekler belirgindir; siyah nokta ve sivilce eğilimi olur.\n"
    "- **Karma:** T-bölgesi (alın, burun ve çene hattı) parlar; yanaklar normal veya kurudur.\n"
    "- **Normal:** Belirgin parlama ya da gerginlik yoktur, gözenekler küçüktür.\n"
    "- **Kuru:** Gerginlik hissi, mat görünüm ve yer yer pul pul olma görülür.\n\n"
    "Emin değilseniz **Bilmiyorum** seçin; 3 kısa soruyla birlikte bulalım."
)
SENSITIVITY_HELP = (
    "- **Hassas değil:** Yeni ürünlerde genelde kızarıklık, yanma veya kaşıntı olmaz.\n"
    "- **Bazen tahriş olur:** Bazı ürünler, soğuk/rüzgâr veya güneş sonrası zaman zaman kızarır ya da batar.\n"
    "- **Hassas:** Pek çok üründe kızarıklık, yanma veya kaşıntı olur; cilt kolay tepki verir."
)
SENSITIVITY = {"no": "Hassas değil", "sometimes": "Bazen tahriş olur", "yes": "Hassas"}
CONCERNS = {
    "spots": "Sivilce / nokta",
    "redness": "Kızarıklık",
    "tone": "Leke / ton eşitsizliği",
    "shine": "Parlama / yağlanma",
    "texture": "Pürüzlülük / gözenek görünümü",
    "dryness": "Kuruluk / gerginlik",
}
AGE_GROUPS = {"under_18": "18 yaş altı", "18_29": "18-29", "30_44": "30-44", "45_plus": "45+"}
BUDGETS = {"low": "Ekonomik", "mid": "Orta", "high": "Geniş"}
ROUTINE_SIZES = {"minimal": "Minimal (az adım)", "standard": "Standart"}
CURRENT_ACTIVES = {
    "retinol": "Retinol / retinal",
    "aha": "AHA (glikolik, laktik asit)",
    "bha": "BHA (salisilik asit)",
    "vitamin_c": "C vitamini",
    "benzoyl": "Benzoil peroksit",
    "niacinamide": "Niasinamid",
}
MAKEUP = {"unknown": "Belirtmedim", "none": "Kullanmıyorum", "sometimes": "Ara sıra", "daily": "Her gün"}
SUN_EXPOSURE = {"unknown": "Belirtmedim", "low": "Az (çoğunlukla içeride)", "medium": "Orta", "high": "Çok (dışarıda çalışıyorum/spor)"}
PREGNANCY = {"no": "Hayır", "yes": "Evet (hamile veya emziriyorum)", "undisclosed": "Belirtmek istemiyorum"}
ALLERGIES = {"fragrance": "Parfüm / esans", "essential_oils": "Uçucu yağlar", "salicylates": "Salisilat (aspirin) hassasiyeti"}


@dataclass
class SkinProfile:
    skin_type: str = "unknown"
    sensitivity: str = "no"
    concerns: list[str] = field(default_factory=list)
    age_group: str = "18_29"
    pregnant_or_breastfeeding: bool = False
    allergies: list[str] = field(default_factory=list)
    current_actives: list[str] = field(default_factory=list)
    budget: str = "mid"
    routine_size: str = "standard"
    # False when the user chose "prefer not to say": the engine then behaves as if pregnant.
    pregnancy_disclosed: bool = True
    makeup: str = "unknown"
    sun_exposure: str = "unknown"

    def __post_init__(self) -> None:
        # Unknown values from old sessions or bad input fall back to safe defaults.
        if self.skin_type not in SKIN_TYPES:
            self.skin_type = "unknown"
        if self.sensitivity not in SENSITIVITY:
            self.sensitivity = "no"
        if self.age_group not in AGE_GROUPS:
            self.age_group = "18_29"
        if self.budget not in BUDGETS:
            self.budget = "mid"
        if self.routine_size not in ROUTINE_SIZES:
            self.routine_size = "standard"
        if self.makeup not in MAKEUP:
            self.makeup = "unknown"
        if self.sun_exposure not in SUN_EXPOSURE:
            self.sun_exposure = "unknown"
        self.concerns = [c for c in dict.fromkeys(self.concerns) if c in CONCERNS]
        self.allergies = [a for a in dict.fromkeys(self.allergies) if a in ALLERGIES]
        self.current_actives = [a for a in dict.fromkeys(self.current_actives) if a in CURRENT_ACTIVES]

    @property
    def is_sensitive(self) -> bool:
        return self.sensitivity in {"yes", "sometimes"}

    @property
    def pregnancy_caution(self) -> bool:
        """Conservative: pregnancy-unsafe ingredients are excluded unless the user said "no"."""
        return self.pregnant_or_breastfeeding or not self.pregnancy_disclosed

    @property
    def pregnancy_status(self) -> str:
        if not self.pregnancy_disclosed:
            return "undisclosed"
        return "yes" if self.pregnant_or_breastfeeding else "no"

    @property
    def is_minor(self) -> bool:
        return self.age_group == "under_18"

    def to_dict(self) -> dict:
        return asdict(self)

    def vlm_safe_dict(self) -> dict:
        """The subset a VLM may see: no pregnancy, allergy or age data."""
        return {
            "cilt_tipi": SKIN_TYPES[self.skin_type],
            "hassasiyet": SENSITIVITY[self.sensitivity],
            "hedefler": [CONCERNS[c] for c in self.concerns],
        }
