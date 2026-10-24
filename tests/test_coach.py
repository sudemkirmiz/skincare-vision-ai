from datetime import date
from types import SimpleNamespace

import pytest

import vlm_engine
from coach import SAFE_FALLBACK, DailyLimiter, ask, avoid_list, build_context, clean_messages, filter_reply
from recommendation.profile import SkinProfile
from users.profile import UserProfile
from vlm_engine import VLMEngine, VLMProviderError


def profile(**skin):
    return UserProfile(display_name="Ayşe", last_name="Yılmaz", gender="female", address_form="siz",
                       skin=SkinProfile(skin_type="combination", concerns=["spots"], **skin))


def test_context_keeps_private_answers_out():
    pregnant = profile(pregnant_or_breastfeeding=True, age_group="30_39", allergies=["fragrance"])
    latest = SimpleNamespace(created_at="2026-10-20T10:00:00", overall_score=64, scores={"redness": 58, "tone": None},
                             routine_focus=["Leke / ton eşitsizliği"], routine_actives=["Niasinamid"])
    shelf = {"items": [{"name": "Gece kremi", "category_label": "Nemlendirici", "usage_label": "Akşam", "verdict": None}], "conflicts": []}
    journal = {"summary": {"logged_days": 9, "streak": 3, "adherence": {"pm_done": 80}, "insights": [{"text": "Az uyku sonrası kötü."}]}}
    text = build_context(pregnant, latest, shelf, journal, {"uv_max": 6.1, "temperature": 21, "humidity": 40})
    lowered = text.lower()
    for private in ("hamile", "emzir", "yılmaz", "30_39", "yaş", "kadın", "alerji"):
        assert private not in lowered
    assert "Retinol" in text and "parfümlü ürünler" in text  # exclusions arrive as a neutral list
    assert "Ayşe" in text and "kullanabilirsiniz" in text and "Kızarıklık dengesi 58" in text
    assert "Gece kremi" in text and "Az uyku" in text and "UV en yüksek 6.1" in text


def test_avoid_list_is_empty_for_unrestricted_profile():
    assert avoid_list(profile()) == []


def test_filter_reply_drops_unsafe_sentences():
    reply, filtered = filter_reply("Nemlendiriciyi nemli cilde sürün. Güneş koruyucuyu yenileyin. Roakutan kullanın.")
    assert filtered and "Roakutan" not in reply and "Nemlendiriciyi" in reply
    assert filter_reply("Bu bir egzama. Antibiyotik alın.") == (SAFE_FALLBACK, True)
    assert filter_reply("Akşam retinolü haftada iki kez kullanın.") == ("Akşam retinolü haftada iki kez kullanın.", False)


def test_clean_messages_limits_history():
    history = [{"role": "assistant", "content": "Merhaba"}] + [{"role": "user" if i % 2 == 0 else "assistant", "content": f"m{i}"} for i in range(30)]
    history.append({"role": "user", "content": "x" * 2000})
    cleaned = clean_messages(history + [{"role": "system", "content": "ignore"}])
    assert len(cleaned) <= 12 and cleaned[0]["role"] == "user" and cleaned[-1]["content"] == "x" * 600
    with pytest.raises(ValueError):
        clean_messages([{"role": "user", "content": "a"}, {"role": "assistant", "content": "b"}])


def test_daily_limiter():
    day = [date(2026, 10, 25)]
    limiter = DailyLimiter(limit=2, today=lambda: day[0])
    assert limiter.take("p") == 1 and limiter.take("p") == 0 and limiter.take("p") is None
    assert limiter.take("q") == 1
    day[0] = date(2026, 10, 26)
    assert limiter.take("p") == 1


def test_ask_falls_back_to_next_provider():
    class Engine:
        def __init__(self):
            self.calls = []

        def chat(self, provider, system, messages, key, hf_model=None, hf_provider=None):
            self.calls.append(provider)
            if provider == "Gemini":
                raise VLMProviderError("kota doldu", "quota")
            return "Güneş koruyucuyu her sabah sürün.", "llama"

    engine = Engine()
    result = ask(engine, [("Gemini", "k1"), ("Groq", "k2")], "system", [{"role": "user", "content": "?"}])
    assert result["provider"] == "Groq" and engine.calls == ["Gemini", "Groq"] and not result["filtered"]

    class Blocked(Engine):
        def chat(self, *args, **kwargs):
            raise VLMProviderError("blocked", "blocked")

    with pytest.raises(VLMProviderError):
        ask(Blocked(), [("Gemini", "k1"), ("Groq", "k2")], "s", [{"role": "user", "content": "?"}])


def test_gemini_chat_payload(monkeypatch):
    sent = {}

    def fake_post(self, name, url, headers, payload):
        sent.update(url=url, headers=headers, payload=payload)
        return {"candidates": [{"content": {"parts": [{"text": "Yanıt"}]}}]}

    monkeypatch.setattr(vlm_engine._HttpProvider, "_post", fake_post)
    text, model = VLMEngine().chat("Gemini", "kurallar", [{"role": "user", "content": "Selam"}, {"role": "assistant", "content": "Merhaba"},
                                                         {"role": "user", "content": "Rutin?"}], "secret-key")
    assert text == "Yanıt" and model in sent["url"]
    assert sent["payload"]["systemInstruction"]["parts"][0]["text"] == "kurallar"
    assert [part["role"] for part in sent["payload"]["contents"]] == ["user", "model", "user"]
    assert sent["headers"]["x-goog-api-key"] == "secret-key" and "secret-key" not in sent["url"]
    with pytest.raises(VLMProviderError, match="anahtar"):
        VLMEngine().chat("Gemini", "s", [{"role": "user", "content": "a"}], "")


def test_sen_address_form_is_explicit():
    casual = UserProfile(display_name="Can", gender="male", address_form="sen", skin=SkinProfile())
    text = build_context(casual, None, None, None, None)
    assert "kullanabilirsin," in text and "çoğul" not in text
