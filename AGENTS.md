# Repository Guidelines

## Module Organization

## Build, Test, and Development Commands

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run all tests
pytest

# Run a specific test file or pattern
pytest tests/test_discovery.py
pytest src/applybot/discovery/tests/ -k "test_dedup"

# Run linting & formatting
ruff check src/
ruff format src/
black --check src/
mypy src/

# Set up pre-commit hooks
pre-commit install
```

## Coding Style & Naming Conventions

- **Python 3.12+** — use modern syntax (`from __future__ import annotations`, `str | None` union types).
- **Formatter**: Black, line length 88.
- **Linter**: Ruff with rules `E`, `F`, `I`, `N`, `W`, `UP`; E501 (line length) ignored.
- **Type checker**: MyPy in strict mode; Pydantic mypy plugin enabled.
- **Naming**: modules/files `snake_case.py`; Pydantic models `PascalCase`; private helpers prefixed `_`.
- **Pre-commit hooks** enforce: trailing whitespace removal, EOF newlines, YAML/JSON/TOML validity, no debug statements, no private keys.

Run `pre-commit install` once to enable automatic checks on every commit.

## Testing Guidelines

- **Framework**: pytest with `asyncio_mode = "auto"`.
- **Test locations**: `tests/` for integration tests; `src/applybot/*/tests/` for module-level unit tests.
- **Naming**: files `test_*.py`, functions `test_*`.
- **Fixtures**: Shared mocks (in-memory Firestore client) live in `tests/conftest.py` so tests run without Google Cloud dependencies.
- Tests that require the real LLM or network are not committed — use mocks. Prefer deterministic, offline tests.

## Commit & Pull Request Guidelines

- **Commit format**: [Conventional Commits](https://www.conventionalcommits.org/) — `type(scope): message`.
  - Types: `feat`, `fix`, `docs`, `ci`, `chore`, `infra`, `refactor`.
  - Scopes: `dashboard`, `discovery`, `llm`, `models`, `tracking` — omit if change spans multiple areas.
  - Examples: `feat(dashboard): add Run Discovery button`, `fix: increase max_tokens to prevent JSON truncation`.
- **PR descriptions**: describe what changed and why; link issues when applicable.
- **CI triggers**: append `--tf-apply` or `--docker` to commit messages to trigger Terraform or Docker workflows on push to `main`.
- Make sure to talk to the user in english

## Virtual Environment (CRITICAL)
**ALWAYS verify the virtual environment is active before running ANY Python or pip command.** Installing packages into the system Python is destructive and unwanted.

