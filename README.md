# NaLaMap

NaLaMap is an open-source platform that helps users find and analyze geospatial data in a natural way. It combines modern web technologies with AI capabilities to create an intuitive interface for interacting with geographic information.

## Features

* Upload and display vector data on a map. 
* Geocode Locations using OSM and GeoNames (e.g. hospitals, schools, roads, railways). Intelligent geometry filtering ensures queries return the correct feature types (e.g., road segments instead of bus stops). See [OSM Geometry Filtering Documentation](docs/geocoding-osm-geometry-filtering.md).
* Find and integrate data from existing Open Data Portals or own databases.
* Chat with AI-agent to retrieve information on data content and quality.
* **Multi-Provider LLM Support**: Choose from OpenAI, Azure OpenAI, Google Gemini, Mistral AI, or DeepSeek.
* AI-assisted map and layer styling. 
* Automated Geoprocessing using natural language (e.g buffer, centroids, intersections).
* Create and share GIS-AI-Applications for people without geodata expertise based on custom use-cases, processing logic and data-sources.
* Flexible Extension Possibilities of Toolbox e.g. for including document or web-search
* **Color Customization**: Customize the application's color scheme to match corporate branding or personal preferences. See [Color Customization Guide](docs/color-customization.md).






## Versioning Strategy

**NaLaMap follows [Semantic Versioning](https://semver.org/) for all releases using the format `MAJOR.MINOR.PATCH`:**

- **MAJOR** version increments for incompatible API changes, significant architectural changes, or breaking changes to existing functionality
- **MINOR** version increments for new features, enhancements, or backwards-compatible functionality additions (e.g., new geospatial tools, additional data sources, UI improvements)
- **PATCH** version increments for backwards-compatible bug fixes, security patches, and minor improvements

**Release Tags:** All releases are tagged in Git using the format `v{MAJOR}.{MINOR}.{PATCH}` (e.g., `v1.0.0`, `v1.2.3`).

**Pre-release versions** may use suffixes like `-alpha`, `-beta`, or `-rc` for testing purposes (e.g., `v1.1.0-beta.1`).

**Current Version:** The project is currently in active development. The first stable release will be tagged as `v1.0.0` once core functionality is complete and thoroughly tested.

## Project Structure

```
nalamap/
├── backend/              # Python FastAPI backend
│   ├── api/              # API endpoints
│   ├── core/             # Core configurations
│   ├── models/           # Data models
│   ├── services/         # Business logic services
│   │   ├── agents/       # AI agent implementations
│   │   ├── ai/           # AI service providers
│   │   ├── database/     # Database connectors
│   │   └── tools/        # Utility tools
│   └── main.py           # Application entry point
├── frontend/             # Next.js frontend
│   ├── app/              # Next.js application
│   │   ├── components/   # React components
│   │   ├── hooks/        # Custom React hooks
│   │   └── page.tsx      # Main page component
│   └── public/           # Static assets
└── nginx/                # Nginx configuration for serving the application
```

> 📖 **For detailed architecture documentation**, see [ARCHITECTURE.md](ARCHITECTURE.md)  
> 🤖 **For AI agent development guidelines**, see [AGENTS.md](AGENTS.md)
## Simplified Entitiy Relationship Model
The following model was created to give you a high level overview of how NaLaMap works. It shows an example user-request to change the sytling of a vector layer in the map. 
<img width="950" height="534" alt="image" src="https://github.com/user-attachments/assets/6a09918a-fbd0-4860-a362-a5d4f55e871a" />


## Getting Started

### ⚙️ Prerequisites

- **Git**  
- **Python 3.10+**  
- **Node.js 18+**  
- **Docker & Docker Compose** (optional)  
- **[Poetry](https://python-poetry.org/docs/)** (for backend)

### Quick Setup (Recommended)

Follow these steps to get the application running locally:

#### 1. Clone the Repository
```bash
git clone git@github.com:nalamap/nalamap.git
cd nalamap
```

#### 2. Environment Configuration

**Create your environment file:**
Create a `.env` file in the root directory based on the provided `.env.example`:
```bash
cp .env.example .env
```

**Configure your environment variables:**
Edit the `.env` file to include your configuration. The environment file contains several categories of settings:

- **AI Provider Configuration**: Choose between OpenAI, Azure OpenAI, Google AI, Mistral AI, or DeepSeek and provide the corresponding API keys
- **Database Settings**: PostgreSQL connection details (a demo database is pre-configured)
- **API Endpoints**: Backend API base URL configuration
- **Optional Services**: LangSmith tracing for monitoring AI interactions

**Map / WMTS Projection Safety**:

To avoid rendering projection-mismatched WMTS layers, the backend filters out any WMTS layer that lacks a WebMercator (EPSG:3857 family) TileMatrixSet by default.

Environment variable to control this behavior:

`NALAMAP_FILTER_NON_WEBMERCATOR_WMTS` (default: `true`)

Set to `false` to allow all WMTS layers (may lead to visual misalignment unless tiles are in WebMercator).

Details: see `docs/wmts.md`.

> **Note**: The `.env.example` includes a demo database connection that you can use for testing. For production use, configure your own database credentials.

**⚠️ Important: Single Provider Selection**
You can only use **ONE AI provider at a time**. The active provider is determined by the `LLM_PROVIDER` environment variable. To switch providers, change this value and restart the application.

**Supported LLM_PROVIDER values and their models:**

| Provider | LLM_PROVIDER Value | Default Model | Model Configuration | Additional Configuration |
|----------|-------------------|---------------|-------------------|--------------------------|
| OpenAI | `openai` | `gpt-4o-mini` | `OPENAI_MODEL` | `OPENAI_API_KEY` |
| Azure OpenAI | `azure` | User-defined | `AZURE_OPENAI_DEPLOYMENT` | `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_API_VERSION` |

| Google AI | `google` | `gemini-1.5-pro-latest` | `GOOGLE_MODEL` | `GOOGLE_API_KEY` |
| Mistral AI | `mistral` | `mistral-large-latest` | `MISTRAL_MODEL` | `MISTRAL_API_KEY` |
| DeepSeek | `deepseek` | `deepseek-chat` | `DEEPSEEK_MODEL` | `DEEPSEEK_API_KEY` |

**Example configuration:**
```bash
# Choose your provider
LLM_PROVIDER=openai

# Configure the model (optional - defaults to recommended model)
OPENAI_MODEL=gpt-4o-mini

# Add the corresponding API key
OPENAI_API_KEY=your_openai_api_key_here

# Note: You only need to configure the provider you're using
```

**🎯 Model Selection:**
All providers now support configurable model selection via environment variables. If you don't specify a model, NaLaMap uses cost-effective default models optimized for geospatial tasks.

**⚙️ Advanced Parameter Customization:**
To modify advanced LLM parameters (temperature, max_tokens, timeout, etc.), edit the provider files in `backend/services/ai/`:
- `openai.py` - OpenAI configuration
- `google_genai.py` - Google AI configuration
- `mistralai.py` - Mistral AI configuration
- `deepseek.py` - DeepSeek configuration
- `azureai.py` - Azure OpenAI configuration

Each file contains a `get_llm()` function where you can adjust parameters like `temperature`, `max_tokens`, `max_retries`, etc.

#### 3. Setup Backend (Python/FastAPI)
```bash
# Navigate to backend directory
cd backend

# We recommend poetry config virtualenvs.create true to manage your .venv inside the repo
poetry install

# Start the backend server
poetry run python main.py
```

The frontend will be available at `http://localhost:3000`

The backend will be available at `http://localhost:8000`
- API Documentation: `http://localhost:8000/docs`

#### 4. Setup Frontend (Next.js)
Open a new terminal and run:
```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm i

# Start development server
npm run dev
```

### Alternative: Docker Deployment

If you prefer using Docker:

1. Configure your environment variables as described above.

2. Start the application using Docker Compose:
   ```bash
   docker-compose up
   ```

3. Access the application at `http://localhost:80`

### Docker Development Environment

For a complete development environment with hot-reload capabilities:

```bash
docker-compose -f dev.docker-compose.yml up --build
```

## Technologies Used

### Backend
- **FastAPI**: Modern, fast web framework for building APIs
- **LangChain**: Framework for developing applications powered by language models
- **LangGraph**: For building complex AI agent workflows
- **OpenAI/Azure/DeepSeek**: AI model providers for natural language processing
- **Uvicorn**: ASGI server for serving the FastAPI application

### Frontend
- **Next.js 15**: React framework for building web applications
- **React 19**: JavaScript library for building user interfaces
- **Leaflet**: Open-source JavaScript library for interactive maps
- **Tailwind CSS**: Utility-first CSS framework
- **TypeScript**: Typed JavaScript for safer code

### Infrastructure
- **Docker**: Container platform
- **Nginx**: Web server and reverse proxy

## Tests

The project includes comprehensive test suites for both backend and frontend components.

### Backend Tests (pytest)

Navigate to the backend directory and run the tests:
```bash
cd backend
poetry run pytest tests/

# Run with verbose output
poetry run pytest tests/ -v

# Run specific test markers (unit, integration, styling, etc.)
poetry run pytest tests/ -m unit
```

### Frontend Tests (Playwright)

Navigate to the frontend directory and run the E2E tests:
```bash
cd frontend

# Install Playwright browsers (first time only)
npx playwright install --with-deps

# Run all tests
npm test

# Run in interactive UI mode
npx playwright test --ui
```

> 📖 **For detailed testing guidelines**, see [CONTRIBUTING.md](CONTRIBUTING.md#testing-guidelines)  
> 📖 **For frontend test documentation**, see [frontend/tests/README.md](frontend/tests/README.md)

**Note**: Some tests may require environment variables (e.g., `OPENAI_API_KEY`). Mock data is used where possible to avoid external dependencies.

## Troubleshooting

### Common Issues

**Backend fails to start with "Address already in use" error:**
- Check if port 8000 is already in use: `lsof -i :8000`
- Kill any existing processes: `kill <PID>`

**LLM API errors:**
- Verify your `.env` file is in the root directory
- Check that your provider's API key is set correctly (e.g., `OPENAI_API_KEY`, `GOOGLE_API_KEY`, `MISTRAL_API_KEY`, etc.)
- Ensure `LLM_PROVIDER` matches your chosen provider (openai, azure, google, mistral, or deepseek)

**Frontend fails to start:**
- Ensure Node.js 18+ is installed: `node --version`
- Clear npm cache: `npm cache clean --force`
- Delete node_modules and reinstall: `rm -rf node_modules && npm i`

## Security

🔒 **Important Security Notes:**

* **Never commit `.env` files** with real API keys to version control
* **Use `.env.example`** as a template and add your own credentials  
* **Rotate API keys regularly** and monitor usage
* **File uploads are not committed** to version control for privacy

**For production deployments:**

* Use environment variables or secure secret management
* Enable HTTPS/TLS encryption  
* Implement proper authentication and authorization
* Regular security audits and dependency updates

**Reporting Security Vulnerabilities:**
If you discover a security vulnerability, please send an email to [info@nalamap.org] instead of using the issue tracker.

## Documentation

NaLaMap has comprehensive documentation to help you get started and contribute:

### Core Documentation
- **[README.md](README.md)** (this file) - Project overview and quick start guide
- **[CONTRIBUTING.md](CONTRIBUTING.md)** - Main development guide
  - Environment setup and running components
  - Testing guidelines (pytest, Playwright)
  - Code quality & linting
  - Workflow and troubleshooting
- **[AGENTS.md](AGENTS.md)** - Context for AI coding assistants
  - Repository map and architecture context
  - Agent-specific best practices
  - Core directives for AI tools
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - System architecture and design
  - High-level architecture overview
  - Backend and frontend structure
  - AI agent system (LangGraph)
  - Data flow and communication patterns
  - Deployment architecture

### Additional Documentation
- **[CONTRIBUTING.md](CONTRIBUTING.md)** - How to contribute to the project
- **[CHANGELOG.md](CHANGELOG.md)** - Version history
- **[backend/tests/README.md](backend/tests/README.md)** - Backend testing guide
- **[backend/services/tools/README.md](backend/services/tools/README.md)** - AI tools documentation
- **[frontend/tests/README.md](frontend/tests/README.md)** - Frontend testing guide
- **[docs/](docs/)** - Feature-specific documentation
  - Color customization
  - Azure deployment
  - Performance optimizations
  - And more...

## Contributing

We welcome contributions from the community! If you're interested in helping improve NaLaMap, please check out our documentation:

- **[Contributing Guide](CONTRIBUTING.md)** - Guidelines for development and testing
- **[AGENTS.md](AGENTS.md)** - Context for AI coding assistants
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - System architecture and component structure
- **[Code of Conduct](CODE_OF_CONDUCT.md)** - Community guidelines

Feel also free to join our [community channel (Discord)](http://discord.nalamap.org/) to get to know us. We have regular meetings where we discuss the roadmap, feature requirements and ongoing work. 

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Inspired by the need for more intuitive geospatial data exploration
- Built with open-source mapping libraries and AI technologies
- Special thanks to all contributors and the open-source community
