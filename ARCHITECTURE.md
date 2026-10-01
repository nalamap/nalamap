# ARCHITECTURE.md - NaLaMap System Architecture

> **Purpose**: Comprehensive guide to the NaLaMap system architecture, component organization, and design patterns.  
> **Audience**: Developers, architects, and contributors who need to understand the system structure.

---

## 📋 Table of Contents

1. [System Overview](#system-overview)
2. [High-Level Architecture](#high-level-architecture)
3. [Backend Architecture](#backend-architecture)
4. [Frontend Architecture](#frontend-architecture)
5. [Data Flow & Communication](#data-flow--communication)
6. [AI Agent Architecture](#ai-agent-architecture)
7. [Database & Storage](#database--storage)
8. [Deployment Architecture](#deployment-architecture)
9. [Security Architecture](#security-architecture)
10. [Extension Points](#extension-points)

---

## 🌐 System Overview

**NaLaMap** is a geospatial AI platform that enables users to interact with geographic data using natural language. The system combines modern web technologies with AI capabilities to provide an intuitive interface for geospatial analysis.

### Core Capabilities
- 🗺️ **Geospatial Data Management**: Upload, display, and manage vector/raster data
- 🤖 **AI-Powered Analysis**: Natural language interface for geospatial queries
- 🎨 **Intelligent Styling**: AI-assisted map styling and visualization
- 🔧 **Geoprocessing**: Automated spatial operations (buffer, intersection, etc.)
- 🔍 **Data Discovery**: Find and integrate external geospatial data sources
- 🎯 **Geocoding**: Location search using OSM and GeoNames

### Technology Stack

| Layer | Technologies |
|-------|-------------|
| **Frontend** | Next.js 16, React 19, TypeScript, Leaflet, Tailwind CSS |
| **Backend** | Python 3.11+, FastAPI, Uvicorn |
| **AI/ML** | LangChain, LangGraph, OpenAI/Azure/Google/Mistral/DeepSeek |
| **Database** | PostgreSQL (with PostGIS), SQLite-vec |
| **Infrastructure** | Docker, Docker Compose, Nginx |
| **Maps** | Leaflet, OpenStreetMap, WMS/WFS/WMTS/WCS |

---

## 🏗️ High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        User Browser                         │
│  ┌───────────────────────────────────────────────────────┐  │
│  │              Next.js Frontend (Port 3000)             │  │
│  │  - React Components  - Zustand Stores  - Leaflet Map │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                          │  │  │
                    HTTP/WebSocket
                          │  │  │
┌─────────────────────────────────────────────────────────────┐
│                    Nginx Reverse Proxy                      │
│          (Routes requests, CORS, Static assets)             │
└─────────────────────────────────────────────────────────────┘
                          │  │  │
              ┌───────────┴──┴──┴──────────┐
              │                             │
              ▼                             ▼
┌──────────────────────────┐    ┌──────────────────────────┐
│   FastAPI Backend        │    │   External Services      │
│      (Port 8000)         │    │                          │
│                          │    │  - OpenAI / Azure AI     │
│  ┌────────────────────┐  │    │  - Google Gemini         │
│  │   API Endpoints    │  │    │  - Mistral AI            │
│  └────────────────────┘  │    │  - DeepSeek              │
│  ┌────────────────────┐  │    │  - OSM / GeoNames        │
│  │  AI Agent System   │  │◄───┤  - OGC Services          │
│  │  (LangGraph)       │  │    │  - Azure Blob Storage    │
│  └────────────────────┘  │    └──────────────────────────┘
│  ┌────────────────────┐  │
│  │  Geospatial Tools  │  │
│  └────────────────────┘  │
│  ┌────────────────────┐  │
│  │  Vector Store      │  │
│  │  (SQLite-vec)      │  │
│  └────────────────────┘  │
└──────────────────────────┘
              │
              ▼
┌──────────────────────────┐
│   PostgreSQL Database    │
│   (with PostGIS)         │
│   - User sessions        │
│   - Layer metadata       │
│   - Settings             │
└──────────────────────────┘
```

---

## 🔧 Backend Architecture

### Directory Structure

```
backend/
├── main.py                    # FastAPI application entry point
├── pyproject.toml             # Poetry dependencies & configuration
├── poetry.lock                # Locked dependencies
│
├── api/                       # API endpoint definitions
│   ├── nalamap.py            # Main chat/agent API
│   ├── data_management.py    # Data upload/management endpoints
│   ├── settings.py           # Settings CRUD endpoints
│   ├── auto_styling.py       # Automatic styling endpoints
│   ├── ai_style.py           # AI-powered styling endpoints
│   ├── file_streaming.py     # File upload/streaming endpoints
│   └── debug.py              # Debug/testing endpoints
│
├── core/                      # Core configuration
│   └── config.py             # Environment variables, settings
│
├── models/                    # Data models (Pydantic)
│   ├── geodata.py            # GeoDataObject, LayerStyle
│   ├── states.py             # DataState, GeoDataAgentState
│   ├── settings_model.py     # Settings models
│   ├── user.py               # User models
│   └── messages/             # Message models
│       └── chat_messages.py  # NaLaMapRequest, NaLaMapResponse
│
├── services/                  # Business logic
│   ├── single_agent.py       # Single ReAct agent (current)
│   ├── multi_agent_orch.py   # Multi-agent orchestration (legacy)
│   ├── background_tasks.py   # Async background tasks
│   ├── default_agent_settings.py # Default agent configuration
│   │
│   ├── agents/               # AI agent implementations (legacy)
│   │   ├── nala_map_ai.py   # Main geospatial AI agent
│   │   ├── langgraph_agent.py # LangGraph-based agent
│   │   ├── supervisor_agent.py # Agent supervisor/router
│   │   └── geoprocessing_agent.py # Geoprocessing specialist
│   │
│   ├── ai/                   # LLM provider integrations
│   │   ├── llm_config.py    # LLM configuration management
│   │   ├── openai.py        # OpenAI integration
│   │   ├── azureai.py       # Azure OpenAI integration
│   │   ├── google_genai.py  # Google Gemini integration
│   │   ├── mistralai.py     # Mistral AI integration
│   │   └── deepseek.py      # DeepSeek integration
│   │
│   ├── tools/                # AI agent tools (function calling)
│   │   ├── geocoding.py     # Geocoding tools (OSM, GeoNames)
│   │   ├── styling_tools.py # Map styling tools
│   │   ├── geoprocess_tools.py # Geoprocessing operations
│   │   ├── attribute_tools.py # Attribute analysis
│   │   ├── librarian_tools.py # Data discovery/search
│   │   ├── geostate_management.py # Layer state management
│   │   ├── wms_tools.py     # OGC service tools
│   │   └── geoprocessing/   # Detailed geoprocessing ops
│   │       └── ops/         # Individual operations
│   │
│   ├── database/             # Database connectors
│   │   └── database.py      # PostgreSQL connection
│   │
│   └── storage/              # File storage abstractions
│       └── ...              # Azure Blob / Local storage
│
├── tests/                    # Test suite
│   ├── conftest.py          # pytest fixtures
│   ├── test_*.py            # Test files
│   └── ...
│
└── uploads/                  # Local file uploads (dev)
```

### API Layer

**Location**: `backend/api/`

The API layer defines REST endpoints using FastAPI. Key endpoints include:

| Endpoint | Purpose | Methods |
|----------|---------|---------|
| `/api/chat` | AI agent interaction | POST |
| `/api/upload` | File upload | POST |
| `/api/settings` | Settings CRUD | GET, POST, PUT, DELETE |
| `/api/auto-style` | Automatic styling | POST |
| `/api/ai-style` | AI-powered styling | POST |
| `/docs` | Swagger API documentation | GET |

**Example Endpoint** (`api/nalamap.py`):
```python
@router.post("/chat")
async def chat_with_nalamap(request: NaLaMapRequest) -> NaLaMapResponse:
    """Main chat endpoint for AI agent interaction."""
    # Process request, invoke agent, return response
```

### Service Layer

**Location**: `backend/services/`

The service layer contains business logic and orchestrates the AI agent system.

#### Single Agent System (Current)

**File**: `services/single_agent.py`

The current implementation uses a **single ReAct agent** created with LangGraph's `create_react_agent`:

- **GeoAgent**: A unified agent with access to all tools
- **Tool Selection**: Agent reasons about which tools to use based on context
- **Configurable**: Tools and system prompt can be customized per session
- **State Management**: Uses `GeoDataAgentState` to track layers, results, and conversation

**Key Function**: `create_geo_agent(model_settings, selected_tools)`
- Creates and returns a configured ReAct agent
- Dynamically loads tools based on settings
- Applies custom system prompt if provided

**Default Tools** (`services/default_agent_settings.py`):
- Geocoding tools (Nominatim, Overpass)
- Geoprocessing tools (buffer, clip, union, etc.)
- Styling tools (manual, auto-style, color schemes)
- Attribute tools (query, filter, summarize)
- State management tools (metadata search, describe)
- Data discovery tools (GeoServer, PostGIS)

#### Multi-Agent Architecture (Legacy)

**File**: `services/multi_agent_orch.py`

The legacy multi-agent system used a supervisor to route queries:
- **Supervisor Agent**: Routed requests to specialized agents
- **Geo Helper Agent**: Handled geospatial queries and operations
- **Librarian Agent**: Searched and discovered external data sources

**Status**: Currently deprecated in favor of the single agent approach. Available via `/chat2` endpoint for compatibility.

#### Agent Workflow

The single agent follows this pattern:
1. User query received
2. Agent created with configured tools and prompt
3. Agent enters ReAct loop (Reason → Act → Observe)
4. Tools called as needed to fulfill request
5. Response generated and returned to frontend

### AI Tools

**Location**: `backend/services/tools/`

Tools are functions that the AI agent can call to perform actions. All tools are registered in `services/default_agent_settings.py` and can be dynamically configured per session.

#### Tool Categories

- **Geocoding** (`geocoding.py`):
  - `geocode_using_nominatim_to_geostate`: Location search using OpenStreetMap Nominatim
  - `geocode_using_overpass_to_geostate`: POI search using Overpass API (restaurants, hospitals, etc.)

- **Geoprocessing** (`geoprocess_tools.py`):
  - `geoprocess_tool`: Unified tool for spatial operations (buffer, clip, union, intersect, centroid, etc.)
  - Operations work on existing layers in the session state

- **Styling** (`styling_tools.py`):
  - `style_map_layers`: Manual styling with explicit parameters
  - `auto_style_new_layers`: Intelligent auto-styling for new layers
  - `check_and_auto_style_layers`: Automatic style checker and updater
  - `apply_intelligent_color_scheme`: Apply color theory-based styling

- **Attributes** (`attribute_tools.py`):
  - `attribute_tool`: Unified tool for attribute operations
  - Query layer attributes, filter features, summarize numeric columns
  - Uses safe CQL-lite predicate language for filtering

- **State Management** (`geostate_management.py`):
  - `metadata_search`: Search through available datasets using semantic similarity
  - `describe_geodata_object`: Get detailed information about a specific layer

- **Data Discovery**:
  - `get_custom_geoserver_data` (`geoserver/custom_geoserver.py`): Fetch data from custom GeoServer instances
  - `query_librarian_postgis` (`librarian_tools.py`): Search PostGIS databases for relevant datasets

**Tool Definition Pattern**:
```python
from langchain.tools import tool

@tool
def geocode_using_nominatim_to_geostate(
    state: GeoDataAgentState,
    location: str
) -> dict:
    """
    Geocode a location name to coordinates using Nominatim.
    
    Args:
        state: Current agent state
        location: Location name or address
        
    Returns:
        dict with coordinates, bounding box, and GeoJSON
    """
    # Implementation
    return result
```

### Models Layer

**Location**: `backend/models/`

Pydantic models define data structures:

- **GeoDataObject** (`geodata.py`): Represents a map layer
- **LayerStyle** (`geodata.py`): Layer styling properties
- **DataState** (`states.py`): Agent conversation state
- **SettingsSnapshot** (`settings_model.py`): User settings

### Database Layer

**Location**: `backend/services/database/`

PostgreSQL database with PostGIS extension for spatial data:
- User sessions
- Layer metadata
- Settings storage
- Vector embeddings (SQLite-vec for semantic search)

---

## 💻 Frontend Architecture

### Directory Structure

```
frontend/
├── app/                       # Next.js App Router
│   ├── page.tsx              # Main application page
│   ├── layout.tsx            # Root layout
│   ├── globals.css           # Global styles
│   │
│   ├── components/           # React components
│   │   ├── ColorInjector.tsx # Dynamic color injection
│   │   ├── StoreProvider.tsx # Zustand store provider
│   │   │
│   │   ├── chat/            # Chat interface components
│   │   │   ├── AgentInterface.tsx
│   │   │   ├── ChatMessage.tsx
│   │   │   └── ...
│   │   │
│   │   ├── maps/            # Map components
│   │   │   ├── MapComponent.tsx # Main Leaflet map
│   │   │   ├── LayerRenderer.tsx
│   │   │   └── ...
│   │   │
│   │   ├── sidebar/         # Sidebar components
│   │   │   ├── Sidebar.tsx
│   │   │   ├── LayerManagement.tsx
│   │   │   └── ...
│   │   │
│   │   └── settings/        # Settings components
│   │       ├── SettingsPanel.tsx
│   │       ├── ColorSettings.tsx
│   │       ├── ModelSettings.tsx
│   │       └── ToolSettings.tsx
│   │
│   ├── hooks/               # Custom React hooks
│   │   ├── useMapInteraction.ts
│   │   ├── useLayerState.ts
│   │   └── ...
│   │
│   ├── stores/              # Zustand state management
│   │   ├── mapStore.ts     # Map state (layers, viewport)
│   │   ├── chatStore.ts    # Chat state (messages, sessions)
│   │   ├── uiStore.ts      # UI state (sidebars, modals)
│   │   ├── settingsStore.ts # Settings state
│   │   └── ...
│   │
│   ├── models/              # TypeScript types/interfaces
│   │   └── ...
│   │
│   └── utils/               # Utility functions
│       └── ...
│
├── tests/                   # Playwright E2E tests
│   ├── leaflet-map.spec.ts
│   ├── chat-interface.spec.ts
│   ├── settings.spec.ts
│   └── fixtures/           # Test fixtures
│
├── public/                  # Static assets
│   └── ...
│
├── package.json             # Dependencies
├── tsconfig.json           # TypeScript configuration
├── tailwind.config.ts      # Tailwind CSS configuration
├── playwright.config.ts    # Playwright configuration
└── next.config.mjs         # Next.js configuration
```

### Component Architecture

**Main Application Structure** (`app/page.tsx`):

```
┌─────────────────────────────────────────────────────────┐
│                    Main Page (page.tsx)                 │
│  ┌────────────┐  ┌──────────────┐  ┌────────────────┐  │
│  │  Sidebar   │  │ Map Component│  │ Agent Interface│  │
│  │            │  │   (Leaflet)  │  │  (Chat)        │  │
│  │  - Tools   │  │              │  │                │  │
│  │  - Layers  │  │  - Layers    │  │  - Messages    │  │
│  │  - Settings│  │  - Controls  │  │  - Input       │  │
│  └────────────┘  └──────────────┘  └────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### State Management (Zustand)

**Location**: `app/stores/`

Zustand provides lightweight, hook-based state management:

- **mapStore**: Layer data, map viewport, selected features
- **chatStore**: Chat messages, session management, streaming state
- **uiStore**: UI state (sidebar visibility, modals, panels)
- **settingsStore**: User preferences, color customization

**Store Pattern**:
```typescript
import { create } from 'zustand';

interface MapState {
  layers: Layer[];
  viewport: Viewport;
  addLayer: (layer: Layer) => void;
  removeLayer: (id: string) => void;
}

export const useMapStore = create<MapState>((set) => ({
  layers: [],
  viewport: { center: [0, 0], zoom: 2 },
  addLayer: (layer) => set((state) => ({ 
    layers: [...state.layers, layer] 
  })),
  removeLayer: (id) => set((state) => ({ 
    layers: state.layers.filter(l => l.id !== id) 
  })),
}));
```

### Map Integration (Leaflet)

**Location**: `app/components/maps/`

Leaflet powers the interactive map:
- **MapComponent.tsx**: Main map container
- **LayerRenderer.tsx**: Renders GeoJSON layers
- **Controls**: Custom map controls (zoom, fullscreen, etc.)

**Map Capabilities**:
- Display vector data (GeoJSON)
- Display raster data (WMS, WMTS)
- Feature selection and editing
- Custom styling (color, stroke, fill)
- Geocoding search
- Drawing tools

### API Communication

**Pattern**: Frontend uses `fetch` API to communicate with backend:

```typescript
// Example: Send chat message
const response = await fetch('/api/chat', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    messages: [...],
    geodata: [...],
    session_id: sessionId,
  }),
});

const data = await response.json();
```

---

## 🔄 Data Flow & Communication

### Chat Interaction Flow

```
User Input (Frontend)
    │
    ▼
Chat Store (Zustand)
    │
    ▼
POST /api/chat (Backend)
    │
    ▼
Create Single Agent (create_geo_agent)
    │
    ├─→ Configure LLM
    ├─→ Load System Prompt
    └─→ Load Enabled Tools (from settings)
    │
    ▼
ReAct Agent Loop
    │
    ├─→ Reason about next action
    ├─→ Select and call tool(s)
    │       │
    │       ├─→ geocode_using_nominatim_to_geostate
    │       ├─→ geocode_using_overpass_to_geostate
    │       ├─→ geoprocess_tool
    │       ├─→ style_map_layers
    │       ├─→ attribute_tool
    │       └─→ metadata_search
    │
    ├─→ Observe tool results
    └─→ Repeat until answer is ready
    │
    ▼
Agent Response (JSON)
    │
    ▼
Frontend Updates State
    │
    ├─→ Chat Store (new message)
    ├─→ Map Store (new layers/results)
    └─→ UI Update (re-render)
```

**Key Endpoints**:
- `/api/chat`: Main endpoint using single ReAct agent (current)
- `/api/chat2`: Legacy endpoint using multi-agent orchestration (deprecated)

### Layer Management Flow

```
User Action (Add Layer)
    │
    ▼
Frontend Event Handler
    │
    ▼
Map Store (addLayer)
    │
    ├─→ POST /api/upload (if file upload)
    │       │
    │       └─→ Backend saves file
    │
    └─→ Layer added to Leaflet map
    │
    ▼
Map Re-renders with new layer
```

### Settings Flow

```
User Changes Settings
    │
    ▼
Settings Component
    │
    ▼
POST /api/settings (Backend)
    │
    ▼
Database (PostgreSQL)
    │
    ▼
Response (updated settings)
    │
    ▼
Settings Store (Zustand)
    │
    ▼
UI Updates (colors, tools, etc.)
```

---

## 🤖 AI Agent Architecture

### Single Agent System with LangGraph

**Location**: `backend/services/single_agent.py`

NaLaMap uses a **single ReAct agent** built with LangGraph's `create_react_agent` that has access to multiple specialized tools. The agent uses a reasoning loop to decide which tools to call based on user queries.

```
┌─────────────────────────────────────────────────────────┐
│              Single ReAct Agent (GeoAgent)              │
│         (Reasons and selects appropriate tools)         │
└─────────────────────────────────────────────────────────┘
                          │
          ┌───────────────┼───────────────┬──────────────┐
          │               │               │              │
          ▼               ▼               ▼              ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ Geocoding    │  │ Geoprocessing│  │   Styling    │  │  Attributes  │
│   Tools      │  │    Tools     │  │    Tools     │  │    Tools     │
│              │  │              │  │              │  │              │
│ - Nominatim  │  │ - Buffer     │  │ - Manual     │  │ - Query      │
│ - Overpass   │  │ - Clip       │  │ - Auto-style │  │ - Filter     │
│              │  │ - Intersect  │  │ - Color      │  │ - Summarize  │
└──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘

          ▼               ▼               ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  Metadata    │  │  Geoserver   │  │  Librarian   │
│   Search     │  │   Tools      │  │    Tools     │
│              │  │              │  │              │
│ - Describe   │  │ - Custom     │  │ - PostGIS    │
│ - Search     │  │   Geoserver  │  │   Search     │
└──────────────┘  └──────────────┘  └──────────────┘
```

### Available Tools

**Location**: `backend/services/tools/`

The agent has access to the following tool categories:

| Category | Tools | Purpose |
|----------|-------|---------|
| **Geocoding** | `geocode_using_nominatim_to_geostate`, `geocode_using_overpass_to_geostate` | Convert location names to coordinates, find POIs |
| **Geoprocessing** | `geoprocess_tool` | Spatial operations (buffer, clip, union, intersect) |
| **Styling** | `style_map_layers`, `auto_style_new_layers`, `check_and_auto_style_layers`, `apply_intelligent_color_scheme` | Visual customization of map layers |
| **Attributes** | `attribute_tool` | Query, filter, and analyze layer attributes |
| **State Management** | `metadata_search`, `describe_geodata_object` | Search and describe existing layers |
| **Data Discovery** | `get_custom_geoserver_data`, `query_librarian_postgis` | Find external data sources |

**Tool Configuration**: Tools can be enabled/disabled per session via settings, allowing customization of agent capabilities.

### Agent Creation

**Function**: `create_geo_agent()` in `single_agent.py`

The agent is created with:
- **LLM**: Configured via `get_llm()` (supports multiple providers)
- **Tools**: Dynamically configured based on user settings
- **State Schema**: `GeoDataAgentState` (tracks messages, layers, results)
- **System Prompt**: Configurable instructions for agent behavior
- **Tool Binding**: Tools are bound with `parallel_tool_calls=False` for sequential execution

```python
def create_geo_agent(
    model_settings: Optional[ModelSettings] = None,
    selected_tools: Optional[List[ToolConfig]] = None,
) -> CompiledStateGraph:
    llm = get_llm()
    system_prompt = DEFAULT_SYSTEM_PROMPT  # or custom from settings
    tools_dict = create_configured_tools(DEFAULT_AVAILABLE_TOOLS, selected_tools)
    tools = list(tools_dict.values())
    
    return create_react_agent(
        name="GeoAgent",
        state_schema=GeoDataAgentState,
        tools=tools,
        model=llm.bind_tools(tools, parallel_tool_calls=False),
        prompt=system_prompt,
    )
```

### Agent State

**GeoDataAgentState** (`models/states.py`):
```python
class GeoDataAgentState(TypedDict):
    messages: List[BaseMessage]           # Conversation history
    geodata_layers: List[GeoDataObject]   # Current map layers
    geodata_results: List[GeoDataObject]  # Query results
    geodata_last_results: List[GeoDataObject]  # Previous results
    results_title: str                    # Title for results
    options: SettingsSnapshot             # User settings
    remaining_steps: int                  # Max reasoning steps
```

### ReAct Loop

The agent follows a **ReAct (Reasoning + Acting)** pattern:

1. **User Query** → Agent receives the query
2. **Reasoning** → Agent thinks about which tool(s) to use
3. **Action** → Agent calls appropriate tool(s)
4. **Observation** → Agent receives tool results
5. **Repeat** → Steps 2-4 until answer is found
6. **Response** → Agent generates final response

**Example Flow**:
```
User: "Show hospitals in Berlin"
    ↓
Agent Reasoning: "I need to geocode Berlin and find hospitals"
    ↓
Action 1: Call geocode_using_nominatim_to_geostate("Berlin")
    ↓
Observation: {lat: 52.52, lon: 13.405, bbox: [...]}
    ↓
Agent Reasoning: "Now I'll search for hospitals in this area"
    ↓
Action 2: Call geocode_using_overpass_to_geostate("hospital", bbox)
    ↓
Observation: [list of 50 hospitals as GeoJSON]
    ↓
Agent Reasoning: "I have the data, I'll respond"
    ↓
Response: "I've added 50 hospitals in Berlin to the map"
```

### Multi-Agent Architecture (Legacy)

> **Note**: The multi-agent orchestration system (`services/multi_agent_orch.py`) with supervisor and specialized agents is **currently not in use**. The `/chat2` endpoint uses this legacy system, but the main `/chat` endpoint uses the single agent approach described above.

The multi-agent system included:
- **Supervisor Agent**: Routed requests to specialized agents
- **Geo Helper Agent**: Handled geospatial queries
- **Librarian Agent**: Searched for external data

This architecture may be revisited in the future for more complex use cases.

### LLM Provider Abstraction

**Location**: `backend/services/ai/`

Multiple LLM providers are supported through a unified interface:

- `llm_config.py`: Configuration management
- `openai.py`: OpenAI GPT models
- `azureai.py`: Azure OpenAI models
- `google_genai.py`: Google Gemini models
- `mistralai.py`: Mistral AI models
- `deepseek.py`: DeepSeek models

**Provider Selection**: Controlled by `LLM_PROVIDER` environment variable

---

## 💾 Database & Storage

### PostgreSQL Database

**Purpose**: Persistent data storage

**Schema** (conceptual):
```sql
-- User sessions
CREATE TABLE sessions (
    id VARCHAR PRIMARY KEY,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    user_id VARCHAR
);

-- Layer metadata
CREATE TABLE layers (
    id VARCHAR PRIMARY KEY,
    session_id VARCHAR REFERENCES sessions(id),
    name VARCHAR,
    data_type VARCHAR,
    data_source VARCHAR,
    geojson_data JSONB,
    style JSONB,
    visible BOOLEAN,
    created_at TIMESTAMP
);

-- Settings
CREATE TABLE settings (
    session_id VARCHAR PRIMARY KEY,
    color_settings JSONB,
    model_settings JSONB,
    tool_settings JSONB,
    updated_at TIMESTAMP
);
```

### Vector Store (SQLite-vec)

**Purpose**: Semantic search over data descriptions

**Usage**:
- Store embeddings of layer descriptions
- Enable natural language search
- Find similar datasets

### File Storage

**Local Storage** (Development):
- Location: `backend/uploads/`
- Used for uploaded files (GeoJSON, Shapefiles, KML)

**Azure Blob Storage** (Production):
- Configurable via `USE_AZURE_STORAGE` environment variable
- Secure file upload/download with SAS tokens
- Metadata stored in PostgreSQL

---

## 🚀 Deployment Architecture

### Development Environment

```
┌─────────────────────────────────────────────────────────┐
│              Developer Machine                          │
│  ┌───────────────┐       ┌────────────────┐            │
│  │  Backend      │       │  Frontend      │            │
│  │  (Python)     │       │  (Next.js)     │            │
│  │  Port 8000    │◄──────┤  Port 3000     │            │
│  └───────────────┘       └────────────────┘            │
└─────────────────────────────────────────────────────────┘
```

**Start Command**: 
```bash
# Terminal 1
cd backend && poetry run python main.py

# Terminal 2
cd frontend && npm run dev
```

### Docker Development Environment

```
┌─────────────────────────────────────────────────────────┐
│           Docker Compose (dev.docker-compose.yml)       │
│  ┌───────────────┐       ┌────────────────┐            │
│  │  Backend      │       │  Frontend      │            │
│  │  Container    │       │  Container     │            │
│  │  Port 8000    │◄──────┤  Port 3000     │            │
│  └───────────────┘       └────────────────┘            │
│         │                        │                      │
│         └────────┬───────────────┘                      │
│                  │                                      │
│         ┌────────▼─────────┐                            │
│         │  Volume Mounts   │                            │
│         │  (Hot Reload)    │                            │
│         └──────────────────┘                            │
└─────────────────────────────────────────────────────────┘
```

**Start Command**: 
```bash
docker-compose -f dev.docker-compose.yml up --build
```

### Production Environment

```
┌─────────────────────────────────────────────────────────┐
│                    Internet                             │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│              Nginx Reverse Proxy (Port 80)              │
│  - SSL/TLS termination                                  │
│  - Static asset serving                                 │
│  - Load balancing                                       │
│  - CORS handling                                        │
└─────────────────────────────────────────────────────────┘
                │                    │
      ┌─────────┴─────────┐  ┌──────┴────────┐
      │                   │  │               │
      ▼                   ▼  ▼               ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  Backend     │  │  Frontend    │  │  PostgreSQL  │
│  Container   │  │  Container   │  │  Database    │
│  (FastAPI)   │  │  (Next.js)   │  │              │
│  Port 8000   │  │  Port 3000   │  │  Port 5432   │
└──────────────┘  └──────────────┘  └──────────────┘
```

**Start Command**: 
```bash
docker-compose up --build
```

### Cloud Deployment (Azure Container Apps)

**Reference**: `docs/azure-container-apps-config.md`

- Backend and Frontend deployed as separate container apps
- Azure Blob Storage for file uploads
- PostgreSQL managed database
- Environment variables managed via Azure Key Vault

---

## 🔒 Security Architecture

### Authentication & Authorization

**Current**: Session-based (development)
**Future**: OAuth2, JWT tokens

### CORS Configuration

**Location**: `backend/main.py`

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_CORS_ORIGINS,  # From .env
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### API Key Management

- LLM API keys stored in environment variables
- Never committed to version control
- Rotated regularly

### File Upload Security

- File type validation
- Size limits enforced
- Sandboxed processing
- Virus scanning (production)

### Database Security

- Parameterized queries (prevent SQL injection)
- Connection pooling
- SSL/TLS connections (production)

---

## 🔌 Extension Points

### Adding a New AI Tool

1. **Create tool function** in `backend/services/tools/`
2. **Add tool to agent** in `backend/services/agents/`
3. **Write tests** in `backend/tests/`
4. **Update frontend** (if UI changes needed)

**Example**:
```python
# backend/services/tools/my_new_tool.py
from langchain.tools import tool

@tool
def my_new_tool(param: str) -> dict:
    """Tool description for LLM."""
    # Implementation
    return {"result": "..."}
```

### Adding a New LLM Provider

1. **Create provider file** in `backend/services/ai/`
2. **Implement `get_llm()` function**
3. **Add provider to config** in `llm_config.py`
4. **Update documentation**

### Adding a New Frontend Component

1. **Create component** in `app/components/`
2. **Add types** in `app/models/`
3. **Connect to store** (if stateful)
4. **Write tests** in `tests/`

### Adding a New OGC Service Type

1. **Create service handler** in `backend/services/tools/`
2. **Add metadata extraction**
3. **Update frontend rendering** in `MapComponent.tsx`
4. **Add tests**

---

## 📚 Related Documentation

- **Development Guide**: `AGENTS.md`
- **Contributing**: `CONTRIBUTING.md`
- **Color Customization**: `docs/color-customization.md`
- **Runtime Environment**: `docs/runtime-environment.md`
- **Azure Deployment**: `docs/azure-container-apps-config.md`

---

**Last Updated**: October 2025  
**Maintainers**: NaLaMap Development Team
