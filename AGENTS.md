# AGENTS.md - AI Development Context

> **Target Audience**: AI coding assistants (Cursor, Copilot, etc.) and automated development tools.

This document provides high-level context and specific instructions for AI agents working on the NaLaMap project. For standard development procedures, please refer to **[CONTRIBUTING.md](CONTRIBUTING.md)**.

---

## 🤖 Core Directives for Agents

When contributing to this repository, you **MUST** follow these rules:

1.  **Single Source of Truth**: All development workflows (testing, linting, running) are defined in **[CONTRIBUTING.md](CONTRIBUTING.md)**. Do not hallucinate alternative procedures.
2.  **Test-Driven Development**:
    *   **Always** run existing tests before modifying code to establish a baseline.
    *   **Always** write new tests for new features or bug fixes.
    *   **Verify** changes by running the relevant test suite (`pytest` for backend, `playwright` for frontend).
3.  **Code Quality**:
    *   **Linting is mandatory**. After editing files, run the linters defined in `CONTRIBUTING.md` (`flake8`, `black`, `npm run lint`).
    *   Fix linter errors immediately. Do not submit code with linting violations.
4.  **Documentation**:
    *   Update `README.md` files if you change how a component works.
    *   If you add a new tool, update `backend/services/tools/README.md`.
    *   If you add a new dependency, update `pyproject.toml` or `package.json`.

---

## 🗺️ Repository Map & Context

To help you navigate the codebase efficiently:

### Backend Structure (`backend/`)
*   **API Layer**: `api/` (FastAPI endpoints).
*   **Business Logic**: `services/` (AI agents, tools, database logic).
    *   `services/agents/`: Legacy agent implementations.
    *   `services/tools/`: **Core AI tools** (geocoding, geoprocessing). **Read `backend/services/tools/README.md`** for details.
*   **Data Models**: `models/` (Pydantic models).
*   **Tests**: `tests/` (pytest suite). **Read `backend/tests/README.md`** for details.

### Frontend Structure (`frontend/`)
*   **Pages**: `app/page.tsx` (Main entry).
*   **Components**: `app/components/` (React components).
    *   `maps/`: Leaflet map logic.
    *   `chat/`: AI chat interface.
*   **State**: `app/stores/` (Zustand stores).
*   **Tests**: `tests/` (Playwright E2E). **Read `frontend/tests/README.md`** for details.

### Key Configuration Files
*   `backend/pyproject.toml`: Python dependencies and tool config (flake8, black).
*   `frontend/package.json`: Node dependencies and scripts.
*   `docker-compose.yml`: Production deployment.
*   `dev.docker-compose.yml`: Development environment.

---

## 🛠️ Common Tasks for Agents

### 1. Adding a New AI Tool
When asked to add a new capability to the AI assistant:
1.  Create the tool function in `backend/services/tools/`.
2.  Use the `@tool` decorator from `langchain.tools`.
3.  Add unit tests in `backend/tests/`.
4.  **Register the tool** in `backend/services/default_agent_settings.py`.
5.  Document it in `backend/services/tools/README.md`.

### 2. Modifying the Agent Workflow
The main agent logic is in `backend/services/single_agent.py` (LangGraph ReAct agent).
*   If changing the system prompt, look for `DEFAULT_SYSTEM_PROMPT`.
*   If changing tool selection logic, check `create_geo_agent`.

### 3. Debugging
If tests fail:
*   **Backend**: Read the `pytest` output. Use `pytest -vv` for more detail. Check `backend/app_output.log` if available.
*   **Frontend**: Use `npx playwright test --ui` or check the HTML report.

---

## 🔄 Quick Reference: Commands

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

#### Log File

The backend writes all log output to **`backend/debug.log`** in addition to stdout.
The file rotates automatically at 5 MB (2 backups kept), so it never grows unbounded.
It is listed in `.gitignore` (`*.log`) and is never committed.

```bash
# Watch logs live while the backend is running
tail -f backend/debug.log

# Show only the last 50 lines
tail -50 backend/debug.log

# Find all chat requests (includes first 120 chars of the user query)
grep "\[CHAT\]" backend/debug.log

# Find all agent tool activity (which tools were active for each request)
grep "\[AGENT\]" backend/debug.log

# Find errors and warnings only
grep -E "ERROR|WARNING" backend/debug.log

# Combine: see the full lifecycle of the last few requests
grep -E "\[CHAT\]|\[AGENT\]|on_tool_start|on_tool_end|ERROR" backend/debug.log | tail -40
```

**Structured log markers** added to key locations:

| Marker | Module | What it logs |
|--------|--------|-------------|
| `[CHAT]` | `api.nalamap` | User query (first 120 chars) at request start |
| `[AGENT] tools_available=` | `services.single_agent` | Full list of configured tools before dynamic selection |
| `[AGENT] tools_active=` | `services.single_agent` | Final tool list passed to the agent (after dynamic selection, if enabled) |
| `[AGENT] dynamic tool selection:` | `services.single_agent` | Number selected and their names, when dynamic tool selection is on |

#### Log Level

Control verbosity via the `LOG_LEVEL` environment variable (applies to both console and file):

```bash
# Default — INFO and above
poetry run python main.py

# Verbose — includes LangGraph state transitions and agent internals
LOG_LEVEL=DEBUG poetry run python main.py

# Quiet — warnings and errors only (useful in production)
LOG_LEVEL=WARNING poetry run python main.py
```

#### Other debug commands

```bash
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

*   **Run Backend Tests**: `cd backend && poetry run pytest`
*   **Run Frontend Tests**: `cd frontend && npx playwright test`
*   **Lint Backend**: `cd backend && poetry run flake8 . && poetry run black .`
*   **Lint Frontend**: `cd frontend && npm run lint`
