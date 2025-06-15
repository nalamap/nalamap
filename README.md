# GeoWeaver

GeoWeaver is an open-source platform that helps users find and analyze geospatial data in a natural way. It combines modern web technologies with AI capabilities to create an intuitive interface for interacting with geographic information.

## Features

- **Natural Language Interface**: Interact with maps and geospatial data using conversational prompts
- **Multiple Mapping Options**: Choose between Leaflet and MapLibre GL for different mapping needs
- **AI-Powered Analysis**: Leverage AI models to interpret and analyze geospatial data
- **WMS Integration**: Connect with Web Map Service providers to access diverse geospatial datasets
- **User Management**: Secure authentication and user management system
- **Responsive Design**: Works across desktop and mobile devices
- **Docker Deployment**: Easy setup and deployment using Docker containers

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

### Environment Configuration

Before running the application, you'll need to set up your environment variables:

1. Create a `.env` file in the root directory based on the provided `.env.example`:
   ```bash
   cp .env.example .env
   ```

2. Edit the `.env` file to include your API keys and other required settings:
   - OpenAI API key
   - Azure OpenAI API key (if using Azure)
   - DeepSeek API key (if using DeepSeek)
   - Database connection details
   - Other service configurations

> **Note**: Additional README files are available in both the `/frontend` and `/backend` directories with more specific instructions for each component.

### Docker Deployment

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/geoweaver.git
   cd geoweaver
   ```

2. Configure your environment variables as described above.

3. Start the application using Docker Compose:
   ```bash
   docker-compose up
   ```

4. Access the application at `http://localhost:80`

### Development Setup

#### Backend (FastAPI)

1. Navigate to the backend directory:
   ```bash
   cd backend
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the development server:
   ```bash
   uvicorn main:app --reload
   ```

#### Frontend (Next.js)

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Start the development server:
   ```bash
   npm run dev
   ```

4. Access the frontend at `http://localhost:3000`

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
- **PostgreSQL**: Database for persistent storage
- **Uvicorn**: ASGI server for serving the FastAPI application

### Frontend
- **Next.js 15**: React framework for building web applications
- **React 19**: JavaScript library for building user interfaces
- **Leaflet**: Open-source JavaScript library for interactive maps
- **MapLibre GL**: JavaScript library for vector maps
- **Tailwind CSS**: Utility-first CSS framework
- **TypeScript**: Typed JavaScript for safer code

### Infrastructure
- **Docker**: Container platform
- **Nginx**: Web server and reverse proxy

## Running Tests

The project includes a test suite for the backend components. To run the tests:

1. Navigate to the backend directory:
   ```bash
   cd backend
   ```

2. Create and activate a Python virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. Install pytest and project dependencies:
   ```bash
   pip install pytest
   pip install -r requirements.txt
   ```

4. Run the tests:
   ```bash
   python -m pytest tests/ -v
   ```

Note: Some tests may require a running server or mock data. If you encounter connection errors, it's likely because the test is trying to access resources that aren't available in the test environment.

## Contributing

We welcome contributions from the community! If you're interested in helping improve GeoWeaver, please check out our [Contributing Guide](CONTRIBUTING.md) for information on how to get started.

Please also review our [Code of Conduct](CODE_OF_CONDUCT.md) to ensure a positive and inclusive environment for all contributors.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Inspired by the need for more intuitive geospatial data exploration
- Built with open-source mapping libraries and AI technologies
- Special thanks to all contributors and the open-source community