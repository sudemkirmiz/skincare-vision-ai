import json
import sqlite3

import pytest

from history.compare import compare_records, trend_rows
from history.store import SCHEMA_VERSION, HistoryStore, clean_person, record_from_payload, thumbnail_from_data_uri


def payload(analysis_id, overall=60, spots=10, cheek=4, scores=None, yaw=0.0, method="mediapipe", quality="good"):
    scores = scores or {"spots": 60, "redness": 60, "tone": 60, "texture": 60, "shine": 60}
    return {
        "analysis_id": analysis_id,
        "result": {"image_quality": {"status": quality}, "detected_regions": {"method": method, "head_pose": {"yaw": yaw, "pitch": 0, "roll": 0}},
                   "visible_observations": ["Hafif kızarıklık."]},
        "skin_metrics": {"available": True, "overall_score": overall, "scores": scores,
                         "spot_counts": {"yolo": 2, "colour": spots - 2, "total": spots},
                         "regions": {"left_cheek": {"name": "Sol yanak", "redness": 50, "tone": 70, "shine": 90}},
                         "skin_tone": {"ita": 45.0, "category": "Açık"}},
        "region_summary": {"regions": [
            {"key": "left_cheek", "count": cheek, "visible": True},
            {"key": "forehead", "count": 0, "visible": False},
        ]},
        "routine": {"focus": ["Kızarıklık"], "actives": [{"name": "Azelaik asit"}]},
        "vlm_output": {"provider": "Gemini"},
    }


@pytest.fixture
def store(tmp_path):
    return HistoryStore(tmp_path / "nested" / "history.db")


def test_schema_is_created_and_versioned(store):
    with sqlite3.connect(store.path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
    HistoryStore(store.path)  # re-opening must not re-run migrations


def test_save_and_read_back_roundtrip(store):
    store.save(record_from_payload(payload("a1"), "  Ben  ", note="ilk", thumbnail=b"\xff\xd8jpeg"))
    (record,) = store.list("Ben")
    assert record.id == "a1" and record.person == "Ben"
    assert record.overall_score == 60 and record.spot_counts["total"] == 10
    assert record.regions == {"left_cheek": 4, "forehead": None}  # invisible region kept as unknown, not zero
    assert record.routine_actives == ["Azelaik asit"]
    assert record.thumbnail == b"\xff\xd8jpeg"
    assert store.exists("a1") and store.get("missing") is None


def test_saving_same_analysis_twice_does_not_duplicate(store):
    store.save(record_from_payload(payload("a1"), "Ben"))
    store.save(record_from_payload(payload("a1"), "Ben", note="güncel"))
    assert [r.note for r in store.list("Ben")] == ["güncel"]


def test_persons_are_separate_and_deletable(store):
    store.save(record_from_payload(payload("a1"), "Ben", thumbnail=b"x" * 5000))
    store.save(record_from_payload(payload("b1"), "Kardeşim"))
    store.add_event("Ben", "routine_start", "2026-10-01")
    assert store.persons() == ["Ben", "Kardeşim"]
    assert store.delete_person("Ben") == 1
    assert store.list("Ben") == [] and store.events("Ben") == []
    assert [r.id for r in store.list("Kardeşim")] == ["b1"]


def test_events(store):
    event_id = store.add_event("Ben", "routine_start", "2026-10-01", note="azelaik başladım")
    assert store.events("Ben")[0]["note"] == "azelaik başladım"
    with pytest.raises(ValueError):
        store.add_event("Ben", "unknown")
    store.delete_event(event_id)
    assert store.events("Ben") == []


def test_exports_exclude_thumbnail_bytes(store):
    store.save(record_from_payload(payload("a1"), "Ben", thumbnail=b"secret-bytes"))
    exported = json.loads(store.export_json("Ben"))
    assert exported["analyses"][0]["has_thumbnail"] is True
    assert "secret-bytes" not in store.export_json("Ben")
    csv_text = store.export_csv("Ben")
    assert csv_text.splitlines()[0].startswith("tarih,genel_skor")
    assert "60" in csv_text.splitlines()[1]


def test_csv_export_escapes_formula_like_notes(store):
    store.save(record_from_payload(payload("a1"), "Ben", note='=HYPERLINK("https://example.test")'))
    assert "'=HYPERLINK" in store.export_csv("Ben")


def test_compare_reports_improvement_and_noise():
    store_records = []
    before = record_from_payload(payload("a", overall=45, spots=20, cheek=8, scores={"spots": 40, "redness": 40, "tone": 60, "texture": 60, "shine": 60}), "Ben")
    after = record_from_payload(payload("b", overall=62, spots=10, cheek=3, scores={"spots": 70, "redness": 55, "tone": 62, "texture": 57, "shine": 60}), "Ben")
    from history.store import HistoryRecord

    for data in (before, after):
        store_records.append(HistoryRecord(**data))
    result = compare_records(*store_records)
    by_key = {s["key"]: s["direction"] for s in result["scores"]}
    assert by_key == {"spots": "better", "redness": "better", "tone": "same", "texture": "same", "shine": "same"}
    assert {r["key"]: r["direction"] for r in result["regions"]}["left_cheek"] == "better"
    assert result["spot_delta"] == -10
    assert any("17 puan yükseldi" in line for line in result["summary"])
    assert any("%50 azaldı" in line for line in result["summary"])


def test_comparability_warnings():
    from history.store import HistoryRecord

    a = HistoryRecord(**record_from_payload(payload("a", yaw=2), "Ben"))
    b = HistoryRecord(**record_from_payload(payload("b", yaw=28, method="haar", quality="needs_review"), "Ben"))
    notes = compare_records(a, b)["comparability_notes"]
    assert any("farklı yöntemle" in n for n in notes)
    assert any("Baş açıları" in n for n in notes)
    assert any("kalitesi" in n for n in notes)


def test_trend_rows_long_format(store):
    store.save(record_from_payload(payload("a1", overall=50), "Ben"))
    rows = trend_rows(store.list("Ben"))
    assert {row["seri"] for row in rows} >= {"Genel skor", "Kızarıklık dengesi"}
    assert all(set(row) == {"tarih", "seri", "değer", "id"} for row in rows)


def test_helpers():
    assert clean_person("   ") == "Ben"
    assert clean_person("  Ayşe   Yılmaz ") == "Ayşe Yılmaz"
    assert thumbnail_from_data_uri("data:image/jpeg;base64,aGVsbG8=") == b"hello"
    assert thumbnail_from_data_uri(None) is None



def test_journal_upsert_list_delete_and_erasure(store):
    store.save_journal("p1", "2026-10-20", {"am_done": True, "pm_done": None, "skin_feel": 4, "triggers": ["stress", "stress"],
                                            "symptoms": ["breakout"], "actives": ["Retinol", "Retinol"], "note": " not "})
    saved = store.save_journal("p1", "2026-10-20", {"am_done": True, "pm_done": False, "skin_feel": 3, "triggers": ["stress"]})
    assert saved["pm_done"] is False and saved["symptoms"] == []
    store.save_journal("p1", "2026-10-21", {"skin_feel": 5, "actives": ["Retinol", "Retinol"]})
    entries = store.journal("p1")
    assert [entry["date"] for entry in entries] == ["2026-10-20", "2026-10-21"]
    assert entries[0]["skin_feel"] == 3 and entries[1]["actives"] == ["Retinol"] and entries[1]["am_done"] is None
    assert store.journal("p1", since="2026-10-21")[0]["date"] == "2026-10-21"
    assert '"journal"' in store.export_json("p1")
    store.delete_journal("p1", "2026-10-21")
    assert len(store.journal("p1")) == 1
    store.delete_person("p1")
    assert store.journal("p1") == []


def test_v2_database_is_migrated_to_journal(tmp_path):
    path = tmp_path / "old.db"
    with sqlite3.connect(path) as connection:
        from history.store import MIGRATIONS
        for version in (1, 2):  # a v2 database, before journal and shelf
            for statement in MIGRATIONS[version]:
                connection.execute(statement)
        connection.execute("PRAGMA user_version = 2")
    store = HistoryStore(path)
    store.save_journal("p1", "2026-10-25", {"skin_feel": 4})
    assert store.journal("p1")[0]["skin_feel"] == 4


def test_shelf_items_are_per_person_and_erased(store):
    item = {"name": "SPF", "category": "sunscreen", "usage": "am", "inci": "Zinc Oxide"}
    item_id = store.save_shelf_item("p1", item)
    store.save_shelf_item("p2", item)
    store.save_shelf_item("p1", {**item, "name": "SPF 50"}, item_id)
    assert [entry["name"] for entry in store.shelf("p1")] == ["SPF 50"]
    assert store.shelf_item("p2", item_id) is None
    store.delete_person("p1")
    assert store.shelf("p1") == [] and len(store.shelf("p2")) == 1
