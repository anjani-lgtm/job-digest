"""Tests for SQLite database operations."""

import sqlite3
from datetime import datetime, timezone

from job_digest.db import (
    get_connection,
    get_top_jobs,
    get_unscored_jobs,
    log_digest,
    save_scores,
    upsert_jobs,
)
from job_digest.models import Job, ScoredJob


def _make_job(company="Acme", title="SWE", location="SF", source="test", sid="1", url="https://x.com") -> Job:
    return Job(
        source=source, source_id=sid, company=company, title=title,
        location=location, url=url, fetched_at=datetime.now(timezone.utc),
    )


def test_upsert_and_dedup(tmp_path):
    conn = get_connection(str(tmp_path / "test.db"))
    jobs = [_make_job(), _make_job()]  # same dedup_key
    assert upsert_jobs(conn, jobs) == 1  # only one inserted
    conn.close()


def test_upsert_different_jobs(tmp_path):
    conn = get_connection(str(tmp_path / "test.db"))
    jobs = [_make_job(title="SWE"), _make_job(title="Data Engineer", sid="2")]
    assert upsert_jobs(conn, jobs) == 2
    conn.close()


def test_get_unscored_jobs(tmp_path):
    conn = get_connection(str(tmp_path / "test.db"))
    upsert_jobs(conn, [_make_job()])
    unscored = get_unscored_jobs(conn)
    assert len(unscored) == 1
    assert unscored[0]["title"] == "SWE"
    conn.close()


def test_save_and_get_top_jobs(tmp_path):
    conn = get_connection(str(tmp_path / "test.db"))
    upsert_jobs(conn, [
        _make_job(title="SWE", sid="1"),
        _make_job(title="Data Eng", sid="2"),
    ])
    unscored = get_unscored_jobs(conn)
    scores = [
        ScoredJob(job_id=unscored[0]["id"], fit_score=90, match_reasons=["a", "b", "c"]),
        ScoredJob(job_id=unscored[1]["id"], fit_score=70, match_reasons=["d", "e", "f"]),
    ]
    save_scores(conn, scores)
    top = get_top_jobs(conn, limit=10)
    assert len(top) == 2
    assert top[0]["fit_score"] >= top[1]["fit_score"]
    conn.close()


def test_log_digest_excludes_sent(tmp_path):
    conn = get_connection(str(tmp_path / "test.db"))
    upsert_jobs(conn, [_make_job()])
    unscored = get_unscored_jobs(conn)
    job_id = unscored[0]["id"]
    save_scores(conn, [ScoredJob(job_id=job_id, fit_score=80, match_reasons=["x"])])
    log_digest(conn, [job_id])
    top = get_top_jobs(conn)
    assert len(top) == 0  # already sent
    conn.close()
