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

> **See [CONTRIBUTING.md](CONTRIBUTING.md) for the full list.**

*   **Run Backend Tests**: `cd backend && poetry run pytest`
*   **Run Frontend Tests**: `cd frontend && npx playwright test`
*   **Lint Backend**: `cd backend && poetry run flake8 . && poetry run black .`
*   **Lint Frontend**: `cd frontend && npm run lint`
