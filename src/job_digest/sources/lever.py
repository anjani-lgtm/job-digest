"""Lever Postings API source."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

from job_digest.config import env_list
from job_digest.models import Job
from job_digest.sources.base import JobSource
from job_digest.utils import RateLimiter, strip_html

log = logging.getLogger(__name__)

_BASE = "https://api.lever.co/v0/postings/{company}"


class LeverSource(JobSource):
    name = "lever"

    def __init__(self) -> None:
        self.companies = env_list("LEVER_COMPANIES")
        self._limiter = RateLimiter(calls_per_second=2.0)

    async def fetch(self) -> list[Job]:
        jobs: list[Job] = []
        async with httpx.AsyncClient(timeout=30) as client:
            for company in self.companies:
                try:
                    await self._limiter.acquire()
                    resp = await client.get(_BASE.format(company=company))
                    resp.raise_for_status()
                    items = resp.json()
                    for item in items:
                        jobs.append(self._normalize(item, company))
                    log.info("  %s: %d jobs", company, len(items))
                except Exception:
                    log.warning("  %s: failed (company may not exist)", company)
        return jobs

    def _normalize(self, raw: dict, company: str) -> Job:
        categories = raw.get("categories", {})
        posted = None
        if raw.get("createdAt"):
            posted = datetime.fromtimestamp(raw["createdAt"] / 1000, tz=timezone.utc)

        return Job(
            source=self.name,
            source_id=raw.get("id", ""),
            company=company,
            title=raw.get("text", ""),
            location=categories.get("location", ""),
            workplace_type=categories.get("workplaceType"),
            department=categories.get("department"),
            description_plain=strip_html(raw.get("descriptionPlain", raw.get("description", ""))),
            url=raw.get("hostedUrl", f"https://jobs.lever.co/{company}/{raw.get('id', '')}"),
            posted_at=posted,
            fetched_at=datetime.now(timezone.utc),
        )
