from __future__ import annotations

import os
from pathlib import Path

from flowmate.persistence.errors import PersistenceConfigurationError


SCHEMA_VERSION = 3
DEFAULT_DB_PATH = Path("data") / "flowmate.db"


def resolve_database_path(db_path: str | Path | None = None) -> Path:
    configured = db_path if db_path is not None else os.getenv("FLOWMATE_DB_PATH")
    path = Path(configured) if configured else DEFAULT_DB_PATH
    if not path.name:
        raise PersistenceConfigurationError("FLOWMATE_DB_PATH must point to a file.")
    return path


def initialize_schema(connection) -> None:
    connection.execute("PRAGMA foreign_keys = ON")
    current_version = connection.execute("PRAGMA user_version").fetchone()[0]
    if current_version < 1:
        _migrate_to_v1(connection)
    if current_version < 2:
        _migrate_to_v2(connection)
    if current_version < 3:
        _migrate_to_v3(connection)
    connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")


def _migrate_to_v1(connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            task_id TEXT PRIMARY KEY,
            user_input TEXT NOT NULL,
            goal TEXT NOT NULL,
            status TEXT NOT NULL,
            risk_level TEXT NOT NULL,
            requires_confirmation INTEGER NOT NULL,
            confirmation_status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS plan_steps (
            task_id TEXT NOT NULL,
            step_id TEXT NOT NULL,
            step_order INTEGER NOT NULL,
            description TEXT NOT NULL,
            tool_name TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY(task_id, step_id),
            FOREIGN KEY(task_id) REFERENCES tasks(task_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS tool_calls (
            task_id TEXT NOT NULL,
            step_id TEXT NOT NULL,
            tool_name TEXT NOT NULL,
            arguments_json TEXT NOT NULL,
            status TEXT NOT NULL,
            result_json TEXT,
            error TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY(task_id, step_id),
            FOREIGN KEY(task_id, step_id)
                REFERENCES plan_steps(task_id, step_id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_tasks_updated_at ON tasks(updated_at);
        CREATE INDEX IF NOT EXISTS idx_plan_steps_task_order
            ON plan_steps(task_id, step_order);
        """
    )


def _migrate_to_v2(connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS triggers (
            trigger_id TEXT PRIMARY KEY,
            trigger_type TEXT NOT NULL,
            status TEXT NOT NULL,
            source_event_id TEXT NOT NULL,
            source_event_start TEXT NOT NULL,
            source_event_location TEXT NOT NULL,
            source_event_summary TEXT,
            lead_time_minutes INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            last_evaluated_at TEXT,
            fired_at TEXT,
            generated_task_id TEXT,
            FOREIGN KEY(generated_task_id) REFERENCES tasks(task_id)
        );

        CREATE UNIQUE INDEX IF NOT EXISTS idx_triggers_unique_active_fired_event
            ON triggers(source_event_id)
            WHERE status IN ('ACTIVE', 'FIRED');

        CREATE INDEX IF NOT EXISTS idx_triggers_status_start
            ON triggers(status, source_event_start);
        """
    )


def _migrate_to_v3(connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            display_name TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS devices (
            device_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            device_type TEXT NOT NULL,
            display_name TEXT NOT NULL,
            status TEXT NOT NULL,
            last_seen_at TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        );

        CREATE TABLE IF NOT EXISTS device_capabilities (
            device_id TEXT NOT NULL,
            capability TEXT NOT NULL,
            enabled INTEGER NOT NULL,
            PRIMARY KEY(device_id, capability),
            FOREIGN KEY(device_id) REFERENCES devices(device_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS task_device_state (
            task_id TEXT PRIMARY KEY,
            owner_user_id TEXT NOT NULL,
            origin_device_id TEXT NOT NULL,
            current_device_id TEXT NOT NULL,
            version INTEGER NOT NULL CHECK(version >= 1),
            updated_at TEXT NOT NULL,
            FOREIGN KEY(task_id) REFERENCES tasks(task_id) ON DELETE CASCADE,
            FOREIGN KEY(owner_user_id) REFERENCES users(user_id),
            FOREIGN KEY(origin_device_id) REFERENCES devices(device_id),
            FOREIGN KEY(current_device_id) REFERENCES devices(device_id)
        );

        CREATE TABLE IF NOT EXISTS handoffs (
            handoff_id TEXT PRIMARY KEY,
            task_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            source_device_id TEXT NOT NULL,
            target_device_id TEXT NOT NULL,
            required_capability TEXT NOT NULL,
            status TEXT NOT NULL,
            context_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            accepted_at TEXT,
            rejected_at TEXT,
            cancelled_at TEXT,
            task_version INTEGER NOT NULL,
            FOREIGN KEY(task_id) REFERENCES tasks(task_id) ON DELETE CASCADE,
            FOREIGN KEY(user_id) REFERENCES users(user_id),
            FOREIGN KEY(source_device_id) REFERENCES devices(device_id),
            FOREIGN KEY(target_device_id) REFERENCES devices(device_id)
        );

        CREATE INDEX IF NOT EXISTS idx_devices_user
            ON devices(user_id, device_type);
        CREATE INDEX IF NOT EXISTS idx_handoffs_task_created
            ON handoffs(task_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_handoffs_target_status
            ON handoffs(target_device_id, status, created_at);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_handoffs_unique_pending_route
            ON handoffs(task_id, source_device_id, target_device_id)
            WHERE status = 'PENDING';
        """
    )
