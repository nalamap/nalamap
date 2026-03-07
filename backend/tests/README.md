# Backend Tests

This directory contains the test suite for the NaLaMap backend, built with [pytest](https://docs.pytest.org/).

## 🏃 Running Tests

### Prerequisites

Ensure you have the backend dependencies installed:

```bash
cd backend
poetry install
```

### Basic Usage

Run all tests:
```bash
poetry run pytest tests/
```

Run a specific test file:
```bash
poetry run pytest tests/test_geocoding.py
```

Run with verbose output:
```bash
poetry run pytest tests/ -v
```

### Test Markers

We use markers to categorize tests. You can run specific categories using the `-m` flag:

```bash
poetry run pytest tests/ -m unit
```

Available markers:
- `unit`: Unit tests for individual functions (fast, no external calls)
- `integration`: Integration tests (may involve DB or mocked API calls)
- `slow`: Tests that take longer than 5 seconds
- `performance`: Performance and stress tests
- `edge_case`: Edge case and boundary condition tests
- `styling`: Tests related to map styling and color theory
- `geoserver`: Tests for GeoServer integration

### Coverage

To generate a coverage report:

```bash
poetry run pytest tests/ --cov=. --cov-report=html
```
The report will be generated in `htmlcov/index.html`.

## 📂 Structure

- `conftest.py`: Global fixtures and configuration (DB setup, mock clients).
- `test_*.py`: Test files corresponding to modules.
- `manual_test_*.py`: Scripts for manual verification (not run by default pytest).

## 🛠️ Writing Tests

1. **Naming**: Test files must start with `test_`. Test functions must start with `test_`.
2. **Fixtures**: Use fixtures from `conftest.py` for common setup (e.g., `db_session`, `mock_llm`).
3. **Mocking**: Avoid real external API calls (OpenAI, OSM) in unit tests. Use `unittest.mock` or custom mocks provided in `conftest.py`.
4. **Async**: For async functions, use `pytest-asyncio` (installed) and mark tests with `@pytest.mark.asyncio`.

Example:
```python
import pytest

@pytest.mark.unit
@pytest.mark.asyncio
async def test_my_async_function():
    result = await my_async_function()
    assert result == "expected"
```
