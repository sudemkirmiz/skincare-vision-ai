# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Sudem Kırmız
"""Security regression tests. Route checks walk the whole app, so a new endpoint is covered automatically."""
import dataclasses
import re
from io import BytesIO

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from PIL import Image

from api.container import Container
from api.server import AUTH_FAILURE_LIMIT, FRONTEND_DIST, create_app
from config import get_settings

TOKEN = "t" * 40
PROFILE = {
    "display_name": "Ayşe", "last_name": "Yılmaz", "gender": "female", "consent": True, "address_form": "siz",
    "skin": {"skin_type": "combination", "sensitivity": "sometimes", "age_group": "18_29", "pregnancy": "no"},
}
PUBLIC_EXCEPTIONS = {"/api/health"}  # readiness probe only, no details


def app_client(tmp_path, **overrides) -> TestClient:
    settings = dataclasses.replace(get_settings(), history_db_path=tmp_path / "security.db", vlm_second_opinion=False, **overrides)
    return TestClient(create_app(settings, Container(settings)))


def api_routes(app) -> list[tuple[str, str]]:
    """(method, concrete path) for every API route, with dummy values for path parameters."""
    routes = []
    for route in app.routes:
        if isinstance(route, APIRoute) and route.path.startswith("/api/"):
            path = re.sub(r"\{extension\}", "pdf", route.path)
            path = re.sub(r"\{day\}", "2026-01-01", path)
            path = re.sub(r"\{[a-z_]+\}", "abc123", path)
            routes += [(method, path) for method in route.methods - {"HEAD"}]
    return routes


def test_every_api_route_requires_the_access_token(tmp_path):
    with app_client(tmp_path, app_access_token=TOKEN) as client:
        routes = api_routes(client.app)
        assert len(routes) > 30
        for method, path in routes:
            status = client.request(method, path).status_code
            if path in PUBLIC_EXCEPTIONS:
                assert status in {200, 503}, path
            else:
                assert status == 401, f"{method} {path} answered {status} without a token"


def test_cookie_token_only_authenticates_reads(tmp_path):
    with app_client(tmp_path, app_access_token=TOKEN) as client:
        client.cookies.set("scv_token", TOKEN)
        assert client.get("/api/profiles").status_code == 200
        # A cross-site form could carry the cookie; writes therefore need the header.
        assert client.post("/api/profiles", json=PROFILE).status_code == 401
        assert client.post("/api/profiles", json=PROFILE, headers={"Authorization": f"Bearer {TOKEN}"}).status_code == 201


def test_wrong_tokens_pause_the_ip_even_for_the_right_token(tmp_path):
    with app_client(tmp_path, app_access_token=TOKEN) as client:
        good = {"Authorization": f"Bearer {TOKEN}"}
        assert client.get("/api/options", headers=good).status_code == 200
        for _ in range(AUTH_FAILURE_LIMIT):
            assert client.get("/api/options", headers={"Authorization": "Bearer wrong"}).status_code == 401
        paused = client.get("/api/options", headers=good)
        assert paused.status_code == 429 and int(paused.headers["retry-after"]) > 0


def test_missing_token_attempts_do_not_lock_anyone_out(tmp_path):
    with app_client(tmp_path, app_access_token=TOKEN) as client:
        for _ in range(AUTH_FAILURE_LIMIT + 5):
            client.get("/api/options")  # e.g. the app's first load before the token is typed
        assert client.get("/api/options", headers={"Authorization": f"Bearer {TOKEN}"}).status_code == 200


def _seed_records(client, pid: str) -> list[str]:
    """Two saved analyses with face previews, so comparison routes reach their real code path."""
    from history.store import record_from_payload

    buffer = BytesIO()
    Image.new("RGB", (64, 64), (200, 160, 140)).save(buffer, "JPEG")
    ids = []
    for index in range(2):
        record = record_from_payload({"skin_metrics": {"available": True, "overall_score": 50 + index, "scores": {}}}, pid, thumbnail=buffer.getvalue())
        record["id"] = f"rec{index}{pid[:6]}"
        record["created_at"] = f"2026-01-0{index + 1}T10:00:00"
        client.app.state.container.store.save(record)
        ids.append(record["id"])
    return ids


def _body_for(path: str) -> dict:
    if "/shelf" in path:
        return {"name": "Krem", "category": "moisturizer", "usage": "both"}
    if "/events" in path:
        return {"kind": "note", "note": "x"}
    if "/journal/" in path:
        return {"am_done": True}
    return PROFILE


def test_every_profile_route_hides_other_devices_data(tmp_path):
    with app_client(tmp_path, profile_scope="device") as client:
        owner, stranger = {"X-Device-Key": "o" * 40}, {"X-Device-Key": "s" * 40}
        pid = client.post("/api/profiles", json=PROFILE, headers=owner).json()["id"]
        before, after = _seed_records(client, pid)
        client.post(f"/api/profiles/{pid}/events", json={"kind": "note", "note": "x"}, headers=owner)
        assert client.get(f"/api/profiles/{pid}/compare?before={before}&after={after}", headers=owner).status_code == 200
        today = __import__("datetime").date.today().isoformat()
        checked = 0
        for route in client.app.routes:
            if not (isinstance(route, APIRoute) and "{profile_id}" in route.path):
                continue
            path = route.path.replace("{profile_id}", pid).replace("{extension}", "json").replace("{day}", today)
            path = re.sub(r"\{[a-z_]+\}", "abc123", path) + f"?before={before}&after={after}"
            for method in route.methods - {"HEAD"}:
                status = client.request(method, path, headers=stranger, json=_body_for(path)).status_code
                # Exactly what a missing profile returns: nothing tells the stranger the profile exists.
                assert status == 404, f"{method} {path} answered {status} to another device"
                checked += 1
        assert checked >= 15
        for path in (f"/api/history/{before}/thumbnail", f"/api/history/{before}"):
            assert client.request("DELETE" if path.endswith(before) else "GET", path, headers=stranger).status_code == 404
        assert client.get(f"/api/history/{before}/thumbnail", headers=owner).status_code == 200


def test_device_cookie_only_identifies_reads(tmp_path):
    with app_client(tmp_path, profile_scope="device") as client:
        client.cookies.set("scv_device", "c" * 40)
        assert client.get("/api/profiles").status_code == 200
        assert client.post("/api/profiles", json=PROFILE).status_code == 400
        for bad in ("short", "x" * 200, "a" * 39 + "!", "../" * 20):
            assert client.get("/api/profiles", headers={"X-Device-Key": bad}).status_code == 400


def test_security_headers_on_api_and_app(tmp_path):
    with app_client(tmp_path) as client:
        for path in ("/api/options", "/"):
            headers = client.get(path).headers
            assert headers["x-content-type-options"] == "nosniff"
            assert headers["x-frame-options"] == "DENY"
            assert headers["cross-origin-opener-policy"] == "same-origin"
            assert headers["cross-origin-resource-policy"] == "same-origin"
            assert "microphone=()" in headers["permissions-policy"] and "payment=()" in headers["permissions-policy"]
            csp = headers["content-security-policy"]
            assert "script-src 'self'" in csp and "frame-ancestors 'none'" in csp and "unsafe-eval" not in csp
        assert client.get("/api/options").headers["cache-control"] == "no-store"


def test_typed_provider_keys_are_validated(tmp_path):
    with app_client(tmp_path, allow_user_api_keys=True) as client:
        pid = client.post("/api/profiles", json=PROFILE).json()["id"]
        for bad in ("short", "has space inside the key", "x" * 600, "key	with-a-tab-123"):
            response = client.post("/api/coach", json={"profile_id": pid, "provider": "Gemini", "messages": [{"role": "user", "content": "selam"}]},
                                   headers={"X-Provider-Key": bad})
            assert response.status_code == 422, bad


def test_host_and_cors_allowlists(tmp_path):
    with app_client(tmp_path) as client:
        assert client.get("/api/health", headers={"Host": "evil.example"}).status_code == 400
        response = client.options("/api/profiles", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"})
        assert "access-control-allow-origin" not in response.headers


def test_uploads_reject_non_images_and_pixel_bombs(tmp_path):
    with app_client(tmp_path, max_image_pixels=1_000_000) as client:
        pid = client.post("/api/profiles", json=PROFILE).json()["id"]
        fake = client.post("/api/analyses", data={"profile_id": pid, "use_vlm": "false"}, files=[("files", ("x.png", b"<?php echo 1;", "image/png"))])
        assert fake.status_code == 422
        buffer = BytesIO()
        Image.new("RGB", (2000, 2000), (200, 160, 140)).save(buffer, "PNG")
        bomb = client.post("/api/analyses", data={"profile_id": pid, "use_vlm": "false"}, files=[("files", ("big.png", buffer.getvalue(), "image/png"))])
        assert bomb.status_code == 422


def test_hostile_names_stay_inert_in_downloads(tmp_path):
    with app_client(tmp_path) as client:
        hostile = {**PROFILE, "display_name": 'Ayşe"\r\nSet-Cookie: x=1', "last_name": "=HYPERLINK(\"http://evil\")"}
        response = client.post("/api/profiles", json=hostile)
        pid = response.json()["id"]
        export = client.get(f"/api/profiles/{pid}/history/export.csv")
        disposition = export.headers["content-disposition"]
        assert "\r" not in disposition and "\n" not in disposition and "set-cookie" not in {k.lower() for k in export.headers if k.lower() != "content-disposition"}
        assert re.fullmatch(r'attachment; filename="[A-Za-z0-9_.-]+"', disposition)


@pytest.mark.skipif(not (FRONTEND_DIST / "index.html").exists(), reason="frontend not built")
def test_static_files_cannot_escape_the_build_folder(tmp_path):
    with app_client(tmp_path) as client:
        for path in ("/..%2f..%2f.env", "/%2e%2e/%2e%2e/.env", "/assets/..%2f..%2f..%2fsrc%2fconfig.py", "/....//....//.env"):
            response = client.get(path)
            assert "GEMINI_API_KEY" not in response.text and "def get_settings" not in response.text, path
        assert client.get("/api/does-not-exist").status_code == 404
