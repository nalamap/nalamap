# NaLaMap

NaLaMap is an open-source platform that helps users find and analyze geospatial data in a natural way. It combines modern web technologies with AI capabilities to create an intuitive interface for interacting with geographic information.

## Features

* Upload and display vector data on a map. 
* Geocode Locations using OSM and GeoNames (e.g. hospitals, schools etc.).
* Find and integrate data from existing Open Data Portals or own databases.
* Chat with AI-agent to retrieve information on data content and quality.
* AI-assisted map and layer styling. 
* Automated Geoprocessing using natural language (e.g buffer, centroids, intersections).
* Create and share GIS-AI-Applications for people without geodata expertise based on custom use-cases, processing logic and data-sources.
* Flexible Extension Possibilities of Toolbox e.g. for including document or web-search

## Roadmap

We use GitHub [Milestones](https://github.com/nalamap/nalamap/milestones) and a [Kanban board](https://github.com/orgs/nalamap/projects/1/) to collaborate on our Minimal Viable Product (MVP). We hope to realize this first major release (V.1.0.0) in February 2026. 

Our next Milestone is V 0.2.0 scheduled for the 20th of September 2025. You can See a collection of planned improvements below. Issues describing those improvements will be added to the Kanban Board continously. 

<img width="1202" height="607" alt="image" src="https://github.com/user-attachments/assets/68bd8a33-0b43-4c1f-8b24-28196a3a07ff" />



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

- **AI Provider Configuration**: Choose between OpenAI, Azure OpenAI, or DeepSeek and provide the corresponding API keys
- **Database Settings**: PostgreSQL connection details (a demo database is pre-configured)
- **API Endpoints**: Backend API base URL configuration
- **Optional Services**: LangSmith tracing for monitoring AI interactions

**Key variables to configure:**
- `OPENAI_API_KEY`: Your OpenAI API key (required for OpenAI provider)
- `LLM_PROVIDER`: Set to "openai", "azure", or "deepseek" 
- `DATABASE_AZURE_URL`: Database connection (demo database provided)
- `NEXT_PUBLIC_API_BASE_URL`: Frontend-to-backend communication URL

> **Note**: The `.env.example` includes a demo database connection that you can use for testing. For production use, configure your own database credentials.

#### 3. Setup Backend (Python/FastAPI)
```bash
# Navigate to backend directory
cd backend

# We recommend poetry config virtualenvs.create true to manage your .venv inside the repo
poetry install

# Start the backend server
poetry run python main.py
```

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

The frontend will be available at `http://localhost:3000`

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

The project includes a test suite for the backend components. To run the tests:

1. Navigate to the backend directory and make sure you have setup the backend before:
   ```bash
   poetry run pytest tests/
   ```

Note: Some tests may require a running server or mock data. If you encounter connection errors, it's likely because the test is trying to access resources that aren't available in the test environment.

## Troubleshooting

### Common Issues

**Backend fails to start with "Address already in use" error:**
- Check if port 8000 is already in use: `lsof -i :8000`
- Kill any existing processes: `kill <PID>`

**OpenAI API errors:**
- Verify your `.env` file is in the `backend/` directory
- Check that `OPENAI_API_KEY` is set correctly

**Frontend fails to start:**
- Ensure Node.js 18+ is installed: `node --version`
- Clear npm cache: `npm cache clean --force`
- Delete node_modules and reinstall: `rm -rf node_modules && npm i`

> **Note**: Additional README files are available in the `/frontend` directory with more specific instructions for each component.

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

## Contributing

We welcome contributions from the community! If you're interested in helping improve NaLaMap, please check out our [Contributing Guide](CONTRIBUTING.md) for information on how to get started.

Please also review our [Code of Conduct](CODE_OF_CONDUCT.md) to ensure a positive and inclusive environment for all contributors.

Fell also fee to join our [community channel (Discord)](http://discord.nalamap.org/) to get to know us. We have regular meetings where we discuss the roadmap, feature requirements and ongoing work. 

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Inspired by the need for more intuitive geospatial data exploration
- Built with open-source mapping libraries and AI technologies
- Special thanks to all contributors and the open-source community
