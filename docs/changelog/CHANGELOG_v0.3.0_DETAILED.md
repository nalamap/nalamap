# Changelog - NaLaMap

## [v0.3.0] - 2026-03-23

All notable changes since v0.2.0-iucn (243 commits, October 2025 – March 2026).

---

## 🚀 NaLaMap v0.3.0 Release Summary

### Highlights
- **Semantic OSM Geocoding**: A brand-new 9-step pipeline for resolving natural-language queries into OSM tags via embeddings, fuzzy matching, and LLM expansion.
- **Agent Streaming & Parallel Tools**: Real-time SSE streaming replaces polling; the agent can now call multiple tools concurrently.
- **Smart Projection Handling**: Automatic CRS selection for geoprocessing based on data extent, with hybrid geodesic/planar computation strategies.
- **New LLM Providers**: Anthropic (Claude), Moonshot AI (Kimi), xAI (Grok) alongside the existing OpenAI, Azure, Google, Mistral, and DeepSeek.
- **MCP Integration**: Model Context Protocol support for connecting external tool servers.
- **OSINT Tools**: ECMWF Weather, NASA GIBS, and World Bank indicator queries.
- **Infrastructure Hardening**: Persistent Docker volumes, database resilience, dependency pinning, CI/CD modernisation.

### 📊 Impact Metrics
- **243 Commits** across 5 months of development
- **15 Pull Requests** merged
- **Major Features**: 30+ new capabilities
- **Test Coverage**: 867+ backend tests passing; Playwright E2E suite maintained
- **Contributors**: ZuitAMB (169), mucke2701 (23), Jo-Schie (37), Clawson (3), Andreas T. Meyer-Berg (11)

---

## 🔎 Semantic OSM Geocoding

### ✨ New Features
- **TagInfo API fetcher (F01)** — downloads and indexes ~14 000 OSM tag definitions with usage statistics from the TagInfo API
- **OSM tag vector store (F02)** — persistent SQLite + sqlite-vec database storing tag embeddings with pluggable providers (hashing / OpenAI / Azure OpenAI)
- **SemanticTagResolver (F03)** — multi-stage resolution pipeline: vector similarity → fuzzy matching → LLM expansion
- **Backend API endpoints (F04)** — REST endpoints to trigger tag population, check status, and rebuild the embedding store
- **Resolution chain wiring (F05)** — SemanticTagResolver integrated into the existing geocoding.py resolution chain
- **Tag Database settings UI (F06)** — frontend settings panel to trigger, monitor, and rebuild the tag store with progress tracking
- **Query Transparency Backend (F07)** — backend returns resolved tags and generated Overpass queries alongside results
- **Query Transparency Frontend (F08)** — frontend displays the resolved tags so users see exactly what was searched
- **Fuzzy Matching Enhancement (F09)** — RapidFuzz integration for approximate tag matching when vector search misses
- **LLM semantic tag expansion (Phase A)** — LLM broadens thin semantic results with contextual tag suggestions
- **Wildcard queries & geometry filtering** — support for broader OSM `*` queries with automatic geometry-type filtering
- **Grouped search results** — Overpass results grouped by query in the SearchResults panel
- **Improved disambiguation** — plain-language labels and choice-oriented responses when multiple interpretations exist
- **Dynamic embedding dimension detection** — the vector store detects the embedding provider's dimension at runtime and auto-migrates if it changes between deployments
- **Deferred embedding probe** — status-only calls no longer trigger external API requests; the embedding model is only probed before actual write/search operations

### 🐛 Bug Fixes
- Fixed supplementing thin semantic tag results with LLM expansion when vector search returns too few candidates
- Fixed Overpass query limits, tag capping, and improved frontend contrast for transparency display
- Treated `aeroway=aerodrome` as point feature (not linear) to fix airport query timeouts

### 🧪 Tests
- Comprehensive test suites for TagVectorStore, vector store embeddings, similarity quality, threading safety, and fallback behaviour

---

## 🤖 AI Agent & LLM

### Agent Core

#### ✨ New Features
- **Server-Sent Events (SSE) streaming** — real-time streaming from the LangGraph agent to the frontend, replacing request/response polling
- **Parallel tool execution** — the agent calls multiple tools concurrently for faster multi-tool queries
- **Conversation summarisation** — automatic context summarisation with session management and cleanup, keeping long conversations within the token window
- **Dynamic tool selection** — Agent Settings component allowing users to enable/disable individual tools at runtime
- **Tool progress indicators** — formatted tool input parameters and output previews streamed to the frontend during execution
- **Smart scrolling** — auto-scroll control in chat components during streaming responses
- **Performance monitoring** — agent execution timing and metrics utilities with corresponding UI
- **Comprehensive state management** — improved agent state management with visibility defaults, session tracking, and reset functionality
- **Cancellation logging** — enhanced cancellation tracking and test coverage for streaming requests
- **Reset functionality** — sidebar button to clear chat, layers, and settings with confirmation dialog
- **Persistent debug logging** — rotating log file (`debug.log`) with structured markers (`[CHAT]`, `[AGENT]`)

#### 🐛 Bug Fixes
- Fixed session ID consistency between chat and preload endpoints
- Fixed empty AI messages being displayed in agent responses
- Prevented 500 error on `/auth/me` with invalid tokens

#### 🧪 Tests
- Updated tests to mock streaming endpoints for chat interactions
- Added cancellation logging and streaming request tests
- Enhanced scale control tests with dynamic updates

### Multi-Step Planning (Experimental)

> **Note**: This feature is working but not yet fully stable.

#### ✨ New Features
- **Multi-step execution planning** — the agent decomposes complex geospatial queries into a sequence of tool calls and executes them stepwise
- **PlanDisplay component** — collapsible tool details and improved rendering logic for plan steps in the frontend
- **Tool chaining** — planning supports chaining across all tool types including geoprocessing, geocoding, and styling
- **Enable/disable toggle** — planning can be enabled or disabled per session via settings
- **`geodata_last_results` for styling** — `style_map_layers` and `apply_intelligent_color_scheme` can access the last tool's output for seamless chaining

#### 🐛 Bug Fixes
- Fixed plan continuation loop and strengthened plan instructions
- Fixed step tracking, keepalive, and geoDataList clearing in planning mode
- Fixed planning always executing even when disabled
- Resolved critical planning bugs related to state management

### LLM Providers

#### ✨ New Features
- **Anthropic (Claude)** — full connector with `langchain-anthropic` integration
- **Moonshot AI (Kimi)** — additional LLM provider
- **xAI (Grok)** — additional LLM provider
- **Provider ordering** — environment-variable-driven ordering of LLM providers
- **Updated model list** — refreshed OpenAI, Azure, and other provider model catalogues with 2026 models
- **Per-user message management** — `message_management_mode` setting stored per user

#### 🧪 Tests
- Added provider ordering validation tests
- Updated model selection tests for new providers and model names
- Enhanced max_tokens validation tests

---

## 🗺️ Geoprocessing & Projections

### ✨ New Features
- **Smart CRS selection** — automatic selection of an appropriate projected CRS based on data extent (EPSG lookup with continental, UTM, and regional fallback)
- **Frontend CRS toggle** — user-facing setting to enable/disable smart CRS selection, enabled by default
- **Hybrid geodesic/planar strategies** — buffer and area operations choose between geodesic and planar computation depending on data characteristics
- **CRS metadata display** — processing results show the chosen CRS and origin layers in both SearchResults and LayerList
- **Agent CRS override** — the agent can manually specify a CRS to override automatic selection
- **User-configurable model settings** — dedicated model selection for geoprocessing execution
- **Origin layer tracking** — processing metadata includes source layer references

### 🐛 Bug Fixes
- Simplified geoprocessing to planar-only with smart CRS selection
- Fixed ESRI authority for ESRI projection codes
- Corrected South America Lambert Conformal Conic EPSG code
- Fixed remaining CRS issues to only use EPSG and WKT
- Fixed buffer operation f-string formatting bugs
- Fixed numpy serialisation and `ProcessingMetadata` field mapping for WKT projections
- Removed reference to non-existent `expected_error` field in `ProcessingMetadata`

### 🧪 Tests
- Comprehensive projection tests: `test_projection_utils`, `test_projection_decider`, `test_projection_selection_mapping`
- Smart CRS selection tests: `test_smart_crs_setting`
- Buffer bug fix tests with parameterised coverage
- Updated geoprocessing integration tests

---

## 🔌 Model Context Protocol (MCP)

### ✨ New Features
- **MCP server & client** — implementation of the Model Context Protocol for connecting external tool servers to the agent
- **Authentication support** — API key and custom header authentication for MCP connections
- **Settings UI** — frontend panel to configure, manage, and test MCP server connections
- **Example selection** — hide example server selection when no examples are available

### 🧪 Tests
- MCP settings and configuration tests

---

## 🛰️ OSINT Tools

### ✨ New Features
- **ECMWF Weather tool** — weather data retrieval
- **World Bank indicators** — data query tool with interactive chart rendering component (frontend)
- **NASA GIBS imagery** — satellite imagery layers
- **NASA tools & World Bank chart** — dedicated frontend components for visualisation

---

## 📦 Layer Management & UI

### ✨ New Features
- **GeoJSON download** — download button on layers with drag-and-drop support for file export
- **Layer metadata popup** — drag handle component with detailed layer information display
- **Marker support** — `marker-color` and `marker-symbol` for GeoJSON point features
- **Image proxy** — legend image endpoint to work around CORS issues on external WMS legend URLs
- **CORS proxy** — deployment identifier and dynamic User-Agent headers for external service requests
- **Custom scale control** — dynamic Leaflet scale control positioned based on layer panel state
- **Insecure GeoServer connections** — support for connecting to GeoServer backends over HTTP (opt-in)

### 🎨 UI/UX Improvements
- Enhanced layer hover effect with improved border styling
- Source layers display and processing metadata in SearchResults and LayerList
- Geoprocessing tools use actual layer titles in the UI
- Improved chat scrolling behaviour
- Enhanced streaming message display with filtered empty AI messages
- Enhanced `ToolProgressIndicator` with formatted tool input parameters

### 🐛 Bug Fixes
- Fixed default visibility to `true` for `GeoDataObject` and new layers
- Fixed global preload session sharing for preconfigured GeoServers
- Fixed layer text and icon wrapping/spacing issues in LayerList

### 🧪 Tests
- Performance metrics tracking and corresponding UI tests
- Updated agent-add-layer tests for updated chat placeholder

---

## 🔐 Authentication & Security

### ✨ New Features
- **AUTH_ENABLED toggle** — disable authentication entirely for local development or demos
- **OIDC social login** — Google provider (extensible) with cloud deployment support, login/callback protocol handling
- **Per-user settings** — `message_management_mode` stored per user
- **Cookie security hardening** — configurable `Secure`, `HttpOnly`, and `SameSite` cookie attributes
- **SECRET_KEY validation** — production and Azure docker-compose files require a non-empty secret via `${SECRET_KEY:?}` substitution; dev compose omits the variable so the backend uses its built-in default

### 🐛 Bug Fixes
- Fixed cloud deployment same-protocol issue for login and callback
- Prevented 500 error on `/auth/me` with invalid tokens

---

## 🗃️ Database & Storage

### ✨ New Features
- **Database init resilience** — retry logic with exponential backoff and lazy table creation for ephemeral cloud databases (Azure Container Apps cold starts)
- **Map and layer data model** — added `Map` and `Layer` models with Alembic migrations
- **OIDC columns migration** — added OIDC-related columns to the user model

### 🐛 Bug Fixes
- Fixed `asyncio.Lock` usage, exception info logging, and cooldown handling in database init
- Handled missing/SQLite `DATABASE_URL` gracefully in async session setup
- Updated Alembic env to support `postgresql` scheme for async engine

---

## ☁️ Infrastructure & DevOps

### Docker & Containers

#### ✨ New Features
- **Persistent volumes** — `backend-data` and `backend-uploads` named volumes in all docker-compose files for SQLite databases and uploaded files
- **Comprehensive env vars** — all docker-compose files pass the full set of backend environment variables (LLM providers, embedding config, authentication, MCP, logging, LangSmith)
- **Poetry-based Dockerfile** — migrated backend image to Poetry with multi-stage builds
- **Startup benchmarks** — scripts for measuring container startup time
- **Health check paths** — updated to support subpath deployments

#### 🐛 Bug Fixes
- Resolved Poetry segfault with hybrid export+pip approach
- Reverted Python to 3.13 (3.14 packages not yet available)
- Used absolute uvicorn path in all compose files and Dockerfile CMD
- Removed optional syntax directives from frontend Dockerfiles
- Added g++ compiler to Docker image for contourpy build

### CI/CD

#### ✨ New Features
- **GitHub Actions modernisation** — updated to Node 24 runtime (`FORCE_JAVASCRIPT_ACTIONS_TO_NODE24`), Python 3.13, `actions/checkout@v4`, `actions/setup-python@v5`
- **Docker image workflow** — matrix build-and-push for backend, frontend, nginx with GHCR publishing, metadata artifacts, SHA/branch/PR tagging
- **Deploy dispatch** — cross-repository workflow dispatch to infrastructure repo with payload metadata and retry logic
- **Commit message sanitisation** — safe handling of special characters in dispatch payloads

#### 🐛 Bug Fixes
- Fixed dispatch conditions for pull requests and ensured dispatch runs even if some matrix builds fail

### Nginx

#### ✨ New Features
- **Loading page** — lightweight HTML page served while the backend starts
- **Health check endpoints** — backend, frontend, and nginx health checks for container orchestration

### Deployment

#### ✨ New Features
- **Deployment configuration** — JSON-based deployment config for custom instances
- **Dynamic User-Agent** — deployment identifier in User-Agent headers
- **CORS proxy** — image proxy for external legend URLs

---

## 📚 Documentation

### ✨ New Features
- **`.env.example` overhaul** — expanded with all provider configurations (Anthropic, Moonshot, xAI), embedding settings, MCP, CORS, cookie security, OIDC, WMTS filtering, and log level
- **README updates** — added Anthropic, Moonshot, and xAI to the LLM providers table; documented Semantic OSM Geocoding and MCP features
- **CONTRIBUTING.md refactoring** — reduced redundancy with AGENTS.md and improved development workflow documentation
- **AGENTS.md improvements** — added debug logging documentation, structured log markers, and log level configuration
- **Architecture docs** — updated for new subsystems

---

## 🧹 Dependency & Code Quality

### Backend Dependencies
- **Constraint migration** — all `>=` constraints changed to `^` (caret) to prevent accidental major-version upgrades
- **Major upgrades**: black 25→26, isort 6→8, pydantic 2.11→2.12, langchain-core 0.3.76→0.3.83, langchain-openai 0.3.33→0.3.35, langgraph 0.6.7→0.6.11, fastapi 0.116.0→0.116.2
- **New dependencies**: `langchain-anthropic`, `rapidfuzz`
- **Codebase reformat** — full reformat of 68 files with black 26 and isort 8

### Frontend Dependencies
- **Updated**: Next.js 15.5.14, React 19, Tailwind 4.2.2
- **Package-lock refresh**: safe updates across the npm dependency tree

### 🐛 Bug Fixes
- Fixed pandas NaN vs None assertion in `test_attribute_tools_large_datasets`
- Updated test model names from `gpt-4` to `gpt-4.1-mini` across test files

---

## 🙏 Contributors

| Contributor | Commits |
|---|---:|
| ZuitAMB | 169 |
| Jo-Schie | 37 |
| mucke2701 | 23 |
| Andreas T. Meyer-Berg | 11 |
| Clawson | 3 |
| dependabot[bot] | 1 |

---

**Note**: This detailed changelog covers all 243 commits since v0.2.0-iucn. For the summary version, see [`CHANGELOG.md`](../../CHANGELOG.md).
