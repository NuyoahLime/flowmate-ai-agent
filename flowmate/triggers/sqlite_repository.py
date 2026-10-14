from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from flowmate.persistence.database import initialize_schema, resolve_database_path
from flowmate.persistence.errors import PersistenceIntegrityError
from flowmate.persistence.sqlite_repository import save_task_aggregate
from flowmate.schemas import Task, TriggerDefinition, TriggerStatus, TriggerType
from flowmate.triggers.errors import TriggerPersistenceError


class SQLiteTriggerRepository:
    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = resolve_database_path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection:
            with connection:
                initialize_schema(connection)

    def save(self, trigger: TriggerDefinition) -> None:
        try:
            with closing(self._connect()) as connection:
                with connection:
                    self._save_trigger(connection, trigger)
        except sqlite3.IntegrityError as exc:
            raise TriggerPersistenceError("Trigger violates persistence integrity.") from exc

    def get(self, trigger_id: str) -> TriggerDefinition | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM triggers WHERE trigger_id = ?",
                (trigger_id,),
            ).fetchone()
        return self._trigger_from_row(row) if row is not None else None

    def get_by_source_event_id(self, source_event_id: str) -> TriggerDefinition | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM triggers WHERE source_event_id = ? ORDER BY created_at DESC LIMIT 1",
                (source_event_id,),
            ).fetchone()
        return self._trigger_from_row(row) if row is not None else None

    def list_active(self) -> list[TriggerDefinition]:
        return self.list_triggers(status=TriggerStatus.ACTIVE, limit=1000)

    def list_due(self, *, now: datetime) -> list[TriggerDefinition]:
        if now.tzinfo is None:
            raise TriggerPersistenceError("Due trigger query requires timezone-aware now.")
        return [
            trigger
            for trigger in self.list_active()
            if trigger.trigger_at <= now.astimezone(trigger.source_event_start.tzinfo)
            < trigger.source_event_start
        ]

    def list_triggers(
        self,
        *,
        status: TriggerStatus | None = None,
        limit: int = 50,
    ) -> list[TriggerDefinition]:
        if limit <= 0:
            return []
        query = "SELECT * FROM triggers"
        params: tuple = ()
        if status is not None:
            query += " WHERE status = ?"
            params = (status.value,)
        query += " ORDER BY source_event_start ASC, trigger_id ASC LIMIT ?"
        params = (*params, limit)
        with closing(self._connect()) as connection:
            rows = connection.execute(query, params).fetchall()
        return [self._trigger_from_row(row) for row in rows]

    def mark_evaluated(self, trigger_id: str, *, evaluated_at: datetime) -> None:
        with closing(self._connect()) as connection:
            with connection:
                connection.execute(
                    "UPDATE triggers SET last_evaluated_at = ? WHERE trigger_id = ?",
                    (_dump_datetime(evaluated_at), trigger_id),
                )

    def mark_expired(self, trigger_id: str, *, expired_at: datetime) -> None:
        with closing(self._connect()) as connection:
            with connection:
                connection.execute(
                    """
                    UPDATE triggers
                    SET status = ?, last_evaluated_at = ?
                    WHERE trigger_id = ? AND status = ?
                    """,
                    (
                        TriggerStatus.EXPIRED.value,
                        _dump_datetime(expired_at),
                        trigger_id,
                        TriggerStatus.ACTIVE.value,
                    ),
                )

    def fire_with_task(
        self,
        trigger: TriggerDefinition,
        task: Task,
        *,
        fired_at: datetime,
    ) -> None:
        try:
            with closing(self._connect()) as connection:
                with connection:
                    save_task_aggregate(connection, task, now=_dump_datetime(fired_at))
                    cursor = connection.execute(
                        """
                        UPDATE triggers
                        SET status = ?,
                            last_evaluated_at = ?,
                            fired_at = ?,
                            generated_task_id = ?
                        WHERE trigger_id = ? AND status = ?
                        """,
                        (
                            TriggerStatus.FIRED.value,
                            _dump_datetime(fired_at),
                            _dump_datetime(fired_at),
                            task.id,
                            trigger.id,
                            TriggerStatus.ACTIVE.value,
                        ),
                    )
                    if cursor.rowcount != 1:
                        raise TriggerPersistenceError(
                            "Trigger was not ACTIVE when attempting to fire."
                        )
        except sqlite3.IntegrityError as exc:
            raise PersistenceIntegrityError("Task and trigger fire transaction failed.") from exc

    def _save_trigger(self, connection: sqlite3.Connection, trigger: TriggerDefinition) -> None:
        connection.execute(
            """
            INSERT INTO triggers (
                trigger_id, trigger_type, status, source_event_id,
                source_event_start, source_event_location, source_event_summary,
                lead_time_minutes, created_at, last_evaluated_at,
                fired_at, generated_task_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(trigger_id) DO UPDATE SET
                trigger_type = excluded.trigger_type,
                status = excluded.status,
                source_event_id = excluded.source_event_id,
                source_event_start = excluded.source_event_start,
                source_event_location = excluded.source_event_location,
                source_event_summary = excluded.source_event_summary,
                lead_time_minutes = excluded.lead_time_minutes,
                last_evaluated_at = excluded.last_evaluated_at,
                fired_at = excluded.fired_at,
                generated_task_id = excluded.generated_task_id
            """,
            (
                trigger.id,
                trigger.trigger_type.value,
                trigger.status.value,
                trigger.source_event_id,
                _dump_datetime(trigger.source_event_start),
                trigger.source_event_location,
                trigger.source_event_summary,
                trigger.lead_time_minutes,
                _dump_datetime(trigger.created_at),
                _dump_optional_datetime(trigger.last_evaluated_at),
                _dump_optional_datetime(trigger.fired_at),
                trigger.generated_task_id,
            ),
        )

    def _trigger_from_row(self, row) -> TriggerDefinition:
        try:
            return TriggerDefinition(
                id=row["trigger_id"],
                trigger_type=TriggerType(row["trigger_type"]),
                status=TriggerStatus(row["status"]),
                source_event_id=row["source_event_id"],
                source_event_start=_load_datetime(row["source_event_start"]),
                source_event_location=row["source_event_location"],
                source_event_summary=row["source_event_summary"],
                lead_time_minutes=row["lead_time_minutes"],
                created_at=_load_datetime(row["created_at"]),
                last_evaluated_at=_load_optional_datetime(row["last_evaluated_at"]),
                fired_at=_load_optional_datetime(row["fired_at"]),
                generated_task_id=row["generated_task_id"],
            )
        except (ValueError, TypeError, ValidationError) as exc:
            raise TriggerPersistenceError("Stored trigger is invalid.") from exc

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection


def _dump_datetime(value: datetime) -> str:
    if value.tzinfo is None:
        raise TriggerPersistenceError("Trigger datetime must be timezone-aware.")
    return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _dump_optional_datetime(value: datetime | None) -> str | None:
    return _dump_datetime(value) if value is not None else None


def _load_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _load_optional_datetime(value: str | None) -> datetime | None:
    return _load_datetime(value) if value is not None else None
