"""Tests for scorer module (unit tests that don't call the API)."""

import json

from job_digest.models import Preferences, Profile
from job_digest.scorer import _build_user_message


def _profile():
    return Profile(
        name="Test",
        current_title="SWE",
        years_experience=5,
        skills=["Python", "AWS"],
        domains=["fintech"],
        education=[{"degree": "BS CS", "school": "MIT"}],
        summary="Backend engineer.",
    )


def _prefs():
    return Preferences(
        target_titles=["SWE"],
        title_exclusions=["Intern"],
        locations=["Remote"],
        remote_ok=True,
        industries=["fintech"],
    )


def test_build_user_message_structure():
    jobs = [
        {"id": 1, "title": "SWE", "company": "Acme", "location": "SF",
         "department": "Eng", "description_plain": "Build stuff."},
        {"id": 2, "title": "DE", "company": "Beta", "location": "NY",
         "department": None, "description_plain": "Data things."},
    ]
    msg = _build_user_message(_profile(), _prefs(), jobs)
    parsed = json.loads(msg)
    assert "profile" in parsed
    assert "preferences" in parsed
    assert "jobs" in parsed
    assert len(parsed["jobs"]) == 2
    assert parsed["jobs"][0]["job_id"] == 1


def test_description_truncated():
    long_desc = "x" * 1000
    jobs = [{"id": 1, "title": "SWE", "company": "Acme", "location": "SF",
             "department": None, "description_plain": long_desc}]
    msg = _build_user_message(_profile(), _prefs(), jobs)
    parsed = json.loads(msg)
    assert len(parsed["jobs"][0]["description_snippet"]) == 500
