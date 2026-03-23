"""CLI entry point: ingest → score → publish."""

from __future__ import annotations

import argparse
import asyncio
import logging
import re
import sys

from job_digest.config import get_preferences, get_profile, load_config
from job_digest.db import (
    get_all_scored_jobs,
    get_connection,
    get_top_jobs,
    get_unscored_jobs,
    log_digest,
    save_scores,
    upsert_jobs,
)
from job_digest.models import Preferences
from job_digest.publisher import publish_digest
from job_digest.scorer import score_jobs
from job_digest.sources.apify import ApifySource
from job_digest.sources.ashby import AshbySource
from job_digest.sources.greenhouse import GreenhouseSource
from job_digest.sources.lever import LeverSource

log = logging.getLogger("job_digest")


def _hard_filter(jobs: list, prefs: Preferences) -> list:
    """Apply hard filters before storing — removes obvious mismatches."""
    filtered = []

    # Title exclusions from both title_exclusions and hard_filters
    title_exclusions = [e.lower() for e in prefs.title_exclusions]
    if prefs.hard_filters and prefs.hard_filters.get("exclude_if_title_contains"):
        title_exclusions.extend(
            t.lower() for t in prefs.hard_filters["exclude_if_title_contains"]
        )
    title_exclusions = list(set(title_exclusions))

    # Description exclusions from hard_filters
    desc_exclusions = []
    if prefs.hard_filters and prefs.hard_filters.get("exclude_if_description_contains"):
        desc_exclusions = [
            d.lower() for d in prefs.hard_filters["exclude_if_description_contains"]
        ]

    for job in jobs:
        title_lower = job.title.lower()
        if any(exc in title_lower for exc in title_exclusions):
            continue

        if desc_exclusions:
            desc_lower = job.description_plain.lower()
            if any(exc in desc_lower for exc in desc_exclusions):
                continue

        filtered.append(job)

    return filtered


async def _ingest() -> int:
    """Fetch from all sources, filter, deduplicate, and store."""
    sources = [GreenhouseSource(), LeverSource(), AshbySource(), ApifySource()]
    prefs = get_preferences()
    conn = get_connection()

    total_new = 0
    for source in sources:
        try:
            log.info("Fetching from %s...", source.name)
            jobs = await source.fetch()
            log.info("  Fetched %d raw jobs from %s", len(jobs), source.name)
            jobs = _hard_filter(jobs, prefs)
            log.info("  %d jobs after hard filter", len(jobs))
            new = upsert_jobs(conn, jobs)
            log.info("  %d new jobs stored", new)
            total_new += new
        except Exception:
            log.exception("Error fetching from %s", source.name)

    conn.close()
    return total_new


def _relevance_filter(jobs: list[dict], prefs: Preferences) -> list[dict]:
    """Pre-filter unscored jobs to only those with marketing/growth-relevant titles.
    This runs BEFORE sending to Claude to avoid scoring thousands of irrelevant
    engineering/design/sales roles."""

    # Phrases that can match as substrings (long enough to be unambiguous)
    substring_phrases = [
        "marketing", "growth", "lifecycle", "retention",
        "demand gen", "product marketing", "brand market", "brand strateg",
        "go-to-market", "go to market",
        "ecommerce", "e-commerce",
        "partnerships", "affiliate", "influencer",
        "paid media", "paid social", "paid search",
        "content strateg", "content market",
        "performance market",
        "consumer insight", "user research",
        "copywriter", "creative director", "creative lead",
        "acquisition market",
    ]

    # Short words that need word-boundary matching to avoid false positives
    # (e.g. "sem" matching "assembly", "crm" matching "discrimin")
    word_boundary_terms = ["gtm", "crm", "seo", "sem"]
    word_boundary_pattern = re.compile(
        r"\b(" + "|".join(re.escape(t) for t in word_boundary_terms) + r")\b"
    )

    # Also match exact title patterns from preferences
    target_title_phrases = [t.lower() for t in prefs.target_titles + prefs.adjacent_titles]

    all_substring_phrases = substring_phrases + target_title_phrases

    filtered = []
    for job in jobs:
        title_lower = job["title"].lower()
        if any(phrase in title_lower for phrase in all_substring_phrases):
            filtered.append(job)
        elif word_boundary_pattern.search(title_lower):
            filtered.append(job)

    return filtered


def _score() -> int:
    """Score all unscored jobs (pre-filtered for relevance)."""
    conn = get_connection()
    prefs = get_preferences()
    unscored = get_unscored_jobs(conn)
    if not unscored:
        log.info("No unscored jobs.")
        conn.close()
        return 0

    log.info("Found %d unscored jobs.", len(unscored))
    relevant = _relevance_filter(unscored, prefs)
    log.info("  %d jobs after relevance pre-filter (saving API cost).", len(relevant))

    if not relevant:
        log.info("No relevant jobs to score.")
        conn.close()
        return 0

    profile = get_profile()
    scores = score_jobs(profile, prefs, relevant)
    save_scores(conn, scores)
    log.info("Scored %d jobs.", len(scores))
    conn.close()
    return len(scores)


def _publish() -> int:
    """Publish all scored jobs to docs/index.html, ranked by score."""
    conn = get_connection()
    all_jobs = get_all_scored_jobs(conn)
    if not all_jobs:
        log.info("No scored jobs to publish.")
        conn.close()
        return 0

    log.info("Publishing digest with %d scored jobs...", len(all_jobs))
    path = publish_digest(all_jobs)
    conn.close()
    log.info("Digest published to %s", path)
    return len(all_jobs)


def _run() -> None:
    """Full pipeline: ingest → score → publish."""
    new = asyncio.run(_ingest())
    log.info("Ingestion complete: %d new jobs.", new)
    scored = _score()
    log.info("Scoring complete: %d jobs scored.", scored)
    published = _publish()
    log.info("Done. Published digest with %d jobs.", published)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(description="Job Digest — find and rank job postings")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("ingest", help="Fetch jobs from all sources")
    sub.add_parser("score", help="Score unscored jobs via Claude")
    sub.add_parser("publish", help="Publish top 10 unsent jobs to docs/")
    sub.add_parser("run", help="Full pipeline: ingest → score → publish")

    args = parser.parse_args()
    cmd = args.command or "run"

    load_config()

    if cmd == "ingest":
        asyncio.run(_ingest())
    elif cmd == "score":
        _score()
    elif cmd == "publish":
        _publish()
    elif cmd == "run":
        _run()
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
