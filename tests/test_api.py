# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Sudem Kırmız
import dataclasses
import os
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from api.container import AnalysisCache, Container
from api.server import create_app
from config import get_settings

SAMPLES = Path(__file__).resolve().parents[1] / "samples"
PROFILE = {
    "display_name": "Ayşe", "last_name": "Yılmaz", "gender": "female", "consent": True, "address_form": "siz",
    "answered": ["last_name", "concerns"],
    "skin": {"skin_type": "combination", "sensitivity": "sometimes", "age_group": "18_29", "pregnancy": "no", "concerns": ["spots"]},
}


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    settings = dataclasses.replace(get_settings(), history_db_path=tmp_path_factory.mktemp("db") / "history.db", vlm_second_opinion=False)
    container = Container(settings)
    with TestClient(create_app(settings, container)) as test_client:
        yield test_client


@pytest.fixture(scope="module")
def profile(client):
    response = client.post("/api/profiles", json=PROFILE)
    assert response.status_code == 201, response.text
    return response.json()


def sample(name: str) -> bytes:
    path = SAMPLES / name
    if not path.exists():
        pytest.skip("sample photos are local-only")
    return path.read_bytes()


@pytest.fixture(scope="module")
def analysis(client, profile):
    files = [("files", ("yuz.png", sample("01_frontal_lying.png"), "image/png"))]
    response = client.post("/api/analyses", files=files, data={"profile_id": profile["id"], "use_vlm": "false", "second_opinion": "false"})
    assert response.status_code == 200, response.text
    return response.json()


def test_health_and_options_never_expose_keys(client):
    health = client.get("/api/health").json()
    assert health["status"] == "ok" and health["ready"] is True
    assert set(health) == {"status", "version", "ready"}
    status = client.get("/api/status").json()
    assert set(status["providers"]) == {"Gemini", "OpenAI", "Hugging Face", "Groq"}
    body = client.get("/api/health").text + client.get("/api/status").text + client.get("/api/options").text
    for name in ("GEMINI_API_KEY", "OPENAI_API_KEY", "GROQ_API_KEY", "HF_TOKEN"):
        value = os.getenv(name, "")
        if value:
            assert value not in body
    options = client.get("/api/options").json()
    assert options["skin_types"]["combination"].startswith("Karma") and "T-bölgesi" in options["skin_type_help"]
    assert options["quiz"]["t_zone"]["options"]["oily"]
    assert options["hf_models"] and all(isinstance(model, str) for model in options["hf_models"])


def test_quiz_endpoint(client):
    assert client.post("/api/quiz/skin-type", json={"t_zone": "oily", "cheeks": "normal", "blotting": "sometimes"}).json()["skin_type"] == "combination"
    assert client.post("/api/quiz/skin-type", json={"t_zone": "oily"}).json()["skin_type"] is None


def test_profile_validation_and_crud(client, profile):
    errors = client.post("/api/profiles", json={"display_name": "A"}).json()["detail"]["errors"]
    assert len(errors) == 6
    assert client.post("/api/profiles", json={**PROFILE, "unexpected": "field"}).status_code == 422
    male = client.post("/api/profiles", json={**PROFILE, "display_name": "Can", "gender": "male", "skin": {**PROFILE["skin"], "pregnancy": None}})
    assert male.status_code == 201 and male.json()["skin"]["pregnancy"] == "no"
    assert {p["display_name"] for p in client.get("/api/profiles").json()} >= {"Ayşe", "Can"}
    updated = client.put(f"/api/profiles/{profile['id']}", json={**PROFILE, "address_form": "sen"}).json()
    assert updated["address_form"] == "sen" and updated["consent_at"] == profile["consent_at"]
    client.put(f"/api/profiles/{profile['id']}", json=PROFILE)
    assert client.post(f"/api/profiles/{profile['id']}/touch").status_code == 204
    assert client.get("/api/profiles/nope").status_code == 404
    assert client.delete(f"/api/profiles/{male.json()['id']}").status_code == 204


def test_upload_validation(client, profile):
    bad_model = client.post("/api/analyses", data={"profile_id": profile["id"], "provider": "Hugging Face", "hf_model": "evil/model", "use_vlm": "false"},
                            files={"files": ("a.png", b"x", "image/png")})
    assert bad_model.status_code == 422 and "Hugging Face" in bad_model.json()["detail"]
    bad = [("files", ("x.png", b"not an image", "image/png"))]
    assert client.post("/api/analyses", files=bad, data={"profile_id": profile["id"]}).status_code == 422
    buffer = BytesIO()
    Image.new("RGB", (20, 20)).save(buffer, format="PNG")
    four = [("files", (f"{i}.png", buffer.getvalue(), "image/png")) for i in range(4)]
    assert client.post("/api/analyses", files=four, data={"profile_id": profile["id"]}).status_code == 422
    ok_file = [("files", ("a.png", buffer.getvalue(), "image/png"))]
    assert client.post("/api/analyses", files=ok_file, data={"profile_id": profile["id"], "provider": "Evil"}).status_code == 422


def test_analysis_payload_and_derived_endpoints(client, profile, analysis):
    assert analysis["face_found"] and analysis["skin_metrics"]["available"]
    assert analysis["routine"]["am"][-1]["step"] == "Güneş koruma"
    analysis_id, pid = analysis["analysis_id"], profile["id"]
    assert client.get(f"/api/analyses/{analysis_id}/routine", params={"profile_id": pid}).json()["am"]
    products = client.get(f"/api/analyses/{analysis_id}/products", params={"profile_id": pid}).json()
    assert products["sections"][0]["search_links"][0]["icon"] == "trendyol.png"
    pdf = client.get(f"/api/analyses/{analysis_id}/report.pdf", params={"profile_id": pid})
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    assert 'filename="Cilt_Raporu_Ayse_Yilmaz_' in pdf.headers["content-disposition"]
    assert client.get(f"/api/analyses/{analysis_id}/report.txt", params={"profile_id": pid}).text.startswith("SkinCare Vision AI")
    assert client.get(f"/api/analyses/{analysis_id}/report.exe", params={"profile_id": pid}).status_code == 404


def test_other_profile_cannot_read_analysis(client, analysis):
    other = client.post("/api/profiles", json={**PROFILE, "display_name": "Zeynep"}).json()
    assert client.get(f"/api/analyses/{analysis['analysis_id']}/routine", params={"profile_id": other["id"]}).status_code == 404


def test_save_history_compare_events_export(client, profile, analysis):
    pid = profile["id"]
    assert client.post(f"/api/analyses/{analysis['analysis_id']}/save", json={"profile_id": pid, "note": "ilk"}).json()["saved"]
    second = client.post("/api/analyses", files=[("files", ("b.png", sample("03_studio_frontal.png"), "image/png"))],
                         data={"profile_id": pid, "use_vlm": "false", "second_opinion": "false"}).json()
    client.post(f"/api/analyses/{second['analysis_id']}/save", json={"profile_id": pid, "keep_thumbnail": False})
    history = client.get(f"/api/profiles/{pid}/history").json()
    assert len(history["records"]) == 2 and history["trend"]
    first = next(r for r in history["records"] if r["id"] == analysis["analysis_id"])
    assert first["thumbnail_url"] and client.get(first["thumbnail_url"]).headers["content-type"] == "image/jpeg"
    comparison = client.get(f"/api/profiles/{pid}/compare", params={"before": first["id"], "after": second["analysis_id"]}).json()
    assert comparison["summary"]
    no_thumbnail = client.get(f"/api/profiles/{pid}/compare/map", params={"before": first["id"], "after": second["analysis_id"]})
    assert no_thumbnail.status_code == 422 and "önizlemesi" in no_thumbnail.json()["detail"]
    assert client.get(f"/api/profiles/{pid}/compare/map", params={"before": first["id"], "after": first["id"]}).status_code == 404
    event_id = client.post(f"/api/profiles/{pid}/events", json={"kind": "routine_start", "note": "azelaik"}).json()["id"]
    assert client.post(f"/api/profiles/{pid}/events", json={"kind": "hack"}).status_code == 422
    assert client.get(f"/api/profiles/{pid}/history").json()["events"][0]["note"] == "azelaik"
    assert client.delete(f"/api/events/{event_id}").status_code == 204
    csv = client.get(f"/api/profiles/{pid}/history/export.csv")
    assert csv.text.startswith("tarih,genel_skor") and "Cilt_Gecmisi_Ayse_Yilmaz" in csv.headers["content-disposition"]
    assert client.delete(f"/api/profiles/{pid}/history").json()["deleted"] == 2


def test_product_check(client, profile):
    verdict = client.post("/api/products/check", json={"profile_id": profile["id"], "inci_text": "Aqua, Retinol, Parfum, Linalool"}).json()
    assert verdict["verdict"] in {"caution", "avoid"} and "Retinol" in verdict["detected_actives"]
    assert client.post("/api/products/check", json={"profile_id": profile["id"], "inci_text": "x"}).status_code == 422


def test_analysis_cache_ttl_and_owner():
    now = [0.0]
    cache = AnalysisCache(ttl=10, max_items=2, clock=lambda: now[0])
    cache.put("p1", {"analysis_id": "a"})
    assert cache.get("a", "p1") == {"analysis_id": "a"} and cache.get("a", "p2") is None
    now[0] = 11
    assert cache.get("a", "p1") is None


def test_optional_app_access_token(tmp_path):
    settings = dataclasses.replace(get_settings(), history_db_path=tmp_path / "auth.db", app_access_token="secret-token")
    with TestClient(create_app(settings, Container(settings))) as secured:
        assert secured.get("/api/health").status_code == 200
        assert secured.get("/api/status").status_code == 401
        assert secured.get("/api/options").status_code == 401
        assert secured.get("/api/options", headers={"Authorization": "Bearer wrong"}).status_code == 401
        assert secured.get("/api/options", headers={"Authorization": "Bearer secret-token"}).status_code == 200


def test_public_mode_fails_closed_without_safe_settings(tmp_path):
    settings = dataclasses.replace(get_settings(), history_db_path=tmp_path / "public.db", public_deployment=True, app_access_token="")
    with pytest.raises(RuntimeError, match="APP_ACCESS_TOKEN"):
        create_app(settings)
    short = dataclasses.replace(settings, app_access_token="too-short", allow_user_api_keys=False)
    with pytest.raises(RuntimeError, match="32 karakterli"):
        create_app(short)


def test_health_is_not_ready_without_required_model(tmp_path):
    settings = dataclasses.replace(
        get_settings(), history_db_path=tmp_path / "health.db", history_enabled=False, yolo_model_path=tmp_path / "missing.pt"
    )
    with TestClient(create_app(settings, Container(settings))) as unhealthy:
        response = unhealthy.get("/api/health")
        assert response.status_code == 503
        assert response.json()["status"] == "degraded"
        assert unhealthy.get("/api/status").json()["models"]["yolo"] is False


def test_request_body_limit_is_applied_before_json_parsing(tmp_path):
    settings = dataclasses.replace(get_settings(), history_db_path=tmp_path / "body.db", max_request_body_mb=2)
    with TestClient(create_app(settings, Container(settings))) as limited:
        response = limited.post("/api/profiles", content=b"x" * (2 * 1024 * 1024 + 1), headers={"Content-Type": "application/json"})
        assert response.status_code == 413
        assert response.headers["x-content-type-options"] == "nosniff"


def test_public_mode_security_headers_and_docs(tmp_path):
    settings = dataclasses.replace(
        get_settings(), history_db_path=tmp_path / "public-secure.db", public_deployment=True,
        app_access_token="a" * 32, allow_user_api_keys=False,
    )
    with TestClient(create_app(settings, Container(settings))) as public:
        health = public.get("/api/health")
        assert health.headers["x-frame-options"] == "DENY"
        assert "default-src 'self'" in health.headers["content-security-policy"]
        assert health.headers["strict-transport-security"].startswith("max-age=")
        assert public.get("/docs").status_code == 404
        assert public.get("/openapi.json").status_code == 404


def test_public_mode_rejects_wildcard_hosts(tmp_path, monkeypatch):
    monkeypatch.setenv("ALLOWED_HOSTS", "*")
    settings = dataclasses.replace(
        get_settings(), history_db_path=tmp_path / "host.db", public_deployment=True,
        app_access_token="a" * 32, allow_user_api_keys=False,
    )
    with pytest.raises(RuntimeError, match="ALLOWED_HOSTS"):
        create_app(settings)


def test_frontend_shell_and_unknown_api_route(client):
    from api.server import FRONTEND_DIST

    assert client.get("/api/does-not-exist").status_code == 404
    if not (FRONTEND_DIST / "index.html").exists():
        pytest.skip("frontend/dist is not built")
    for path in ("/", "/gecmis", "/urun-kontrolu"):
        response = client.get(path)
        assert response.status_code == 200 and "<div id=\"root\">" in response.text
    # Path traversal must not escape the dist folder.
    assert "<div id=\"root\">" in client.get("/..%2F.env").text


def test_capture_check(client):
    buffer = BytesIO()
    Image.new("RGB", (360, 480), (200, 180, 160)).save(buffer, format="JPEG")
    result = client.post("/api/capture/check", files={"frame": ("f.jpg", buffer.getvalue(), "image/jpeg")}, data={"target": "front"}).json()
    assert result["ok"] is False and result["message"]
    assert client.post("/api/capture/check", files={"frame": ("f.jpg", buffer.getvalue(), "image/jpeg")}, data={"target": "back"}).status_code == 422
    assert client.post("/api/capture/check", files={"frame": ("f.jpg", b"junk", "image/jpeg")}).status_code == 422


def test_journal_endpoints(client, profile):
    from datetime import date, timedelta

    pid, today = profile["id"], date.today()
    empty = client.get(f"/api/profiles/{pid}/journal").json()
    assert empty["entries"] == [] and empty["summary"]["needed_days"] == 7
    body = {"am_done": True, "pm_done": True, "skin_feel": 4, "triggers": ["period", "stress"], "symptoms": ["breakout"], "actives": [" Retinol "]}
    saved = client.put(f"/api/profiles/{pid}/journal/{today.isoformat()}", json=body).json()
    assert saved["entries"][-1]["actives"] == ["Retinol"] and saved["summary"]["streak"] == 1
    for bad_day in ((today + timedelta(days=1)).isoformat(), (today - timedelta(days=40)).isoformat(), "dün"):
        assert client.put(f"/api/profiles/{pid}/journal/{bad_day}", json=body).status_code == 422
    assert client.put(f"/api/profiles/{pid}/journal/{today.isoformat()}", json={"triggers": ["hack"]}).status_code == 422
    assert client.put(f"/api/profiles/{pid}/journal/{today.isoformat()}", json={"skin_feel": 9}).status_code == 422
    options = client.get("/api/options").json()["journal"]
    assert options["female_only"] == ["period"] and options["skin_feel"]["5"] == "Çok iyi"
    assert client.delete(f"/api/profiles/{pid}/journal/{today.isoformat()}").json()["entries"] == []


def test_period_trigger_is_rejected_for_male_profile(client):
    male = client.post("/api/profiles", json={**PROFILE, "display_name": "Ali", "gender": "male",
                                               "skin": {**PROFILE["skin"], "pregnancy": None}}).json()
    day = __import__("datetime").date.today().isoformat()
    response = client.put(f"/api/profiles/{male['id']}/journal/{day}", json={"triggers": ["period"]})
    assert response.status_code == 422
    client.delete(f"/api/profiles/{male['id']}")


def test_shelf_endpoints(client, profile):
    pid = profile["id"]
    body = {"name": "Gece Serumu", "category": "serum", "usage": "pm", "inci": "Aqua, Retinol", "opened_at": "2026-01-01", "pao_months": 12}
    created = client.post(f"/api/profiles/{pid}/shelf", json=body)
    assert created.status_code == 201
    shelf = created.json()
    assert shelf["items"][0]["actives"] == ["retinol"] and shelf["items"][0]["expiry"] and shelf["categories"]["sunscreen"]
    item_id = shelf["items"][0]["id"]
    updated = client.put(f"/api/profiles/{pid}/shelf/{item_id}", json={**body, "usage": "both"}).json()
    assert updated["items"][0]["usage_label"] == "Sabah ve akşam"
    assert client.put(f"/api/profiles/{pid}/shelf/nope", json=body).status_code == 404
    assert client.post(f"/api/profiles/{pid}/shelf", json={**body, "category": "hack"}).status_code == 422
    assert client.post(f"/api/profiles/{pid}/shelf", json={**body, "opened_at": "2999-01-01"}).status_code == 422
    assert client.post(f"/api/profiles/{pid}/shelf", json={**body, "pao_months": 99}).status_code == 422
    assert client.delete(f"/api/profiles/{pid}/shelf/{item_id}").json()["items"] == []


def test_weather_endpoint_uses_profile(client, profile, monkeypatch):
    import services.weather as weather

    monkeypatch.setattr(weather, "_get", lambda url, params, trust_env: {
        "current": {"temperature_2m": 20, "relative_humidity_2m": 50, "uv_index": 4},
        "daily": {"uv_index_max": [6.5], "temperature_2m_max": [22], "temperature_2m_min": [12]},
    })
    result = client.get("/api/weather", params={"lat": 39.93, "lon": 32.85, "profile_id": profile["id"]}).json()
    assert result["uv_band"]["label"] == "Yüksek" and result["tips"][0]["kind"] == "uv" and result["source"] == "Open-Meteo"
    assert client.get("/api/weather", params={"lat": 120, "lon": 0}).status_code == 422


def test_coach_endpoint(client, profile, monkeypatch):
    import vlm.engine as vlm_engine

    seen = {}

    def fake_chat(self, provider, system, messages, api_key, hf_model=None, hf_provider=None):
        seen.update(provider=provider, system=system, messages=messages, key=api_key)
        return "Akşam niasinamidi nemlendiriciden önce sürün.", "fake-model"

    monkeypatch.setattr(vlm_engine.VLMEngine, "chat", fake_chat)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    body = {"profile_id": profile["id"], "provider": "Gemini", "messages": [{"role": "user", "content": "Niasinamidi ne zaman sürmeliyim?"}],
            "weather": {"uv_max": 5, "temperature": 18, "humidity": 60}}
    result = client.post("/api/coach", json=body).json()
    assert result["reply"].startswith("Akşam") and result["provider"] == "Gemini" and result["remaining"] >= 0
    assert "Yılmaz" not in seen["system"] and "UV en yüksek 5.0" in seen["system"]
    assert client.post("/api/coach", json={**body, "provider": "Evil"}).status_code == 422
    assert client.post("/api/coach", json={**body, "messages": [{"role": "assistant", "content": "x"}]}).status_code == 422
    assert client.get("/api/coach/suggestions").json()


def test_device_scope_keeps_each_browsers_profiles_private(tmp_path):
    settings = dataclasses.replace(get_settings(), history_db_path=tmp_path / "devices.db", profile_scope="device", vlm_second_opinion=False)
    with TestClient(create_app(settings, Container(settings))) as shared:
        alice, bob = {"X-Device-Key": "a" * 40}, {"X-Device-Key": "b" * 40}
        assert shared.get("/api/options").status_code == 200  # needs no device key
        assert shared.get("/api/profiles").status_code == 400
        mine = shared.post("/api/profiles", json=PROFILE, headers=alice).json()
        shared.post(f"/api/profiles/{mine['id']}/events", json={"kind": "note", "note": "x"}, headers=alice)
        assert [p["id"] for p in shared.get("/api/profiles", headers=alice).json()] == [mine["id"]]
        assert shared.get("/api/profiles", headers=bob).json() == []
        # Another device cannot read, change or delete it, nor its records and events.
        for method, path in (("GET", f"/api/profiles/{mine['id']}"), ("GET", f"/api/profiles/{mine['id']}/history"),
                             ("DELETE", f"/api/profiles/{mine['id']}"), ("GET", f"/api/profiles/{mine['id']}/journal")):
            assert shared.request(method, path, headers=bob).status_code == 404, path
        event = shared.get(f"/api/profiles/{mine['id']}/history", headers=alice).json()["events"][0]
        assert shared.delete(f"/api/events/{event['id']}", headers=bob).status_code == 404
        # The cookie works like the header (images and downloads cannot send headers).
        shared.cookies.set("scv_device", "a" * 40)
        assert shared.get(f"/api/profiles/{mine['id']}").status_code == 200
        # Writes need the header: a cookie alone (as a cross-site request would carry) is not enough.
        assert shared.delete(f"/api/events/{event['id']}").status_code == 400
        assert shared.delete(f"/api/events/{event['id']}", headers=alice).status_code == 204


def test_access_token_cookie_for_images_and_downloads(tmp_path):
    settings = dataclasses.replace(get_settings(), history_db_path=tmp_path / "cookie.db", app_access_token="secret-token")
    with TestClient(create_app(settings, Container(settings))) as secured:
        assert secured.get("/api/options").status_code == 401
        secured.cookies.set("scv_token", "wrong")
        assert secured.get("/api/options").status_code == 401
        secured.cookies.set("scv_token", "secret-token")
        assert secured.get("/api/options").status_code == 200


def test_public_mode_allows_bring_your_own_key_when_enabled(tmp_path):
    settings = dataclasses.replace(get_settings(), history_db_path=tmp_path / "byok.db", public_deployment=True,
                                   app_access_token="x" * 40, allow_user_api_keys=True, profile_scope="device")
    with TestClient(create_app(settings, Container(settings)), base_url="http://localhost") as public:
        options = public.get("/api/options", headers={"Authorization": "Bearer " + "x" * 40}).json()
        assert options["flags"]["allow_user_api_keys"] is True and options["flags"]["device_scoped"] is True


def test_missing_system_library_falls_back_to_haar(tmp_path, monkeypatch):
    """A slim server without libEGL must keep working (Haar face detection), not answer 500 everywhere."""
    import api.container as container_module

    def broken(*_args, **_kwargs):
        raise OSError("libEGL.so.1: cannot open shared object file")

    monkeypatch.setattr(container_module, "FaceLandmarkAnalyzer", broken)
    settings = dataclasses.replace(get_settings(), history_db_path=tmp_path / "egl.db")
    container = Container(settings)
    assert container.landmarks is None
    with TestClient(create_app(settings, container)) as degraded:
        assert degraded.get("/api/health").status_code in {200, 503}
        assert degraded.get("/api/options").status_code == 200
        assert degraded.get("/api/status").json()["models"]["landmarks"] is False
