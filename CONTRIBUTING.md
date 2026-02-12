# Contributing to NaLaMap

Thank you for your interest in contributing to NaLaMap! This guide provides comprehensive instructions for setting up your environment, developing features, and submitting changes.

> **Note for AI Agents**: This file is the **Single Source of Truth** for development standards, testing procedures, and workflows. Please follow these instructions strictly.

---

## 📋 Table of Contents

1. [Getting Started](#getting-started)
2. [Environment Setup](#environment-setup)
3. [Running the Application](#running-the-application)
4. [Testing Guidelines](#testing-guidelines)
5. [Code Quality & Linting](#code-quality--linting)
6. [Development Workflow](#development-workflow)
7. [Common Development Tasks](#common-development-tasks)
8. [Troubleshooting](#troubleshooting)
9. [Community Guidelines](#community-guidelines)

---

## 🚀 Getting Started

### Issues
- Check existing issues before creating a new one.
- Use issue templates when reporting bugs or requesting features.
- Be clear and provide as much information as possible.

### Pull Requests
- Create a branch for your changes (do not commit directly to `main`).
- Keep changes focused on a single concern.
- Follow existing code style and conventions.
- **Must include tests** for new functionality.
- Update documentation as needed.

---

## 🛠️ Environment Setup

### Prerequisites
- **Python 3.11+**
- **Node.js 18+**
- **Poetry** (Python dependency management)
- **Docker & Docker Compose** (optional)
- **Git**

### Setup Steps

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

## 🏃 Running the Application

### Backend (FastAPI)
**Directory**: `backend/`

```bash
cd backend
poetry install
poetry run python main.py
```
- **URL**: `http://localhost:8000`
- **Docs**: `http://localhost:8000/docs`

### Frontend (Next.js)
**Directory**: `frontend/`

```bash
cd frontend
npm install
npm run dev
```
- **URL**: `http://localhost:3000`

### Full Stack via Docker
```bash
docker-compose -f dev.docker-compose.yml up --build
```

---

## 🧪 Testing Guidelines

### Backend Tests (pytest)
**Location**: `backend/tests/`
**Detailed Guide**: [`backend/tests/README.md`](backend/tests/README.md)

```bash
cd backend

# Run all tests
poetry run pytest tests/

# Run specific markers
poetry run pytest tests/ -m unit
poetry run pytest tests/ -m integration
```

### Frontend Tests (Playwright)
**Location**: `frontend/tests/`
**Detailed Guide**: [`frontend/tests/README.md`](frontend/tests/README.md)

```bash
cd frontend

# Install browsers (first time)
npx playwright install --with-deps

# Run all tests
npm test

# Run UI mode (debug)
npx playwright test --ui
```

---

## ✅ Code Quality & Linting

### Backend (Python)
**Tools**: Flake8, Black, isort.

```bash
cd backend
poetry run flake8 .        # Linting
poetry run black --check . # Format check
poetry run black .         # Auto-format
poetry run isort .         # Sort imports
```

### Frontend (TypeScript)
**Tools**: ESLint.

```bash
cd frontend
npm run lint
```

---

## 🔄 Development Workflow

1. **Create a Feature Branch**:
   ```bash
   git checkout -b features/YYYYMMDD_YourFeatureName
   ```

2. **Develop & Test**:
   - Write tests *before* or *alongside* code.
   - Run tests frequently (`npm test`, `pytest`).

3. **Check Quality**:
   - Run linters before committing.
   - Ensure no regressions.

4. **Commit**:
   - Use clear, descriptive messages.
   - Example: `feat: Add new geocoding functionality`

5. **Submit PR**:
   - Push to GitHub.
   - Open PR targeting `main`.
   - Ensure CI checks pass.

---

## 🛠️ Common Development Tasks

### Adding Dependencies
- **Backend**: `cd backend && poetry add <package>`
- **Frontend**: `cd frontend && npm install <package>`

### Adding an AI Tool
1. Create tool in `backend/services/tools/`.
2. Add tests in `backend/tests/`.
3. Register tool in `backend/services/default_agent_settings.py`.
4. Update frontend UI if needed.
5. Verify with `backend/services/tools/README.md`.

---

## 🐛 Troubleshooting

- **Port 8000 in use**: `lsof -i :8000` then `kill <PID>`.
- **LLM Errors**: Check `.env` for `LLM_PROVIDER` and API keys.
- **Frontend Start Fail**: `rm -rf node_modules && npm install`.

---

## 🤝 Community Guidelines

- Be respectful and inclusive.
- Focus on constructive feedback.
- Help others when you can.

If you have questions, please open an issue or reach out to the project maintainers.

---

## 📚 Documentation Strategy

We maintain a comprehensive documentation structure to help both human developers and AI agents understand and contribute to the project.

### High-Level Overview
- **[README.md](README.md)**: The main entry point for users and potential developers. Provides an overview, features, and quick start guide.
- **[CONTRIBUTING.md](CONTRIBUTING.md)**: (This file) The **Single Source of Truth** for development workflows, testing, and contribution standards.
- **[AGENTS.md](AGENTS.md)**: Context for AI coding agents, including repository maps and agent-specific best practices.
- **[ARCHITECTURE.md](ARCHITECTURE.md)**: Detailed system architecture, component design, and data flow.
- **[CHANGELOG.md](CHANGELOG.md)**: History of changes and versions.

### Component-Specific Documentation
- **[backend/tests/README.md](backend/tests/README.md)**: Guide for running and writing backend tests.
- **[backend/services/tools/README.md](backend/services/tools/README.md)**: Documentation for the AI tools available in the system.
- **[frontend/tests/README.md](frontend/tests/README.md)**: Guide for frontend E2E testing with Playwright.
- **[e2e-tests/README.md](e2e-tests/README.md)**: Guide for full-stack end-to-end testing.

### Feature Documentation
Specific feature guides (e.g., Color Customization, Azure Deployment) are located in the `docs/` directory.

**When contributing, please ensure you update the relevant documentation.**
