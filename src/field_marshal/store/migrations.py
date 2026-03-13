"""Schema migrations for the Field Marshal store."""

from __future__ import annotations

import sqlite3


_MIGRATIONS: list[tuple[int, list[str]]] = [
    (
        1,
        [
            """
            CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY,
                task_type TEXT NOT NULL,
                phase TEXT NOT NULL,
                status TEXT NOT NULL,
                priority INTEGER NOT NULL DEFAULT 50,
                assigned_to TEXT,
                input_payload TEXT NOT NULL,
                output_payload TEXT,
                retry_count INTEGER NOT NULL DEFAULT 0,
                max_retries INTEGER NOT NULL DEFAULT 3,
                reason_code TEXT,
                parent_task_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)",
            "CREATE INDEX IF NOT EXISTS idx_tasks_phase ON tasks(phase)",
            """
            CREATE TABLE IF NOT EXISTS artifacts (
                artifact_id TEXT PRIMARY KEY,
                artifact_type TEXT NOT NULL,
                parent_artifact_id TEXT,
                task_id TEXT,
                path TEXT NOT NULL,
                checksum TEXT NOT NULL,
                metadata_json TEXT NOT NULL,
                qa_status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_artifacts_task_id ON artifacts(task_id)",
            """
            CREATE TABLE IF NOT EXISTS events (
                event_id TEXT PRIMARY KEY,
                task_id TEXT,
                event_type TEXT NOT NULL,
                message TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_events_task_id ON events(task_id)",
            """
            CREATE TABLE IF NOT EXISTS review_items (
                review_id TEXT PRIMARY KEY,
                artifact_id TEXT,
                task_id TEXT,
                reason TEXT NOT NULL,
                status TEXT NOT NULL,
                resolution_notes TEXT,
                created_at TEXT NOT NULL
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_review_items_status ON review_items(status)",
            """
            CREATE TABLE IF NOT EXISTS scene_packets (
                scene_id TEXT PRIMARY KEY,
                concept_id TEXT NOT NULL,
                duration_target REAL NOT NULL,
                narration TEXT NOT NULL,
                setting TEXT NOT NULL,
                characters TEXT NOT NULL,
                emotion TEXT NOT NULL,
                start_requirements TEXT NOT NULL,
                end_requirements TEXT NOT NULL,
                forbidden_elements TEXT NOT NULL,
                motion_note TEXT NOT NULL,
                fallback_frame_ids TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS clip_jobs (
                clip_id TEXT PRIMARY KEY,
                scene_id TEXT NOT NULL,
                start_image_id TEXT NOT NULL,
                end_image_id TEXT NOT NULL,
                prompt TEXT NOT NULL,
                duration REAL NOT NULL,
                style_lock TEXT NOT NULL,
                motion_lock TEXT NOT NULL,
                retry_policy TEXT NOT NULL,
                status TEXT NOT NULL,
                output_path TEXT
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_clip_jobs_scene_id ON clip_jobs(scene_id)",
            """
            CREATE TABLE IF NOT EXISTS manifests (
                id TEXT PRIMARY KEY,
                stage TEXT NOT NULL,
                parent_id TEXT,
                inputs_json TEXT NOT NULL,
                outputs_json TEXT NOT NULL,
                params_json TEXT NOT NULL,
                status TEXT NOT NULL,
                qa_json TEXT NOT NULL,
                retry_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """,
        ],
    ),
]


def apply_migrations(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL
        )
        """
    )
    current = _current_version(conn)
    for version, statements in _MIGRATIONS:
        if version <= current:
            continue
        for statement in statements:
            conn.execute(statement)
        conn.execute(
            "INSERT INTO schema_migrations(version, applied_at) VALUES (?, datetime('now'))",
            (version,),
        )


def _current_version(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT COALESCE(MAX(version), 0) AS current_version FROM schema_migrations"
    ).fetchone()
    if row is None:
        return 0
    return int(row["current_version"])
