# Changelog - NaLaMap

## [v0.3.0] - 2026-03-23

All notable changes since v0.2.0-iucn (243 commits, October 2025 – March 2026).

---

### 🔎 Semantic OSM Geocoding

A completely new geocoding pipeline that understands natural-language place descriptions and maps them to the correct OpenStreetMap tags.

- **TagInfo API fetcher** — downloads and indexes ~14 000 OSM tag definitions with usage counts
- **OSM tag vector store** — persistent SQLite + sqlite-vec database for tag embeddings with pluggable embedding providers (hashing / OpenAI / Azure)
- **SemanticTagResolver** — multi-stage pipeline: vector similarity → fuzzy matching (RapidFuzz) → LLM expansion, turning free-text queries into precise Overpass tag sets
- **Query transparency** — backend returns the resolved tags and Overpass queries; frontend displays them so users can see exactly what was searched
- **Tag database management UI** — settings panel to trigger, monitor, and rebuild the tag embedding store
- **Wildcard queries & geometry filtering** — support for broader OSM queries with automatic geometry-type filtering
- **Grouped search results** — Overpass results grouped by query in the frontend SearchResults panel
- **Improved disambiguation** — plain-language labels and choice-oriented responses when multiple interpretations exist
- **Dynamic embedding dimension detection** — the vector store detects the embedding provider's dimension at runtime and auto-migrates if it changes between deployments

### 🤖 AI Agent Improvements

- **Streaming (SSE)** — real-time Server-Sent Events streaming from the LangGraph agent to the frontend, replacing request/response polling
- **Parallel tool execution** — the agent can call multiple tools concurrently for faster results
- **Conversation summarisation** — automatic context summarisation with session management and cleanup, keeping long conversations within the token window
- **Dynamic tool selection** — agent settings component allowing users to enable/disable individual tools at runtime
- **Tool progress indicators** — formatted tool input parameters and output previews streamed to the frontend during execution
- **Smart scrolling** — auto-scroll control in chat components during streaming responses
- **Performance monitoring** — agent execution timing and metrics utilities with corresponding UI
- **Multi-step planning (experimental)** — the agent can decompose complex geospatial queries into a sequence of tool calls and execute them stepwise. Working but not yet fully stable.

### 🗺️ Geoprocessing & Projections

- **Smart CRS selection** — automatic selection of an appropriate projected coordinate system based on data extent, with a frontend toggle and per-user override
- **Hybrid geodesic/planar strategies** — buffer and area operations choose between geodesic and planar computation depending on data characteristics
- **CRS metadata display** — processing results show the chosen CRS and origin layers in both SearchResults and LayerList
- **User-configurable model settings** — dedicated model selection for geoprocessing execution

### 🌐 New LLM & Embedding Providers

- **Anthropic (Claude)** — full connector with langchain-anthropic integration
- **Moonshot AI (Kimi)** and **xAI (Grok)** — additional LLM providers
- **Provider ordering** — environment-variable-driven ordering of LLM providers
- **Embedding provider toggle** — switch between hashing (offline/free), OpenAI, or Azure OpenAI embeddings via `EMBEDDING_PROVIDER`

### 🔌 Model Context Protocol (MCP)

- **MCP server & client** — integration with external tools via the Model Context Protocol
- **Authentication support** — API key and custom header authentication for MCP connections
- **Settings UI** — frontend panel to configure and manage MCP servers

### 🛰️ OSINT Tools

- **ECMWF Weather** — weather data retrieval tool
- **World Bank indicators** — data query tool with chart rendering component
- **NASA GIBS imagery** — satellite imagery layers

### 📦 Layer Management & UI

- **GeoJSON download** — download button on layers with drag-and-drop support
- **Layer metadata popup** — drag handle component with detailed layer information
- **Improved layer styling** — source layers display, hover effects, and enhanced processing metadata
- **Marker support** — `marker-color` and `marker-symbol` for GeoJSON point features
- **Image proxy** — legend image endpoint to work around CORS issues
- **Reset functionality** — sidebar button to clear chat, layers, and settings with confirmation dialog

### 🔐 Authentication & Security

- **AUTH_ENABLED toggle** — disable authentication entirely for local development or demos
- **OIDC social login** — Google (and extensible to other providers) with cloud deployment support
- **Per-user settings** — message management mode stored per user
- **Cookie security hardening** — configurable secure/httponly/samesite cookie attributes
- **SECRET_KEY validation** — production docker-compose files require a non-empty secret; dev compose uses the backend default

### ☁️ Infrastructure & DevOps

- **Persistent volumes** — `backend-data` and `backend-uploads` named volumes in all docker-compose files for SQLite databases and uploaded files
- **Database init resilience** — retry logic and lazy table creation for ephemeral cloud databases
- **Optimised Dockerfiles** — multi-stage builds, startup benchmarks, and Poetry-based backend image
- **CI/CD updates** — GitHub Actions updated to Node 24 runtime, Python 3.13, checkout v4, setup-python v5
- **Docker image workflow** — build-and-push with matrix strategy, GHCR publishing, metadata artifacts, and deploy dispatch to infrastructure repo
- **Health check endpoints** — backend, frontend, and nginx health checks for container orchestration
- **Nginx loading page** — lightweight HTML page served while the backend starts
- **Persistent debug logging** — rotating log file with structured markers (`[CHAT]`, `[AGENT]`)
- **Deployment configuration** — JSON-based deployment config for custom instances with CORS proxy and dynamic User-Agent headers

### 🧹 Dependency & Code Quality

- **Backend dependencies pinned** — all `>=` constraints migrated to `^` (caret) to prevent accidental major-version upgrades
- **Backend packages updated** — black 26, isort 8, pydantic 2.12, langchain-core 0.3.83, langgraph 0.6.11, fastapi 0.116
- **Frontend packages updated** — Next.js 15.5, React 19, Tailwind 4.2
- **Codebase reformatted** — full reformat with black 26 and isort 8 (68 files)
- **Documentation refresh** — updated `.env.example`, `README.md`, `CONTRIBUTING.md`, and `AGENTS.md`

---

## [v0.2.0-iucn] - Since v.0.1.0-beta.1

All notable changes since version 0.1.0-beta.1 (350+ commits from October 2025).

---

## 🚀 NaLaMap Release Summary - October 2025

### 🎯 Frontend Revolution
- **Enhanced Map Experience**: Complete WMTS support, improved layer management, and GeoJSON rendering
- **Settings Overhaul**: New collapsible settings with GeoServer backends, embedding progress tracking, and dark mode
- **Color Customization**: Dynamic color system with IUCN Green List defaults and improved accessibility
- **UI/UX Polish**: Responsive layout, better mobile experience, and enhanced chat interface

### ⚙️ Backend Powerhouse
- **File Streaming**: Gzip compression and range request support for large GeoJSON files
- **Azure Integration**: Blob storage support with SAS URLs and CORS configuration
- **Security Hardening**: Cookie security, session validation, and path traversal protection
- **Performance Boost**: GeoJSON caching, background task management, and optimized embeddings

### 🤖 AI & Agent Evolution
- **Multi-Provider LLM**: Support for OpenAI, Azure AI, Google, Mistral, and DeepSeek
- **New Models**: GPT-5-nano/mini, o1-mini, o3-mini with advanced pricing and capabilities
- **Smart Tools**: Enhanced attribute tools with LLM-powered layer naming and fuzzy matching

### 🛠️ Tool Ecosystem Growth
- **GeoServer Tools**: Custom GeoServer integration with WMS/WFS/WMTS support
- **Geoprocessing**: Area calculation, clipping, and dissolving operations
- **Data Processing**: Improved WFS handling, GeoJSON normalization, and central file management

### 🚀 Infrastructure Excellence
- **CI/CD Pipeline**: Docker workflows, performance testing, and automated dependency updates
- **Cloud Ready**: Azure Container Apps deployment and multi-environment configuration
- **Quality Assurance**: Comprehensive testing and linting across the entire codebase

### 📊 Impact Metrics
- **350+ Commits** across 4 months of intensive development
- **Major Features**: 50+ new capabilities and enhancements
- **Test Coverage**: Expanded E2E and unit test suites
- **Contributors**: ZuitAMB, mucke2701, Jo-Schie, and Aminsch

---

## 📋 Detailed Changelogs

For the complete detailed changelog for v0.3.0, see: [`docs/changelog/CHANGELOG_v0.3.0_DETAILED.md`](docs/changelog/CHANGELOG_v0.3.0_DETAILED.md)

For the complete detailed changelog for v0.2.0-iucn, see: [`docs/changelog/CHANGELOG_v0.2.0-iucn_DETAILED.md`](docs/changelog/CHANGELOG_v0.2.0-iucn_DETAILED.md)

These detailed versions include:
- Complete breakdown by Frontend, Backend, Agent, Tools, and Infrastructure
- All bug fixes, improvements, and technical details
- Full contributor information and commit statistics
- Hierarchical organization by component and feature type