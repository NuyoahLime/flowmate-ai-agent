import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

GOOGLE_CALENDAR_READONLY_SCOPES = (
    "https://www.googleapis.com/auth/calendar.events.readonly",
)


class GoogleCalendarAuthError(Exception):
    pass


class GoogleCalendarConfigurationError(GoogleCalendarAuthError, ValueError):
    pass


@dataclass(frozen=True)
class GoogleCalendarSettings:
    client_secret_file: Path
    token_file: Path
    timezone: str
    calendar_id: str = "primary"

    @classmethod
    def from_env(cls) -> "GoogleCalendarSettings":
        client_secret = os.getenv("GOOGLE_CALENDAR_CLIENT_SECRET_FILE")
        token = os.getenv("GOOGLE_CALENDAR_TOKEN_FILE")
        timezone = os.getenv("GOOGLE_CALENDAR_TIMEZONE")
        calendar_id = os.getenv("GOOGLE_CALENDAR_ID", "primary")

        missing = [
            name
            for name, value in (
                ("GOOGLE_CALENDAR_CLIENT_SECRET_FILE", client_secret),
                ("GOOGLE_CALENDAR_TOKEN_FILE", token),
                ("GOOGLE_CALENDAR_TIMEZONE", timezone),
            )
            if not value
        ]
        if missing:
            raise GoogleCalendarConfigurationError(
                "Missing Google Calendar configuration: " + ", ".join(missing)
            )
        if not calendar_id.strip():
            raise GoogleCalendarConfigurationError(
                "GOOGLE_CALENDAR_ID must not be blank."
            )

        return cls(
            client_secret_file=Path(client_secret),
            token_file=Path(token),
            timezone=timezone,
            calendar_id=calendar_id,
        )


def build_google_calendar_service(
    settings: GoogleCalendarSettings,
    *,
    allow_interactive: bool = False,
) -> Any:
    credentials = _load_credentials(settings.token_file)

    if credentials is not None and credentials.expired and credentials.refresh_token:
        try:
            credentials.refresh(Request())
        except Exception as exc:
            raise GoogleCalendarAuthError(
                "Google Calendar OAuth token refresh failed."
            ) from exc

    if credentials is None or not credentials.valid:
        if not allow_interactive:
            raise GoogleCalendarAuthError(
                "Google Calendar OAuth authorization is required."
            )
        if not settings.client_secret_file.is_file():
            raise GoogleCalendarAuthError(
                "Google Calendar OAuth client secret file is unavailable."
            )
        try:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(settings.client_secret_file),
                GOOGLE_CALENDAR_READONLY_SCOPES,
            )
            credentials = flow.run_local_server(port=0)
        except Exception as exc:
            raise GoogleCalendarAuthError(
                "Google Calendar interactive OAuth authorization failed."
            ) from exc

    _persist_credentials(settings.token_file, credentials)
    try:
        return build(
            "calendar",
            "v3",
            credentials=credentials,
            cache_discovery=False,
        )
    except Exception as exc:
        raise GoogleCalendarAuthError(
            "Google Calendar service construction failed."
        ) from exc


def _load_credentials(token_file: Path) -> Credentials | None:
    if not token_file.is_file():
        return None
    try:
        return Credentials.from_authorized_user_file(
            str(token_file),
            GOOGLE_CALENDAR_READONLY_SCOPES,
        )
    except Exception as exc:
        raise GoogleCalendarAuthError(
            "Google Calendar OAuth token file could not be loaded."
        ) from exc


def _persist_credentials(token_file: Path, credentials: Credentials) -> None:
    try:
        token_file.parent.mkdir(parents=True, exist_ok=True)
        token_file.write_text(credentials.to_json(), encoding="utf-8")
    except Exception as exc:
        raise GoogleCalendarAuthError(
            "Google Calendar OAuth token could not be persisted."
        ) from exc
