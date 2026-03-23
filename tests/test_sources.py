"""Tests for job source normalization."""

from datetime import datetime, timezone

from job_digest.sources.greenhouse import GreenhouseSource
from job_digest.sources.lever import LeverSource
from job_digest.sources.ashby import AshbySource


def test_greenhouse_normalize():
    source = GreenhouseSource()
    raw = {
        "id": 123,
        "title": "Software Engineer",
        "location": {"name": "San Francisco, CA"},
        "content": "<p>Build things.</p>",
        "updated_at": "2025-01-15T12:00:00Z",
        "absolute_url": "https://boards.greenhouse.io/acme/jobs/123",
        "departments": [{"name": "Engineering"}],
    }
    job = source._normalize(raw, "acme")
    assert job.title == "Software Engineer"
    assert job.company == "acme"
    assert job.location == "San Francisco, CA"
    assert job.department == "Engineering"
    assert "Build things" in job.description_plain
    assert job.source == "greenhouse"


def test_lever_normalize():
    source = LeverSource()
    raw = {
        "id": "abc-def",
        "text": "Backend Engineer",
        "categories": {
            "location": "New York, NY",
            "department": "Platform",
            "workplaceType": "Remote",
        },
        "descriptionPlain": "Join us.",
        "hostedUrl": "https://jobs.lever.co/acme/abc-def",
        "createdAt": 1705000000000,
    }
    job = source._normalize(raw, "acme")
    assert job.title == "Backend Engineer"
    assert job.location == "New York, NY"
    assert job.workplace_type == "Remote"


def test_ashby_normalize():
    source = AshbySource()
    raw = {
        "id": "xyz",
        "title": "Data Engineer",
        "location": "Remote",
        "department": "Data",
        "descriptionHtml": "<b>Great role</b>",
        "publishedAt": "2025-02-01T00:00:00Z",
        "jobUrl": "https://jobs.ashbyhq.com/acme/xyz",
    }
    job = source._normalize(raw, "acme")
    assert job.title == "Data Engineer"
    assert job.location == "Remote"
    assert "Great role" in job.description_plain
