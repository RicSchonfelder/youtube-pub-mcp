import json
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials as OAuthCredentials
from google_auth_oauthlib.flow import InstalledAppFlow

load_dotenv()

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtubepartner",
]

CHANNELS_DIR = Path.home() / ".youtube-pub-mcp" / "channels"


def _ensure_channel_dir(channel_id: str) -> Path:
    path = CHANNELS_DIR / channel_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def _build_credentials(
    token_data: dict[str, object] | None,
) -> OAuthCredentials | None:
    try:
        # google.oauth2.credentials.Credentials.from_authorized_user_info avoids
        # requiring the legacy JSON file path. We fall back when needed.
        return OAuthCredentials.from_authorized_user_info(token_data, SCOPES)
    except Exception:
        return None


def _save_token(channel_id: str, creds: OAuthCredentials) -> None:
    token_path = _ensure_channel_dir(channel_id) / "token.json"
    token_data = json.loads(creds.to_json())
    with open(token_path, "w", encoding="utf-8") as f:
        json.dump(token_data, f, indent=2)


def get_credentials(channel_id: str, *, _no_refresh: bool = False) -> Optional[OAuthCredentials]:
    """Return cached and refreshed credentials for `channel_id`, or None.

    `_no_refresh` skips the network refresh step; intended for tests/mocks.
    """
    token_path = _ensure_channel_dir(channel_id) / "token.json"
    if not token_path.exists():
        return None
    with open(token_path, "r", encoding="utf-8") as f:
        token_data = json.load(f)
    creds = _build_credentials(token_data)
    if creds is None:
        return None
    if not _no_refresh and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        _save_token(channel_id, creds)
    return creds


def authenticate(
    channel_id: str,
    client_secret_path: str | os.PathLike[str] | None = None,
) -> OAuthCredentials:
    """Run local OAuth flow and persist token."""
    if client_secret_path is None:
        client_secret_path = os.getenv("YT_CLIENT_SECRET", "client_secret.json")
    flow = InstalledAppFlow.from_client_secrets_file(str(client_secret_path), SCOPES)
    creds = flow.run_local_server(port=0)
    _save_token(channel_id, creds)
    return creds


def list_channels() -> list[str]:
    if not CHANNELS_DIR.exists():
        return []
    return [d.name for d in CHANNELS_DIR.iterdir() if d.is_dir()]


def revoke_channel(channel_id: str) -> None:
    path = CHANNELS_DIR / channel_id
    if path.exists():
        import shutil

        shutil.rmtree(path)
