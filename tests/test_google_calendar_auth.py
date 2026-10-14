from pathlib import Path

import pytest

from flowmate.integrations.calendar import google_auth
from flowmate.integrations.calendar.google_auth import (
    GOOGLE_CALENDAR_READONLY_SCOPES,
    GoogleCalendarAuthError,
    GoogleCalendarConfigurationError,
    GoogleCalendarSettings,
    build_google_calendar_service,
)


class FakeCredentials:
    def __init__(
        self,
        *,
        valid=True,
        expired=False,
        refresh_token=None,
    ):
        self.valid = valid
        self.expired = expired
        self.refresh_token = refresh_token
        self.refresh_calls = 0

    def refresh(self, request):
        self.refresh_calls += 1
        self.valid = True
        self.expired = False

    def to_json(self):
        return '{"token":"sensitive-test-token"}'


def settings(tmp_path: Path) -> GoogleCalendarSettings:
    return GoogleCalendarSettings(
        client_secret_file=tmp_path / "client-secret.json",
        token_file=tmp_path / "token.json",
        timezone="Asia/Shanghai",
        calendar_id="primary",
    )


def test_readonly_scope_contains_no_calendar_write_scope():
    assert GOOGLE_CALENDAR_READONLY_SCOPES == (
        "https://www.googleapis.com/auth/calendar.events.readonly",
    )
    assert "https://www.googleapis.com/auth/calendar.events" not in GOOGLE_CALENDAR_READONLY_SCOPES
    assert "https://www.googleapis.com/auth/calendar" not in GOOGLE_CALENDAR_READONLY_SCOPES


def test_settings_from_env_requires_explicit_secret_token_and_timezone(monkeypatch):
    for name in (
        "GOOGLE_CALENDAR_CLIENT_SECRET_FILE",
        "GOOGLE_CALENDAR_TOKEN_FILE",
        "GOOGLE_CALENDAR_TIMEZONE",
        "GOOGLE_CALENDAR_ID",
    ):
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(GoogleCalendarConfigurationError) as exc_info:
        GoogleCalendarSettings.from_env()

    assert "GOOGLE_CALENDAR_CLIENT_SECRET_FILE" in str(exc_info.value)
    assert "GOOGLE_CALENDAR_TOKEN_FILE" in str(exc_info.value)
    assert "GOOGLE_CALENDAR_TIMEZONE" in str(exc_info.value)


def test_settings_from_env_defaults_calendar_id_to_primary(monkeypatch, tmp_path):
    monkeypatch.setenv("GOOGLE_CALENDAR_CLIENT_SECRET_FILE", str(tmp_path / "secret.json"))
    monkeypatch.setenv("GOOGLE_CALENDAR_TOKEN_FILE", str(tmp_path / "token.json"))
    monkeypatch.setenv("GOOGLE_CALENDAR_TIMEZONE", "Asia/Shanghai")
    monkeypatch.delenv("GOOGLE_CALENDAR_ID", raising=False)

    config = GoogleCalendarSettings.from_env()

    assert config.calendar_id == "primary"
    assert config.timezone == "Asia/Shanghai"


def test_valid_saved_credentials_build_service_and_persist_token(
    monkeypatch,
    tmp_path,
    capsys,
):
    config = settings(tmp_path)
    config.token_file.write_text("{}", encoding="utf-8")
    credentials = FakeCredentials()
    service = object()
    calls = {}
    monkeypatch.setattr(
        google_auth.Credentials,
        "from_authorized_user_file",
        lambda path, scopes: credentials,
    )

    def fake_build(api, version, **kwargs):
        calls.update({"api": api, "version": version, **kwargs})
        return service

    monkeypatch.setattr(google_auth, "build", fake_build)

    result = build_google_calendar_service(config)

    assert result is service
    assert calls["api"] == "calendar"
    assert calls["version"] == "v3"
    assert calls["credentials"] is credentials
    assert calls["cache_discovery"] is False
    assert "sensitive-test-token" not in capsys.readouterr().out


def test_expired_credentials_refresh_when_refresh_token_exists(monkeypatch, tmp_path):
    config = settings(tmp_path)
    config.token_file.write_text("{}", encoding="utf-8")
    credentials = FakeCredentials(valid=False, expired=True, refresh_token="refresh")
    monkeypatch.setattr(
        google_auth.Credentials,
        "from_authorized_user_file",
        lambda path, scopes: credentials,
    )
    monkeypatch.setattr(google_auth, "build", lambda *args, **kwargs: object())

    build_google_calendar_service(config)

    assert credentials.refresh_calls == 1
    assert credentials.valid is True


def test_missing_credentials_require_explicit_interactive_mode(tmp_path):
    with pytest.raises(GoogleCalendarAuthError):
        build_google_calendar_service(settings(tmp_path), allow_interactive=False)


def test_interactive_flow_uses_readonly_scope_and_persists_token(
    monkeypatch,
    tmp_path,
):
    config = settings(tmp_path)
    config.client_secret_file.write_text("{}", encoding="utf-8")
    credentials = FakeCredentials()
    captured = {}

    class FakeFlow:
        def run_local_server(self, port):
            captured["port"] = port
            return credentials

    def fake_from_client_secrets_file(path, scopes):
        captured["path"] = path
        captured["scopes"] = scopes
        return FakeFlow()

    monkeypatch.setattr(
        google_auth.InstalledAppFlow,
        "from_client_secrets_file",
        fake_from_client_secrets_file,
    )
    monkeypatch.setattr(google_auth, "build", lambda *args, **kwargs: object())

    build_google_calendar_service(config, allow_interactive=True)

    assert captured["scopes"] == GOOGLE_CALENDAR_READONLY_SCOPES
    assert captured["port"] == 0
    assert config.token_file.is_file()


def test_token_load_and_service_build_failures_are_wrapped(monkeypatch, tmp_path):
    config = settings(tmp_path)
    config.token_file.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        google_auth.Credentials,
        "from_authorized_user_file",
        lambda path, scopes: (_ for _ in ()).throw(ValueError("secret detail")),
    )

    with pytest.raises(GoogleCalendarAuthError) as load_error:
        build_google_calendar_service(config)

    assert "secret detail" not in str(load_error.value)

    credentials = FakeCredentials()
    monkeypatch.setattr(
        google_auth.Credentials,
        "from_authorized_user_file",
        lambda path, scopes: credentials,
    )
    monkeypatch.setattr(
        google_auth,
        "build",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("auth header")),
    )

    with pytest.raises(GoogleCalendarAuthError) as build_error:
        build_google_calendar_service(config)

    assert "auth header" not in str(build_error.value)
