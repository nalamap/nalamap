# Changelog - NaLaMap

## [Unreleased] - Since v.0.1.0-beta.1

All notable changes since version 0.1.0-beta.1 (350+ commits from October 2025).

---

## 🚀 NaLaMap Release Summary - October 2025

## Major Achievements Since v.0.1.0-beta.1

### 🎯 Frontend Revolution
- **Enhanced Map Experience**: Complete WMTS support, improved layer management, and GeoJSON rendering
- **Settings Overhaul**: New collapsible settings with GeoServer backends, embedding progress tracking, and dark mode
- **Color Customization**: Dynamic color system with and improved accessibility
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
- **Cloud Ready**: Container images, example docker-compose deployment and multi-environment configuration
- **Quality Assurance**: 350+ commits with comprehensive testing and linting

### 📊 Impact Metrics
- **350+ Commits** across 4 months of intensive development
- **Major Features**: 50+ new capabilities and enhancements  
- **Test Coverage**: Expanded E2E and unit test suites
- **Contributors**: ZuitAMB, mucke2701, Jo-Schie, and Aminsch

---

## 🎯 Frontend

### Map Component

#### ✨ New Features
- **WMTS Support**: Enhanced WMTS integration with WebMercator filtering and configuration options
- **WMTS URL Parsing**: Added version detection and propagation for WMTS services
- **WMTS Matrix Sets**: Added WebMercator matrix set validation and selection
- **Layer Rendering**: Improved GeoJSON layer rendering with comprehensive test suite
- **Popup Enhancement**: Enhanced Leaflet popups with size constraints and scrolling for large attribute tables
- **Layer Management**: Added layer management functionality to Sidebar component with toggle state
- **Layer Stability**: Improved layer order key generation for React stability by filtering visible layers
- **Map Context**: Enhanced LeafletGeoJSONLayer with map context logging and layer functionality updates

#### 🐛 Bug Fixes
- **Layer Naming**: Improved layer naming for WFS and WMTS presentation
- **Layer Re-renders**: Fixed unnecessary re-renders by replacing forceUpdate pattern with stable styleKey
- **Loading State**: Added loading state management to prevent premature renders and ensure proper cleanup

#### 🧪 Tests
- **E2E Tests**: Added Playwright frontend tests with CI integration
- **Layer Tests**: Added simple layer rendering test for GeoJSON layers
- **Store Tests**: Improved store exposure test robustness with enhanced readiness checks

---

### Settings Page

#### ✨ New Features
- **Custom Geoserver Integration**: Added Options to configure custom GeoServer backends including a progress bar during embedding.
- **Example GeoServers**: Added support for example GeoServer backends (MapX, WorldPop)
- **Settings Initialization**: Added SettingsInitializer component to initialize settings on app load
- **Collapsible Sections**: Added collapsible tools section and prompt visibility toggle
- **GeoServer Settings**: Added GeoServer, Model, and Tool settings components
- **Search Portals Deprecation**: Deprecated search_portals in favor of example_geoserver_backends
- **Tool Metadata**: Added tool metadata for configuration and UI display with categories and display names

#### 🎨 UI/UX Improvements
- **Dark Mode Styles**: Added dark mode styles for settings components
- **Visual Consistency**: Updated background colors and text styles for improved visual consistency
- **Accessibility**: Updated contrasts text colors for improved accessibility

#### 🧪 Tests
- **Settings Tests**: Added comprehensive tests for color settings, GeoServer backends, model settings, and tools configuration
- **Collapsible Tests**: Enhanced tests by expanding Model Settings and GeoServer Backends components

---

### Color Customization

#### ✨ New Features
- **Color System**: Added comprehensive color customization feature with dynamic CSS injection
- **Color Settings**: Implemented settings management for colors
- **Color Picker**: Enhanced color selection with clickable gradient preview
- **Quick Color Picker**: Add quick color picker open for multiple selections

#### 🎨 UI/UX Improvements
- **Dark Mode**: Implemented dark mode styles and tests for theme toggling
- **Dark Mode Colors**: Added dark mode styles for secondary colors and inline elements
- **Color Organization**: Refactored color settings and UI components for improved accessibility and organization
- **Color Normalization**: Improved color normalization and auto-styling logic for map layers

#### 🐛 Bug Fixes
- **Color Hex Codes**: Fixed color hex codes in parse_color function
- **Color Formatting**: Corrected formatting of color settings comments

#### 🧪 Tests
- **Dark Mode Tests**: Added comprehensive dark mode tests with theme storage and visibility checks
- **Color Picker Tests**: Added tests to ensure color picker panel remains open when changing colors
- **Color Settings Tests**: Enhanced color settings tests with improved visibility checks
- **Active Indicator**: Simplified Active indicator visibility checks in dark mode tests

---

### UI & Layout

#### ✨ New Features
- **UI Store**: Added UI store for managing layout widths and sidebar width
- **Responsive Layout**: Implemented responsive layout management
- **Layer Toggle**: Added layer/chat toggle buttons with improved positioning
- **Mobile Menu**: Enhanced mobile menu toggle with larger button size
- **Sidebar**: Refactored Sidebar and Home components for improved layout and accessibility

#### 🎨 UI/UX Improvements
- **Button Styles**: Updated button styles in Home component for improved visibility
- **Button Interactivity**: Enhanced button interactivity with cursor pointer style
- **Button Positions**: Swapped button positions for improved accessibility
- **Fixed Width**: Set fixed width for layer toggle button
- **Header Alignment**: Center aligned headers in AgentInterface and LayerManagement
- **Visual Consistency**: Enhanced UI styling across components for improved visual consistency
- **Hover States**: Updated button hover states and background colors
- **Message Bubbles**: Added border to human message bubble for improved visual distinction

#### 🐛 Bug Fixes
- **UI Resizing**: Fixed UI resizing issues
- **Panel Resizing**: Fixed panels resizing behavior
- **Layout Simplification**: Simplified map panel styling

---

### Chat Interface

#### ✨ New Features
- **Add to Map**: Added test suite for "Add to Map" button functionality
- **Layer Management**: Integrated layer management with chat interface

#### 🎨 UI/UX Improvements
- **More Chatty**: Made chat interface more conversational
- **LayerManagement Styles**: Updated LayerManagement styles for improved UI consistency

---

### Testing & Quality

#### 🧪 Tests
- **Playwright Integration**: Added Playwright frontend tests and CI integration
- **E2E Framework**: Implemented comprehensive end-to-end testing framework
- **Frontend Performance**: Added frontend performance testing workflow with metrics extraction
- **Store Testing**: Added StoreExposer and StoreProvider components for E2E testing
- **Console Handling**: Enhanced console message handling by filtering expected warnings
- **Test Improvements**: Simplified frontend test readme

#### 🔧 Configuration
- **ESLint**: Updated next.config.ts to disable ESLint and TypeScript checks during production builds
- **Package Updates**: Updated package.json to remove leaflet fullscreen and add eslint packages

---

## ⚙️ Backend

### API & Endpoints

#### ✨ New Features
- **File Streaming**: Implemented streaming file endpoint for GeoJSON files with gzip compression
- **Range Requests**: Added range request handling for file streaming
- **File Metadata**: Added support for Azure Blob Storage in file metadata retrieval
- **Runtime Config**: Implemented API route for serving runtime environment configuration
- **Health Checks**: Added health check endpoints for Nginx and backend services
- **Large Buffers**: Added large buffer configurations for chat and geoprocessing API endpoints
- **API Routing**: Updated API endpoints to remove '/api' prefix for cleaner routing

#### 🐛 Bug Fixes
- **Content-Length**: Adjusted Content-Length handling for streaming responses
- **File Sanitization**: Sanitized filenames to prevent path traversal vulnerabilities
- **File Existence**: Enhanced file serving logic to validate file existence before serving
- **Response Buffering**: Fixed sendfile and buffering for proper streaming support
- **GeoJSON Encoding**: Enhanced GeoJSON encoding with UTF-8 support and validation

#### 🔒 Security
- **Cookie Security**: Implemented cookie security configuration with SameSite and Secure flags
- **Session Validation**: Added session ID validation to prevent cookie injection attacks
- **Path Validation**: Enhanced file upload path validation to reject absolute paths and hidden segments
- **Upload Security**: Improved file upload metadata retrieval with nested path support

---

### Database & Storage

#### ✨ New Features
- **Azure Blob Storage**: Implemented Azure Blob Storage integration with SAS URL support
- **Centralized Storage**: Refactored file handling to use centralized storage management
- **GeoJSON Caching**: Implemented GeoJSON caching mechanism with size limit and expiration
- **File Management**: Utilized central file management for saving GeoDataFrames

#### 🐛 Bug Fixes
- **Vector Store Threading**: Refactored vector store to use thread-local storage for SQLite connections
- **Database Availability**: Enhanced database availability checks and error handling

#### 🧪 Tests
- **Threading Tests**: Added comprehensive threading tests for vector store implementation
- **Cache Tests**: Added tests for GeoJSON cache functionality

---

### Embeddings & Vector Search

#### ✨ New Features
- **OpenAI Embeddings**: Added OpenAI embeddings support with fallback mechanism
- **Azure Embeddings**: Integrated Azure OpenAI embeddings
- **Hashing Embeddings**: Enhanced hashing embeddings with TF-IDF, stopword filtering, and n-gram support
- **Semantic Similarity**: Improved semantic similarity through enhanced embedding techniques
- **Background Tasks**: Implemented background task manager with priority-based thread pools
- **Progress Tracking**: Enhanced embedding progress tracking in frontend

#### 🧪 Tests
- **Integration Tests**: Updated tests for embeddings integration and consistency

---

### Logging & Monitoring

#### ✨ New Features
- **Centralized Logging**: Implemented centralized logging utility for improved error handling
- **Error Tracking**: Integrated centralized logging across components
- **Environment Logging**: Configure logging level based on environment variable

---

### Testing & Quality

#### 🧪 Tests
- **Backend Tests**: Added comprehensive backend test suites
- **Auto Styling Tests**: Added tests for auto styling and streaming APIs
- **GeoServer Tests**: Enhanced GeoServer backend tests with improved mock setup
- **Preload Tests**: Added comprehensive tests for GeoServer backend preload
- **Geoprocessing Tests**: Added geoprocessing test suite with mock data
- **E2E Performance**: Added end-to-end performance testing framework

#### 🔧 Linting & Formatting
- **Code Quality**: Numerous linting fixes throughout backend including (flake8 + black)

---

## 🤖 Agent & LLM

### LLM Integration

#### ✨ New Features
- **Multi-Provider Support**: Added support for Anthropic, Google, Mistral, and DeepSeek
- **Azure AI**: Enhanced Azure AI integration with multi-model support
- **OpenAI Models**: Added new OpenAI models 'o1-mini' and 'o3-mini' with pricing & model details
- **Model Selection**: Implemented state-based model selection
- **Max Tokens**: Enhanced LLM configuration with max_tokens validation
- **Model Metadata**: Added model metadata for costs and capabilities
- **Default Model**: Updated default OpenAI model to gpt-4.1-mini

#### 🐛 Bug Fixes
- **Model Compatibility**: Fixed langchain-core MRO conflicts by pinning compatible version
- **Azure Validation**: Added Azure provider validation and skip test if env vars not set

#### 🧪 Tests
- **Agent Tests**: Fixed flaky agent test
- **Tool Selection**: Added test suite for tool selection behavior with improved system prompts

---

### System Prompts

#### ✨ New Features
- **Best Practices**: Added best practices for attribute tool usage to system prompt documentation
- **System Prompt Updates**: Updated system prompts for better tool usage

---

## 🛠️ Tools

### Attribute Tools

#### ✨ New Features
- **Attribute Tool 2**: Added attribute_tool2 with comprehensive test suite and agent integration
- **Smart Layer Naming**: Implemented smart layer naming using LLM for filtered/selected/sorted operations
- **Detailed Descriptions**: Added detailed descriptions for filtered, selected, and sorted features
- **Large Dataset Tests**: Added comprehensive tests for attribute_tools with large datasets
- **Dataset Description**: Enhanced dataset description functions with improved column previewing
- **Sort Fields**: Updated sort_fields parameter to use dict format

#### 🐛 Bug Fixes
- **None Handling**: Fixed match-layer-names for None Object
- **Description Optimization**: Removed suggested_next_steps from describe_dataset_gdf to reduce LLM calls

#### 🧪 Tests
- **Comprehensive Tests**: Enhanced attribute_tools test suite with improved coverage

---

### GeoServer Tools

#### ✨ New Features
- **Custom GeoServer Tool**: Added custom GeoServer toolsupporting all WMS layers
- **Layer Type Support**: Added support for remaining geoserver layer types
- **WFS Support**: Added support for WFS URLs with proper EPSG:4326 handling
- **Bounding Box**: Added optional bounding box filtering to custom GeoServer data tool
- **Backend Names**: Added name and description for custom geoserver backends
- **Tool Configuration**: Simplified tool configuration with additional tests

#### 🧪 Tests
- **GeoServer Tests**: Added comprehensive GeoServer backend tests
- **WFS Tests**: Enhanced tests for WFS handling and filtering behavior

---

### Geoprocessing Tools

#### ✨ New Features
- **Area Calculation**: Added geoprocessing operations for area calculation
- **Clipping**: Implemented clipping geometries
- **Dissolving**: Added dissolving geometries functionality
- **Layer Naming**: Added enhanced layer naming and metadata for geoprocessing
- **Operation Details**: Added operation details to description field
- **Default CRS**: Implemented default CRS handling for geoprocessing
- **Layer Matching**: Added matching layer names functionality

#### 🐛 Bug Fixes
- **Empty Results**: Added bounds validation for empty geoprocessing results
- **Properties Handling**: Set properties to None instead of empty dict
- **Defensive Coding**: Added defensive coding to handle None values in operation details

#### 🧪 Tests
- **Geoprocessing Tests**: Added geoprocessing test suite with mock data
- **Parameterized Tests**: Implemented parameterized tests via testcases.json

---

### Data Loading & Processing

#### ✨ New Features
- **WFS URLs**: Added support for WFS URLs with EPSG:4326 parameter injection
- **GeoDataFrame Saving**: Refactored _save_gdf_as_geojson to use central file management
- **Geometry Handling**: Refactored _fc_from_gdf to improve geometry handling
- **Upload Directory**: Ensured upload directory exists in _load_gdf
- **GeoJSON Properties**: Enhanced GeoJSON handling by ensuring 'properties' field is included
- **GeoJSON Support**: Added GeoJSON support and improved filename sanitization
- **GeoJSON Normalization**: Added GeoJSON normalization utility with comprehensive test suite

#### 🐛 Bug Fixes
- **Error Messaging**: Improved error messaging in data loading functions
- **Test Data**: Updated GeoJSON test data links to use consistent test-data.geojson

#### 🧪 Tests
- **Structure Tests**: Added tests for GeoDataObject structure
- **Normalization Tests**: Added comprehensive test suite for GeoJSON normalization

---

### Other Tools

#### 🐛 Bug Fixes
- **Librarian Tools**: Disabled librarian search temporarily
- **Import Cleanup**: Commented out unused librarian tools import

---

### Utility Functions

#### ✨ New Features
- **Slugify Enhancement**: Enhanced slugify function to handle None and special characters
- **Slug Length Limit**: Limited slug length to 100 characters
- **CRS Sanitization**: Sanitized CRS options to include only commonly used projections

#### 🧪 Tests
- **Slugify Tests**: Added tests for enhanced slugify functionality
- **CRS Tests**: Refactored test_sanitize_crs_list_basic for improved clarity

---

## 🚀 Pipelines & Infrastructure

### CI/CD

#### ✨ New Features
- **Docker Workflow**: Added GitHub Actions workflow for building and pushing Docker images
- **Docker Images**: Documented Docker images on GHCR
- **Cross-Infra Deployment**: Added MVP cross infra deployment trigger
- **Frontend Performance**: Added frontend performance testing workflow with Playwright
- **Dependabot**: Added dependabot configuration for automated dependency updates
- **Upload Artifact**: Updated upload-artifact action to v4 for performance results
- **Permissions**: Added permissions to ci.yml pipeline

---

### Docker & Containers

#### ✨ New Features
- **Runtime Environment**: Enhanced runtime environment configuration for cloud deployments
- **Environment Config**: Centralized GeoServer env config and extended settings flows
- **Health Checks**: Added health check endpoints for services
- **Entrypoint Scripts**: Enhanced entrypoint scripts for better error handling
- **Environment Variables**: Improved environment variable management

#### 🐛 Bug Fixes
- **Environment Defaults**: Fixed runtime environment defaults for nginx and frontend

#### 📝 Documentation
- **Docker Images**: Added documentation for Docker images in pull requests
- **Image Naming**: Updated Docker image naming convention documentation

---

### Nginx

#### ✨ New Features
- **CORS Configuration**: Implemented CORS with dynamic origin handling and preflight support
- **Body Size Limit**: Increased body size limit for larger uploads
- **Streaming Support**: Updated nginx configuration for optimized file transfers
- **Health Checks**: Added health check endpoints
- **SNI Configuration**: Ensured SNI uses logical upstream host
- **Resolver**: Added resolver to nginx configuration

#### 🐛 Bug Fixes
- **Proxy Buffering**: Fixed proxy_max_temp_file_size settings for large responses

---

### Deployment

#### ✨ New Features
- **Azure Container Apps**: Enhanced configuration for Azure Container Apps deployment
- **Terraform Docs**: Added Terraform configuration guidance for multi-model setup

---

### Dependencies

#### ⬆️ Upgrades
- **LangChain**: Upgraded LangChain and related packages to latest versions
- **langchain-core**: Pinned langchain-core to compatible version 0.3.68
- **Node**: Bumped node from 22-alpine to 24-alpine in frontend
- **Next.js**: Bumped next from 15.4.2 to 15.5.3
- **Chalk**: Bumped chalk from 5.4.1 to 5.6.2
- **Zustand**: Bumped zustand from 5.0.6 to 5.0.8
- **Simple-swizzle**: Bumped simple-swizzle from 0.2.2 to 0.2.4
- **NumPy**: Bumped numpy from 2.3.1 to 2.3.3
- **Azure Storage**: Bumped azure-storage-blob from 12.25.1 to 12.26.0
- **HF-Xet**: Bumped hf-xet from 1.1.5 to 1.1.10
- **Tailwind**: Bumped @tailwindcss/oxide-linux-x64-gnu to 4.1.13
- **Package Security**: Applied package security updates

#### 🐛 Bug Fixes
- **Poetry Dependencies**: Relocked poetry dependencies
- **Compatibility**: Fixed compatibility issues with package upgrades

---

## 📚 Documentation

#### ✨ New Features
- **Architecture Docs**: Added comprehensive architecture documentation
- **README Updates**: Updated README with .env configuration section
- **Port Information**: Added frontend port information to README
- **Azure Docs**: Added Azure Storage Account CORS configuration documentation
- **Attribute Tool Docs**: Added documentation for attribute_tool2

---

## 🔧 Configuration & Environment

#### ✨ New Features
- **Local Environment**: Added local environment configuration for backend and frontend
- **.env.local**: Configured local environment variables for frontend API integration
- **.dockerignore**: Added .dockerignore files for better build efficiency
- **.gitignore**: Updated .gitignore to include .env.local and test-results/.last-run.json

---

## 🎨 Miscellaneous

#### 🔧 Refactoring
- **Code Organization**: Numerous refactoring improvements for code organization
- **Test Organization**: Improved test file organization and readability
- **Import Cleanup**: Cleaned up unused imports across codebase
- **Formatting**: Applied consistent formatting with Black and Flake8

#### 🐛 Bug Fixes
- **Temperature Settings**: Adjusted temperature settings for LLM models

---

## 📊 Statistics

- **Total Commits**: 350+
- **Time Period**: October 2025
- **Previous Version**: v.0.1.0-beta.1

---

## 🙏 Contributors

- ZuitAMB
- mucke2701
- Jo-Schie
- Aminsch

---

**Note**: This changelog covers all commits since v.0.1.0-beta.1. The next release will be tagged accordingly with semantic versioning.
