# AGENTS.md - NaLaMap Development Guide for AI Agents

> **Purpose**: This guide instructs AI agents on how to efficiently develop in the NaLaMap project.  
> **Target Audience**: AI coding assistants, automated development tools, and human developers.

---

## 📋 Table of Contents

1. [Project Overview](#project-overview)
2. [Quick Start for Development](#quick-start-for-development)
3. [Running Project Components](#running-project-components)
4. [Testing Guidelines](#testing-guidelines)
5. [Code Quality & Linting](#code-quality--linting)
6. [Development Workflow](#development-workflow)
7. [Common Development Tasks](#common-development-tasks)
8. [Troubleshooting](#troubleshooting)

---

## 📖 Project Overview

**NaLaMap** is an open-source geospatial AI platform built with:
- **Backend**: Python 3.11+, FastAPI, LangChain, LangGraph
- **Frontend**: Next.js 15, React 19, TypeScript, Leaflet
- **Infrastructure**: Docker, Nginx, PostgreSQL

**Repository Structure**:
```
nalamap/
├── backend/              # Python FastAPI backend
├── frontend/             # Next.js frontend  
├── nginx/                # Nginx reverse proxy configuration
├── docs/                 # Documentation
├── .github/workflows/    # CI/CD pipelines
└── docker-compose.yml    # Production deployment
```

---

## 🚀 Quick Start for Development

### Prerequisites
- **Python 3.11+**
- **Node.js 18+**  
- **Poetry** (Python dependency management)
- **Docker & Docker Compose** (optional)
- **Git**

### Environment Setup

1. **Clone the repository**:
   ```bash
   git clone git@github.com:nalamap/nalamap.git
   cd nalamap
   ```

2. **Configure environment variables**:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration (API keys, database credentials, etc.)
   ```

3. **Configure Poetry** (recommended):
   ```bash
   poetry config virtualenvs.create true
   poetry config virtualenvs.in-project true
   ```

---

## 🏃 Running Project Components

### Backend (FastAPI)

**Directory**: `backend/`

#### Local Development (Recommended for testing)
```bash
cd backend

# Install dependencies
poetry install

# Run the backend server
poetry run python main.py
```

**Backend runs on**: `http://localhost:8000`  
**API Documentation**: `http://localhost:8000/docs` (Swagger UI)

#### Docker Development
```bash
# From project root
docker-compose -f dev.docker-compose.yml up backend --build
```

### Frontend (Next.js)

**Directory**: `frontend/`

#### Local Development (Recommended for testing)
```bash
cd frontend

# Install dependencies
npm install

# Run development server with hot reload
npm run dev
```

**Frontend runs on**: `http://localhost:3000`

#### Docker Development
```bash
# From project root
docker-compose -f dev.docker-compose.yml up frontend --build
```

### Full Stack Development

**Option 1: Local Development** (Best for active development)
```bash
# Terminal 1: Backend
cd backend && poetry run python main.py

# Terminal 2: Frontend  
cd frontend && npm run dev
```

**Option 2: Docker Development** (Matches production environment)
```bash
# From project root
docker-compose -f dev.docker-compose.yml up --build
```

**Option 3: Production-like Deployment**
```bash
# From project root
docker-compose up --build
```

---

## 🧪 Testing Guidelines

### Backend Tests (pytest)

**Location**: `backend/tests/`

#### Running Backend Tests

```bash
cd backend

# Run all tests
poetry run pytest tests/

# Run specific test file
poetry run pytest tests/test_styling_ops.py

# Run with verbose output
poetry run pytest tests/ -v

# Run tests with specific markers
poetry run pytest tests/ -m unit
poetry run pytest tests/ -m integration
poetry run pytest tests/ -m styling

# Run tests and show durations
poetry run pytest tests/ --durations=10

# Run tests with coverage
poetry run pytest tests/ --cov=. --cov-report=html
```

#### Test Markers Available
- `unit`: Unit tests for individual functions
- `integration`: Integration tests via API
- `slow`: Slow running tests (>5 seconds)
- `performance`: Performance and stress tests
- `edge_case`: Edge case and boundary condition tests
- `styling`: All styling-related tests
- `color_theory`: Tests related to color theory

#### Writing New Backend Tests
- Place new test files in `backend/tests/`
- Name test files with `test_*.py` pattern
- Use fixtures from `conftest.py`
- Add appropriate test markers
- Mock external API calls to avoid rate limits
- Follow existing test patterns

**Example Test Structure**:
```python
import pytest
from models.geodata import GeoDataObject

@pytest.mark.unit
def test_something(sample_river_layer):
    """Test description."""
    # Arrange
    layer = sample_river_layer
    
    # Act
    result = some_function(layer)
    
    # Assert
    assert result is not None
```

### Frontend Tests (Playwright)

**Location**: `frontend/tests/`

#### Running Frontend Tests

```bash
cd frontend

# Install Playwright browsers (first time only)
npx playwright install --with-deps

# Run all tests
npm test
# or
npx playwright test

# Run specific test file
npx playwright test tests/leaflet-map.spec.ts

# Run in interactive UI mode (recommended for debugging)
npx playwright test --ui

# Run in headed mode (see browser)
npx playwright test --headed

# Run specific test by name
npx playwright test -g "should display geocoded location"

# Generate HTML report
npx playwright test --reporter=html
npx playwright show-report
```

#### Frontend Test Categories
- **Map Tests** (`leaflet-map.spec.ts`): Geocoding, Overpass, OGC services
- **Chat Interface** (`chat-interface.spec.ts`): AI chat functionality
- **Settings** (`settings.spec.ts`, `settings-tools-collapsible.spec.ts`): Settings panels
- **Geoprocessing** (`geoprocessing.spec.ts`): Spatial operations
- **Layer Management**: Layer loading and caching tests
- **Color Settings** (`color-settings.spec.ts`): Color customization

#### Writing New Frontend Tests
- Use Playwright test framework
- Place tests in `frontend/tests/`
- Use fixtures from `frontend/tests/fixtures/`
- Mock backend API responses when appropriate
- Test user interactions and UI state

---

## ✅ Code Quality & Linting

### Backend Linting & Formatting

**Tools**: Flake8 (linting), Black (formatting), isort (import sorting)

#### Running Linters

```bash
cd backend

# Run flake8 (linting)
poetry run flake8 .

# Run black (formatting check)
poetry run black --check .

# Auto-format with black
poetry run black .

# Sort imports with isort
poetry run isort .
```

#### Backend Code Standards
- **Line Length**: 100 characters (configured in `pyproject.toml`)
- **Style Guide**: PEP 8 with Black formatting
- **Import Order**: Managed by isort
- **Ignore Rules**: E203, W503 (conflicts with Black)

#### Configuration Files
- `backend/pyproject.toml`: Contains `[tool.flake8]` and `[tool.black]` sections
- Per-file ignores are configured for specific patterns (e.g., long docstrings, test fixtures)

### Frontend Linting

```bash
cd frontend

# Run Next.js linter
npm run lint
```

**Note**: Frontend linting is configured but not strictly enforced in CI/CD.

---

## 🔄 Development Workflow

### Before Starting Work

1. **Pull latest changes**:
   ```bash
   git pull origin main
   ```

2. **Create a feature branch**:
   ```bash
   git checkout -b features/YYYYMMDD_YourFeatureName
   ```

3. **Ensure environment is up-to-date**:
   ```bash
   # Backend
   cd backend && poetry install
   
   # Frontend
   cd frontend && npm install
   ```

### While Developing

1. **Run components locally** (see [Running Project Components](#running-project-components))

2. **Write tests for new features**:
   - Add unit tests for new functions/modules
   - Add integration tests for new API endpoints
   - Add E2E tests for new UI features

3. **Run tests frequently**:
   ```bash
   # Backend
   poetry run pytest tests/
   
   # Frontend
   npm test
   ```

4. **Check code quality**:
   ```bash
   # Backend linting
   poetry run flake8 .
   poetry run black --check .
   
   # Frontend linting
   npm run lint
   ```

### Before Committing

**Critical Checklist**:

✅ **All tests pass**:
```bash
cd backend && poetry run pytest tests/
cd frontend && npm test
```

✅ **Code is properly formatted**:
```bash
cd backend && poetry run black .
cd backend && poetry run flake8 .
```

✅ **No regressions introduced** (run relevant test suites)

✅ **New features have tests** (aim for >80% coverage)

✅ **Documentation updated** (if adding new features or changing APIs)

### Committing Changes

```bash
# Stage changes
git add .

# Commit with descriptive message
git commit -m "feat: Add new geocoding functionality"

# Push to your branch
git push origin features/YYYYMMDD_YourFeatureName
```

### Creating Pull Requests

1. Push your branch to GitHub
2. Create a Pull Request targeting `main`
3. Ensure CI/CD checks pass (see [CI/CD Pipeline](#cicd-pipeline))
4. Request review from maintainers
5. Address review feedback
6. Merge once approved

---

## 🛠️ Common Development Tasks

### Adding a New Backend Dependency

```bash
cd backend
poetry add <package-name>

# For dev dependencies
poetry add --group dev <package-name>
```

### Adding a New Frontend Dependency

```bash
cd frontend
npm install <package-name>

# For dev dependencies
npm install --save-dev <package-name>
```

### Adding a New API Endpoint

1. **Create/modify endpoint in** `backend/api/`
2. **Add corresponding tests in** `backend/tests/`
3. **Update models if needed in** `backend/models/`
4. **Update frontend API calls in** `frontend/app/` (components, hooks, or stores)
5. **Add frontend E2E tests in** `frontend/tests/`
6. **Run full test suite**

### Adding a New AI Tool

1. **Create tool in** `backend/services/tools/`
2. **Add tool tests in** `backend/tests/`
3. **Register tool with agent in** `backend/services/agents/`
4. **Update frontend UI** (if tool requires new interface elements)
5. **Test tool integration** end-to-end

### Debugging Backend Issues

```bash
# Run backend with debug logging
cd backend
LOG_LEVEL=DEBUG poetry run python main.py

# Run single test with detailed output
poetry run pytest tests/test_specific.py -v -s

# Use Python debugger
poetry run python -m pdb main.py
```

### Debugging Frontend Issues

```bash
# Check browser console for errors
# Use React DevTools browser extension

# Run tests in headed mode
npx playwright test --headed --debug

# Run tests in UI mode
npx playwright test --ui
```

---

## 🔧 CI/CD Pipeline

**Location**: `.github/workflows/ci.yml`

### CI Checks on Pull Requests

The following checks run automatically:

1. **Backend Tests** (`test` job):
   - Runs pytest test suite
   - Requires `OPENAI_API_KEY` secret

2. **Backend Linting** (`lint` job):
   - Runs `flake8` for code linting
   - Runs `black --check` for formatting

3. **Frontend E2E Tests** (`frontend-tests` job):
   - Runs Playwright test suite
   - Tests run in headless mode

4. **Frontend Performance** (`frontend-performance` job):
   - Performance benchmarking tests

### Ensuring CI Success

Before pushing:
```bash
# Backend
cd backend
poetry run pytest tests/
poetry run flake8 .
poetry run black --check .

# Frontend
cd frontend
npm test
```

---

## 🐛 Troubleshooting

### Backend Issues

**Issue**: `Address already in use` on port 8000
```bash
# Find process using port 8000
lsof -i :8000

# Kill process
kill <PID>
```

**Issue**: Import errors or module not found
```bash
cd backend
poetry install --no-cache
```

**Issue**: Database connection errors
- Check `.env` file has correct `DATABASE_AZURE_URL`
- Ensure database is accessible from your network

**Issue**: LLM API errors
- Verify `LLM_PROVIDER` is set correctly in `.env`
- Check corresponding API key is configured (e.g., `OPENAI_API_KEY`)
- Ensure you have API credits/quota available

### Frontend Issues

**Issue**: Frontend fails to start
```bash
cd frontend
rm -rf node_modules .next
npm install
npm run dev
```

**Issue**: API connection errors
- Ensure backend is running on `http://localhost:8000`
- Check `NEXT_PUBLIC_API_BASE_URL` in `.env`
- Verify CORS settings in `backend/main.py`

**Issue**: Playwright tests failing
```bash
# Reinstall browsers
npx playwright install --with-deps

# Clear cache
rm -rf .next
```

### Docker Issues

**Issue**: Docker build fails
```bash
# Clean Docker cache
docker system prune -a

# Rebuild with no cache
docker-compose build --no-cache
```

**Issue**: Container won't start
```bash
# Check logs
docker-compose logs backend
docker-compose logs frontend

# Restart specific service
docker-compose restart backend
```

---

## 📚 Additional Resources

- **Architecture Documentation**: See `ARCHITECTURE.md`
- **Contributing Guide**: See `CONTRIBUTING.md`
- **Color Customization**: See `docs/color-customization.md`
- **Frontend Test Guide**: See `frontend/tests/README.md`
- **API Documentation**: Run backend and visit `http://localhost:8000/docs`

---

## 🤖 Agent-Specific Best Practices

### When Adding Features
1. ✅ Always check existing implementations first
2. ✅ Write tests before/alongside code
3. ✅ Run tests after each change
4. ✅ Maintain consistent code style (use linters)
5. ✅ Update documentation for new features

### When Fixing Bugs
1. ✅ Write a failing test that reproduces the bug
2. ✅ Fix the bug
3. ✅ Verify test now passes
4. ✅ Check for similar issues elsewhere
5. ✅ Run full test suite to ensure no regressions

### When Refactoring
1. ✅ Ensure full test coverage exists first
2. ✅ Make small, incremental changes
3. ✅ Run tests after each change
4. ✅ Verify no behavioral changes (tests still pass)
5. ✅ Update documentation if interfaces change

---

**Last Updated**: October 2025  
**Maintainers**: NaLaMap Development Team  
**Contact**: [info@nalamap.org](mailto:info@nalamap.org)
