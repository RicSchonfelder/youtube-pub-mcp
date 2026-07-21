from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any
import random
import time

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from youtube_pub_mcp.auth import get_credentials

if TYPE_CHECKING:
    from youtube_pub_mcp.scheduler import Scheduler

UPLOAD_BODY_REQUIRED_SNIPPET_FIELDS = ("title", "description", "tags")


class YouTubeClient:
    def __init__(self, channel_id: str) -> None:
        creds = get_credentials(channel_id)
        if creds is None:
            raise RuntimeError(f"Channel '{channel_id}' not authenticated. Run auth.authenticate() first.")
        self.channel_id = channel_id
        self.service = build("youtube", "v3", credentials=creds)

    def upload(self, file_path: str | Path, title: str, description: str = "",
               tags: list[str] | None = None, category_id: str = "22",
               privacy_status: str = "private", publish_at: str | None = None,
               notify_subscribers: bool = True) -> dict[str, Any]:
        """Upload a video.

        When ``publish_at`` is provided, ``privacy_status`` cannot be
        ``private`` schedules are only supported for private videos on
        YouTube Data API v3. A mismatch is coerced to ``private`` to avoid
        API errors while preserving the provided schedule.
        """
        if publish_at:
            effective_privacy = (
                privacy_status if privacy_status == "private" else "private"
            )
            privacy_status = effective_privacy

        body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": tags or [],
                "categoryId": category_id,
            },
            "status": {
                "privacyStatus": privacy_status,
                "selfDeclaredMadeForKids": False,
            },
        }
        if publish_at:
            body["status"]["publishAt"] = publish_at
        self._log_quota_reserve()
        media = MediaFileUpload(str(file_path), chunksize=-1, resumable=True)
        request = self.service.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media,
            notifySubscribers=notify_subscribers,
        )
        response = self._execute_with_retry(request)
        return response

    def publish_draft(self, draft_id: str, privacy_status: str = "public",
                      publish_at: str | None = None) -> dict[str, Any]:
        body: dict[str, Any] = {
            "id": draft_id,
            "status": {"privacyStatus": privacy_status},
        }
        if publish_at and privacy_status == "private":
            body["status"]["publishAt"] = publish_at
        self._log_quota_reserve()
        request = self.service.videos().update(part="status", body=body)
        return self._execute_with_retry(request)

    def upload_thumbnail(
        self, video_id: str, file_path: str | Path
    ) -> dict[str, Any]:
        """Upload or replace a custom thumbnail for a video."""
        media = MediaFileUpload(str(file_path), chunksize=-1, resumable=False)
        request = self.service.thumbnails().set(
            videoId=video_id,
            media_body=media,
        )
        return self._execute_with_retry(request)

    def list_drafts(self, *, max_results: int = 50) -> list[dict[str, Any]]:
        """List best-effort non-public videos for the authenticated channel.

        YouTube Data API v3 does not expose drafts directly; this returns
        private/unlisted videos for the channel after shading the upload list.
        """
        channel_info = (
            self.service.channels()
            .list(mine=True, part="contentDetails,id,snippet")
            .execute()
            .get("items", [{}])[0]
        )
        channel_id = channel_info.get("id", self.channel_id)
        response = (
            self.service.videos()
            .list(mine=True, part="snippet,status", maxResults=max_results, myRating="none")
            .execute()
        )
        return [video for video in response.get("items", []) if video.get("status", {}).get("privacyStatus") != "public"]

    def get_quota(self) -> dict[str, Any]:
        """Return the quota model for the authenticated channel.

        Quota consumed and remaining are not exposed by the Data API, so this
        is treated as a local artifact until persisted quota counters are
        integrated.
        """
        return {
            "channel_id": self.channel_id,
            "limit": 10_000,
            "unit": "units/day",
            "used": None,
            "remaining": None,
        }

    def _execute_with_retry(
        self, request: Any, *, max_attempts: int = 3, base_delay: float = 1.5
    ) -> dict[str, Any]:
        attempts = 0
        while True:
            try:
                return request.execute()
            except HttpError as exc:
                status_code = exc.resp.status if exc.resp else None
                if status_code and status_code >= 500 and attempts < max_attempts - 1:
                    attempts += 1
                    delay = base_delay * (2 ** (attempts - 1)) + random.uniform(0, 0.5)
                    time.sleep(delay)
                    continue
                raise
            except OSError as exc:
                if attempts < max_attempts - 1:
                    attempts += 1
                    time.sleep(base_delay * (2 ** (attempts - 1)))
                    continue
                raise

    def _log_quota_reserve(self) -> None:
        # Hook for future integration with Scheduler-backed quota counters.
        return None
