# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Sudem Kırmız
"""Skin coach: a short, cosmetic-only conversation grounded in the user's own data.

Privacy follows the analysis rules: the model gets the display name and address form, skin type,
sensitivity and goals, the routine, shelf product names and journal patterns. It never gets the
surname, age, gender, pregnancy or allergy answers; those only shape a neutral "do not suggest"
list of ingredients. Replies pass the same safety filter as analysis comments, sentence by sentence.
"""
from __future__ import annotations

import re
import threading
from datetime import date
from typing import Any

from analysis.skin_metrics import SCORE_LABELS
from recommendation.engine import exclusion_reason
from recommendation.ingredients import INGREDIENTS
from recommendation.profile import CONCERNS, SENSITIVITY, SKIN_TYPES
from safety.safe_response_builder import contains_blocked_term
from users.profile import UserProfile
from vlm.engine import VLMEngine, VLMProviderError

MAX_MESSAGE_CHARS = 600
MAX_HISTORY = 12
DAILY_LIMIT = 40
FALLBACK_KINDS = {"quota", "server", "network", "auth", "credits", "config"}
SAFE_FALLBACK = (
    "Bu konu tıbbi bir değerlendirme gerektirebilir; en doğru yanıtı bir dermatolog verir. "
    "İsterseniz rutininiz, ürünleriniz veya günlük bakım alışkanlıklarınız hakkında yardımcı olabilirim."
)
SUGGESTIONS = [
    "Rutinime yeni bir aktif nasıl eklerim?",
    "Rafımdaki ürünleri birlikte kullanabilir miyim?",
    "Bugünkü havaya göre neye dikkat etmeliyim?",
    "Günlüğüme göre cildimi en çok ne etkiliyor?",
]

SYSTEM_RULES = """Sen SkinCare Vision AI uygulamasının cilt bakım koçusun. Türkçe, sıcak ve kısa yanıt ver.
Kurallar:
- Yalnızca kozmetik cilt bakımı, rutin, ürün içerikleri, güneş koruma ve günlük alışkanlıklar hakkında konuş. Başka konularda kibarca bu alana dön.
- Tanı koyma, hastalık adı verme, reçeteli ilaç veya doz önerme. Ağrı, kanama, hızla büyüyen/şekil değiştiren ben, yaygın döküntü, yanık veya enfeksiyon belirtisi anlatılırsa yalnızca dermatoloğa başvurmasını öner.
- "Önermeyeceğin içerikler" listesindekileri asla önerme; sorulursa bu kullanıcı için uygun görünmediğini ve dermatoloğa danışmasını söyle, nedenini tahmin etme.
- Marka uydurma; içerik ve ürün tipi üzerinden konuş. Kullanıcının rafındaki ürünlere adlarıyla atıf yapabilirsin.
- Fotoğraf göremezsin; yalnızca aşağıdaki verilere dayan. Veri yoksa genel ve temkinli konuş.
- Yanıt en fazla 6 cümle veya 5 maddelik kısa bir liste olsun. Gerekirse bir takip sorusu sor.
- Kullanıcının adı {name}. {address_rule} Tüm cümlelerde tutarlı ol."""
ADDRESS_RULES = {
    "siz": 'Kullanıcıya "siz" diye hitap et: ikinci çoğul şahıs kullan (cildiniz, kullanabilirsiniz, sürün); asla "sen"li konuşma.',
    "sen": 'Kullanıcıya "sen" diye hitap et: ikinci tekil şahıs kullan (cildin, kullanabilirsin, sür).',
}


def _address(profile: UserProfile) -> str:
    return "sen" if profile.address_form == "sen" else "siz"


def avoid_list(profile: UserProfile) -> list[str]:
    """Ingredient names this profile should not be offered; reasons are deliberately left out."""
    names = [item.name for item in INGREDIENTS.values() if exclusion_reason(item, profile.skin)]
    if "fragrance" in profile.skin.allergies:
        names.append("parfümlü ürünler")
    if "essential_oils" in profile.skin.allergies:
        names.append("uçucu yağ içeren ürünler")
    return names


def build_context(profile: UserProfile, latest: Any | None, shelf: dict[str, Any] | None, journal: dict[str, Any] | None,
                  weather: dict[str, Any] | None) -> str:
    skin = profile.skin
    lines = [SYSTEM_RULES.format(address_rule=ADDRESS_RULES[_address(profile)], name=profile.display_name or "kullanıcı"), "", "Kullanıcı verileri:"]
    lines.append(f"- Cilt tipi: {SKIN_TYPES.get(skin.skin_type, skin.skin_type)}; hassasiyet: {SENSITIVITY.get(skin.sensitivity, skin.sensitivity)}")
    if skin.concerns:
        lines.append(f"- Hedefler: {', '.join(CONCERNS.get(c, c) for c in skin.concerns)}")
    avoid = avoid_list(profile)
    lines.append(f"- Önermeyeceğin içerikler: {', '.join(avoid) if avoid else 'yok'}")
    if latest is not None:
        scores = ", ".join(f"{SCORE_LABELS.get(key, key)} {value}" for key, value in (latest.scores or {}).items() if value is not None)
        lines.append(f"- Son analiz ({latest.created_at[:10]}): Cilt Skoru {latest.overall_score}/100; alt skorlar: {scores or '—'}")
        if latest.routine_focus:
            lines.append(f"- Bakım odağı: {', '.join(latest.routine_focus)}")
        if latest.routine_actives:
            lines.append(f"- Rutindeki aktifler: {', '.join(latest.routine_actives)}")
    if shelf and shelf.get("items"):
        products = []
        for item in shelf["items"][:15]:
            verdict = item["verdict"]["verdict_label"] if item.get("verdict") else "içerik girilmedi"
            products.append(f"{item['name']} ({item['category_label']}, {item['usage_label']}, {verdict})")
        lines.append(f"- Rafındaki ürünler: {'; '.join(products)}")
        for warning in (shelf.get("conflicts") or [])[:3]:
            lines.append(f"- Raf uyarısı: {warning}")
    if journal:
        summary = journal.get("summary") or {}
        adherence = summary.get("adherence") or {}
        lines.append(f"- Günlük: {summary.get('logged_days', 0)} gün kayıt, seri {summary.get('streak', 0)} gün, "
                     f"akşam rutini uyumu {adherence.get('pm_done') if adherence.get('pm_done') is not None else '—'}%")
        for insight in (summary.get("insights") or [])[:4]:
            lines.append(f"- Günlük bulgusu: {insight['text']}")
    if weather:
        lines.append(f"- Bugün hava: UV en yüksek {weather.get('uv_max')}, sıcaklık {weather.get('temperature')}°C, nem %{weather.get('humidity')}")
    lines.append(f"- Bugünün tarihi: {date.today().isoformat()}")
    return "\n".join(lines)


_SENTENCE = re.compile(r"(?<=[.!?…])\s+|\n+")


def filter_reply(text: str) -> tuple[str, bool]:
    """Drop sentences with blocked terms; if most of the answer is unsafe, use a safe fallback."""
    parts = [part.strip() for part in _SENTENCE.split(text.strip()) if part.strip()]
    kept = [part for part in parts if not contains_blocked_term(part)]
    if not parts or len(kept) < len(parts) / 2:
        return SAFE_FALLBACK, True
    return "\n".join(kept)[:2500], len(kept) != len(parts)


def clean_messages(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    """Last turns only, user/assistant roles only, ending with the user's question."""
    cleaned = [{"role": m["role"], "content": m["content"].strip()[:MAX_MESSAGE_CHARS]}
               for m in messages if m.get("role") in {"user", "assistant"} and (m.get("content") or "").strip()]
    cleaned = cleaned[-MAX_HISTORY:]
    while cleaned and cleaned[0]["role"] != "user":
        cleaned.pop(0)
    if not cleaned or cleaned[-1]["role"] != "user":
        raise ValueError("Son mesaj kullanıcıdan gelmeli.")
    return cleaned


class DailyLimiter:
    def __init__(self, limit: int = DAILY_LIMIT, today=date.today) -> None:
        self.limit, self._today = limit, today
        self._counts: dict[tuple[str, str], int] = {}
        self._lock = threading.Lock()

    def take(self, key: str) -> int | None:
        """Remaining messages after this one, or None when the limit is reached."""
        day = self._today().isoformat()
        with self._lock:
            self._counts = {k: v for k, v in self._counts.items() if k[1] == day}
            used = self._counts.get((key, day), 0)
            if used >= self.limit:
                return None
            self._counts[(key, day)] = used + 1
            return self.limit - used - 1


def ask(engine: VLMEngine, chain: list[tuple[str, str]], system: str, messages: list[dict[str, str]],
        hf_model: str | None = None, hf_provider: str | None = None) -> dict[str, Any]:
    """Try providers in order; returns the filtered reply and which provider answered."""
    errors = []
    for provider, key in chain:
        try:
            text, model = engine.chat(provider, system, messages, key, hf_model, hf_provider)
        except VLMProviderError as error:
            errors.append(f"{provider}: {error}")
            if error.kind in FALLBACK_KINDS:
                continue
            break
        reply, filtered = filter_reply(text)
        return {"reply": reply, "provider": provider, "model": model, "filtered": filtered}
    raise VLMProviderError("Cilt koçu şu an yanıt veremiyor.\n" + "\n".join(errors[:3]), "unknown")
