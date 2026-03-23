"""Publishes the digest as a static HTML page to docs/ for GitHub Pages."""

from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

log = logging.getLogger(__name__)

_ROOT = Path(__file__).resolve().parent.parent.parent


def _render_digest(jobs: list[dict], generated_at: str) -> str:
    """Render the digest HTML from the Jinja2 template."""
    env = Environment(
        loader=FileSystemLoader(str(_ROOT / "templates")),
        autoescape=True,
    )
    template = env.get_template("digest.html")

    enriched = []
    for j in jobs:
        reasons = j.get("match_reasons", "[]")
        if isinstance(reasons, str):
            reasons = json.loads(reasons)
        enriched.append({**j, "match_reasons": reasons})

    return template.render(jobs=enriched, generated_at=generated_at)


def publish_digest(jobs: list[dict]) -> Path:
    """Write the digest to docs/index.html and archive a dated copy."""
    if not jobs:
        log.info("No jobs to publish.")
        return _ROOT / "docs" / "index.html"

    now = datetime.now(timezone.utc)
    generated_at = now.strftime("%B %d, %Y at %I:%M %p UTC")
    date_slug = now.strftime("%Y-%m-%d")

    html = _render_digest(jobs, generated_at)

    docs_dir = _ROOT / "docs"
    archive_dir = docs_dir / "archive"
    docs_dir.mkdir(exist_ok=True)
    archive_dir.mkdir(exist_ok=True)

    index_path = docs_dir / "index.html"
    index_path.write_text(html)
    log.info("Published digest to %s", index_path)

    archive_path = archive_dir / f"{date_slug}.html"
    shutil.copy2(index_path, archive_path)
    log.info("Archived digest to %s", archive_path)

    return index_path
