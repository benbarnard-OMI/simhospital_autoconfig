# Contributing

## Development Setup

1. Clone the repository.
2. Create a virtual environment (recommended due to PEP 668):

```bash
python3 -m venv .venv
source .venv/bin/activate
```

3. Install the package in editable mode with development dependencies:

```bash
pip install -e ".[dev]"
```

4. Run the test suite:

```bash
pytest -v
```

## Code Style

- Follow PEP 8.
- Add docstrings to all public functions and classes.
- Add type hints where practical.
- Update tests when changing behavior.

## Adding a New Data Source

1. Create a new client module in `simhospital_autoconfig/` (e.g., `new_source.py`).
2. Add unit tests in `tests/` with mocked HTTP responses.
3. Update `generators.py` to consume the new data.
4. Update `__main__.py` to orchestrate the new fetcher.
5. Update the README with the new data source.

## Running Linting

```bash
pip install ruff
ruff check simhospital_autoconfig tests
```

## Building for Distribution

```bash
python -m build
```
