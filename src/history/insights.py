# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Sudem Kırmız
"""Personal patterns from the daily journal: adherence, streaks and possible triggers.

Every insight compares the user's own days with and without something, needs a minimum number of
days on both sides and is worded as an association, never as a cause. Lifestyle triggers are
compared with the *next* day, because skin reacts with a delay; the period is compared same-day.
"""
from __future__ import annotations

from datetime import date, timedelta
from statistics import mean
from typing import Any

TRIGGERS = {
    "short_sleep": "Az uyku",
    "stress": "Stresli gün",
    "sugar": "Şekerli / işlenmiş gıda",
    "dairy": "Süt ürünleri",
    "heavy_makeup": "Yoğun makyaj",
    "sun": "Uzun süre güneş",
    "sweat": "Spor / terleme",
    "new_product": "Yeni ürün denedim",
    "period": "Regl dönemi",
}
# The period is only offered to women; it is compared with the same day.
SAME_DAY_TRIGGERS = {"period"}
FEMALE_ONLY_TRIGGERS = {"period"}
SYMPTOMS = {
    "breakout": "Yeni sivilce",
    "irritation": "Kızarma / yanma",
    "dryness": "Kuruluk / gerginlik",
    "oiliness": "Aşırı yağlanma",
}
SKIN_FEEL = {1: "Çok kötü", 2: "Kötü", 3: "Orta", 4: "İyi", 5: "Çok iyi"}

MIN_DAYS_FOR_INSIGHTS = 7
MIN_GROUP = 3  # days needed on each side of a comparison
FEEL_GAP = 0.5  # skin-feel points (1-5)
RATE_GAP = 0.25  # share of days with a symptom
INSIGHT_WINDOW_DAYS = 90  # older days are ignored: habits and routines change
ADHERENCE_DAYS = 14
DISCLAIMER = "Bu bulgular yalnızca sizin kayıtlarınızdaki ilişkileri gösterir; neden-sonuç kanıtı değildir. Kayıt arttıkça daha güvenilir olur."


def _day(value: str) -> date:
    return date.fromisoformat(value)


def _share(values: list[bool]) -> float:
    return sum(values) / len(values) if values else 0.0


def streak(entries: list[dict[str, Any]], today: date) -> int:
    """Consecutive logged days ending today (or yesterday, so the streak survives until tonight)."""
    logged = {_day(entry["date"]) for entry in entries}
    current = today if today in logged else today - timedelta(days=1)
    count = 0
    while current in logged:
        count += 1
        current -= timedelta(days=1)
    return count


STREAK_MILESTONES = (3, 7, 14, 30, 60, 100)


def _routine_days(entries: list[dict[str, Any]]) -> set[date]:
    return {_day(entry["date"]) for entry in entries if entry["am_done"] or entry["pm_done"]}


def routine_streak(entries: list[dict[str, Any]], today: date) -> dict[str, Any]:
    """Days in a row with at least one routine done; today may still be open, so yesterday keeps the streak alive."""
    days = _routine_days(entries)
    current = today if today in days else today - timedelta(days=1)
    count = 0
    while current in days:
        count += 1
        current -= timedelta(days=1)
    best = run = 0
    previous: date | None = None
    for day in sorted(days):
        run = run + 1 if previous and day - previous == timedelta(days=1) else 1
        best, previous = max(best, run), day
    by_day = {_day(entry["date"]): entry for entry in entries}
    week = []
    for offset in range(6, -1, -1):
        entry = by_day.get(today - timedelta(days=offset), {})
        week.append({"date": (today - timedelta(days=offset)).isoformat(), "am": entry.get("am_done") is True, "pm": entry.get("pm_done") is True})
    return {
        "current": count,
        "best": best,
        "today_done": today in days,
        "reached": max((step for step in STREAK_MILESTONES if count >= step), default=0),
        "next": next((step for step in STREAK_MILESTONES if step > count), None),
        "week": week,
    }


def adherence(entries: list[dict[str, Any]], today: date, days: int = ADHERENCE_DAYS) -> dict[str, Any]:
    start = today - timedelta(days=days - 1)
    recent = [entry for entry in entries if start <= _day(entry["date"]) <= today]
    result: dict[str, Any] = {"days": days, "logged": len(recent)}
    for key in ("am_done", "pm_done"):
        answered = [entry[key] for entry in recent if entry[key] is not None]
        result[key] = round(100 * _share(answered)) if answered else None
    return result


def _feel_trend(entries: list[dict[str, Any]], today: date) -> dict[str, Any] | None:
    def average(first: int, last: int) -> float | None:
        values = [entry["skin_feel"] for entry in entries
                  if entry["skin_feel"] and first <= (today - _day(entry["date"])).days <= last]
        return round(mean(values), 1) if len(values) >= MIN_GROUP else None

    this_week, last_week = average(0, 6), average(7, 13)
    if this_week is None:
        return None
    return {"this_week": this_week, "last_week": last_week, "change": None if last_week is None else round(this_week - last_week, 1)}


def _pairs(entries: list[dict[str, Any]], same_day: bool) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """(cause day, outcome day) pairs: the next calendar day, or the same day."""
    by_day = {_day(entry["date"]): entry for entry in entries}
    if same_day:
        return [(entry, entry) for entry in entries]
    return [(entry, by_day[_day(entry["date"]) + timedelta(days=1)]) for entry in entries
            if _day(entry["date"]) + timedelta(days=1) in by_day]


def _compare(pairs, has_cause) -> dict[str, Any] | None:
    """Skin feel and symptom rates on outcome days after days with vs. without the cause."""
    with_cause = [outcome for cause, outcome in pairs if has_cause(cause)]
    without = [outcome for cause, outcome in pairs if not has_cause(cause)]
    feel_with = [outcome["skin_feel"] for outcome in with_cause if outcome["skin_feel"]]
    feel_without = [outcome["skin_feel"] for outcome in without if outcome["skin_feel"]]
    result: dict[str, Any] = {"with_days": len(with_cause), "without_days": len(without), "feel_gap": None, "symptoms": {}}
    if len(feel_with) >= MIN_GROUP and len(feel_without) >= MIN_GROUP:
        result["feel_with"], result["feel_without"] = round(mean(feel_with), 1), round(mean(feel_without), 1)
        result["feel_gap"] = round(mean(feel_without) - mean(feel_with), 1)  # > 0: worse with the cause
    if len(with_cause) >= MIN_GROUP and len(without) >= MIN_GROUP:
        for key in SYMPTOMS:
            rate_with = _share([key in outcome["symptoms"] for outcome in with_cause])
            rate_without = _share([key in outcome["symptoms"] for outcome in without])
            result["symptoms"][key] = (round(rate_with, 2), round(rate_without, 2))
    return result


def _percent(value: float) -> str:
    return f"%{round(100 * value)}"


def _trigger_insights(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    insights = []
    for key, label in TRIGGERS.items():
        same_day = key in SAME_DAY_TRIGGERS
        when = "olduğu günlerde" if same_day else "olan günlerin ertesinde"
        comparison = _compare(_pairs(entries, same_day), lambda entry, key=key: key in entry["triggers"])
        if not comparison:
            continue
        evidence = {"with_days": comparison["with_days"], "without_days": comparison["without_days"]}
        gap = comparison["feel_gap"]
        if gap is not None and gap >= FEEL_GAP:
            insights.append({
                "kind": "trigger", "key": key, "tone": "warn", "title": label, "strength": gap,
                "text": f"“{label}” {when} cildinizi ortalama {gap:.1f} puan daha kötü değerlendirmişsiniz "
                        f"({comparison['feel_with']} / 5, diğer günlerde {comparison['feel_without']} / 5).",
                "evidence": evidence,
            })
        for symptom, (rate_with, rate_without) in comparison["symptoms"].items():
            if rate_with - rate_without >= RATE_GAP:
                insights.append({
                    "kind": "trigger", "key": key, "tone": "warn", "title": f"{label} → {SYMPTOMS[symptom].lower()}", "strength": rate_with - rate_without,
                    "text": f"“{label}” {when} “{SYMPTOMS[symptom].lower()}” {_percent(rate_with)} oranında görülmüş; diğer günlerde {_percent(rate_without)}.",
                    "evidence": evidence,
                })
    return insights


def _active_insights(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Irritation or dryness the morning after an evening active, compared with evenings without it."""
    pairs = _pairs(entries, same_day=False)
    actives = sorted({active for entry in entries for active in entry["actives"]})
    insights = []
    for active in actives:
        comparison = _compare(pairs, lambda entry, active=active: active in entry["actives"])
        for symptom in ("irritation", "dryness"):
            rate_with, rate_without = comparison["symptoms"].get(symptom, (0.0, 0.0))
            if rate_with - rate_without >= RATE_GAP:
                insights.append({
                    "kind": "active", "key": active, "tone": "warn", "title": f"{active} sonrası {SYMPTOMS[symptom].lower()}", "strength": rate_with - rate_without,
                    "text": f"{active} kullandığınız akşamların ertesinde “{SYMPTOMS[symptom].lower()}” {_percent(rate_with)} oranında görülmüş "
                            f"(diğer günlerde {_percent(rate_without)}). Sıklığı azaltmayı veya nemlendiriciyle tamponlamayı düşünebilirsiniz.",
                    "evidence": {"with_days": comparison["with_days"], "without_days": comparison["without_days"]},
                })
    return insights


def _routine_insight(entries: list[dict[str, Any]]) -> dict[str, Any] | None:
    comparison = _compare(_pairs(entries, same_day=False), lambda entry: entry["pm_done"] is True)
    gap = comparison["feel_gap"]
    if gap is None or -gap < FEEL_GAP:
        return None
    return {
        "kind": "routine", "key": "pm_done", "tone": "good", "title": "Akşam rutini işe yarıyor gibi", "strength": -gap,
        "text": f"Akşam rutininizi yaptığınız günlerin ertesinde cildinizi ortalama {-gap:.1f} puan daha iyi değerlendirmişsiniz "
                f"({comparison['feel_with']} / 5, atladığınız günlerin ertesinde {comparison['feel_without']} / 5).",
        "evidence": {"with_days": comparison["with_days"], "without_days": comparison["without_days"]},
    }


def _score_insight(entries: list[dict[str, Any]], records: list[Any]) -> dict[str, Any] | None:
    """Evening adherence between the last two saved analyses, next to the Skin Score change."""
    scored = [record for record in records if record.overall_score is not None]
    if len(scored) < 2:
        return None
    first, last = scored[-2], scored[-1]
    start, end = first.created_at[:10], last.created_at[:10]
    between = [entry["pm_done"] for entry in entries if start <= entry["date"] <= end and entry["pm_done"] is not None]
    if len(between) < 5:
        return None
    change = last.overall_score - first.overall_score
    return {
        "kind": "score", "key": "score", "tone": "good" if change > 0 else "info", "title": "Rutin uyumu ve Cilt Skoru", "strength": 0,
        "text": f"Son iki analiziniz arasında akşam rutinine uyumunuz {_percent(_share(between))}; Cilt Skorunuz bu sürede "
                f"{'+' if change > 0 else ''}{change} puan değişti.",
        "evidence": {"with_days": len(between), "without_days": 0},
    }


def build_insights(entries: list[dict[str, Any]], records: list[Any], today: date | None = None) -> dict[str, Any]:
    today = today or date.today()
    window = [entry for entry in entries if (today - _day(entry["date"])).days < INSIGHT_WINDOW_DAYS]
    logged = len(window)
    summary = {
        "streak": streak(entries, today),
        "adherence": adherence(entries, today),
        "routine": routine_streak(entries, today),
        "feel": _feel_trend(entries, today),
        "logged_days": logged,
        "needed_days": max(0, MIN_DAYS_FOR_INSIGHTS - logged),
        "insights": [],
        "disclaimer": DISCLAIMER,
    }
    if logged < MIN_DAYS_FOR_INSIGHTS:
        return summary
    insights = _trigger_insights(window) + _active_insights(window)
    insights.sort(key=lambda item: -item["strength"])
    for extra in (_routine_insight(window), _score_insight(window, records)):
        if extra:
            insights.append(extra)
    summary["insights"] = insights[:8]
    return summary
