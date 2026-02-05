# Deployment Configuration Guide

This guide explains how to customize NaLaMap deployments using configuration files.

## Overview

NaLaMap supports custom deployment configurations that allow operators to:

- **Pre-configure GeoServer backends** with automatic embedding on startup
- **Enable/disable specific tools** based on organizational needs
- **Set default model provider and settings**
- **Customize the system prompt** for specialized use cases
- **Apply custom color themes** for branding

## Quick Start

1. **Copy the example configuration:**
   ```bash
   cp backend/deployment-config.example.json backend/deployment-config.json
   ```

2. **Edit the configuration** with your settings

3. **Set the environment variable:**
   ```bash
   export DEPLOYMENT_CONFIG_PATH=/path/to/deployment-config.json
   ```

4. **Start the server** - the configuration will be loaded automatically

## Configuration File Format

### Basic Structure

```json
{
  "config_name": "My Deployment",
  "config_description": "Custom configuration for production",
  "config_version": "1.0",
  
  "geoserver_backends": [...],
  "mcp_servers": [...],
  "model_settings": {...},
  "tools": [...],
  "system_prompt": "...",
  "theme": "light",
  "color_settings": {...}
}
```

### GeoServer Backends

Pre-configure GeoServer connections that are available to all users:

```json
{
  "geoserver_backends": [
    {
      "url": "https://geoserver.example.org/geoserver/",
      "name": "Corporate GeoServer",
      "description": "Internal data layers",
      "enabled": true,
      "preload_on_startup": true,
      "search_term": "population",
      "username": "optional-user",
      "password": "optional-pass",
      "allow_insecure": false
    }
  ]
}
```

**Options:**

| Field | Type | Description |
|-------|------|-------------|
| `url` | string | GeoServer base URL (required) |
| `name` | string | Display name for the backend |
| `description` | string | Description shown to users |
| `enabled` | boolean | Whether backend is active (default: true) |
| `preload_on_startup` | boolean | Preload layer embeddings at server start |
| `search_term` | string | Optional filter for which layers to preload |
| `username` | string | Basic auth username |
| `password` | string | Basic auth password |
| `allow_insecure` | boolean | Allow self-signed SSL certificates |

**Note:** Backends with `preload_on_startup: true` will have their layer metadata embedded when the server starts. This enables faster semantic search but increases startup time.

### Model Settings

Override default LLM configuration:

```json
{
  "model_settings": {
    "model_provider": "azure",
    "model_name": "gpt-4o",
    "max_tokens": 8000,
    "enable_smart_crs": true,
    "enable_dynamic_tools": false,
    "tool_selection_strategy": "conservative",
    "tool_similarity_threshold": 0.3,
    "use_summarization": false
  }
}
```

**Available Providers:**
- `openai` - OpenAI API
- `azure` - Azure OpenAI Service
- `google` - Google Gemini
- `mistral` - Mistral AI
- `anthropic` - Anthropic Claude

**Tool Selection Strategies:**
- `all` - Load all tools (no filtering)
- `semantic` - Filter by semantic similarity
- `conservative` - Semantic + core tools (recommended)
- `minimal` - Only most relevant tools

### Tool Configuration

Enable or disable specific tools:

```json
{
  "tools": [
    {"name": "geoprocess", "enabled": true},
    {"name": "geocode_nominatim", "enabled": true},
    {"name": "geocode_overpass", "enabled": true},
    {"name": "get_custom_geoserver_data", "enabled": true},
    {"name": "style_layers", "enabled": true},
    {"name": "autostyle_new_layers", "enabled": true},
    {"name": "check_and_autostyle", "enabled": true},
    {"name": "apply_color_scheme", "enabled": true},
    {"name": "search_metadata", "enabled": true},
    {"name": "attribute_tool", "enabled": false},
    {"name": "attribute_tool2", "enabled": true}
  ]
}
```

**Note:** Tools not listed in the configuration use their default enabled state.

### Custom System Prompt

Override the default system prompt for specialized use cases:

```json
{
  "system_prompt": "You are a specialized geospatial assistant for environmental monitoring..."
}
```

### Theme and Colors

Set the default theme and custom color scheme:

```json
{
  "theme": "dark",
  "color_settings": {
    "primary": {
      "shade_50": "#FAFBFA",
      "shade_100": "#E3E7E4",
      ...
      "shade_950": "#181B19"
    },
    ...
  }
}
```

**Tip:** Use the Settings page in the UI to customize colors, then export the settings JSON to get the color configuration.

## Environment Variables

| Variable | Description |
|----------|-------------|
| `DEPLOYMENT_CONFIG_PATH` | Path to the deployment configuration JSON file |
| `LOG_LEVEL` | Logging level (DEBUG, INFO, WARNING, ERROR) |

## Validation and Error Handling

The configuration is validated at server startup:

1. **File validation** - Checks if file exists and is valid JSON
2. **Schema validation** - Validates against the Pydantic model
3. **Tool validation** - Warns about unknown tool names
4. **Model validation** - Warns if provider/model is unavailable
5. **URL validation** - Checks GeoServer URL format

**Warnings** are logged but don't prevent startup:
- Unknown tool names (ignored)
- Unavailable model providers (falls back to default)
- Missing URL protocols (auto-added)

**Errors** prevent configuration from loading:
- Invalid JSON syntax
- Missing required fields
- File not found

Check the server logs for configuration status:

```
INFO - Loading deployment configuration from: /path/to/config.json
INFO - Deployment config loaded successfully:
  - Config name: My Deployment
  - GeoServer backends: 2 (1 to preload)
  - Tool overrides: 5
  - Custom model settings: True
  - Custom colors: False
  - Theme: dark
  - Warnings: 0
```

## GeoServer Preloading

When backends have `preload_on_startup: true`:

1. Server starts normally (doesn't block on preload)
2. Preloading runs in a background thread
3. Layer metadata is embedded for semantic search
4. Embeddings are stored with a global session scope
5. All user sessions share the preloaded embeddings

**Benefits:**
- Faster semantic search for common backends
- Reduced load on user's first query
- Consistent search experience

**Trade-offs:**
- Longer initial server startup
- Memory usage for embeddings
- Periodic refresh may be needed for updated layers

## Example Configurations

### Minimal Configuration

```json
{
  "config_name": "Minimal",
  "tools": [
    {"name": "attribute_tool", "enabled": false}
  ]
}
```

### Production with Azure OpenAI

```json
{
  "config_name": "Production",
  "model_settings": {
    "model_provider": "azure",
    "model_name": "gpt-4o",
    "max_tokens": 8000,
    "enable_performance_metrics": true
  },
  "geoserver_backends": [
    {
      "url": "https://internal-geoserver.corp.example/geoserver/",
      "name": "Corporate Data",
      "preload_on_startup": true
    }
  ],
  "theme": "light"
}
```

### Restricted Tool Set

```json
{
  "config_name": "Restricted",
  "tools": [
    {"name": "geocode_overpass", "enabled": false},
    {"name": "geoprocess", "enabled": false}
  ],
  "model_settings": {
    "enable_dynamic_tools": true,
    "tool_selection_strategy": "minimal"
  }
}
```

## Troubleshooting

### Configuration not loading

1. Check `DEPLOYMENT_CONFIG_PATH` is set correctly
2. Verify the file path exists and is readable
3. Check logs for validation errors

### Unknown tools warning

The tool name doesn't match any available tool. Check spelling or use `/api/settings/options` to see available tools.

### Model provider unavailable

The configured provider's API key is not set. Configure the appropriate environment variable:
- OpenAI: `OPENAI_API_KEY`
- Azure: `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`
- Google: `GOOGLE_API_KEY`
- Mistral: `MISTRAL_API_KEY`
- Anthropic: `ANTHROPIC_API_KEY`

### Preload taking too long

Consider:
- Using `search_term` to limit which layers are preloaded
- Reducing the number of backends with `preload_on_startup: true`
- Checking GeoServer performance

---

For more information, see the main documentation at `/docs` or contact the development team.
