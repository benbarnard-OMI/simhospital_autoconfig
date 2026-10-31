# Contributing

## Development Setup

1. Clone the repository.
2. Create a virtual environment on Python 3.12 (recommended due to PEP 668).

```bash
uv venv --python 3.12 .venv     # or: python3.12 -m venv .venv
source .venv/bin/activate
```

Pin the interpreter deliberately. A venv created from whatever `python3` happens to
be installed breaks silently when the system Python is upgraded: `pyvenv.cfg` and
`lib/python3.X/site-packages` keep pointing at the old minor version, which drops
off `sys.path` and makes every installed package unimportable.

3. Install the package in editable mode with development dependencies:

```bash
pip install -e ".[dev]"
```

4. Create a local secrets file. `.env` is gitignored; `.env.example` documents the keys.

```bash
cp .env.example .env    # then fill in CENSUS_API_KEY
```

`CENSUS_API_KEY` is free from <https://api.census.gov/data/key_signup.html> and is
required for real demographics — without it the Census client raises immediately and
`ethnicity.csv` falls back to the upstream UK distribution. The test suite does not
need it. `TYPESAFE_API_KEY` is only needed for the live TypeSafe audit tests, which
skip when it is absent.

To load `.env` into the current shell: `set -a; . ./.env; set +a`

5. Run the test suite:

```bash
pytest -v        # 141 passed, 7 skipped without API keys
```

6. Validate generated configs against the real simulator:

```bash
make validate-simulator
```

## Code Style

- Follow PEP 8; the ruff rule set is declared in `pyproject.toml` under `[tool.ruff]`.
- Add docstrings to all public functions and classes.
- Add type hints where practical.
- Update tests when changing behavior.
- When a check or test encodes a fact about an external API, assert on the *outgoing
  request*, not just the parsed response. A mock that returns columns the client never
  asked for is how the Census ethnicity bug stayed hidden.

## Adding a New Data Source

1. Create a new client module in `simhospital_autoconfig/` (e.g., `new_source.py`).
2. Add unit tests in `tests/` with mocked HTTP responses.
3. Update `generators.py` to consume the new data.
4. Update `__main__.py` to orchestrate the new fetcher.
5. Add a deterministic check in `deterministic_checks.py` that fails when the new
   source silently degrades to defaults.
6. Update the README with the new data source.

## Running Linting

```bash
ruff check simhospital_autoconfig tests     # ruff is pinned in the dev extra
```

## Building for Distribution

```bash
python -m build
```
