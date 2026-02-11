# Contributing to NaLaMap

Thank you for your interest in contributing to NaLaMap! We're excited to welcome community contributions as we build this project together.

## Getting Started

### Issues

- Check existing issues before creating a new one related to a new feature or pull request. 
- Use the issue templates when reporting bugs or requesting features
- Be clear and provide as much information as possible

### Pull Requests

- Create a branch for your changes (don't commit directly to `main`)
- Make your changes focused and keep them to a single concern
- Follow existing code style and conventions
- Include tests for new functionality when possible
- Update documentation as needed

## Development Workflow

1. Fork the repository
2. Create a new branch from `main` for your changes
3. Make your changes
4. Test your changes
5. Submit a pull request

## Code Style

- Follow the existing code style in the project
- Use meaningful variable and function names
- Include comments for complex logic

### Linting Rules

**Backend (Python):**
- **Flake8**: Code linting with 100 character line length
- **Black**: Code formatting with 100 character line length
- **isort**: Import sorting
- Run locally: `poetry run flake8 .` and `poetry run black --check .`

**Frontend:**
- Currently no enforced linting rules
- ESLint is configured but not required for builds to pass

**CI Integration:**
- Backend linting checks run automatically on pull requests
- Ensure your backend code passes these checks before submitting

### Testing

Before opening a pull request, please run the backend test suite locally:

```bash
cd backend
poetry run pytest tests/
```

Also run the frontend Playwright tests, since these are part of the CI workflow:

```bash
cd frontend
npx playwright install --with-deps
npx playwright test
```

Pull requests will also run tests automatically in CI. Running tests locally first
helps catch issues early and keeps the review process smooth.

## Commit Messages

- Use clear, descriptive commit messages
- Start with a brief summary line
- Add more detailed explanation if necessary
- Reference issue numbers when applicable

## Review Process

- All contributions require review before merging
- Be responsive to feedback and questions
- Be patient, as reviews may take some time

## Community Guidelines

- Be respectful and inclusive in all interactions
    - Focus on constructive feedback
    - Help others when you can
    If you have any questions or need assistance, please open an issue or reach out to the project maintainers.

## Documentation Strategy

We maintain a comprehensive documentation structure to help both human developers and AI agents understand and contribute to the project.

### High-Level Overview
- **[README.md](README.md)**: The main entry point for users and potential developers. Provides an overview, features, and quick start guide.
- **[AGENTS.md](AGENTS.md)**: Dedicated onboarding guide for AI coding agents (and humans). Covers development workflow, testing, and environment setup in detail.
- **[CONTRIBUTING.md](CONTRIBUTING.md)**: (This file) Guidelines for contributing, including issue reporting, PR process, and code standards.
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

    We appreciate all contributions, whether it's code, documentation, bug reports, or feature suggestions!
