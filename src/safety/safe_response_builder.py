# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Sudem Kırmız
from __future__ import annotations

import unicodedata
from dataclasses import dataclass

DISCLAIMER = (
    "Bu çıktı tıbbi tanı değildir; yalnızca görsel bakım ön değerlendirmesidir. "
    "Şikayet, ağrı, hızlı değişim veya endişe varsa dermatoloğa danışılmalıdır."
)

FALLBACK_ITEM = "Görselden yalnızca bakım odaklı genel bir ön değerlendirme yapılabilir."

# Diagnoses, disease names, prescription-only actives and treatment claims.
BLOCKED_TERMS = [
    # diagnosis / disease claims
    "akne hastalığı",
    "akne vulgaris",
    "egzama",
    "ekzama",
    "rosacea",
    "rozasea",
    "sedef",
    "psoriasis",
    "dermatit",
    "melanom",
    "melanoma",
    "kanser",
    "karsinom",
    "tümör",
    "enfeksiyon",
    "mantar enfeksiyonu",
    "teşhis",
    "kesin tanı",
    "tanısı konul",
    "hastalığınız",
    # medication / prescription
    "ilaç kullan",
    "ilaç al",
    "reçete",
    "antibiyotik",
    "doksisiklin",
    "isotretinoin",
    "izotretinoin",
    "roakutan",
    "accutane",
    "tretinoin",
    "adapalen",
    "kortizon",
    "kortikosteroid",
    "steroid",
    "hormon tedavisi",
    "doğum kontrol hap",
    "doz",
    # treatment claims
    "tedavi gerekir",
    "tedavi edilmeli",
    "tedavi eder",
    "iyileştirir",
    "kesin çözüm",
]


@dataclass(frozen=True)
class SafeSkinResponse:
    visible_observations: list[str]
    care_suggestions: list[str]
    disclaimer: str
    removed_count: int = 0


def normalize_text(text: str) -> str:
    # Turkish dotted/dotless i must collapse to the same form before matching.
    lowered = text.replace("İ", "i").replace("I", "ı").casefold().replace("ı", "i")
    decomposed = unicodedata.normalize("NFKD", lowered)
    return "".join(character for character in decomposed if not unicodedata.combining(character))


_NORMALIZED_TERMS = [normalize_text(term) for term in BLOCKED_TERMS]


def contains_blocked_term(text: str) -> bool:
    normalized = normalize_text(text)
    return any(term in normalized for term in _NORMALIZED_TERMS)


class SafeResponseBuilder:
    def build(
        self,
        visible_observations: list[str],
        care_suggestions: list[str],
    ) -> SafeSkinResponse:
        observations, removed_observations = self._filter_items(visible_observations)
        suggestions, removed_suggestions = self._filter_items(care_suggestions)
        return SafeSkinResponse(
            visible_observations=observations,
            care_suggestions=suggestions,
            disclaimer=DISCLAIMER,
            removed_count=removed_observations + removed_suggestions,
        )

    def _filter_items(self, items: list[str]) -> tuple[list[str], int]:
        safe_items = [item for item in items if not contains_blocked_term(item)]
        removed = len(items) - len(safe_items)
        if safe_items:
            return safe_items, removed
        return [FALLBACK_ITEM], removed


if __name__ == "__main__":
    builder = SafeResponseBuilder()
    result = builder.build(
        visible_observations=[
            "T bölgesinde hafif parlama görünümü olabilir.",
            "Egzama var gibi görünüyor.",
        ],
        care_suggestions=[
            "Nazik bir temizleyici tercih edilebilir.",
            "İlaç kullan.",
        ],
    )
    print(result)
