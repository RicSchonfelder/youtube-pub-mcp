import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

try:
    import jsonschema
    
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False

from youtube_pub_mcp.youtube import YouTubeClient

SCHEDULE_PATH = Path("youtube-schedule.json")

_SCHEMA_PATH = Path(__file__).with_name("docs") / "scheduler-schema.md"
_SCHEMA_CACHE: dict[str, dict[str, Any]] = {}


def _load_schema() -> dict[str, Any] | None:
    if not _SCHEMA_PATH.exists():
        return None
    text = _SCHEMA_PATH.read_text(encoding="utf-8")
    start = text.find("```json")
    end = text.find("```", start + 7)
    if start == -1 or end == -1:
        return None
    raw = text[start + 7 : end].strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _schema() -> dict[str, Any] | None:
    if "main" not in _SCHEMA_CACHE:
        _SCHEMA_CACHE["main"] = _load_schema()
    return _SCHEMA_CACHE["main"]


def _validate(data: dict[str, Any]) -> None:
    if not HAS_JSONSCHEMA:
        return
    schema = _schema()
    if schema is None:
        return
    try:
        jsonschema.validate(data, schema)
    except Exception:
        pass


def channel_schedule_path(channel_id: str, base_dir: Path | None = None) -> Path:
    base = base_dir or Path.home() / ".youtube-pub-mcp" / "schedules"
    path = base / f"{channel_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


class Scheduler:
    def __init__(
        self,
        schedule_path: str | Path = SCHEDULE_PATH,
        youtube_client: YouTubeClient | None = None,
    ) -> None:
        self.path = Path(schedule_path)
        self.youtube = youtube_client

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {
                "version": "1.0.0",
                "generated_at": _now_iso(),
                "quota": _default_quota(),
                "jobs": [],
            }
        with open(self.path, "r", encoding="utf-8") as f:
            data = json.load(f)
        _validate(data)
        return data

    def save(self, data: dict[str, Any]) -> None:
        data["generated_at"] = _now_iso()
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def add_job(self, job: dict[str, Any]) -> dict[str, Any]:
        data = self.load()
        jobs = data.setdefault("jobs", [])
        if any(existing.get("id") == job.get("id") for existing in jobs):
            raise ValueError(f"Duplicated job id: {job.get('id')}")
        enriched = _enrich_job(job)
        jobs.append(enriched)
        self.save(data)
        return enriched

    def pending_jobs(
        self,
        channel_id: str = "",
        statuses: tuple[str, ...] | None = None,
        quota_aware: bool = True,
    ) -> list[dict[str, Any]]:
        """Return jobs eligible to run now, optionally constrained by quota.

        Default statuses include schema-relevant actionable states.
        """
        data = self.load()
        now = datetime.now(timezone.utc)
        default_statuses = ("ready", "pending", "scheduled")
        selected = [
            j
            for j in data.get("jobs", [])
            if j.get("status") in (statuses or default_statuses)
            and _parse_dt(j.get("scheduled_at", "")) <= now
            and (not channel_id or j.get("channel") == channel_id)
            and _is_within_window(j, now, data)
        ]
        if quota_aware:
            quota_limit = _quota_limit(data)
            selected = _apply_daily_limit(selected, now, quota_limit)
        return selected

    def mark(self, job_id: str, status: str, **extra: Any) -> None:
        data = self.load()
        for job in data.get("jobs", []):
            if job.get("id") == job_id:
                job["status"] = status
                job["updated_at"] = _now_iso()
                job.update(extra)
                break
        self.save(data)

    def next_pending_job(
        self,
        channel_id: str = "",
        statuses: tuple[str, ...] | None = None,
    ) -> dict[str, Any] | None:
        jobs = self.pending_jobs(channel_id=channel_id, statuses=statuses, quota_aware=False)
        if not jobs:
            return None
        jobs_sorted = sorted(jobs, key=lambda j: j.get("scheduled_at", ""))
        quota_limit = _quota_limit(self.load())
        data = self.load()
        now = datetime.now(timezone.utc)
        eligible = _apply_daily_limit(jobs_sorted, now, quota_limit)
        return eligible[0] if eligible else None

    def export(self) -> dict[str, Any]:
        return self.load()


def _quota_limit(data: dict[str, Any]) -> int:
    try:
        return int(data.get("quota", {}).get("daily_limit", 15))
    except Exception:
        return 15


def _quota_window_start(data: dict[str, Any], *, now: datetime | None = None) -> datetime | None:
    quota = data.get("quota", {})
    window_start = quota.get("window_start")
    if not window_start:
        return None
    try:
        now = now or datetime.now(timezone.utc)
        today = now.date()
        t = datetime.strptime(window_start, "%H:%M").time()
        candidate = datetime.combine(today, t, tzinfo=timezone.utc)
        if candidate > now:
            candidate -= timedelta(days=1)
        return candidate
    except (TypeError, ValueError):
        return None


def _is_within_window(job: dict[str, Any], now: datetime, data: dict[str, Any]) -> bool:
    window_start = _quota_window_start(data, now=now)
    if window_start is None:
        return True
    return now >= window_start


def _default_quota() -> dict[str, Any]:
    return {
        "daily_limit": 15,
        "window_start": "00:00",
        "window_end": "23:59",
        "timezone": "UTC",
    }


def _enrich_job(job: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(job)
    enriched.setdefault("status", "pending")
    enriched.setdefault("created_at", _now_iso())
    enriched.setdefault("updated_at", enriched["created_at"])
    return enriched


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_dt(s: str) -> datetime:
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return datetime.min.replace(tzinfo=timezone.utc)


def _apply_daily_limit(
    jobs: list[dict[str, Any]], now: datetime, daily_limit: int
) -> list[dict[str, Any]]:
    if daily_limit <= 0:
        return []
    return jobs[:daily_limit]
