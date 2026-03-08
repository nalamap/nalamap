# AI Agent Tools

This directory contains the tools (functions) available to the NaLaMap AI agent. These tools enable the agent to interact with geospatial data, perform analysis, and manage the application state.

## 🛠️ Tool Categories

### 📍 Geocoding (`geocoding.py`)
Tools for converting location names to coordinates and finding points of interest.
- `geocode_using_nominatim_to_geostate`: Search for locations (cities, addresses) using OSM Nominatim.
- `geocode_using_overpass_to_geostate`: Search for specific features (hospitals, schools, restaurants) within a bounding box using the Overpass API.

### 🗺️ Geoprocessing (`geoprocess_tools.py`)
Tools for performing spatial operations on vector data.
- `geoprocess_tool`: A unified entry point for operations like:
    - **Buffer**: Create a zone around features.
    - **Clip**: Cut one layer using another.
    - **Intersect**: Find overlapping areas.
    - **Union**: Combine layers.
    - **Centroid**: Find the center point of features.
    - **Dissolve**: Merge features based on attributes.

### 🎨 Styling (`styling_tools.py`)
Tools for visualizing data on the map.
- `style_map_layers`: Apply manual styles (color, opacity, stroke).
- `auto_style_new_layers`: Automatically generate styles based on data content.
- `check_and_auto_style_layers`: Verify and update styles.
- `apply_intelligent_color_scheme`: Apply color palettes based on color theory.

### 📊 Attributes (`attribute_tools.py`)
Tools for analyzing and filtering tabular data associated with map features.
- `attribute_tool`: Query and filter data using SQL-like predicates (e.g., "population > 100000").
- Supports filtering, summarizing, and inspecting attributes.

### 💾 State Management (`geostate_management.py`)
Tools for managing the current session's data.
- `metadata_search`: Search for loaded layers using semantic similarity.
- `describe_geodata_object`: Get detailed metadata about a specific layer.

### 📚 Data Discovery (`librarian_tools.py`, `geoserver/`)
Tools for finding external data.
- `query_librarian_postgis`: Search the internal PostGIS database for datasets.
- `get_custom_geoserver_data`: Connect to and fetch data from external GeoServer instances.

## 📝 Tool Registration

Tools are registered in `backend/services/default_agent_settings.py`. The `create_configured_tools` function determines which tools are enabled for a specific session based on user settings.

## ➕ Adding a New Tool

1. Create a new function decorated with `@tool` (from `langchain.tools`).
2. Define clear arguments and a descriptive docstring (this is what the LLM sees).
3. Implement the logic.
4. Register the tool in `backend/services/default_agent_settings.py`.
5. Add tests in `backend/tests/`.
