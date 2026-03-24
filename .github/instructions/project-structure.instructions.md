---
description: "Use when navigating, modifying, or adding code to the applybot project. Describes project layout, where to find plans and component documentation."
applyTo: "**"
---
# ApplyBot Project Structure

## Top-Level Layout

```
applybot/
├── README.md               # Full project plan, architecture, data models, and design decisions
├── STATUS.md               # Current progress and next steps
├── core_idea.md            # Original project vision
├── pyproject.toml          # Dependencies and tool config (black, ruff, mypy)
├── alembic.ini             # Alembic migration config
├── alembic/                # Database migration scripts
├── data/                   # Local data files (SQLite DB, resume, exports)
├── src/applybot/           # All application source code
│   ├── config.py           # Pydantic Settings — environment-based configuration
│   ├── models/             # SQLAlchemy ORM: Job, Application, UserProfile
│   ├── llm/                # Anthropic Claude SDK wrapper
│   ├── profile/            # Profile CRUD and .docx resume parsing/generation
│   ├── discovery/          # Multi-source job scraping, dedup, and ranking
│   │   └── scrapers/       # Pluggable scraper implementations (SerpAPI, Greenhouse, Lever, etc.)
│   ├── application/        # Resume tailoring, Q&A generation, cover letters
│   ├── tracking/           # Application state machine and Gmail integration
│   └── dashboard/          # FastAPI REST API and Streamlit UI
└── tests/                  # pytest test suite
```

## Documentation Convention

- **`README.md` (root)** — The authoritative source for the overall plan: pipeline design, tech stack choices, data models, architecture, and key design decisions. Read this first before making broad changes.
- **Each component directory** (`models/`, `llm/`, `profile/`, `discovery/`, `application/`, `tracking/`, `dashboard/`) **contains its own `README.md`** describing that component's purpose, public API, internal design, and boundaries. Consult the relevant component README before modifying that component.

If you make changes to a component, update its README.md to reflect any new functions, classes, or design changes. If you add a new component, create a new directory under `src/applybot/` with a README.md describing it.

## Instructions

### Virtual Environment (CRITICAL)
**ALWAYS verify the virtual environment is active before running ANY Python or pip command.** Installing packages into the system Python is destructive and unwanted.

Before every terminal command that involves `python`, `pip`, `pytest`, `alembic`, `streamlit`, `uvicorn`, or any project tool:
1. Check if the prompt shows `(.venv)` prefix
2. If not, activate it first:
   - **Windows (PowerShell):** `& .\.venv\Scripts\Activate.ps1`
   - **Windows (cmd):** `.venv\Scripts\activate.bat`
   - **Linux/macOS:** `source .venv/bin/activate`
3. Verify with `python -c "import sys; print(sys.prefix)"` — it must point to the `.venv` directory, not the system Python

**Never run `pip install` without confirming the venv is active.**
