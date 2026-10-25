# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Sudem Kırmız
"""Care comment without any AI provider: built only from the measured metrics, regions, profile and history.

Used when there is no API key, the comment is turned off, or every provider failed, so an analysis never
ends with an empty comment. Every sentence is traceable to a number on the screen and uses cosmetic wording
("görünüm") in the formal address used by all fixed texts.

Wording varies by severity and between equivalent phrasings; the choice is seeded by the measurements, so the
same analysis always reads the same while different faces do not read alike.
"""
from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any

# Same bands as the score status labels: <35 Öncelikli, <55 Dikkat, <75 Orta, ≥75 İyi.
PRIORITY, WATCH, GOOD = 35, 55, 75
MAX_OBSERVATIONS, MAX_SUGGESTIONS = 4, 5
CHANGE_GAP = 4  # score points before a change since the last saved analysis is worth a sentence
REGION_METRICS = ("redness", "tone", "shine")

# {region} is filled with ", en çok … bölgesinde" when one region clearly stands out.
OBSERVATIONS: dict[str, dict[str, tuple[str, ...]]] = {
    "spots": {
        "strong": ("{where} belirgin ve yaygın nokta görünümü var: fotoğrafta {total} nokta işaretlendi{zone}.",
                   "Nokta görünümü yoğun: {where_lower} başta olmak üzere {total} nokta işaretlendi{zone}."),
        "medium": ("{where} dikkat çeken nokta görünümü var: {total} nokta işaretlendi{zone}.",
                   "{total} nokta işaretlendi; en çok {where_lower} öne çıkıyor{zone}."),
        "mild": ("Birkaç dağınık nokta görünümü var ({total} nokta); genel tablo hafif.",),
    },
    "redness": {
        "strong": ("Kızarıklık görünümü belirgin{region}; cilt bariyerinin hassaslaştığına işaret edebilir.",
                   "Belirgin bir kızarıklık görünümü var{region}."),
        "medium": ("Kızarıklık görünümü dikkat çekiyor{region}.", "Orta düzeyde kızarıklık görünümü var{region}."),
        "mild": ("Hafif bir kızarıklık görünümü var{region}.",),
    },
    "tone": {
        "strong": ("Ton eşitsizliği ve leke görünümü belirgin{region}.", "Cilt tonunda belirgin farklılıklar ve leke görünümü var{region}."),
        "medium": ("Ton eşitsizliği ve leke görünümü öne çıkıyor{region}.", "Cilt tonunda dikkat çeken dalgalanmalar var{region}."),
        "mild": ("Cilt tonunda hafif dalgalanmalar var{region}.",),
    },
    "shine": {
        "strong": ("Parlama görünümü belirgin{region}; yağlanma bu bölgede yoğunlaşıyor olabilir.",
                   "Yoğun bir parlama görünümü var{region}."),
        "medium": ("Parlama görünümü dikkat çekiyor{region}.", "Orta düzeyde parlama görünümü var{region}."),
        "mild": ("Hafif bir parlama görünümü var{region}.",),
    },
    "texture": {
        "strong": ("Doku pürüzlülüğü ve gözenek görünümü belirgin.", "Gözenek ve doku görünümü belirgin şekilde pürüzlü."),
        "medium": ("Doku pürüzlülüğü ve gözenek görünümü fark ediliyor.", "Gözenek görünümü ve doku pürüzlülüğü dikkat çekiyor."),
        "mild": ("Doku genel olarak düzgün; yer yer hafif pürüzlülük var.",),
    },
}
SUGGESTIONS: dict[str, tuple[str, ...]] = {
    "spots": ("Noktaları sıkmadan ve sert ovmadan kaçının; nazik temizleme ve düzenli rutinle görünüm genellikle 6-8 haftada dengelenir.",
              "Yastık kılıfını sık değiştirmek ve yüze dokunmamak rutininizi destekler; düzenli kullanımda 6-8 hafta içinde fark görülür."),
    "redness": ("Parfümsüz, yatıştırıcı ürünler seçin ve aynı anda çok sayıda aktif denemeyin; sıcak su ve sert peelingler kızarıklığı artırabilir.",
                "Yeni ürünleri birer birer ve önce küçük bir alanda deneyin; cildiniz sakinleşene kadar rutini sade tutun."),
    "tone": ("Her sabah geniş spektrumlu SPF 50 kullanın ve dışarıdaysanız 2 saatte bir yenileyin; leke görünümünün koyulaşmasını en çok güneş koruması önler.",
             "Ton eşitsizliğinde en etkili adım her gün SPF 50'dir; leke görünümündeki iyileşme genellikle 8-12 haftada belirginleşir."),
    "shine": ("Hafif, yağsız bir nemlendirici kullanın; nemlendiriciyi atlamak parlamayı artırabilir.",
              "Gün içindeki parlama için kâğıt mendil yeterlidir; sık yıkamak cildi kurutup daha fazla yağlanmaya yol açabilir."),
    "texture": ("Haftada 1-2 akşam nazik bir peeling, ilk haftalarda seyrek kullanılarak dokuyu düzleştirmeye yardımcı olabilir.",
                "Düzenli nemlendirme ve haftada 1-2 akşam nazik peeling, doku görünümünü 4-6 haftada iyileştirebilir."),
}
COMBINED = {
    frozenset({"shine", "spots"}): "Parlama ve nokta görünümü birlikte öne çıkıyor; yağ dengesini hedefleyen hafif ürünler ikisine de yardımcı olur.",
    frozenset({"redness", "spots"}): "Nokta ve kızarıklık birlikte görünüyor; sert ürünler yerine yatıştırıcı ve nazik bir rutin daha uygun olur.",
    frozenset({"tone", "spots"}): "Noktalar iz bırakıp tonu etkileyebilir; nokta görünümüyle birlikte güneş korumasına da öncelik verin.",
}
# Profile goals (recommendation.profile.CONCERNS) and the score that measures them.
CONCERN_METRIC = {"spots": "spots", "redness": "redness", "tone": "tone", "shine": "shine", "texture": "texture"}
LABELS = {"spots": "nokta yoğunluğu", "redness": "kızarıklık dengesi", "tone": "ton eşitliği", "shine": "parlama kontrolü", "texture": "doku pürüzsüzlüğü"}


def _tier(score: float) -> str:
    return "strong" if score < PRIORITY else "medium" if score < WATCH else "mild"


def _pick(options: tuple[str, ...], seed: str) -> str:
    return options[int(hashlib.sha256(seed.encode("utf-8")).hexdigest(), 16) % len(options)]


def _capital(text: str) -> str:
    return text[:1].upper() + text[1:]


def _worst_region(region_metrics: dict[str, dict[str, Any]], metric: str) -> str | None:
    """The region that clearly stands out for a metric (low, and at least 10 points below the face average)."""
    scored = [(values[metric], values["name"]) for values in region_metrics.values()
              if isinstance(values.get(metric), (int, float)) and values.get("name")]
    if len(scored) < 2:
        return None
    value, name = min(scored)
    average = sum(score for score, _ in scored) / len(scored)
    return name if value < WATCH and average - value >= 10 else None


def _zone(region_summary: dict[str, Any] | None) -> str:
    zones = (region_summary or {}).get("zones") or {}
    t_zone, u_zone = (zones.get("t_zone") or {}).get("density"), (zones.get("u_zone") or {}).get("density")
    if not isinstance(t_zone, (int, float)) or not isinstance(u_zone, (int, float)) or max(t_zone, u_zone) == 0:
        return ""
    if t_zone >= 1.3 * u_zone:
        return ", çoğu T-bölgesinde (alın ve burun)"
    if u_zone >= 1.3 * t_zone:
        return ", çoğu U-bölgesinde (yanaklar ve çene)"
    return ""


def _observation(key: str, score: float, skin_metrics: dict[str, Any], region_summary: dict[str, Any] | None, seed: str) -> str:
    template = _pick(OBSERVATIONS[key][_tier(score)], f"{seed}:{key}")
    if key == "spots":
        where = (region_summary or {}).get("most_affected_name")
        total = (skin_metrics.get("spot_counts") or {}).get("total")
        return _capital(template.format(
            where=f"{where} bölgenizde" if where else "Yüzünüzde", where_lower=f"{where.lower()} bölgeniz" if where else "yüzünüz",
            total=total if total is not None else "birkaç", zone=_zone(region_summary),
        ))
    region = _worst_region(skin_metrics.get("regions") or {}, key) if key in REGION_METRICS else None
    # The measured value ties the sentence to the score on screen and keeps similar faces from reading alike.
    detail = f" ({round(score)}/100)" + (f", en çok {region.lower()} bölgesinde" if region else "")
    if "{region}" in template:
        return _capital(template.format(region=detail))
    return _capital(template[:-1] + detail + ".")


def _progress(scores: dict[str, float], overall: Any, previous: dict[str, Any] | None) -> str | None:
    """One sentence on what changed since the last saved analysis."""
    if not previous or not isinstance(overall, (int, float)) or not isinstance(previous.get("overall_score"), (int, float)):
        return None
    try:
        when = datetime.fromisoformat(str(previous.get("created_at"))).strftime("%d.%m") + " tarihli "
    except ValueError:
        when = ""
    delta = round(overall - previous["overall_score"])
    old = previous.get("scores") or {}
    changes = sorted((scores[key] - old[key], key) for key in scores if isinstance(old.get(key), (int, float)))
    best = changes[-1] if changes and changes[-1][0] >= CHANGE_GAP else None
    worst = changes[0] if changes and changes[0][0] <= -CHANGE_GAP else None
    if abs(delta) < CHANGE_GAP and not best and not worst:
        return f"{_capital(when)}önceki analizinize göre tablo benzer; Cilt Skorunuz {round(overall)} ile korunuyor."
    parts = [f"{_capital(when)}önceki analizinize göre Cilt Skorunuz {'+' if delta > 0 else ''}{delta} puan değişti"]
    if best:
        parts.append(f"en çok {LABELS[best[1]]} iyileşti (+{round(best[0])})")
    if worst:
        parts.append(f"{LABELS[worst[1]]} geriledi ({round(worst[0])})")
    return ", ".join(parts) + "."


def build_local_comment(
    skin_metrics: dict[str, Any] | None,
    region_summary: dict[str, Any] | None,
    routine: dict[str, Any] | None,
    personalization: dict[str, str] | None = None,
    image_quality: dict[str, Any] | None = None,
    concerns: list[str] | None = None,
    previous: dict[str, Any] | None = None,
) -> dict[str, list[str]] | None:
    """Observations and suggestions in the same shape as the AI comment, or None when nothing was measured."""
    if not skin_metrics or not skin_metrics.get("available"):
        return None
    scores = {key: float(value) for key, value in (skin_metrics.get("scores") or {}).items() if isinstance(value, (int, float)) and key in OBSERVATIONS}
    seed = "|".join(f"{key}{round(value)}" for key, value in sorted(scores.items()))
    name = (personalization or {}).get("hitap_adi", "").strip()

    ranked = sorted((score, key) for key, score in scores.items())
    weak = [(score, key) for score, key in ranked if score < WATCH]
    mild = [(score, key) for score, key in ranked if WATCH <= score < GOOD]
    # With fewer than two clear findings, mild ones are worth a sentence too.
    focus = weak[:3] if len(weak) >= 2 else (weak + mild)[:2]
    weak_keys = {key for _, key in weak[:3]}

    observations = [_observation(key, score, skin_metrics, region_summary, seed) for score, key in focus]
    pair = next((text for combo, text in COMBINED.items() if combo <= weak_keys), None)
    if pair:
        observations.append(pair)
    if not observations:
        observations.append("Ölçülen değerlerin tamamı iyi aralıkta; belirgin bir sorun görünümü öne çıkmıyor.")
    strong = [LABELS[key] for score, key in sorted(ranked, reverse=True) if score >= GOOD]
    if strong:
        observations.append(f"Güçlü yanlarınız: {', '.join(strong[:3])}.")
    for concern in concerns or []:
        metric = CONCERN_METRIC.get(concern)
        if metric and scores.get(metric, 0) >= GOOD:
            observations.append(f"Hedeflerinizdeki {LABELS[metric]} için iyi haber: bu fotoğrafta ölçülen değer iyi aralıkta ({round(scores[metric])}/100).")
            break
    progress = _progress(scores, skin_metrics.get("overall_score"), previous)
    if progress:
        observations.insert(0, progress)
    if name:
        observations[0] = f"{name}, {observations[0][:1].lower()}{observations[0][1:]}"

    targets = weak[:3] or mild[:1]
    suggestions = [_pick(SUGGESTIONS[key], f"{seed}:s:{key}") for _, key in targets]
    for active in (routine or {}).get("actives", [])[:2]:
        strength = (active.get("strength") or active.get("form") or "").replace(" (", ", ").replace(")", "")
        frequency = (active.get("frequency") or "").rstrip(".")
        suggestions.append(f"Rutininizdeki {active['name']}" + (f" ({strength})" if strength else "") + " bu bulgulara göre seçildi"
                           + (f"; kullanım: {frequency[:1].lower()}{frequency[1:]}." if frequency else "."))
    if "tone" not in weak_keys:
        suggestions.append("Gündüz rutininizi SPF 50 güneş koruyucuyla bitirin; tüm aktiflerin etkisini korur.")
    if any(score < PRIORITY for score, key in weak if key in {"spots", "redness"}):
        suggestions.append("Görünüm belirgin ve yaygın olduğu için bir dermatoloğa danışmak en doğru başlangıç olur; bu rutin destekleyicidir.")
    if (image_quality or {}).get("status") not in (None, "ok"):
        note = str((image_quality or {}).get("notes") or "").strip().rstrip(".")
        suggestions.append((f"{note}. " if note else "") + "Daha isabetli ölçüm için gün ışığında, makyajsız ve önden yeni bir fotoğraf çekebilirsiniz.")
    elif not previous:
        suggestions.append("Sonucu geçmişe kaydedip 2-4 hafta sonra benzer ışıkta tekrar analiz ederseniz, değişimi burada puan puan görebilirsiniz.")
    # Priority order (findings, routine, safety, photo) survives the cap; the dermatologist note is never cut.
    derm = [line for line in suggestions if "dermatoloğa" in line]
    ordered = list(dict.fromkeys(suggestions))
    capped = ordered[:MAX_SUGGESTIONS]
    if derm and derm[0] not in capped:
        capped[-1] = derm[0]
    return {"visible_observations": observations[:MAX_OBSERVATIONS], "care_suggestions": capped}
