"""SQLite storage: upsert, dedup, query."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from job_digest.config import env
from job_digest.models import Job, ScoredJob

_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    dedup_key   TEXT UNIQUE NOT NULL,
    source      TEXT NOT NULL,
    source_id   TEXT NOT NULL,
    company     TEXT NOT NULL,
    title       TEXT NOT NULL,
    location    TEXT NOT NULL DEFAULT '',
    workplace_type TEXT,
    department  TEXT,
    description_plain TEXT NOT NULL DEFAULT '',
    url         TEXT NOT NULL,
    posted_at   TEXT,
    fetched_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS scored_jobs (
    job_id        INTEGER PRIMARY KEY REFERENCES jobs(id),
    fit_score     INTEGER NOT NULL,
    match_reasons TEXT NOT NULL DEFAULT '[]',
    scored_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS digest_log (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    sent_at  TEXT NOT NULL,
    job_ids  TEXT NOT NULL DEFAULT '[]'
);
"""


def _connect(db_path: str | None = None) -> sqlite3.Connection:
    path = db_path or env("DB_PATH", "jobs.db")
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(_SCHEMA)
    return conn


def get_connection(db_path: str | None = None) -> sqlite3.Connection:
    return _connect(db_path)


def upsert_jobs(conn: sqlite3.Connection, jobs: list[Job]) -> int:
    """Insert jobs, skipping duplicates. Returns count of new jobs inserted."""
    inserted = 0
    now = datetime.now(timezone.utc).isoformat()
    for job in jobs:
        try:
            conn.execute(
                """INSERT OR IGNORE INTO jobs
                   (dedup_key, source, source_id, company, title, location,
                    workplace_type, department, description_plain, url, posted_at, fetched_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    job.dedup_key,
                    job.source,
                    job.source_id,
                    job.company,
                    job.title,
                    job.location,
                    job.workplace_type,
                    job.department,
                    job.description_plain,
                    job.url,
                    job.posted_at.isoformat() if job.posted_at else None,
                    now,
                ),
            )
            if conn.execute("SELECT changes()").fetchone()[0] > 0:
                inserted += 1
        except sqlite3.Error:
            continue
    conn.commit()
    return inserted


def get_unscored_jobs(conn: sqlite3.Connection) -> list[dict]:
    """Return jobs that haven't been scored yet."""
    rows = conn.execute(
        """SELECT j.* FROM jobs j
           LEFT JOIN scored_jobs s ON j.id = s.job_id
           WHERE s.job_id IS NULL
           ORDER BY j.fetched_at DESC"""
    ).fetchall()
    return [dict(r) for r in rows]


def save_scores(conn: sqlite3.Connection, scores: list[ScoredJob]) -> None:
    now = datetime.now(timezone.utc).isoformat()
    for s in scores:
        conn.execute(
            """INSERT OR REPLACE INTO scored_jobs (job_id, fit_score, match_reasons, scored_at)
               VALUES (?, ?, ?, ?)""",
            (s.job_id, s.fit_score, json.dumps(s.match_reasons), now),
        )
    conn.commit()


def get_top_jobs(conn: sqlite3.Connection, limit: int = 10) -> list[dict]:
    """Top scored jobs not yet sent in a digest."""
    rows = conn.execute(
        """SELECT j.*, s.fit_score, s.match_reasons
           FROM jobs j
           JOIN scored_jobs s ON j.id = s.job_id
           WHERE j.id NOT IN (
               SELECT value FROM digest_log, json_each(digest_log.job_ids)
           )
           ORDER BY s.fit_score DESC
           LIMIT ?""",
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_all_scored_jobs(conn: sqlite3.Connection) -> list[dict]:
    """All scored jobs, ranked by fit_score descending."""
    rows = conn.execute(
        """SELECT j.*, s.fit_score, s.match_reasons
           FROM jobs j
           JOIN scored_jobs s ON j.id = s.job_id
           ORDER BY s.fit_score DESC"""
    ).fetchall()
    return [dict(r) for r in rows]


def log_digest(conn: sqlite3.Connection, job_ids: list[int]) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO digest_log (sent_at, job_ids) VALUES (?, ?)",
        (now, json.dumps(job_ids)),
    )
    conn.commit()
