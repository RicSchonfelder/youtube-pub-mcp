import json
from datetime import datetime, timedelta, timezone

import pytest

from youtube_pub_mcp.scheduler import (
    Scheduler,
    _default_quota,
    _enrich_job,
    _is_within_window,
    _now_iso,
    _parse_dt,
    _quota_limit,
)


def _future_iso(delta_minutes: int = 5) -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=delta_minutes)).isoformat()


def _data_factory(quota: dict | None = None) -> dict:
    quota = quota if quota is not None else _default_quota()
    return {"version": "1.0.0", "generated_at": _now_iso(), "quota": quota, "jobs": []}


def _job_factory(
    job_id: str = "job-1",
    job_type: str = "upload",
    status: str = "ready",
    scheduled_at: str | None = None,
    channel: str = "",
):
    scheduled_at = scheduled_at if scheduled_at is not None else _future_iso(-10)
    return {
        "id": job_id,
        "type": job_type,
        "status": status,
        "scheduled_at": scheduled_at,
        "visibility": {"mode": "public"},
        "payload": {"type": job_type, "video": {}, "draft_id": None},
        "channel": channel,
    }


class TestQuotaHelpers:
    def test_default_quota_shape(self):
        quota = _default_quota()
        assert quota["daily_limit"] == 15
        assert "timezone" in quota
        assert "window_start" in quota and "window_end" in quota

    def test_quota_limit_with_valid_data(self):
        data = {"quota": {"daily_limit": 5}}
        assert _quota_limit(data) == 5

    def test_quota_limit_fallback_when_missing_or_invalid(self):
        assert _quota_limit({}) == 15
        assert _quota_limit({"quota": {}}) == 15
        assert _quota_limit({"quota": {"daily_limit": "bad"}}) == 15


class TestParseDatetime:
    def test_parse_iso(self):
        dt = _parse_dt("2026-07-22T09:00:00Z")
        assert dt.tzinfo is not None
        assert dt.year == 2026

    def test_parse_empty_returns_min(self):
        dt = _parse_dt("")
        assert dt == datetime.min.replace(tzinfo=timezone.utc)

    def test_parse_none_returns_min(self):
        assert _parse_dt(None) == datetime.min.replace(tzinfo=timezone.utc)


class TestEnrichJob:
    def test_enriches_defaults(self):
        job = _job_factory()
        enriched = _enrich_job(job)
        assert enriched["status"] == "ready" == job["status"]
        assert "created_at" in enriched
        assert "updated_at" in enriched

    def test_preserves_id(self):
        enriched = _enrich_job({"id": "xyz"})
        assert enriched["id"] == "xyz"


class TestWithinWindow:
    def test_missing_window_allows_job(self):
        data = _data_factory({"daily_limit": 10})
        assert _is_within_window({}, datetime.now(timezone.utc), data) is True

    def test_window_start_allows_after_start(self):
        window_start = (datetime.now(timezone.utc) - timedelta(hours=1)).strftime("%H:%M")
        data = _data_factory({"daily_limit": 10, "window_start": window_start})
        assert _is_within_window({}, datetime.now(timezone.utc), data) is True


class TestPendingJobs:
    def test_empty_schedule_returns_empty(self, tmp_path):
        path = tmp_path / "empty.json"
        scheduler = Scheduler(schedule_path=path)
        assert scheduler.pending_jobs() == []

    def test_only_future_jobs_are_pending(self, tmp_path):
        path = tmp_path / "future-only.json"
        scheduler = Scheduler(schedule_path=path)
        scheduler.save(_data_factory())
        future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        job = _job_factory(scheduled_at=future)
        scheduler.add_job(job)
        assert scheduler.pending_jobs() == []

    def test_ready_job_is_returned(self, tmp_path):
        path = tmp_path / "ready.json"
        scheduler = Scheduler(schedule_path=path)
        scheduler.save(_data_factory())
        job = _job_factory()
        scheduler.add_job(job)
        result = scheduler.pending_jobs()
        assert len(result) == 1 and result[0]["id"] == job["id"]

    def test_channel_filter(self, tmp_path):
        path = tmp_path / "channel.json"
        scheduler = Scheduler(schedule_path=path)
        scheduler.save(_data_factory())
        scheduler.add_job(_job_factory(channel="A"))
        scheduler.add_job(_job_factory(job_id="job-2", channel="B"))
        results = scheduler.pending_jobs(channel_id="A")
        assert [r["id"] for r in results] == ["job-1"]

    def test_daily_limit_limits_selection(self, tmp_path):
        path = tmp_path / "limit.json"
        quota = _default_quota()
        quota["daily_limit"] = 1
        scheduler = Scheduler(schedule_path=path)
        scheduler.save(_data_factory(quota))
        scheduler.add_job(_job_factory(job_id="job-1", status="ready", scheduled_at=_future_iso(-10)))
        scheduler.add_job(_job_factory(job_id="job-2", status="ready", scheduled_at=_future_iso(-10)))
        results = scheduler.pending_jobs()
        assert len(results) == 1

    def test_quota_zero_returns_empty(self, tmp_path):
        path = tmp_path / "quota0.json"
        quota = _default_quota()
        quota["daily_limit"] = 0
        scheduler = Scheduler(schedule_path=path)
        scheduler.save(_data_factory(quota))
        scheduler.add_job(_job_factory())
        assert scheduler.pending_jobs() == []


class TestAddJob:
    def test_add_and_load_roundtrip(self, tmp_path):
        path = tmp_path / "roundtrip.json"
        scheduler = Scheduler(schedule_path=path)
        job = _job_factory()
        saved = scheduler.add_job(job)
        assert saved["id"] == job["id"]
        loaded = scheduler.load()
        assert any(existing["id"] == job["id"] for existing in loaded["jobs"])

    def test_duplicate_job_id_raises(self, tmp_path):
        path = tmp_path / "dup.json"
        scheduler = Scheduler(schedule_path=path)
        scheduler.add_job(_job_factory(job_id="same"))
        with pytest.raises(ValueError):
            scheduler.add_job(_job_factory(job_id="same"))


class TestMark:
    def test_mark_updates_status(self, tmp_path):
        path = tmp_path / "mark.json"
        scheduler = Scheduler(schedule_path=path)
        scheduler.add_job(_job_factory())
        scheduler.mark("job-1", "executing")
        loaded = scheduler.load()
        job = next(j for j in loaded["jobs"] if j["id"] == "job-1")
        assert job["status"] == "executing"
        assert "updated_at" in job
