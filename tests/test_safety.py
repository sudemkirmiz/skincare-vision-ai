# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Sudem Kırmız
from safety.safe_response_builder import DISCLAIMER, FALLBACK_ITEM, SafeResponseBuilder, contains_blocked_term


def test_blocks_diagnosis_and_medication_terms():
    assert contains_blocked_term("Egzama var gibi görünüyor.")
    assert contains_blocked_term("İSOTRETİNOİN kullanılabilir")  # Turkish dotted capital I
    assert contains_blocked_term("Antibiyotik önerilir")
    assert contains_blocked_term("Bu bir TEŞHİS değildir ama...")


def test_allows_cosmetic_language():
    assert not contains_blocked_term("T bölgesinde hafif parlama görünümü olabilir.")
    assert not contains_blocked_term("Nazik bir temizleyici ve güneş koruyucu tercih edilebilir.")
    assert not contains_blocked_term("Akne benzeri birkaç küçük nokta görünüyor.")


def test_builder_filters_and_falls_back():
    result = SafeResponseBuilder().build(
        visible_observations=["Egzama var."],
        care_suggestions=["Nazik temizleyici kullan.", "İlaç kullan."],
    )
    assert result.visible_observations == [FALLBACK_ITEM]
    assert result.care_suggestions == ["Nazik temizleyici kullan."]
    assert result.removed_count == 2
    assert result.disclaimer == DISCLAIMER
