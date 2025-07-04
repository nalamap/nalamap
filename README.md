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

## Project Structure

```
geoweaver/
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

## Prerequisites

- Docker and Docker Compose
- Node.js (for local frontend development)
- Python 3.10+ (for local backend development)

## Getting Started

### Prerequisites

- Python 3.10+ (for backend)
- Node.js 18+ (for frontend)
- Git

### Quick Setup (Recommended)

Follow these steps to get the application running locally:

#### 1. Clone the Repository
```bash
git clone git@github.com:nalamap/nalamap.git
cd nalamap
```

#### 2. Environment Configuration
Create a `.env` file in the backend directory based on the provided `.env.example`:
```bash
cp .env.example backend/.env
```

Edit the `backend/.env` file to include your API keys:
- OpenAI API key (required)
- Azure OpenAI API key (if using Azure)
- DeepSeek API key (if using DeepSeek)
- Database connection details
- Other service configurations

#### 3. Setup Backend (Python/FastAPI)
```bash
# Navigate to backend directory
cd backend

# Create virtual environment
python3 -m venv .venv

# Activate virtual environment
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start the backend server
python3 main.py
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

## Running Tests

The project includes a test suite for the backend components. To run the tests:

1. Navigate to the backend directory and activate your virtual environment:
   ```bash
   cd backend
   source .venv/bin/activate
   ```

2. Install pytest (if not already installed):
   ```bash
   pip install pytest
   ```

3. Run the tests:
   ```bash
   python -m pytest tests/ -v
   ```

Note: Some tests may require a running server or mock data. If you encounter connection errors, it's likely because the test is trying to access resources that aren't available in the test environment.

## Troubleshooting

### Common Issues

**Backend fails to start with "Address already in use" error:**
- Check if port 8000 is already in use: `lsof -i :8000`
- Kill any existing processes: `kill <PID>`

**Import errors with langgraph:**
- Ensure you're using the virtual environment: `source backend/.venv/bin/activate`
- Reinstall dependencies: `pip install -r requirements.txt`

**OpenAI API errors:**
- Verify your `.env` file is in the `backend/` directory
- Check that `OPENAI_API_KEY` is set correctly

**Frontend fails to start:**
- Ensure Node.js 18+ is installed: `node --version`
- Clear npm cache: `npm cache clean --force`
- Delete node_modules and reinstall: `rm -rf node_modules && npm i`

> **Note**: Additional README files are available in both the `/frontend` and `/backend` directories with more specific instructions for each component.

## Contributing

We welcome contributions from the community! If you're interested in helping improve NaLaMap, please check out our [Contributing Guide](CONTRIBUTING.md) for information on how to get started.

Please also review our [Code of Conduct](CODE_OF_CONDUCT.md) to ensure a positive and inclusive environment for all contributors.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Inspired by the need for more intuitive geospatial data exploration
- Built with open-source mapping libraries and AI technologies
- Special thanks to all contributors and the open-source community
