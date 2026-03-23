"""Tests for Pydantic models."""

from job_digest.models import Job, Profile, Preferences, ScoredJob


def test_job_dedup_key_deterministic():
    job = Job(
        source="greenhouse",
        source_id="123",
        company="Acme",
        title="Software Engineer",
        location="San Francisco",
        url="https://example.com/123",
    )
    assert job.dedup_key == job.dedup_key  # same object
    job2 = Job(
        source="lever",
        source_id="456",
        company="Acme",
        title="Software Engineer",
        location="San Francisco",
        url="https://example.com/456",
    )
    assert job.dedup_key == job2.dedup_key  # same company|title|location


def test_job_dedup_key_case_insensitive():
    job1 = Job(
        source="test", source_id="1", company="ACME",
        title="Software Engineer", location="SF", url="https://x.com/1",
    )
    job2 = Job(
        source="test", source_id="2", company="acme",
        title="software engineer", location="sf", url="https://x.com/2",
    )
    assert job1.dedup_key == job2.dedup_key


def test_job_dedup_key_differs_for_different_jobs():
    job1 = Job(
        source="test", source_id="1", company="Acme",
        title="Software Engineer", location="SF", url="https://x.com/1",
    )
    job2 = Job(
        source="test", source_id="2", company="Acme",
        title="Data Engineer", location="SF", url="https://x.com/2",
    )
    assert job1.dedup_key != job2.dedup_key


def test_profile_validates():
    p = Profile(
        name="Test",
        current_title="SWE",
        years_experience=5,
        skills=["Python"],
        domains=["fintech"],
        education=[{"degree": "BS", "school": "MIT"}],
        summary="A dev.",
    )
    assert p.name == "Test"


def test_preferences_minimal():
    prefs = Preferences(
        target_titles=["SWE"],
        title_exclusions=["Intern"],
        locations=["Remote"],
        remote_ok=True,
        industries=["fintech"],
    )
    assert prefs.compensation is None
    assert prefs.fit_weights is None


def test_scored_job():
    s = ScoredJob(job_id=1, fit_score=85, match_reasons=["skill match", "location", "domain"])
    assert s.fit_score == 85
    assert len(s.match_reasons) == 3
