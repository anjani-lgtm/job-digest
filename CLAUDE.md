# Job Digest

Personal job discovery tool that ingests postings from ATS platforms, scores them against a user profile using Claude API, and publishes a ranked digest as a GitHub Pages site.

## Architecture

```
config/          → profile.json (user background) + preferences.json (scoring config)
src/job_digest/  → main CLI, sources/, scorer, publisher, db, models
templates/       → Jinja2 HTML template for digest page
docs/            → GitHub Pages output (index.html + archive/)
tests/           → pytest suite (20 tests)
```

## Key Commands

```bash
.venv/bin/python -c "from job_digest.main import main; import sys; sys.argv = ['job-digest', 'ingest']; main()"
.venv/bin/python -c "from job_digest.main import main; import sys; sys.argv = ['job-digest', 'score']; main()"
.venv/bin/python -c "from job_digest.main import main; import sys; sys.argv = ['job-digest', 'publish']; main()"
.venv/bin/python -c "from job_digest.main import main; import sys; sys.argv = ['job-digest', 'run']; main()"
```

## Running Tests

```bash
.venv/bin/python -m pytest tests/ -v
```

## Important Notes

- Python 3.9 compat: use `Optional[X]` not `X | None` in type hints
- `.env` contains API keys — never commit (in .gitignore)
- `jobs.db` is the SQLite database — never commit (in .gitignore)
- Apify sources are disabled; using direct ATS APIs only (Greenhouse, Lever, Ashby)
- Pre-score relevance filter reduces API cost ~95% — edit `_relevance_filter()` in main.py to adjust
- Scoring costs ~$0.60 per full run (~270 relevant jobs from 3,240 ingested)
- Template shows ALL scored jobs with client-side filtering (default: score 70+)

## Pipeline Flow

1. **Ingest** → fetch from 50 companies across 3 ATS APIs → hard filter → dedup → store in SQLite
2. **Score** → relevance pre-filter → batch score via Claude Sonnet (15/batch) → store scores
3. **Publish** → render all scored jobs to docs/index.html (ranked by score) + archive dated copy

## Pending Work

- Anjani has prioritization/scoring feedback to incorporate
- Enable GitHub Pages (serve from docs/ folder)
- Set up spend limits / rate caps
- Routine run cadence (cron or manual)
