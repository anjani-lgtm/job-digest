"""Greenhouse Job Board API source."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

from job_digest.config import env_list
from job_digest.models import Job
from job_digest.sources.base import JobSource
from job_digest.utils import RateLimiter, strip_html

log = logging.getLogger(__name__)

_BASE = "https://boards-api.greenhouse.io/v1/boards/{board}/jobs"


class GreenhouseSource(JobSource):
    name = "greenhouse"

    def __init__(self) -> None:
        self.boards = env_list("GREENHOUSE_BOARDS")
        self._limiter = RateLimiter(calls_per_second=2.0)

    async def fetch(self) -> list[Job]:
        jobs: list[Job] = []
        async with httpx.AsyncClient(timeout=30) as client:
            for board in self.boards:
                try:
                    await self._limiter.acquire()
                    resp = await client.get(
                        _BASE.format(board=board), params={"content": "true"}
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    for item in data.get("jobs", []):
                        jobs.append(self._normalize(item, board))
                    log.info("  %s: %d jobs", board, len(data.get("jobs", [])))
                except Exception:
                    log.warning("  %s: failed (board may not exist)", board)
        return jobs

    def _normalize(self, raw: dict, board: str) -> Job:
        location = ""
        if raw.get("location"):
            location = raw["location"].get("name", "")

        posted = None
        if raw.get("updated_at"):
            posted = datetime.fromisoformat(raw["updated_at"].replace("Z", "+00:00"))

        departments = raw.get("departments", [])
        dept = departments[0]["name"] if departments else None

        return Job(
            source=self.name,
            source_id=str(raw["id"]),
            company=board,
            title=raw.get("title", ""),
            location=location,
            department=dept,
            description_plain=strip_html(raw.get("content", "")),
            url=raw.get("absolute_url", f"https://boards.greenhouse.io/{board}/jobs/{raw['id']}"),
            posted_at=posted,
            fetched_at=datetime.now(timezone.utc),
        )
