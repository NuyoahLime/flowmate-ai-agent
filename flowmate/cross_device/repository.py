from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

from flowmate.cross_device.errors import (
    CrossDeviceAuthorizationError,
    CrossDeviceConflictError,
    CrossDeviceNotFoundError,
)
from flowmate.cross_device.models import (
    Device,
    DeviceCapability,
    DeviceStatus,
    DeviceType,
    Handoff,
    HandoffContext,
    HandoffStatus,
    TaskDeviceState,
    User,
)
from flowmate.persistence.database import initialize_schema, resolve_database_path


def utc_now() -> datetime:
    return datetime.now(UTC)


def dump_datetime(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def load_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class SQLiteCrossDeviceRepository:
    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = resolve_database_path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection:
            with connection:
                initialize_schema(connection)

    def save_user(self, user: User) -> User:
        with closing(self._connect()) as connection:
            with connection:
                connection.execute(
                    """
                    INSERT INTO users (user_id, display_name, created_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET display_name = excluded.display_name
                    """,
                    (user.id, user.display_name, dump_datetime(user.created_at)),
                )
        return self.get_user(user.id)  # type: ignore[return-value]

    def get_user(self, user_id: str) -> User | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM users WHERE user_id = ?", (user_id,)
            ).fetchone()
        if row is None:
            return None
        return User(
            id=row["user_id"],
            display_name=row["display_name"],
            created_at=load_datetime(row["created_at"]),
        )

    def save_device(
        self,
        device: Device,
        capabilities: Iterable[DeviceCapability],
    ) -> Device:
        with closing(self._connect()) as connection:
            with connection:
                existing = connection.execute(
                    "SELECT user_id FROM devices WHERE device_id = ?", (device.id,)
                ).fetchone()
                if existing is not None and existing["user_id"] != device.user_id:
                    raise CrossDeviceAuthorizationError(
                        "An existing device cannot be reassigned to another user."
                    )
                connection.execute(
                    """
                    INSERT INTO devices (
                        device_id, user_id, device_type, display_name,
                        status, last_seen_at, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(device_id) DO UPDATE SET
                        device_type = excluded.device_type,
                        display_name = excluded.display_name
                    """,
                    (
                        device.id,
                        device.user_id,
                        device.device_type.value,
                        device.display_name,
                        device.status.value,
                        dump_datetime(device.last_seen_at) if device.last_seen_at else None,
                        dump_datetime(device.created_at),
                    ),
                )
                for capability in capabilities:
                    connection.execute(
                        """
                        INSERT INTO device_capabilities (device_id, capability, enabled)
                        VALUES (?, ?, 1)
                        ON CONFLICT(device_id, capability) DO UPDATE SET enabled = 1
                        """,
                        (device.id, capability.value),
                    )
        return self.get_device(device.id)  # type: ignore[return-value]

    def get_device(self, device_id: str) -> Device | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM devices WHERE device_id = ?", (device_id,)
            ).fetchone()
            if row is None:
                return None
            capabilities = connection.execute(
                """
                SELECT capability FROM device_capabilities
                WHERE device_id = ? AND enabled = 1
                ORDER BY capability
                """,
                (device_id,),
            ).fetchall()
        return self._device_from_row(row, capabilities)

    def list_user_devices(self, user_id: str) -> list[Device]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT device_id FROM devices WHERE user_id = ? ORDER BY device_id",
                (user_id,),
            ).fetchall()
        return [device for row in rows if (device := self.get_device(row["device_id"]))]

    def heartbeat(self, device_id: str, *, seen_at: datetime) -> Device:
        with closing(self._connect()) as connection:
            with connection:
                cursor = connection.execute(
                    """
                    UPDATE devices SET status = ?, last_seen_at = ?
                    WHERE device_id = ?
                    """,
                    (DeviceStatus.ONLINE.value, dump_datetime(seen_at), device_id),
                )
                if cursor.rowcount != 1:
                    raise CrossDeviceNotFoundError("Device not found.")
        return self.get_device(device_id)  # type: ignore[return-value]

    def mark_offline(self, device_id: str) -> Device:
        with closing(self._connect()) as connection:
            with connection:
                cursor = connection.execute(
                    "UPDATE devices SET status = ? WHERE device_id = ?",
                    (DeviceStatus.OFFLINE.value, device_id),
                )
                if cursor.rowcount != 1:
                    raise CrossDeviceNotFoundError("Device not found.")
        return self.get_device(device_id)  # type: ignore[return-value]

    def create_task_device_state(
        self,
        *,
        task_id: str,
        owner_user_id: str,
        origin_device_id: str,
        now: datetime,
    ) -> TaskDeviceState:
        with closing(self._connect()) as connection:
            try:
                with connection:
                    connection.execute(
                        """
                        INSERT INTO task_device_state (
                            task_id, owner_user_id, origin_device_id,
                            current_device_id, version, updated_at
                        ) VALUES (?, ?, ?, ?, 1, ?)
                        """,
                        (
                            task_id,
                            owner_user_id,
                            origin_device_id,
                            origin_device_id,
                            dump_datetime(now),
                        ),
                    )
            except sqlite3.IntegrityError as exc:
                existing = self.get_task_device_state(task_id)
                if existing is not None:
                    return existing
                raise CrossDeviceConflictError(
                    "Task device state violates persistence integrity."
                ) from exc
        return self.get_task_device_state(task_id)  # type: ignore[return-value]

    def get_task_device_state(self, task_id: str) -> TaskDeviceState | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM task_device_state WHERE task_id = ?", (task_id,)
            ).fetchone()
        return self._state_from_row(row) if row is not None else None

    def create_handoff(
        self,
        handoff: Handoff,
        *,
        expected_version: int,
        now: datetime,
    ) -> Handoff:
        with closing(self._connect()) as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                state_row = self._require_state_row(connection, handoff.task_id)
                self._require_version(state_row, expected_version)
                duplicate = connection.execute(
                    """
                    SELECT handoff_id FROM handoffs
                    WHERE task_id = ? AND source_device_id = ?
                      AND target_device_id = ? AND status = ?
                    """,
                    (
                        handoff.task_id,
                        handoff.source_device_id,
                        handoff.target_device_id,
                        HandoffStatus.PENDING.value,
                    ),
                ).fetchone()
                if duplicate is not None:
                    raise CrossDeviceConflictError("A matching pending handoff already exists.")
                next_version = expected_version + 1
                connection.execute(
                    """
                    INSERT INTO handoffs (
                        handoff_id, task_id, user_id, source_device_id,
                        target_device_id, required_capability, status, context_json,
                        created_at, accepted_at, rejected_at, cancelled_at, task_version
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, ?)
                    """,
                    (
                        handoff.id,
                        handoff.task_id,
                        handoff.user_id,
                        handoff.source_device_id,
                        handoff.target_device_id,
                        handoff.required_capability.value,
                        HandoffStatus.PENDING.value,
                        json.dumps(handoff.context.model_dump(mode="json"), ensure_ascii=False),
                        dump_datetime(now),
                        next_version,
                    ),
                )
                self._update_state_version(
                    connection,
                    handoff.task_id,
                    expected_version=expected_version,
                    next_version=next_version,
                    now=now,
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return self.get_handoff(handoff.id)  # type: ignore[return-value]

    def accept_handoff(
        self,
        handoff_id: str,
        *,
        expected_version: int,
        now: datetime,
    ) -> tuple[Handoff, TaskDeviceState, bool]:
        with closing(self._connect()) as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                row = self._require_handoff_row(connection, handoff_id)
                if row["status"] == HandoffStatus.ACCEPTED.value:
                    connection.commit()
                    handoff = self._handoff_from_row(row)
                    state = self._state_from_row(
                        self._require_state_row(connection, row["task_id"])
                    )
                    return handoff, state, False
                if row["status"] != HandoffStatus.PENDING.value:
                    raise CrossDeviceConflictError("Only a pending handoff can be accepted.")
                state_row = self._require_state_row(connection, row["task_id"])
                self._require_version(state_row, expected_version)
                next_version = expected_version + 1
                connection.execute(
                    """
                    UPDATE handoffs
                    SET status = ?, accepted_at = ?, task_version = ?
                    WHERE handoff_id = ?
                    """,
                    (
                        HandoffStatus.ACCEPTED.value,
                        dump_datetime(now),
                        next_version,
                        handoff_id,
                    ),
                )
                cursor = connection.execute(
                    """
                    UPDATE task_device_state
                    SET current_device_id = ?, version = ?, updated_at = ?
                    WHERE task_id = ? AND version = ?
                    """,
                    (
                        row["target_device_id"],
                        next_version,
                        dump_datetime(now),
                        row["task_id"],
                        expected_version,
                    ),
                )
                if cursor.rowcount != 1:
                    raise CrossDeviceConflictError("Task version conflict.")
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return (
            self.get_handoff(handoff_id),  # type: ignore[arg-type]
            self.get_task_device_state(row["task_id"]),  # type: ignore[arg-type]
            True,
        )

    def close_handoff(
        self,
        handoff_id: str,
        *,
        expected_version: int,
        status: HandoffStatus,
        now: datetime,
    ) -> tuple[Handoff, TaskDeviceState]:
        if status not in {HandoffStatus.REJECTED, HandoffStatus.CANCELLED}:
            raise ValueError("close_handoff only supports REJECTED or CANCELLED.")
        timestamp_column = "rejected_at" if status == HandoffStatus.REJECTED else "cancelled_at"
        with closing(self._connect()) as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                row = self._require_handoff_row(connection, handoff_id)
                if row["status"] == status.value:
                    connection.commit()
                    return self._handoff_from_row(row), self._state_from_row(
                        self._require_state_row(connection, row["task_id"])
                    )
                if row["status"] != HandoffStatus.PENDING.value:
                    raise CrossDeviceConflictError("Only a pending handoff can be closed.")
                state_row = self._require_state_row(connection, row["task_id"])
                self._require_version(state_row, expected_version)
                next_version = expected_version + 1
                connection.execute(
                    f"""
                    UPDATE handoffs SET status = ?, {timestamp_column} = ?, task_version = ?
                    WHERE handoff_id = ?
                    """,
                    (status.value, dump_datetime(now), next_version, handoff_id),
                )
                self._update_state_version(
                    connection,
                    row["task_id"],
                    expected_version=expected_version,
                    next_version=next_version,
                    now=now,
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return (
            self.get_handoff(handoff_id),  # type: ignore[arg-type]
            self.get_task_device_state(row["task_id"]),  # type: ignore[arg-type]
        )

    def get_handoff(self, handoff_id: str) -> Handoff | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM handoffs WHERE handoff_id = ?", (handoff_id,)
            ).fetchone()
        return self._handoff_from_row(row) if row is not None else None

    def list_handoffs(
        self,
        *,
        task_id: str | None = None,
        target_device_id: str | None = None,
        status: HandoffStatus | None = None,
    ) -> list[Handoff]:
        clauses: list[str] = []
        values: list[str] = []
        if task_id is not None:
            clauses.append("task_id = ?")
            values.append(task_id)
        if target_device_id is not None:
            clauses.append("target_device_id = ?")
            values.append(target_device_id)
        if status is not None:
            clauses.append("status = ?")
            values.append(status.value)
        query = "SELECT * FROM handoffs"
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY created_at DESC, handoff_id DESC"
        with closing(self._connect()) as connection:
            rows = connection.execute(query, values).fetchall()
        return [self._handoff_from_row(row) for row in rows]

    def claim_confirmation(
        self,
        *,
        task_id: str,
        device_id: str,
        expected_version: int,
        confirmed: bool,
        now: datetime,
    ) -> TaskDeviceState:
        with closing(self._connect()) as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                state_row = self._require_state_row(connection, task_id)
                self._require_version(state_row, expected_version)
                device_row = connection.execute(
                    "SELECT user_id FROM devices WHERE device_id = ?", (device_id,)
                ).fetchone()
                if device_row is None:
                    raise CrossDeviceNotFoundError("Device not found.")
                if device_row["user_id"] != state_row["owner_user_id"]:
                    raise CrossDeviceAuthorizationError(
                        "Device does not belong to the task owner."
                    )
                task_row = connection.execute(
                    "SELECT * FROM tasks WHERE task_id = ?", (task_id,)
                ).fetchone()
                if task_row is None:
                    raise CrossDeviceNotFoundError("Task not found.")
                if (
                    task_row["requires_confirmation"] != 1
                    or task_row["confirmation_status"] != "PENDING"
                    or task_row["status"] != "WAITING_CONFIRMATION"
                ):
                    raise CrossDeviceConflictError(
                        "Task no longer has an available confirmation transition."
                    )
                confirmation_status = "CONFIRMED" if confirmed else "REJECTED"
                task_status = "PLANNED" if confirmed else "CANCELLED"
                connection.execute(
                    """
                    UPDATE tasks SET confirmation_status = ?, status = ?, updated_at = ?
                    WHERE task_id = ?
                    """,
                    (confirmation_status, task_status, dump_datetime(now), task_id),
                )
                next_version = expected_version + 1
                self._update_state_version(
                    connection,
                    task_id,
                    expected_version=expected_version,
                    next_version=next_version,
                    now=now,
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return self.get_task_device_state(task_id)  # type: ignore[return-value]

    def count_tasks(self, task_id: str) -> int:
        with closing(self._connect()) as connection:
            return int(
                connection.execute(
                    "SELECT COUNT(*) FROM tasks WHERE task_id = ?", (task_id,)
                ).fetchone()[0]
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @staticmethod
    def _require_state_row(connection: sqlite3.Connection, task_id: str):
        row = connection.execute(
            "SELECT * FROM task_device_state WHERE task_id = ?", (task_id,)
        ).fetchone()
        if row is None:
            raise CrossDeviceNotFoundError("Task device state not found.")
        return row

    @staticmethod
    def _require_handoff_row(connection: sqlite3.Connection, handoff_id: str):
        row = connection.execute(
            "SELECT * FROM handoffs WHERE handoff_id = ?", (handoff_id,)
        ).fetchone()
        if row is None:
            raise CrossDeviceNotFoundError("Handoff not found.")
        return row

    @staticmethod
    def _require_version(state_row, expected_version: int) -> None:
        if state_row["version"] != expected_version:
            raise CrossDeviceConflictError(
                f"Task version conflict: expected {expected_version}, current {state_row['version']}."
            )

    @staticmethod
    def _update_state_version(
        connection: sqlite3.Connection,
        task_id: str,
        *,
        expected_version: int,
        next_version: int,
        now: datetime,
    ) -> None:
        cursor = connection.execute(
            """
            UPDATE task_device_state SET version = ?, updated_at = ?
            WHERE task_id = ? AND version = ?
            """,
            (next_version, dump_datetime(now), task_id, expected_version),
        )
        if cursor.rowcount != 1:
            raise CrossDeviceConflictError("Task version conflict.")

    @staticmethod
    def _device_from_row(row, capability_rows) -> Device:
        return Device(
            id=row["device_id"],
            user_id=row["user_id"],
            device_type=DeviceType(row["device_type"]),
            display_name=row["display_name"],
            status=DeviceStatus(row["status"]),
            last_seen_at=load_datetime(row["last_seen_at"]),
            created_at=load_datetime(row["created_at"]),
            capabilities=[DeviceCapability(item["capability"]) for item in capability_rows],
        )

    @staticmethod
    def _state_from_row(row) -> TaskDeviceState:
        return TaskDeviceState(
            task_id=row["task_id"],
            owner_user_id=row["owner_user_id"],
            origin_device_id=row["origin_device_id"],
            current_device_id=row["current_device_id"],
            version=row["version"],
            updated_at=load_datetime(row["updated_at"]),
        )

    @staticmethod
    def _handoff_from_row(row) -> Handoff:
        return Handoff(
            id=row["handoff_id"],
            task_id=row["task_id"],
            user_id=row["user_id"],
            source_device_id=row["source_device_id"],
            target_device_id=row["target_device_id"],
            required_capability=DeviceCapability(row["required_capability"]),
            status=HandoffStatus(row["status"]),
            context=HandoffContext.model_validate(json.loads(row["context_json"])),
            created_at=load_datetime(row["created_at"]),
            accepted_at=load_datetime(row["accepted_at"]),
            rejected_at=load_datetime(row["rejected_at"]),
            cancelled_at=load_datetime(row["cancelled_at"]),
            task_version=row["task_version"],
        )
