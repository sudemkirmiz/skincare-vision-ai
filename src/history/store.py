"""Local analysis history (SQLite).

Only results and a small face thumbnail are stored, never the uploaded photo. Records
are saved explicitly by the user and can be exported or deleted at any time.
"""
from __future__ import annotations

import base64
import json
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 4
MIGRATIONS = {
    1: [
        """
        CREATE TABLE analyses (
            id TEXT PRIMARY KEY,
            person TEXT NOT NULL,
            created_at TEXT NOT NULL,
            overall_score INTEGER,
            scores TEXT NOT NULL,
            spot_counts TEXT NOT NULL,
            regions TEXT NOT NULL,
            region_metrics TEXT NOT NULL,
            skin_tone TEXT,
            quality_status TEXT,
            method TEXT,
            head_pose TEXT,
            routine_focus TEXT NOT NULL,
            routine_actives TEXT NOT NULL,
            observations TEXT NOT NULL,
            vlm_provider TEXT,
            note TEXT NOT NULL DEFAULT '',
            thumbnail BLOB
        )
        """,
        "CREATE INDEX idx_analyses_person_time ON analyses (person, created_at)",
        """
        CREATE TABLE events (
            id TEXT PRIMARY KEY,
            person TEXT NOT NULL,
            date TEXT NOT NULL,
            kind TEXT NOT NULL,
            note TEXT NOT NULL DEFAULT ''
        )
        """,
    ],
    2: [
        """
        CREATE TABLE profiles (
            id TEXT PRIMARY KEY,
            data TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            last_used_at TEXT NOT NULL
        )
        """,
    ],
    3: [
        # One row per person and day: routine adherence, how the skin felt and possible triggers.
        """
        CREATE TABLE journal (
            person TEXT NOT NULL,
            date TEXT NOT NULL,
            am_done INTEGER,
            pm_done INTEGER,
            skin_feel INTEGER,
            triggers TEXT NOT NULL DEFAULT '[]',
            symptoms TEXT NOT NULL DEFAULT '[]',
            actives TEXT NOT NULL DEFAULT '[]',
            note TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL,
            PRIMARY KEY (person, date)
        )
        """,
    ],
    4: [
        # Products the user owns; the INCI text is kept so the verdict can be re-checked after profile changes.
        """
        CREATE TABLE shelf (
            id TEXT PRIMARY KEY,
            person TEXT NOT NULL,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            usage TEXT NOT NULL,
            inci TEXT NOT NULL DEFAULT '',
            opened_at TEXT,
            pao_months INTEGER,
            created_at TEXT NOT NULL
        )
        """,
        "CREATE INDEX idx_shelf_person ON shelf (person)",
    ],
}
JSON_FIELDS = ("scores", "spot_counts", "regions", "region_metrics", "skin_tone", "head_pose", "routine_focus", "routine_actives", "observations")
EVENT_KINDS = {"routine_start": "Rutine başlandı", "routine_change": "Rutin değişti", "note": "Not"}
MAX_PERSON_LENGTH = 40


@dataclass
class HistoryRecord:
    id: str
    person: str
    created_at: str
    overall_score: int | None
    scores: dict[str, int | None]
    spot_counts: dict[str, int]
    regions: dict[str, int | None]
    region_metrics: dict[str, dict]
    skin_tone: dict | None
    quality_status: str | None
    method: str | None
    head_pose: dict | None
    routine_focus: list[str]
    routine_actives: list[str]
    observations: list[str]
    vlm_provider: str | None
    note: str
    thumbnail: bytes | None

    def to_export_dict(self) -> dict[str, Any]:
        data = {k: v for k, v in self.__dict__.items() if k != "thumbnail"}
        data["has_thumbnail"] = self.thumbnail is not None
        return data


def clean_person(person: str) -> str:
    return " ".join((person or "").split())[:MAX_PERSON_LENGTH] or "Ben"


def record_from_payload(payload: dict[str, Any], person: str, note: str = "", thumbnail: bytes | None = None) -> dict[str, Any]:
    """Flatten an analysis payload into the stored columns (no file paths, no full image)."""
    metrics = payload.get("skin_metrics") or {}
    regions = payload.get("region_summary") or {}
    routine = payload.get("routine") or {}
    detected = (payload.get("result") or {}).get("detected_regions", {})
    available = metrics.get("available")
    return {
        "id": payload.get("analysis_id") or uuid.uuid4().hex[:12],
        "person": clean_person(person),
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "overall_score": metrics.get("overall_score") if available else None,
        "scores": metrics.get("scores", {}) if available else {},
        "spot_counts": metrics.get("spot_counts", {}) if available else {},
        "regions": {r["key"]: (r["count"] if r["visible"] else None) for r in regions.get("regions", [])},
        "region_metrics": metrics.get("regions", {}) if available else {},
        "skin_tone": metrics.get("skin_tone") if available else None,
        "quality_status": ((payload.get("result") or {}).get("image_quality") or {}).get("status"),
        "method": detected.get("method"),
        "head_pose": detected.get("head_pose"),
        "routine_focus": routine.get("focus", []),
        "routine_actives": [item["name"] for item in routine.get("actives", [])],
        "observations": (payload.get("result") or {}).get("visible_observations", []),
        "vlm_provider": (payload.get("vlm_output") or {}).get("provider"),
        "note": (note or "").strip()[:500],
        "thumbnail": thumbnail,
    }


def thumbnail_from_data_uri(data_uri: str | None) -> bytes | None:
    if not data_uri or "," not in data_uri:
        return None
    return base64.b64decode(data_uri.split(",", 1)[1])


class HistoryStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._migrate()

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA foreign_keys=ON")
            yield connection
            connection.commit()
        finally:
            connection.close()

    def _migrate(self) -> None:
        with self._lock, self._connect() as connection:
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            for target in range(version + 1, SCHEMA_VERSION + 1):
                for statement in MIGRATIONS[target]:
                    connection.execute(statement)
                connection.execute(f"PRAGMA user_version = {target}")

    # --- analyses ---------------------------------------------------------
    def save(self, record: dict[str, Any]) -> str:
        values = {key: (json.dumps(value, ensure_ascii=False) if key in JSON_FIELDS else value) for key, value in record.items()}
        columns = ", ".join(values)
        placeholders = ", ".join(f":{key}" for key in values)
        with self._lock, self._connect() as connection:
            connection.execute(f"INSERT OR REPLACE INTO analyses ({columns}) VALUES ({placeholders})", values)
        return record["id"]

    def list(self, person: str, limit: int = 500) -> list[HistoryRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM analyses WHERE person = ? ORDER BY created_at ASC LIMIT ?", (clean_person(person), limit)
            ).fetchall()
        return [self._to_record(row) for row in rows]

    def get(self, record_id: str) -> HistoryRecord | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM analyses WHERE id = ?", (record_id,)).fetchone()
        return self._to_record(row) if row else None

    def exists(self, record_id: str) -> bool:
        with self._connect() as connection:
            return connection.execute("SELECT 1 FROM analyses WHERE id = ?", (record_id,)).fetchone() is not None

    def update_note(self, record_id: str, note: str) -> None:
        with self._lock, self._connect() as connection:
            connection.execute("UPDATE analyses SET note = ? WHERE id = ?", ((note or "").strip()[:500], record_id))

    def delete(self, record_id: str) -> None:
        with self._lock, self._connect() as connection:
            connection.execute("DELETE FROM analyses WHERE id = ?", (record_id,))

    def delete_person(self, person: str) -> int:
        """Right to erasure: removes every analysis and event of this person."""
        person = clean_person(person)
        with self._lock, self._connect() as connection:
            deleted = connection.execute("DELETE FROM analyses WHERE person = ?", (person,)).rowcount
            connection.execute("DELETE FROM events WHERE person = ?", (person,))
            connection.execute("DELETE FROM journal WHERE person = ?", (person,))
            connection.execute("DELETE FROM shelf WHERE person = ?", (person,))
        self.vacuum()
        return deleted

    def vacuum(self) -> None:
        # Make deleted thumbnails actually disappear from the file.
        connection = sqlite3.connect(self.path, timeout=10)
        try:
            connection.execute("VACUUM")
        finally:
            connection.close()

    def persons(self) -> list[str]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT person FROM analyses UNION SELECT person FROM events ORDER BY person"
            ).fetchall()
        return [row[0] for row in rows]

    # --- profiles ---------------------------------------------------------
    # `person` in analyses/events holds the profile id from schema v2 on.
    def save_profile(self, profile: dict[str, Any]) -> str:
        now = datetime.now().isoformat(timespec="seconds")
        profile = {**profile, "updated_at": now}
        with self._lock, self._connect() as connection:
            is_first = connection.execute("SELECT COUNT(*) FROM profiles").fetchone()[0] == 0
            connection.execute(
                """INSERT INTO profiles (id, data, created_at, updated_at, last_used_at) VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET data = excluded.data, updated_at = excluded.updated_at, last_used_at = excluded.last_used_at""",
                (profile["id"], json.dumps(profile, ensure_ascii=False), profile.get("created_at") or now, now, now),
            )
            if is_first:
                # History saved before profiles existed (person "Ben") now belongs to the first profile.
                connection.execute("UPDATE analyses SET person = ? WHERE person = 'Ben'", (profile["id"],))
                connection.execute("UPDATE events SET person = ? WHERE person = 'Ben'", (profile["id"],))
        return profile["id"]

    def get_profile(self, profile_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute("SELECT data FROM profiles WHERE id = ?", (profile_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def list_profiles(self) -> list[dict[str, Any]]:
        """Most recently used first."""
        with self._connect() as connection:
            rows = connection.execute("SELECT data FROM profiles ORDER BY last_used_at DESC").fetchall()
        return [json.loads(row[0]) for row in rows]

    def touch_profile(self, profile_id: str) -> None:
        with self._lock, self._connect() as connection:
            connection.execute("UPDATE profiles SET last_used_at = ? WHERE id = ?", (datetime.now().isoformat(timespec="microseconds"), profile_id))

    def delete_profile(self, profile_id: str) -> None:
        """Removes the profile together with all of its analyses, thumbnails and events."""
        with self._lock, self._connect() as connection:
            connection.execute("DELETE FROM profiles WHERE id = ?", (profile_id,))
            connection.execute("DELETE FROM analyses WHERE person = ?", (profile_id,))
            connection.execute("DELETE FROM events WHERE person = ?", (profile_id,))
            connection.execute("DELETE FROM journal WHERE person = ?", (profile_id,))
            connection.execute("DELETE FROM shelf WHERE person = ?", (profile_id,))
        self.vacuum()

    # --- events -----------------------------------------------------------
    def add_event(self, person: str, kind: str, date: str | None = None, note: str = "") -> str:
        if kind not in EVENT_KINDS:
            raise ValueError(f"unknown event kind {kind!r}")
        event_id = uuid.uuid4().hex[:12]
        with self._lock, self._connect() as connection:
            connection.execute(
                "INSERT INTO events (id, person, date, kind, note) VALUES (?, ?, ?, ?, ?)",
                (event_id, clean_person(person), date or datetime.now().date().isoformat(), kind, (note or "").strip()[:200]),
            )
        return event_id

    def events(self, person: str) -> list[dict[str, str]]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM events WHERE person = ? ORDER BY date", (clean_person(person),)).fetchall()
        return [dict(row) for row in rows]

    def delete_event(self, event_id: str) -> None:
        with self._lock, self._connect() as connection:
            connection.execute("DELETE FROM events WHERE id = ?", (event_id,))

    # --- journal ----------------------------------------------------------
    def save_journal(self, person: str, date: str, entry: dict[str, Any]) -> dict[str, Any]:
        """Insert or replace the day's entry; `entry` is already validated."""
        row = {
            "person": clean_person(person),
            "date": date,
            "am_done": None if entry.get("am_done") is None else int(bool(entry["am_done"])),
            "pm_done": None if entry.get("pm_done") is None else int(bool(entry["pm_done"])),
            "skin_feel": entry.get("skin_feel"),
            "triggers": json.dumps(sorted(set(entry.get("triggers") or [])), ensure_ascii=False),
            "symptoms": json.dumps(sorted(set(entry.get("symptoms") or [])), ensure_ascii=False),
            "actives": json.dumps(list(dict.fromkeys(entry.get("actives") or [])), ensure_ascii=False),
            "note": (entry.get("note") or "").strip()[:200],
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }
        with self._lock, self._connect() as connection:
            connection.execute(
                """INSERT OR REPLACE INTO journal (person, date, am_done, pm_done, skin_feel, triggers, symptoms, actives, note, updated_at)
                   VALUES (:person, :date, :am_done, :pm_done, :skin_feel, :triggers, :symptoms, :actives, :note, :updated_at)""",
                row,
            )
        return self._journal_dict(row)

    def journal(self, person: str, since: str | None = None) -> list[dict[str, Any]]:
        """Oldest first; `since` is an ISO date (inclusive)."""
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM journal WHERE person = ? AND date >= ? ORDER BY date", (clean_person(person), since or "0000-00-00")
            ).fetchall()
        return [self._journal_dict(dict(row)) for row in rows]

    def delete_journal(self, person: str, date: str) -> None:
        with self._lock, self._connect() as connection:
            connection.execute("DELETE FROM journal WHERE person = ? AND date = ?", (clean_person(person), date))

    @staticmethod
    def _journal_dict(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "date": row["date"],
            "am_done": None if row["am_done"] is None else bool(row["am_done"]),
            "pm_done": None if row["pm_done"] is None else bool(row["pm_done"]),
            "skin_feel": row["skin_feel"],
            "triggers": json.loads(row["triggers"]),
            "symptoms": json.loads(row["symptoms"]),
            "actives": json.loads(row["actives"]),
            "note": row["note"],
        }

    # --- product shelf ----------------------------------------------------
    def save_shelf_item(self, person: str, item: dict[str, Any], item_id: str | None = None) -> str:
        """Insert, or replace the item with `item_id` when it belongs to `person`."""
        item_id = item_id or uuid.uuid4().hex[:12]
        row = {
            "id": item_id, "person": clean_person(person), "name": item["name"].strip()[:80], "category": item["category"],
            "usage": item["usage"], "inci": (item.get("inci") or "").strip()[:8000], "opened_at": item.get("opened_at"),
            "pao_months": item.get("pao_months"), "created_at": item.get("created_at") or datetime.now().isoformat(timespec="seconds"),
        }
        with self._lock, self._connect() as connection:
            connection.execute(
                """INSERT OR REPLACE INTO shelf (id, person, name, category, usage, inci, opened_at, pao_months, created_at)
                   VALUES (:id, :person, :name, :category, :usage, :inci, :opened_at, :pao_months, :created_at)""",
                row,
            )
        return item_id

    def shelf(self, person: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM shelf WHERE person = ? ORDER BY created_at", (clean_person(person),)).fetchall()
        return [{key: row[key] for key in row.keys() if key != "person"} for row in rows]

    def shelf_item(self, person: str, item_id: str) -> dict[str, Any] | None:
        return next((item for item in self.shelf(person) if item["id"] == item_id), None)

    def delete_shelf_item(self, person: str, item_id: str) -> None:
        with self._lock, self._connect() as connection:
            connection.execute("DELETE FROM shelf WHERE person = ? AND id = ?", (clean_person(person), item_id))

    # --- export -----------------------------------------------------------
    def export_json(self, person: str) -> str:
        data = {
            "person": clean_person(person),
            "exported_at": datetime.now().isoformat(timespec="seconds"),
            "analyses": [record.to_export_dict() for record in self.list(person)],
            "events": self.events(person),
            "journal": self.journal(person),
            "shelf": self.shelf(person),
        }
        return json.dumps(data, ensure_ascii=False, indent=2)

    def export_csv(self, person: str) -> str:
        import csv
        import io

        records = self.list(person)
        score_keys = sorted({key for record in records for key in record.scores})
        region_keys = sorted({key for record in records for key in record.regions})
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["tarih", "genel_skor", *score_keys, "nokta_toplam", *[f"bolge_{k}" for k in region_keys], "not"])
        for record in records:
            writer.writerow([
                record.created_at, record.overall_score,
                *[record.scores.get(k) for k in score_keys],
                record.spot_counts.get("total"),
                *[record.regions.get(k) for k in region_keys],
                record.note,
            ])
        return buffer.getvalue()

    @staticmethod
    def _to_record(row: sqlite3.Row) -> HistoryRecord:
        data = dict(row)
        for key in JSON_FIELDS:
            data[key] = json.loads(data[key]) if data[key] else ({} if key not in {"routine_focus", "routine_actives", "observations"} else [])
        if data["skin_tone"] == {}:
            data["skin_tone"] = None
        if data["head_pose"] == {}:
            data["head_pose"] = None
        return HistoryRecord(**data)
