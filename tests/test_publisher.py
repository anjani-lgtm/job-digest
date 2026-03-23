"""Tests for publisher module."""

import json

from job_digest.publisher import _render_digest


def test_render_digest_table_structure():
    jobs = [
        {
            "company": "Acme",
            "title": "Growth Lead",
            "location": "San Francisco",
            "department": "Marketing",
            "fit_score": 92,
            "match_reasons": json.dumps(["Strong title fit", "Location match", "D2C industry"]),
            "url": "https://example.com/apply",
            "source": "greenhouse",
        },
    ]
    html = _render_digest(jobs, "March 19, 2026 at 12:00 PM UTC")
    assert "Acme" in html
    assert "Growth Lead" in html
    assert "92" in html
    assert "Strong title fit" in html
    assert "https://example.com/apply" in html
    assert "March 19, 2026" in html
    assert "<table" in html


def test_render_digest_score_colors():
    jobs = [
        {"company": "A", "title": "T", "location": "L", "fit_score": 85,
         "match_reasons": "[]", "url": "#", "source": "test", "department": None},
        {"company": "B", "title": "T", "location": "L", "fit_score": 65,
         "match_reasons": "[]", "url": "#", "source": "test", "department": None},
        {"company": "C", "title": "T", "location": "L", "fit_score": 40,
         "match_reasons": "[]", "url": "#", "source": "test", "department": None},
    ]
    html = _render_digest(jobs, "test")
    assert "badge-green" in html  # 85
    assert "badge-amber" in html  # 65
    assert "badge-gray" in html   # 40


def test_render_digest_sortable():
    jobs = [
        {"company": "A", "title": "T", "location": "L", "fit_score": 80,
         "match_reasons": "[]", "url": "#", "source": "test", "department": None},
    ]
    html = _render_digest(jobs, "test")
    assert "sortTable" in html  # JS sorting function present


def test_publish_digest_writes_files(tmp_path, monkeypatch):
    """Test that publish_digest creates index.html and archive."""
    import job_digest.publisher as pub
    monkeypatch.setattr(pub, "_ROOT", tmp_path)

    # Create templates dir with a minimal template
    templates_dir = tmp_path / "templates"
    templates_dir.mkdir()
    (templates_dir / "digest.html").write_text(
        "<html>{{ jobs|length }} jobs - {{ generated_at }}</html>"
    )

    from job_digest.publisher import publish_digest
    jobs = [
        {"company": "X", "title": "Y", "location": "Z", "fit_score": 90,
         "match_reasons": "[]", "url": "#", "source": "test"},
    ]
    path = publish_digest(jobs)

    assert path.exists()
    assert "1 jobs" in path.read_text()
    archive_files = list((tmp_path / "docs" / "archive").glob("*.html"))
    assert len(archive_files) == 1
