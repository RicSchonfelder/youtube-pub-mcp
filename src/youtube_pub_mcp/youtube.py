from __future__ import annotations

from pathlib import Path
from typing import Any
import random
import time

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from youtube_pub_mcp.auth import get_credentials

UPLOAD_BODY_REQUIRED_SNIPPET_FIELDS = ("title", "description", "tags")


class YouTubeClient:
    def __init__(self, channel_id: str) -> None:
        creds = get_credentials(channel_id)
        if creds is None:
            raise RuntimeError(
                f"Channel '{channel_id}' not authenticated. Run auth.authenticate() first."
            )
        self.channel_id = channel_id
        self.service = build("youtube", "v3", credentials=creds)

    def upload(
        self,
        path: str | Path,
        title: str,
        description: str = "",
        tags: list[str] | None = None,
        thumbnail_local_path: str | Path | None = None,
        scheduled_at: str | None = None,
        notify_subscribers: bool = False,
        category_id: str = "22",
        privacy_status: str = "private",
    ) -> dict[str, Any]:
        """Upload a video file and optionally attach a thumbnail.

        When ``scheduled_at`` is provided, ``privacy_status`` is coerced to
        ``private`` because YouTube scheduling requires private uploads.
        """
        file_path = Path(path)
        if not file_path.exists():
            raise FileNotFoundError(f"Video file not found: {file_path}")

        if not title or not all(isinstance(t, str) and t for t in (title, description, *(tags or []))):
            raise ValueError("Missing required upload metadata.")

        if scheduled_at:
            effective_privacy = privacy_status if privacy_status == "private" else "private"
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
        if scheduled_at:
            body["status"]["publishAt"] = scheduled_at

        media = MediaFileUpload(str(file_path), chunksize=-1, resumable=True)
        request = self.service.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media,
            notifySubscribers=notify_subscribers,
        )
        response = self._execute_with_retry(request)
        video_id = response.get("id")
        if not video_id:
            raise RuntimeError("Upload response missing video id.")

        if thumbnail_local_path:
            self.set_thumbnail(video_id, thumbnail_local_path)

        return response

    def publish_draft(
        self,
        video_id: str,
        scheduled_at: str | None = None,
        privacy_status: str = "public",
    ) -> dict[str, Any]:
        """Publish or schedule an existing private video."""
        body: dict[str, Any] = {
            "id": video_id,
            "status": {"privacyStatus": privacy_status},
        }
        if scheduled_at and privacy_status == "private":
            body["status"]["publishAt"] = scheduled_at

        request = self.service.videos().update(part="status", body=body)
        return self._execute_with_retry(request)

    def set_thumbnail(self, video_id: str, thumbnail_path: str | Path) -> dict[str, Any]:
        """Upload or replace the custom thumbnail for a video."""
        thumb_path = Path(thumbnail_path)
        if not thumb_path.exists():
            raise FileNotFoundError(f"Thumbnail not found: {thumb_path}")

        media = MediaFileUpload(str(thumb_path), chunksize=-1, resumable=False)
        request = self.service.thumbnails().set(
            videoId=video_id,
            media_body=media,
        )
        return self._execute_with_retry(request)

    def list_drafts(
        self,
        *,
        max_results: int = 50,
        page_token: str | None = None,
    ) -> dict[str, Any]:
        """List non-public videos for the authenticated channel.

        Returns the raw API response including ``items`` and pagination
        metadata. YouTube Data API v3 does not expose drafts directly, so
        this returns private/unlisted videos.
        """
        channel_info = (
            self.service.channels()
            .list(mine=True, part="contentDetails,id,snippet")
            .execute()
            .get("items", [{}])[0]
        )
        channel_id = channel_info.get("id", self.channel_id)
        request = self.service.videos().list(
            mine=True,
            part="snippet,status",
            maxResults=max_results,
            myRating="none",
            pageToken=page_token,
        )
        response = self._execute_with_retry(request)
        response["items"] = [
            video
            for video in response.get("items", [])
            if video.get("status", {}).get("privacyStatus") != "public"
        ]
        return response

    def list_videos(
        self,
        *,
        max_results: int = 50,
        page_token: str | None = None,
    ) -> dict[str, Any]:
        """List videos for the authenticated channel.

        Returns the raw API response including ``items`` and pagination
        metadata for both public and private videos.
        """
        request = self.service.videos().list(
            mine=True,
            part="snippet,status",
            maxResults=max_results,
            myRating="none",
            pageToken=page_token,
        )
        return self._execute_with_retry(request)

    def _execute_with_retry(
        self,
        request: Any,
        *,
        max_attempts: int = 3,
        base_delay: float = 1.5,
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
