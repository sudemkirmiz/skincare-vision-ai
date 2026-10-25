# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Sudem Kırmız
"""Record the data behind the static GitHub Pages demo (frontend, VITE_DEMO=1).

Runs the real API in-process on a throwaway database, analyses the demo face offline (no VLM call), seeds a
few weeks of sample history, journal and shelf data, and saves every response the demo needs:

  frontend/src/demo/fixtures.json     API responses (dates are rebased to "today" by the demo at runtime)
  frontend/src/demo/assets/report.pdf     the PDF report for the sample analysis
  frontend/src/demo/assets/export.*       the history export (JSON and CSV)
  frontend/src/demo/assets/sample.jpg     the sample photo shown in the demo upload card

Usage:  .venv\\Scripts\\python scripts\\build_demo_fixtures.py [path\\to\\face.png]
The default face is samples/03_studio_frontal.png (AI-generated portrait; samples/ itself is not in Git).
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FACE = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "samples" / "03_studio_frontal.png"
FIXTURES = ROOT / "frontend" / "src" / "demo" / "fixtures.json"
ASSETS = ROOT / "frontend" / "src" / "demo" / "assets"

workdir = Path(tempfile.mkdtemp(prefix="scv-demo-"))
os.environ["HISTORY_DB_PATH"] = str(workdir / "demo.db")
os.environ["PUBLIC_DEPLOYMENT"] = "false"
for key in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "GROQ_API_KEY", "HF_TOKEN", "HUGGINGFACE_API_KEY"):
    os.environ[key] = ""
sys.path.insert(0, str(ROOT / "src"))

import cv2  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from api.server import create_app  # noqa: E402
from history.store import record_from_payload, thumbnail_from_data_uri  # noqa: E402

# Real Gemini (gemini-flash-lite-latest) output for this photo from an earlier live run, kept so the demo shows
# the care comment without spending API quota on every rebuild.
VLM = {
    "provider": "Gemini",
    "model": "gemini-flash-lite-latest",
    "observations": [
        "Helin, alın ve yanak bölgelerinizde belirgin kızarıklıklar ve küçük noktalar görülmektedir.",
        "Cildinizde ton eşitsizlikleri ve T-bölgesinde parlama gözlemlenmektedir.",
        "Gözenek görünümü ve doku pürüzlülüğü dikkati çekmektedir.",
    ],
    "suggestions": [
        "Nazik temizleyicilerle cildinizi arındırabilir ve günlük rutininizde dengeleyici ürünlere yer verebilirsiniz.",
        "Cilt bariyerini desteklemek için düzenli nemlendirici kullanabilirsiniz.",
        "Gündüzleri güneş koruyucu kullanarak ton eşitsizliklerinin kontrolüne yardımcı olabilirsiniz.",
        "Cildinizi tahriş etmemek için sert ovma işlemlerinden kaçınabilirsiniz.",
    ],
}
PROFILE = {
    "display_name": "Helin", "last_name": "Kaya", "gender": "female", "address_form": "siz", "consent": True,
    "answered": ["makeup", "sun_exposure", "budget"],
    "skin": {"skin_type": "combination", "sensitivity": "sometimes", "age_group": "18_29", "pregnancy": "no",
             "concerns": ["spots", "redness", "tone"], "budget": "mid", "routine_size": "standard",
             "makeup": "sometimes", "sun_exposure": "medium"},
}
# Sample progress: days before today and the Skin Score shift from the real result.
HISTORY = [(84, -14), (63, -11), (42, -7), (21, -4), (0, 0)]
SHELF = [
    ("Jel Temizleyici", "cleanser", "both", "Aqua, Glycerin, Coco-Glucoside, Sodium Lauroyl Sarcosinate, Panthenol", None, None),
    ("C Vitamini Serumu", "serum", "am", "Aqua, Ascorbic Acid, Glycerin, Ferulic Acid, Tocopherol", 300, 6),
    ("Niasinamid %10", "serum", "both", "Aqua, Niacinamide, Zinc PCA, Glycerin, Pentylene Glycol", None, None),
    ("Bariyer Krem", "moisturizer", "both", "Aqua, Glycerin, Ceramide NP, Cholesterol, Squalane, Panthenol", 40, 12),
    ("SPF 50 Fluid", "sunscreen", "am", "Aqua, Zinc Oxide, Glycerin, Tocopherol", 70, 12),
    ("Retinol 0.3%", "serum", "pm", "Aqua, Glycerin, Retinol, Squalane, Tocopherol", None, None),
    ("Glikolik Tonik", "exfoliant", "pm", "Aqua, Glycolic Acid, Glycerin, Aloe Barbadensis Leaf Juice", None, None),
]
SAMPLE_INCI = "Aqua, Glycerin, Niacinamide, Ceramide NP, Panthenol, Sodium Hyaluronate, Parfum, Linalool"


def ok(response):
    assert response.status_code < 300, (response.request.url, response.status_code, response.text[:300])
    return response


def journal_days(today: date) -> list[tuple[date, dict]]:
    """~6 weeks with a pattern the insights can find: short-sleep days are followed by worse skin."""
    days = []
    for back in range(42, 0, -1):
        if back in {17, 30}:
            continue  # a few gaps, like a real journal
        short_sleep = back % 4 == 0
        after_short = (back + 1) % 4 == 0
        feel = 2 if after_short else 4 if back % 3 else 5
        triggers = ["short_sleep"] if short_sleep else ["stress"] if back % 9 == 0 else []
        if back % 11 == 0:
            triggers.append("sun")
        pm = back % 7 != 3
        days.append((today - timedelta(days=back), {
            "am_done": back % 10 != 5, "pm_done": pm, "skin_feel": feel, "triggers": triggers,
            "symptoms": ["breakout"] if after_short else ["oiliness"] if back % 6 == 0 else [],
            "actives": ["Retinol"] if pm and back % 3 == 1 else [], "note": "",
        }))
    return days


def main() -> None:
    today = date.today()
    client = TestClient(create_app())
    services = client.app.state.container
    get = lambda path: ok(client.get(path)).json()  # noqa: E731
    fixtures: dict = {"captured_on": today.isoformat(), "get": {}}

    def keep(path: str) -> dict:
        fixtures["get"][path] = get(path)
        return fixtures["get"][path]

    for path in ("/api/options", "/api/status", "/api/coach/suggestions"):
        keep(path)
    profile = ok(client.post("/api/profiles", json=PROFILE)).json()
    pid = profile["id"]

    # The analysis itself: real models, no VLM call, then the recorded Gemini comment.
    with FACE.open("rb") as handle:
        analysis = ok(client.post("/api/analyses", data={"profile_id": pid, "provider": "Gemini", "use_vlm": "false", "second_opinion": "false"},
                                  files=[("files", ("face.png", handle, "image/png"))])).json()
    aid = analysis["analysis_id"]
    cached = services.analyses.get(aid, pid)
    for payload in (cached, analysis):
        payload["vlm_output"] = {"provider": VLM["provider"], "model": VLM["model"]}
        payload["vlm_error"] = None
        payload["result"]["visible_observations"] = VLM["observations"]
        payload["result"]["care_suggestions"] = VLM["suggestions"]
    fixtures["analysis"] = analysis
    keep(f"/api/analyses/{aid}/routine?profile_id={pid}")
    keep(f"/api/analyses/{aid}/products?profile_id={pid}")

    # Sample history: the real record plus earlier, lower-scoring copies.
    base = record_from_payload(cached, pid, thumbnail=None)
    thumbnail = thumbnail_from_data_uri(cached.get("face_thumbnail_uri"))
    notes = {84: "İlk analiz", 42: "Niasinamide başladım", 0: ""}
    for index, (back, shift) in enumerate(HISTORY):
        record = {**base, "id": f"demo{index}", "thumbnail": thumbnail, "note": notes.get(back, "")}
        record["created_at"] = (datetime.combine(today - timedelta(days=back), datetime.min.time()) + timedelta(hours=9 + index)).isoformat(timespec="seconds")
        record["overall_score"] = max(1, base["overall_score"] + shift)
        record["scores"] = {key: (None if value is None else max(1, min(100, value + shift + (index % 2) * 2))) for key, value in base["scores"].items()}
        total = (base["spot_counts"] or {}).get("total")
        if total:
            new_total = total - shift // 2
            record["spot_counts"] = {**base["spot_counts"], "total": new_total}
            # Per-region counts follow the total, so the comparison table tells the same story.
            record["regions"] = {key: (None if count is None else round(count * new_total / total)) for key, count in base["regions"].items()}
        services.store.save(record)
    services.store.add_event(pid, "routine_start", (today - timedelta(days=42)).isoformat(), "Niasinamid serumuna başladım")
    services.store.add_event(pid, "routine_change", (today - timedelta(days=20)).isoformat(), "Akşam retinol eklendi")
    history = keep(f"/api/profiles/{pid}/history")
    for record in history["records"]:
        record["thumbnail_url"] = cached["face_thumbnail_uri"] if record["thumbnail_url"] else None
    ids = [record["id"] for record in history["records"]]
    fixtures["compare"] = {f"{a}|{b}": get(f"/api/profiles/{pid}/compare?before={a}&after={b}") for i, a in enumerate(ids) for b in ids[i + 1:]}
    fixtures["compare_map"] = {f"{ids[0]}|{ids[-1]}": get(f"/api/profiles/{pid}/compare/map?before={ids[0]}&after={ids[-1]}")}

    for day, entry in journal_days(today):
        services.store.save_journal(pid, day.isoformat(), entry)
    keep(f"/api/profiles/{pid}/journal")

    for name, category, usage, inci, opened_days, pao in SHELF:
        ok(client.post(f"/api/profiles/{pid}/shelf", json={"name": name, "category": category, "usage": usage, "inci": inci,
                                                             "opened_at": None if opened_days is None else (today - timedelta(days=opened_days)).isoformat(),
                                                             "pao_months": pao}))
    keep(f"/api/profiles/{pid}/shelf")
    fixtures["product_check"] = {"inci": SAMPLE_INCI, "verdict": ok(client.post("/api/products/check", json={"profile_id": pid, "inci_text": SAMPLE_INCI, "analysis_id": aid})).json()}

    places = get("/api/weather/search?q=%C4%B0stanbul")
    fixtures["get"]["/api/weather/search"] = places
    if places:
        fixtures["weather"] = get(f"/api/weather?lat={places[0]['lat']}&lon={places[0]['lon']}&profile_id={pid}")

    fixtures["get"]["/api/profiles"] = get("/api/profiles")
    fixtures["profile_id"] = pid

    ASSETS.mkdir(parents=True, exist_ok=True)
    for extension in ("json", "csv"):
        (ASSETS / f"export.{extension}").write_bytes(ok(client.get(f"/api/profiles/{pid}/history/export.{extension}")).content)
    (ASSETS / "report.pdf").write_bytes(ok(client.get(f"/api/analyses/{aid}/report.pdf?profile_id={pid}")).content)
    image = cv2.imread(str(FACE))
    scale = 720 / max(image.shape[:2])
    cv2.imwrite(str(ASSETS / "sample.jpg"), cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA), [cv2.IMWRITE_JPEG_QUALITY, 88])
    FIXTURES.parent.mkdir(parents=True, exist_ok=True)
    FIXTURES.write_text(json.dumps(fixtures, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"fixtures: {FIXTURES.stat().st_size // 1024} KB, score {analysis['skin_metrics'].get('overall_score')}, {len(history['records'])} records")


if __name__ == "__main__":
    main()
