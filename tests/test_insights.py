# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Sudem Kırmız
from datetime import date, timedelta
from types import SimpleNamespace

from history.insights import DISCLAIMER, adherence, build_insights, routine_streak, streak

TODAY = date(2026, 10, 25)


def entry(days_ago, feel=None, triggers=(), symptoms=(), actives=(), am=None, pm=None):
    return {"date": (TODAY - timedelta(days=days_ago)).isoformat(), "am_done": am, "pm_done": pm, "skin_feel": feel,
            "triggers": list(triggers), "symptoms": list(symptoms), "actives": list(actives), "note": ""}


def test_streak_and_adherence():
    entries = [entry(0, am=True, pm=True), entry(1, am=True, pm=False), entry(2, am=False, pm=True), entry(4, am=True)]
    assert streak(entries, TODAY) == 3
    # Logged until yesterday still counts, so the streak survives until the evening.
    assert streak(entries[1:], TODAY) == 2
    result = adherence(entries, TODAY)
    assert result["logged"] == 4 and result["am_done"] == 75 and result["pm_done"] == 67


def test_routine_streak_counts_done_days_and_milestones():
    # A logged day with both routines skipped breaks the routine streak even though the journal streak continues.
    entries = [entry(1, am=True), entry(2, pm=True), entry(3, am=True, pm=True), entry(4, am=False, pm=False),
               entry(5, am=True), entry(6, am=True), entry(7, am=True), entry(8, am=True)]
    result = routine_streak(entries, TODAY)
    assert result["current"] == 3 and result["best"] == 4 and result["today_done"] is False
    assert result["reached"] == 3 and result["next"] == 7
    assert [day["am"] for day in result["week"]] == [True, True, False, True, False, True, False]
    assert result["week"][-1]["date"] == TODAY.isoformat()
    # Skipping both yesterday and today ends it.
    assert routine_streak(entries[2:], TODAY)["current"] == 0


def test_too_few_days_gives_no_insights():
    summary = build_insights([entry(i, feel=3) for i in range(4)], [], TODAY)
    assert summary["needed_days"] == 3 and summary["insights"] == [] and summary["disclaimer"] == DISCLAIMER


def test_short_sleep_is_linked_to_worse_next_day():
    # Every third day is short on sleep and the following day feels worse.
    entries = []
    for i in range(18, -1, -1):
        short = i % 3 == 0
        after_short = (i + 1) % 3 == 0
        entries.append(entry(i, feel=2 if after_short else 4, triggers=["short_sleep"] if short else []))
    summary = build_insights(entries, [], TODAY)
    sleep = [item for item in summary["insights"] if item["key"] == "short_sleep"]
    assert sleep and sleep[0]["tone"] == "warn" and "ertesinde" in sleep[0]["text"]
    assert sleep[0]["evidence"]["with_days"] >= 3
    # A trigger that never coincides with bad days produces nothing.
    assert not [item for item in summary["insights"] if item["key"] == "stress"]


def test_retinol_irritation_and_routine_benefit():
    entries = []
    for i in range(20, -1, -1):
        retinol_night = i % 2 == 0
        after_retinol = (i + 1) % 2 == 0
        entries.append(entry(i, feel=3 if after_retinol else 4, pm=True if i % 4 else False,
                             actives=["Retinol"] if retinol_night else [], symptoms=["irritation"] if after_retinol else []))
    summary = build_insights(entries, [], TODAY)
    retinol = [item for item in summary["insights"] if item["kind"] == "active"]
    assert retinol and retinol[0]["key"] == "Retinol" and "kızarma / yanma" in retinol[0]["text"]


def test_period_is_compared_same_day_and_score_link():
    entries = [entry(i, feel=2 if i < 4 else 4, triggers=["period"] if i < 4 else [], pm=True) for i in range(12)]
    records = [SimpleNamespace(overall_score=50, created_at=(TODAY - timedelta(days=11)).isoformat()),
               SimpleNamespace(overall_score=58, created_at=TODAY.isoformat())]
    summary = build_insights(entries, records, TODAY)
    period = [item for item in summary["insights"] if item["key"] == "period"]
    assert period and "olduğu günlerde" in period[0]["text"]
    score = [item for item in summary["insights"] if item["kind"] == "score"]
    assert score and "+8" in score[0]["text"] and "%100" in score[0]["text"]
