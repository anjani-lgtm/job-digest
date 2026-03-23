"""Ashby public job board API source."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

from job_digest.config import env_list
from job_digest.models import Job
from job_digest.sources.base import JobSource
from job_digest.utils import RateLimiter, strip_html

log = logging.getLogger(__name__)

_BASE = "https://api.ashbyhq.com/posting-api/job-board/{board}"


class AshbySource(JobSource):
    name = "ashby"

    def __init__(self) -> None:
        self.boards = env_list("ASHBY_BOARDS")
        self._limiter = RateLimiter(calls_per_second=2.0)

    async def fetch(self) -> list[Job]:
        jobs: list[Job] = []
        async with httpx.AsyncClient(timeout=30) as client:
            for board in self.boards:
                try:
                    await self._limiter.acquire()
                    resp = await client.get(_BASE.format(board=board))
                    resp.raise_for_status()
                    data = resp.json()
                    board_jobs = data.get("jobs", [])
                    for item in board_jobs:
                        jobs.append(self._normalize(item, board))
                    log.info("  %s: %d jobs", board, len(board_jobs))
                except Exception:
                    log.warning("  %s: failed (board may not exist)", board)
        return jobs

    def _normalize(self, raw: dict, board: str) -> Job:
        location = raw.get("location", "")
        if isinstance(location, dict):
            location = location.get("name", "")

        posted = None
        if raw.get("publishedAt"):
            try:
                posted = datetime.fromisoformat(raw["publishedAt"].replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pass

        return Job(
            source=self.name,
            source_id=str(raw.get("id", "")),
            company=board,
            title=raw.get("title", ""),
            location=location,
            workplace_type=raw.get("employmentType"),
            department=raw.get("department"),
            description_plain=strip_html(raw.get("descriptionHtml", raw.get("description", ""))),
            url=raw.get("jobUrl", f"https://jobs.ashbyhq.com/{board}/{raw.get('id', '')}"),
            posted_at=posted,
            fetched_at=datetime.now(timezone.utc),
        )
