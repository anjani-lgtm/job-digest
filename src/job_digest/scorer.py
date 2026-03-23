"""Claude API batch scoring of jobs against user profile."""

from __future__ import annotations

import json
import logging

import anthropic

from job_digest.config import env
from job_digest.models import Preferences, Profile, ScoredJob

log = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are a job-fit scoring engine. You will receive a candidate profile and detailed \
preferences, then a batch of job postings. For each job, assign a fit_score (0-100) \
and provide exactly 3 short match_reasons explaining the score.

## Scoring Dimensions & Weights

Use the fit_weights provided in the preferences. If not provided, default to:
- title_fit (24%): How well does the job title match target/adjacent titles? Deprioritize titles in the deprioritize list.
- function_fit (22%): Does the role's core function align with core > secondary functions? Penalize deprioritized functions.
- industry_fit (14%): Is the company in a preferred industry? Penalize deprioritized industries. Hard-exclude excluded industries.
- company_stage_fit (10%): Does the company match preferred stage/size/traits?
- location_fit (10%): Bay Area / Remote preferred. Deprioritize out-of-area onsite roles.
- keyword_overlap (10%): Count of high-priority and positive-context keywords found in the description. Penalize negative keywords.
- mission_alignment (6%): Mission-driven, design-forward, product-led, consumer-facing signals.
- work_style_fit (4%): Ownership, cross-functional, builder-oriented signals. Penalize red-flag traits.

## Scoring Guidelines

- 90-100: Exceptional fit — strong match on title, function, industry, and company traits
- 75-89: Strong fit — good match on most dimensions, minor gaps
- 60-74: Moderate fit — some alignment but notable mismatches (e.g. deprioritized function or industry)
- 40-59: Weak fit — significant mismatches on multiple dimensions
- 0-39: Poor fit — clear misalignment (wrong function, excluded industry, red-flag traits)

## Hard Exclusions (score 0)

- Title contains any term from hard_filters.exclude_if_title_contains
- Description contains any term from hard_filters.exclude_if_description_contains
- Industry is in hard_filters.exclude_if_industry_in or industries_to_exclude

## Match Reasons

For each job, provide 3 concise reasons. Include:
- What drove the score up (strengths)
- What drove the score down (gaps or red flags)
- At least one reason should reference a specific preference dimension (title, function, industry, keywords, etc.)

Return ONLY a JSON array (no markdown fences) with objects:
{"job_id": <int>, "fit_score": <int 0-100>, "match_reasons": ["reason1", "reason2", "reason3"]}
"""

BATCH_SIZE = 15


def _build_user_message(
    profile: Profile, preferences: Preferences, jobs: list[dict]
) -> str:
    job_summaries = []
    for j in jobs:
        desc = (j.get("description_plain") or "")[:500]
        job_summaries.append(
            {
                "job_id": j["id"],
                "title": j["title"],
                "company": j["company"],
                "location": j["location"],
                "department": j.get("department"),
                "description_snippet": desc,
            }
        )

    return json.dumps(
        {
            "profile": profile.model_dump(),
            "preferences": preferences.model_dump(),
            "jobs": job_summaries,
        },
        indent=2,
    )


def score_jobs(
    profile: Profile,
    preferences: Preferences,
    jobs: list[dict],
    model: str = "claude-sonnet-4-20250514",
) -> list[ScoredJob]:
    """Score a list of jobs against the profile using Claude API."""
    api_key = env("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")

    client = anthropic.Anthropic(api_key=api_key)
    all_scores: list[ScoredJob] = []

    for i in range(0, len(jobs), BATCH_SIZE):
        batch = jobs[i : i + BATCH_SIZE]
        log.info("Scoring batch %d-%d of %d jobs", i, i + len(batch), len(jobs))

        user_msg = _build_user_message(profile, preferences, batch)
        response = client.messages.create(
            model=model,
            max_tokens=4096,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )

        text = response.content[0].text
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            log.error("Failed to parse scorer response: %s", text[:200])
            continue

        for entry in parsed:
            all_scores.append(
                ScoredJob(
                    job_id=entry["job_id"],
                    fit_score=entry["fit_score"],
                    match_reasons=entry.get("match_reasons", []),
                )
            )

    return all_scores
