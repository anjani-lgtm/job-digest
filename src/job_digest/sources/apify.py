"""Apify actor runner — primary broad discovery engine."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from apify_client import ApifyClient

from job_digest.config import env
from job_digest.models import Job
from job_digest.sources.base import JobSource
from job_digest.utils import strip_html

log = logging.getLogger(__name__)


class ApifySource(JobSource):
    name = "apify"

    def __init__(self) -> None:
        token = env("APIFY_API_TOKEN")
        self._client = ApifyClient(token) if token else None
        self._actors = {}

        # ATS-specific actors
        for key, env_key in [
            ("greenhouse", "APIFY_GREENHOUSE_ACTOR_ID"),
            ("lever", "APIFY_LEVER_ACTOR_ID"),
            ("ashby", "APIFY_ASHBY_ACTOR_ID"),
            ("career-site", "APIFY_CAREER_SITE_ACTOR_ID"),
        ]:
            actor_id = env(env_key)
            if actor_id:
                self._actors[key] = actor_id

    async def fetch(self) -> list[Job]:
        if not self._client:
            log.warning("No APIFY_API_TOKEN set, skipping Apify source.")
            return []

        jobs: list[Job] = []
        for platform, actor_id in self._actors.items():
            try:
                log.info("Running Apify actor %s (%s)...", actor_id, platform)
                items = self._run_actor(actor_id)
                log.info("  Got %d items from %s", len(items), actor_id)
                for item in items:
                    job = self._normalize(item, platform)
                    if job:
                        jobs.append(job)
            except Exception:
                log.exception("Error running Apify actor %s", actor_id)
        return jobs

    def _run_actor(self, actor_id: str) -> list[dict]:
        """Run an Apify actor synchronously and return dataset items."""
        run = self._client.actor(actor_id).call()  # type: ignore[union-attr]
        dataset_id = run["defaultDatasetId"]
        items = list(self._client.dataset(dataset_id).iterate_items())  # type: ignore[union-attr]
        return items

    def _normalize(self, raw: dict, platform: str) -> "Job | None":
        # Try multiple field names — each actor has different output schemas
        company = (
            raw.get("company")
            or raw.get("companyName")
            or raw.get("employer")
            or raw.get("organization")
            or raw.get("hiringOrganization", {}).get("name", "")
            or ""
        )
        title = raw.get("title") or raw.get("name") or raw.get("jobTitle") or ""
        if not company or not title:
            return None

        location = raw.get("location") or raw.get("city") or raw.get("jobLocation") or ""
        if isinstance(location, dict):
            location = location.get("name", "") or location.get("address", "")
        if isinstance(location, list):
            location = ", ".join(str(l) for l in location[:2])

        url = (
            raw.get("url")
            or raw.get("applyUrl")
            or raw.get("jobUrl")
            or raw.get("link")
            or raw.get("applicationUrl")
            or ""
        )

        description = (
            raw.get("description")
            or raw.get("descriptionHtml")
            or raw.get("jobDescription")
            or raw.get("content")
            or ""
        )
        if "<" in description:
            description = strip_html(description)

        posted = None
        for date_field in ("postedAt", "publishedAt", "createdAt", "datePosted", "postingDate"):
            val = raw.get(date_field)
            if val:
                try:
                    posted = datetime.fromisoformat(str(val).replace("Z", "+00:00"))
                    break
                except (ValueError, AttributeError):
                    continue

        return Job(
            source=f"apify-{platform}",
            source_id=str(raw.get("id", raw.get("externalId", raw.get("jobId", "")))),
            company=company,
            title=title,
            location=str(location),
            workplace_type=raw.get("workplaceType") or raw.get("remote") or raw.get("employmentType"),
            department=raw.get("department") or raw.get("team") or raw.get("category"),
            description_plain=description,
            url=url,
            posted_at=posted,
            fetched_at=datetime.now(timezone.utc),
        )
