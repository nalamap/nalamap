# tests/test_chat_integration.py

import json
import os
from types import SimpleNamespace

import geopandas as gpd
import pytest
import requests
from fastapi.testclient import TestClient
from shapely.geometry import shape

from core.config import BASE_URL, LOCAL_UPLOAD_DIR
from main import app  # wherever your FastAPI instance lives

# ensure LOCAL_UPLOAD_DIR exists for test
os.makedirs(LOCAL_UPLOAD_DIR, exist_ok=True)


@pytest.fixture
def client():
    return TestClient(app)


# @pytest.fixture
# def stub_llm(monkeypatch):
#    """
#    Returns a helper that lets your test specify ANY LLM JSON response.
#    Usage in a test:
#
#        # In your test body:
#        stub_llm('{"steps":[{"operation":"union","params":{}}]}')
#    """
#    def _stub(response_text: str):
#        class FakeLLM:
#            def generate(self, _messages_batch):
#                fake = SimpleNamespace(text=response_text)
#                return SimpleNamespace(generations=[[fake]])
#        monkeypatch.setattr(llm_config, "get_llm", lambda: FakeLLM())
#    return _stub
#


@pytest.fixture(autouse=True)
def stub_requests(monkeypatch):
    """
    Returns a helper that lets your test specify ANY number of GeoJSONs
    to be returned by requests.get(), keyed by a substring of the URL.
    Usage in a test:
        # pass a dict mapping URL‐keys to GeoJSON dicts
        stub_requests({
            "aoi.geojson": aoi_geojson,
            "greenland.geojson": greenland_geojson,
        })
    """

    def _stub(mapping: dict[str, dict], status_code: int = 200):
        def fake_get(url, timeout=10):
            for key, sample in mapping.items():
                if key in url:
                    return SimpleNamespace(
                        status_code=status_code,
                        json=lambda sample=sample: sample,
                    )
            raise RuntimeError("No stub defined for URL: {url!r}")

        monkeypatch.setattr(requests, "get", fake_get)

    return _stub


# def test_buffer_endpoint_creates_buffered_result(client):
#    # Prepare payload
#    payload = {
#        "messages": [
#            {
#                "type": "human",
#                "content": "buffer the points by 100 meters of layer with id=layer1",
#            }
#        ],
#        "options": {},
#        "query": "buffer the points by 100 meters of layer with id=layer1",
#        "geodata_last_results": [],
#        "geodata_layers": [
#            {
#                "id": "layer1",
#                "data_source_id": "test",
#                "data_type": "GeoJson",
#                "data_origin": "TOOL",
#                "data_source": "test",
#                "data_link": "http://localhost:8000/upload/points_simple.geojson",
#                "name": "pt",
#                "title": "pt",
#                "description": "",
#                "llm_description": "",
#                "score": 0,
#                "bounding_box": None,
#                "layer_type": "GeoJSON",
#                "properties": {},
#            }
#        ],
#    }
#
#    # Call the API
#    resp = client.post("/api/chat", json=payload)
#    assert resp.status_code == 200, resp.text
#
#    body = resp.json()
#    # Check that one buffered layer was returned
#    assert "geodata_results" in body
#    results = body["geodata_results"]
#    assert isinstance(results, list) and len(results) == 1
#
#    # The returned GeoDataObject should point to our LOCAL_UPLOAD_DIR via BASE_URL
#    link = results[0]["data_link"]
#    assert link.startswith(BASE_URL)
#
#    # And the file should actually exist on disk
#    filename = link.split("/")[-1]
#    saved_path = os.path.join(LOCAL_UPLOAD_DIR, filename)
#    assert os.path.isfile(saved_path)
#
#    # Verify that the saved GeoJSON is a polygon (buffer of a point)
#    with open(saved_path) as f:
#        gj = json.load(f)
#    assert gj["type"] == "FeatureCollection"
#    assert len(gj["features"]) >= 1
#    geom = gj["features"][0]["geometry"]
#    assert geom["type"] == "Polygon"


def test_chat_buffer_line_expected_result(client, stub_requests):
    line = {
        "type": "FeatureCollection",
        "name": "line",
        "crs": {
            "type": "name",
            "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"},
        },
        "features": [
            {
                "type": "Feature",
                "properties": {"id": 1, "name": "Unter den Linden Boulevard"},
                "geometry": {
                    "type": "LineString",
                    "coordinates": [
                        [13.3778, 52.5163],
                        [13.39, 52.517],
                        [13.4, 52.518],
                    ],
                },
            }
        ],
    }

    output_line = {
        "type": "FeatureCollection",
        "name": "line_buffer_500m",
        "crs": {
            "type": "name",
            "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"},
        },
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "id": 1,
                    "name": "Unter den Linden Boulevard 500m Buffer",
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [13.389424328846832, 52.519712249946679],
                            [13.399271653204945, 52.520696921764923],
                            [13.399709585028491, 52.520727375039968],
                            [13.40015031370697, 52.520731563006969],
                            [13.400589594782282, 52.520709445341005],
                            [13.401023197737533, 52.520661235007864],
                            [13.401446946739235, 52.52058739621453],
                            [13.401856760852858, 52.520488639941938],
                            [13.402248693344458, 52.520365917102659],
                            [13.402618969689891, 52.520220409389466],
                            [13.402964023925538, 52.520053517902447],
                            [13.403280532990477, 52.519866849664083],
                            [13.403565448729399, 52.519662202151686],
                            [13.403816027247984, 52.519441545995974],
                            [13.404029855338118, 52.519207006011875],
                            [13.404204873718401, 52.518960840744072],
                            [13.404339396866161, 52.518705420723734],
                            [13.404432129249942, 52.518443205645802],
                            [13.4044821778062, 52.518176720686114],
                            [13.404489060539975, 52.51790853218634],
                            [13.40445271116678, 52.517641222940838],
                            [13.40437347975095, 52.517377367323249],
                            [13.40425212933433, 52.517119506492229],
                            [13.40408982858777, 52.516870123915588],
                            [13.403888140556184, 52.516631621448155],
                            [13.403649007605566, 52.516406296194361],
                            [13.403374732716957, 52.516196318378285],
                            [13.403067957307465, 52.516003710434873],
                            [13.402731635791991, 52.51583032752378],
                            [13.402369007130572, 52.515677839653918],
                            [13.401983563635456, 52.515547715591325],
                            [13.401579017338204, 52.515441208705433],
                            [13.401159264240807, 52.515359344890705],
                            [13.400728346795052, 52.5153029126799],
                            [13.390728346795052, 52.514302851294701],
                            [13.390421630915364, 52.514278743766518],
                            [13.378221630915364, 52.513578700413305],
                            [13.377781293178932, 52.513566654071688],
                            [13.377341135599414, 52.513580932160338],
                            [13.376905397134914, 52.513621397147915],
                            [13.376478274185047, 52.513687659262921],
                            [13.376063880177304, 52.51377908025006],
                            [13.375666205952514, 52.513894779521486],
                            [13.375289081330852, 52.514033642643177],
                            [13.374936138228584, 52.514194332074787],
                            [13.374610775680717, 52.514375300059029],
                            [13.374316127106454, 52.514574803536291],
                            [13.374055030132633, 52.514790920940385],
                            [13.373829999265846, 52.515021570713529],
                            [13.37364320167635, 52.515264531361595],
                            [13.373496436327049, 52.515517462856536],
                            [13.373391116648484, 52.51577792917908],
                            [13.373328256926737, 52.516043421784815],
                            [13.373308462535288, 52.516311383767061],
                            [13.373331924104948, 52.516579234483928],
                            [13.373398415687976, 52.51684439441209],
                            [13.373507296934079, 52.517104309988085],
                            [13.373657519257341, 52.517356478197691],
                            [13.373847635934661, 52.517598470677008],
                            [13.374075816038513, 52.517827957092933],
                            [13.374339862069759, 52.51804272757839],
                            [13.374637231120781, 52.518240714006438],
                            [13.374965059365053, 52.518420009898534],
                            [13.375320189637373, 52.518578888775849],
                            [13.37569920183909, 52.51871582077699],
                            [13.37609844587551, 52.518829487382625],
                            [13.376514076808313, 52.518918794105417],
                            [13.376942091884407, 52.518982881023504],
                            [13.377378369084637, 52.519021131056192],
                            [13.389424328846832, 52.519712249946679],
                        ]
                    ],
                },
            }
        ],
    }
    stub_requests({"line.geojson": line})

    payload = {
        "messages": [
            {
                "type": "human",
                "content": "buffer the line by 500 meters of geodata_layers with name=line",
            }
        ],
        "options": {
            "search_portals": [],
            "geoserver_backends": [],
            "model_settings": {
                "model_provider": "openai",
                "model_name": "gpt-4-nano",
                "max_tokens": 50000,
                "system_prompt": "You are NaLaMap: an advanced geospatial assistant designed to help users without GIS expertise create maps and perform spatial analysis through natural language interaction.\n\n# ROLE AND CAPABILITIES\n- Your primary purpose is to interpret natural language requests about geographic information and translate them into appropriate map visualizations and spatial analyses.\n- You have access to tools for geocoding, querying geographic databases, processing geospatial data, managing map layers, and styling map layers.\n- You can search for specific amenities (e.g., restaurants, parks, hospitals) near a location using the Overpass API.\n- You can style map layers based on natural language descriptions (e.g., 'make the rivers blue', 'thick red borders', 'transparent fill').\n- You're designed to be proactive, guiding users through the map creation process and suggesting potential next steps.\n\n# STATE INFORMATION\n- The public state contains 'geodata_last_results' (previous results) and 'geodata_layers' (geodata selected by the user).\n- The list 'geodata_results' in the state collects tool results, which are presented to the user in a result list\n- IMPORTANT: When a user asks about a specific dataset, ALWAYS check if that dataset exists in 'geodata_last_results' or 'geodata_layers'.\n- When responding to questions about a dataset, first check if it's available in the state, and use its 'title', 'description', 'llm_description', 'data_source', 'layer_type', 'bounding_box' and other properties to provide specific, detailed information.\n# INTERACTION GUIDELINES\n- Be conversational and accessible to users without GIS expertise.\n- AUTOMATIC STYLING PRIORITY: Always check for and automatically style newly uploaded layers at the start of each interaction.\n  - First use check_and_auto_style_layers() to detect layers needing styling.\n  - Then use auto_style_new_layers() to identify which layers need AI-powered styling.\n  - Finally, use your AI reasoning to determine appropriate colors and call style_map_layers() for each layer.\n  - This ensures all new layers get intelligent styling before responding to user queries.\n- Always clarify ambiguous requests by asking specific questions.\n- Proactively guide users through their mapping journey, suggesting potential next steps.\n- When users ask to highlight or visualize a location, use geocoding and layer styling tools.\n- When users want to change the appearance of map layers (colors, thickness, transparency, etc.), use the 'style_map_layers' tool with explicit parameters.\n  - The agent should interpret styling requests and call the tool with specific parameters like fill_color, stroke_color, stroke_width, etc.\n  - SINGLE LAYER DETECTION: When there's only ONE layer, use NO layer_names - auto-applies to that layer.\n  - SPECIFIC LAYER TARGETING: When user mentions a specific layer name (e.g., 'make the Rivers layer blue'), use layer_names=['Rivers'].\n  - SAME COLOR FOR ALL: When user wants the SAME color applied to all layers (e.g., 'make everything green'), use ONE call with no layer_names.\n  - DIFFERENT COLORS FOR EACH: When user wants DIFFERENT colors for each layer (e.g., 'apply 3 different warm colors'), make SEPARATE calls for each layer with layer_names=['LayerName'].\n  - CRITICAL: When using layer_names, use the EXACT layer names from the geodata_layers state. Do NOT modify or truncate the names.\n  - Examples: 'make it blue' with 1 layer → style_map_layers(stroke_color='blue')\n  - Examples: 'make the Rivers blue' → style_map_layers(layer_names=['Rivers'], stroke_color='blue')\n  - Examples: 'make everything green' → style_map_layers(fill_color='green') [same color for all]\n  - Examples: '3 different warm colors' → style_map_layers(layer_names=['Layer1'], fill_color='peach'), then style_map_layers(layer_names=['Layer2'], fill_color='coral'), etc.\n  - Use standard color names (red, blue, green, coral, peach, brown, darkorange, etc.) - these will be converted to proper hex values.\n- AUTOMATIC STYLING: Automatically style all newly uploaded layers based on their names using intelligent AI analysis.\n  - This happens automatically whenever new layers are detected that need styling (have default #3388ff colors).\n  - When you detect new layers via auto_style_new_layers(), analyze each layer name using AI reasoning (not hardcoded rules).\n  - Think intelligently about what each layer represents based on its name and apply appropriate cartographic colors.\n  - IMPORTANT: For automatic styling, each layer should get DIFFERENT appropriate colors - make SEPARATE style_map_layers() calls for each layer using layer_names=['LayerName'].\n  - For each layer, reason about: What does this layer name suggest? What type of geographic feature? What colors would be most appropriate?\n  - Examples of AI reasoning:\n    • 'Rivers_of_Europe' → Think: water features → choose blue tones → style_map_layers(layer_names=['Rivers_of_Europe'], fill_color='lightblue', stroke_color='darkblue')\n    • 'Urban_Buildings_NYC' → Think: built environment → choose browns/grays → style_map_layers(layer_names=['Urban_Buildings_NYC'], fill_color='lightgray', stroke_color='darkgray')\n    • 'National_Parks_Canada' → Think: protected natural areas → choose green tones → style_map_layers(layer_names=['National_Parks_Canada'], fill_color='lightgreen', stroke_color='darkgreen')\n    • 'Transport_Routes_Berlin' → Think: infrastructure → choose appropriate colors → style_map_layers(layer_names=['Transport_Routes_Berlin'], fill_color='yellow', stroke_color='orange')\n  - Always explain your reasoning when applying automatic styling.\n  - Consider accessibility, contrast, and cartographic best practices in your AI analysis.\n- When a user asks to find amenities (e.g., 'restaurants in Paris', 'hospitals near the Colosseum'), use the 'geocode_using_overpass_to_geostate' tool.\n  - For this tool, you must extract the amenity type (e.g., 'restaurant', 'hospital') and the location name (e.g., 'Paris', 'Colosseum').\n  - Pass the original user query as the 'query' parameter.\n  - Pass the extracted amenity type as the 'amenity_key' parameter (e.g., 'restaurant', 'park', 'hospital'). Refer to the tool's internal mapping for supported keys.\n  - Pass the extracted location name as the 'location_name' parameter (e.g., 'Paris', 'Colosseum', 'Brandenburg Gate').\n  - You can optionally specify 'radius_meters' (default 10000m), 'max_results' (default 20), and 'timeout' (default 30s) for the search.\n- Explain spatial concepts in simple, non-technical language.\n- When showing data to users, always provide context about what they're seeing.\n- When users ask about specific datasets like 'Tell me more about the Rivers of Africa dataset' or 'What does this dataset contain?', use the 'metadata_search' tool with the name of the dataset as the query parameter.\n\n# DATA HANDLING\n- Help users discover and use external data sources through WFS and WMS protocols.\n- Assist users in uploading and processing their own geospatial data.\n- Connect with open data portals to help users find relevant datasets.\n\nRemember, your goal is to empower users without GIS expertise to create meaningful maps and gain insights from spatial data through natural conversation.",
            },
            "tools": [
                {
                    "name": "geocode_nominatim",
                    "enabled": True,
                    "prompt_override": "Geocode an address using OpenStreetMap Nominatim API. Returns Bounding Box for further request and GeoJson of the area to show to the user.\nUse for:  Geocoding specific addresses or when detailed data (e.g., place types) is needed.\nStrengths:\n* Provides detailed polygon data as GeoJSON (e.g. polygons of countries, states, cities) which can be used for map visualization and further analysis.\n* For forward geocoding: Converts place names or addresses into geographic coordinates.\n* Detailed address data, including house numbers, street names, neighborhoods, and postcodes.\n* Provides the geographical extent (min/max latitude and longitude) for places, including cities, countries, and sometimes smaller features like neighborhoods\n* Categorizes results by OSM tags, indicating the type of place (e.g., city, street, building, amenity, shop)\n* Reverse geocoding: Converts geographic coordinates into detailed address information.\nLimitations:\n* Nominatim relies on crowd-sourced OSM data, so accuracy and completeness depend on community contributions.\n* Provides limited metadata. It does not include attributes like population, elevation, time zones, or weather data.\n* does not support broader geographical queries like finding nearby places, hierarchical relationships beyond administrative divisions",
                },
                {
                    "name": "geocode_overpass",
                    "enabled": True,
                    "prompt_override": 'Geocode a location and search for amenities/POIs using the Overpass API.\n\nArgs:\n    state: The current agent state containing geodata and messages.\n    tool_call_id: The tool call ID for the response.\n    query: The user-friendly query/description for the search.\n    amenity_key: The amenity type (e.g. "restaurant", "park", "hospital").\n    location_name: The location to search (e.g. "Paris", "London", "Germany").\n    radius_meters: Search radius in meters (default: 10000).\n    max_results: Maximum number of results to return (default: 2500).\n    timeout: Timeout for API requests in seconds (default: 300).\n\nReturns:\n    A Command object to update the agent state or a dictionary with results.',
                },
                {
                    "name": "search_librarian",
                    "enabled": True,
                    "prompt_override": 'Tool to find geospatial layers and datasets for a given thematic query.\nUse for:\n* Finding datasets and layers that match a specific thematic query.\n* Finding datasets and layers that match a specific location given user data.\n* Finding datasets that cannot be found using geocoding tools.\nStrengths:\n* Provides a wide range of geospatial data sources, including maps, satellite imagery, and vector data.\n* Allows for flexible queries using natural language, allowing users to search for data by theme, location, or other criteria.\nLimitations:\n* The results are limited to the datasets, layers and regions available in the database.\n* The search is based on similarity, so the results may not always be exact matches to the query.\nquery: the search string to send to the database for a similarity search, like "Rivers Namibia"\nmaxRows: the maximum number of results to return, default is 10\nportal_filter: portal name (string) or null\nbbox_wkt: WKT polygon string or null like POLYGON((...)) to limit results to an area\nInform the user that the results are limited to the datasets and layers available in the linked database.\nInform the user about the total number of results for the query.\nAlways use the bounding box to limit the results to a specific area.',
                },
                {
                    "name": "geoprocess",
                    "enabled": True,
                    "prompt_override": "Tool to geoprocess a specific geospatial layer from the state.\n\nArgs:\n    state: The agent state containing geodata_layers\n    tool_call_id: ID for this tool call\n    target_layer_id: ID of the specific layer to process. If not provided, will attempt to determine from context.\n    operation: Optional operation hint (buffer, overlay, etc.)\n\nThe tool will apply operations like buffer, overlay, simplify, sjoin, merge, sjoin_nearest, centroid to the specified layer.",
                },
                {
                    "name": "search_metadata",
                    "enabled": True,
                    "prompt_override": "Search for a dataset by name/title in the geodata state and return its metadata.\nThis tool is useful when a user asks for information about a specific dataset they've added to the map.\n\nArgs:\n    state: The agent state containing geodata_layers and geodata_last_results\n    tool_call_id: ID for this tool call\n    query: Search string to match against dataset titles or names\n    prioritize_layers: If True, prioritize searching in geodata_layers (datasets added to map)\n\nReturns detailed metadata about matching datasets including description, source, type, etc.",
                },
                {
                    "name": "style_layers",
                    "enabled": True,
                    "prompt_override": 'Style map layers with visual properties. Tool automatically provides current color context.\n\nCRITICAL: For colorblind-safe, accessibility, or distinguishable styling:\n- NEVER use one call without layer_names (this makes all layers identical!)\n- ALWAYS use separate calls: layer_names=["specific_layer"] with different colors\n- Each call must target ONE layer with a UNIQUE color combination\n\nCOLOR SELECTION GUIDANCE - Use HEX colors (#RRGGBB format):\n\nWARM COLOR SCHEMES - Choose from diverse warm families:\n- Red family: #DC143C, #B22222, #8B0000, #CD5C5C\n- Orange family: #FF4500, #FF6347, #D2691E, #A0522D\n- Yellow family: #FFD700, #DAA520, #B8860B, #F4A460\n- Brown family: #A52A2A, #8B4513, #CD853F, #DEB887\n- Ensure HIGH CONTRAST between layers (avoid similar hues like #FFCC00 vs #FFB300)\n\nCOOL COLOR SCHEMES - Choose from diverse cool families:\n- Blue family: #0000FF, #4169E1, #1E90FF, #87CEEB\n- Green family: #008000, #228B22, #32CD32, #90EE90\n- Purple family: #800080, #9370DB, #8A2BE2, #DDA0DD\n- Teal family: #008080, #20B2AA, #48D1CC, #AFEEEE\n\nCOLORBLIND-SAFE SCHEMES - Use these proven combinations:\n- Orange: #E69F00, Sky Blue: #56B4E9, Green: #009E73\n- Yellow: #F0E442, Blue: #0072B2, Vermillion: #D55E00\n- Purple: #CC79A7, Grey: #999999\n\nEARTH TONE SCHEMES:\n- Browns: #8B4513, #A0522D, #CD853F, #DEB887\n- Greens: #556B2F, #6B8E23, #808000, #9ACD32\n- Tans: #D2B48C, #BC8F8F, #F5DEB3, #DDD8C7\n\nGENERAL PRINCIPLES:\n- Maintain 3:1 contrast ratio minimum between adjacent colors\n- Use darker stroke colors than fill colors for definition\n- Test color combinations for accessibility\n- Consider the map background when choosing colors\n- For 3+ layers, use colors from different families (red, blue, green, not red, pink, coral)\n\nFor uniform appearance (all layers same color):\n- Use one call without layer_names\n- Example: style_map_layers(fill_color="#FF0000", stroke_color="#8B0000")\n\nArgs:\n    layer_names: Target specific layers (REQUIRED for distinguishable styling)\n    fill_color: Fill color as hex (#RRGGBB) - agent should choose intelligently\n    stroke_color: Border color as hex (#RRGGBB) - should be darker than fill\n    stroke_width: Border width in pixels\n    fill_opacity: Fill transparency (0.0 to 1.0)\n    stroke_opacity: Border transparency (0.0 to 1.0)\n    radius: Point marker size\n    dash_pattern: Line dash pattern like "5,5"',
                },
                {
                    "name": "autostyle_new_layers",
                    "enabled": True,
                    "prompt_override": "Automatically apply intelligent styling to newly uploaded layers with default colors.\n\nThis tool directly applies appropriate cartographic colors based on layer names and descriptions,\nusing the comprehensive automatic styling system that analyzes layer names and applies contextually\nappropriate colors and styles for different geographic feature types.\n\nKey examples: hospitals→red family, rivers→blue family, forests→green family, roads→gray family.\n\nArgs:\n    layer_names: Specific layer names to auto-style (if None, styles all layers needing styling)",
                },
                {
                    "name": "check_and_autostyle",
                    "enabled": True,
                    "prompt_override": "Check for newly uploaded layers that have default styling (blue #3388ff colors) and need initial styling.\n\nIMPORTANT: This tool ONLY works for layers with default styling. Do NOT use this tool when:\n- Users want to change existing styled layers (use style_map_layers instead)\n- Users request colorblind-safe styling (use style_map_layers instead)\n- Users want to restyle any layers that already have custom colors (use style_map_layers instead)\n\nOnly use this tool proactively when detecting newly uploaded layers that need initial styling.",
                },
                {
                    "name": "apply_color_scheme",
                    "enabled": True,
                    "prompt_override": 'Apply intelligent color schemes to layers based on natural language requests.\n\nSupports:\n- "colorblind safe" or "accessible" - applies colorblind-safe palette\n- "Set1", "Set2", "Spectral" - applies ColorBrewer schemes\n- "warm colors" - applies warm color palette\n- "cool colors" - applies cool color palette\n\nEach layer gets a unique color from the scheme to ensure distinguishability.\n\nArgs:\n    scheme_request: Natural language color scheme request\n    layer_names: Specific layers to style (if None, styles all layers)',
                },
            ],
        },
        "query": "buffer the line by 500 meters of geodata_layers with name=line",
        "geodata_last_results": [],
        "geodata_layers": [
            {
                "id": "layer2",
                "data_source_id": "test",
                "data_type": "GeoJson",
                "data_origin": "TOOL",
                "data_source": "test",
                "data_link": "http://localhost:8000/upload/line.geojson",
                "name": "line",
                "title": "line",
                "description": "",
                "llm_description": "",
                "score": 0,
                "bounding_box": None,
                "layer_type": "GeoJSON",
                "properties": {},
            }
        ],
    }

    resp = client.post("/api/chat", json=payload)
    assert resp.status_code == 200

    body = resp.json()
    print(body)
    # Check that one buffered layer was returned
    assert "geodata_results" in body
    results = body["geodata_results"]
    assert isinstance(results, list) and len(results) == 1
    # The returned GeoDataObject should point to our LOCAL_UPLOAD_DIR via BASE_URL
    result_link = results[0]["data_link"]
    assert result_link.startswith(BASE_URL)
    filename = result_link.split("/")[-1]
    saved_path = os.path.join(LOCAL_UPLOAD_DIR, filename)
    assert os.path.isfile(saved_path)

    with open(saved_path) as f:
        result_gj = json.load(f)

    # 3) build Shapely geometries for actual and expected
    actual = shape(result_gj["features"][0]["geometry"])

    # your expected geometry dict (output_line) should be in scope here:
    expected = shape(output_line["features"][0]["geometry"])

    # 4) wrap them in GeoSeries
    actual_series = gpd.GeoSeries([actual], crs="EPSG:4326")
    expected_series = gpd.GeoSeries([expected], crs="EPSG:4326")
    print(actual_series)
    print(expected_series)
    # 5a) using almost_equals with decimal precision:
    #    returns a boolean Series; assert all True
    assert actual_series.geom_equals_exact(expected_series, tolerance=0.0015).all()


def test_chat_overlay_intersection_expected_area(client, stub_requests):
    pathaoi = os.path.join(os.path.dirname(__file__), "testdata", "aoi.json")
    with open(pathaoi) as f:
        aoi = json.load(f)

    pathgreenland = os.path.join(os.path.dirname(__file__), "testdata", "greenland.json")
    with open(pathgreenland) as f:
        greenland = json.load(f)

    path_inter_greenland = os.path.join(
        os.path.dirname(__file__),
        "testdata",
        "intersection_greenland_aoi.json",
    )
    with open(path_inter_greenland) as f:
        intersection = json.load(f)

    stub_requests(
        {
            "aoi.geojson": aoi,
            "greenland.geojson": greenland,
        }
    )

    payload = {
        "messages": [
            {
                "type": "human",
                "content": "do the operation overlay with how=intersection and crs=EPSG:3413 on both layers with name=greenland and name=aoi, both layers are already available in your state",
            }
        ],
        "options": {
            "search_portals": [],
            "geoserver_backends": [],
            "model_settings": {
                "model_provider": "openai",
                "model_name": "gpt-4-nano",
                "max_tokens": 50000,
                "system_prompt": "You are NaLaMap: an advanced geospatial assistant designed to help users without GIS expertise create maps and perform spatial analysis through natural language interaction.\n\n# ROLE AND CAPABILITIES\n- Your primary purpose is to interpret natural language requests about geographic information and translate them into appropriate map visualizations and spatial analyses.\n- You have access to tools for geocoding, querying geographic databases, processing geospatial data, managing map layers, and styling map layers.\n- You can search for specific amenities (e.g., restaurants, parks, hospitals) near a location using the Overpass API.\n- You can style map layers based on natural language descriptions (e.g., 'make the rivers blue', 'thick red borders', 'transparent fill').\n- You're designed to be proactive, guiding users through the map creation process and suggesting potential next steps.\n\n# STATE INFORMATION\n- The public state contains 'geodata_last_results' (previous results) and 'geodata_layers' (geodata selected by the user).\n- The list 'geodata_results' in the state collects tool results, which are presented to the user in a result list\n- IMPORTANT: When a user asks about a specific dataset, ALWAYS check if that dataset exists in 'geodata_last_results' or 'geodata_layers'.\n- When responding to questions about a dataset, first check if it's available in the state, and use its 'title', 'description', 'llm_description', 'data_source', 'layer_type', 'bounding_box' and other properties to provide specific, detailed information.\n# INTERACTION GUIDELINES\n- Be conversational and accessible to users without GIS expertise.\n- AUTOMATIC STYLING PRIORITY: Always check for and automatically style newly uploaded layers at the start of each interaction.\n  - First use check_and_auto_style_layers() to detect layers needing styling.\n  - Then use auto_style_new_layers() to identify which layers need AI-powered styling.\n  - Finally, use your AI reasoning to determine appropriate colors and call style_map_layers() for each layer.\n  - This ensures all new layers get intelligent styling before responding to user queries.\n- Always clarify ambiguous requests by asking specific questions.\n- Proactively guide users through their mapping journey, suggesting potential next steps.\n- When users ask to highlight or visualize a location, use geocoding and layer styling tools.\n- When users want to change the appearance of map layers (colors, thickness, transparency, etc.), use the 'style_map_layers' tool with explicit parameters.\n  - The agent should interpret styling requests and call the tool with specific parameters like fill_color, stroke_color, stroke_width, etc.\n  - SINGLE LAYER DETECTION: When there's only ONE layer, use NO layer_names - auto-applies to that layer.\n  - SPECIFIC LAYER TARGETING: When user mentions a specific layer name (e.g., 'make the Rivers layer blue'), use layer_names=['Rivers'].\n  - SAME COLOR FOR ALL: When user wants the SAME color applied to all layers (e.g., 'make everything green'), use ONE call with no layer_names.\n  - DIFFERENT COLORS FOR EACH: When user wants DIFFERENT colors for each layer (e.g., 'apply 3 different warm colors'), make SEPARATE calls for each layer with layer_names=['LayerName'].\n  - CRITICAL: When using layer_names, use the EXACT layer names from the geodata_layers state. Do NOT modify or truncate the names.\n  - Examples: 'make it blue' with 1 layer → style_map_layers(stroke_color='blue')\n  - Examples: 'make the Rivers blue' → style_map_layers(layer_names=['Rivers'], stroke_color='blue')\n  - Examples: 'make everything green' → style_map_layers(fill_color='green') [same color for all]\n  - Examples: '3 different warm colors' → style_map_layers(layer_names=['Layer1'], fill_color='peach'), then style_map_layers(layer_names=['Layer2'], fill_color='coral'), etc.\n  - Use standard color names (red, blue, green, coral, peach, brown, darkorange, etc.) - these will be converted to proper hex values.\n- AUTOMATIC STYLING: Automatically style all newly uploaded layers based on their names using intelligent AI analysis.\n  - This happens automatically whenever new layers are detected that need styling (have default #3388ff colors).\n  - When you detect new layers via auto_style_new_layers(), analyze each layer name using AI reasoning (not hardcoded rules).\n  - Think intelligently about what each layer represents based on its name and apply appropriate cartographic colors.\n  - IMPORTANT: For automatic styling, each layer should get DIFFERENT appropriate colors - make SEPARATE style_map_layers() calls for each layer using layer_names=['LayerName'].\n  - For each layer, reason about: What does this layer name suggest? What type of geographic feature? What colors would be most appropriate?\n  - Examples of AI reasoning:\n    • 'Rivers_of_Europe' → Think: water features → choose blue tones → style_map_layers(layer_names=['Rivers_of_Europe'], fill_color='lightblue', stroke_color='darkblue')\n    • 'Urban_Buildings_NYC' → Think: built environment → choose browns/grays → style_map_layers(layer_names=['Urban_Buildings_NYC'], fill_color='lightgray', stroke_color='darkgray')\n    • 'National_Parks_Canada' → Think: protected natural areas → choose green tones → style_map_layers(layer_names=['National_Parks_Canada'], fill_color='lightgreen', stroke_color='darkgreen')\n    • 'Transport_Routes_Berlin' → Think: infrastructure → choose appropriate colors → style_map_layers(layer_names=['Transport_Routes_Berlin'], fill_color='yellow', stroke_color='orange')\n  - Always explain your reasoning when applying automatic styling.\n  - Consider accessibility, contrast, and cartographic best practices in your AI analysis.\n- When a user asks to find amenities (e.g., 'restaurants in Paris', 'hospitals near the Colosseum'), use the 'geocode_using_overpass_to_geostate' tool.\n  - For this tool, you must extract the amenity type (e.g., 'restaurant', 'hospital') and the location name (e.g., 'Paris', 'Colosseum').\n  - Pass the original user query as the 'query' parameter.\n  - Pass the extracted amenity type as the 'amenity_key' parameter (e.g., 'restaurant', 'park', 'hospital'). Refer to the tool's internal mapping for supported keys.\n  - Pass the extracted location name as the 'location_name' parameter (e.g., 'Paris', 'Colosseum', 'Brandenburg Gate').\n  - You can optionally specify 'radius_meters' (default 10000m), 'max_results' (default 20), and 'timeout' (default 30s) for the search.\n- Explain spatial concepts in simple, non-technical language.\n- When showing data to users, always provide context about what they're seeing.\n- When users ask about specific datasets like 'Tell me more about the Rivers of Africa dataset' or 'What does this dataset contain?', use the 'metadata_search' tool with the name of the dataset as the query parameter.\n\n# DATA HANDLING\n- Help users discover and use external data sources through WFS and WMS protocols.\n- Assist users in uploading and processing their own geospatial data.\n- Connect with open data portals to help users find relevant datasets.\n\nRemember, your goal is to empower users without GIS expertise to create meaningful maps and gain insights from spatial data through natural conversation.",
            },
            "tools": [
                {
                    "name": "geocode_nominatim",
                    "enabled": True,
                    "prompt_override": "Geocode an address using OpenStreetMap Nominatim API. Returns Bounding Box for further request and GeoJson of the area to show to the user.\nUse for:  Geocoding specific addresses or when detailed data (e.g., place types) is needed.\nStrengths:\n* Provides detailed polygon data as GeoJSON (e.g. polygons of countries, states, cities) which can be used for map visualization and further analysis.\n* For forward geocoding: Converts place names or addresses into geographic coordinates.\n* Detailed address data, including house numbers, street names, neighborhoods, and postcodes.\n* Provides the geographical extent (min/max latitude and longitude) for places, including cities, countries, and sometimes smaller features like neighborhoods\n* Categorizes results by OSM tags, indicating the type of place (e.g., city, street, building, amenity, shop)\n* Reverse geocoding: Converts geographic coordinates into detailed address information.\nLimitations:\n* Nominatim relies on crowd-sourced OSM data, so accuracy and completeness depend on community contributions.\n* Provides limited metadata. It does not include attributes like population, elevation, time zones, or weather data.\n* does not support broader geographical queries like finding nearby places, hierarchical relationships beyond administrative divisions",
                },
                {
                    "name": "geocode_overpass",
                    "enabled": True,
                    "prompt_override": 'Geocode a location and search for amenities/POIs using the Overpass API.\n\nArgs:\n    state: The current agent state containing geodata and messages.\n    tool_call_id: The tool call ID for the response.\n    query: The user-friendly query/description for the search.\n    amenity_key: The amenity type (e.g. "restaurant", "park", "hospital").\n    location_name: The location to search (e.g. "Paris", "London", "Germany").\n    radius_meters: Search radius in meters (default: 10000).\n    max_results: Maximum number of results to return (default: 2500).\n    timeout: Timeout for API requests in seconds (default: 300).\n\nReturns:\n    A Command object to update the agent state or a dictionary with results.',
                },
                {
                    "name": "search_librarian",
                    "enabled": True,
                    "prompt_override": 'Tool to find geospatial layers and datasets for a given thematic query.\nUse for:\n* Finding datasets and layers that match a specific thematic query.\n* Finding datasets and layers that match a specific location given user data.\n* Finding datasets that cannot be found using geocoding tools.\nStrengths:\n* Provides a wide range of geospatial data sources, including maps, satellite imagery, and vector data.\n* Allows for flexible queries using natural language, allowing users to search for data by theme, location, or other criteria.\nLimitations:\n* The results are limited to the datasets, layers and regions available in the database.\n* The search is based on similarity, so the results may not always be exact matches to the query.\nquery: the search string to send to the database for a similarity search, like "Rivers Namibia"\nmaxRows: the maximum number of results to return, default is 10\nportal_filter: portal name (string) or null\nbbox_wkt: WKT polygon string or null like POLYGON((...)) to limit results to an area\nInform the user that the results are limited to the datasets and layers available in the linked database.\nInform the user about the total number of results for the query.\nAlways use the bounding box to limit the results to a specific area.',
                },
                {
                    "name": "geoprocess",
                    "enabled": True,
                    "prompt_override": "Tool to geoprocess a specific geospatial layer from the state.\n\nArgs:\n    state: The agent state containing geodata_layers\n    tool_call_id: ID for this tool call\n    target_layer_id: ID of the specific layer to process. If not provided, will attempt to determine from context.\n    operation: Optional operation hint (buffer, overlay, etc.)\n\nThe tool will apply operations like buffer, overlay, simplify, sjoin, merge, sjoin_nearest, centroid to the specified layer.",
                },
                {
                    "name": "search_metadata",
                    "enabled": True,
                    "prompt_override": "Search for a dataset by name/title in the geodata state and return its metadata.\nThis tool is useful when a user asks for information about a specific dataset they've added to the map.\n\nArgs:\n    state: The agent state containing geodata_layers and geodata_last_results\n    tool_call_id: ID for this tool call\n    query: Search string to match against dataset titles or names\n    prioritize_layers: If True, prioritize searching in geodata_layers (datasets added to map)\n\nReturns detailed metadata about matching datasets including description, source, type, etc.",
                },
                {
                    "name": "style_layers",
                    "enabled": True,
                    "prompt_override": 'Style map layers with visual properties. Tool automatically provides current color context.\n\nCRITICAL: For colorblind-safe, accessibility, or distinguishable styling:\n- NEVER use one call without layer_names (this makes all layers identical!)\n- ALWAYS use separate calls: layer_names=["specific_layer"] with different colors\n- Each call must target ONE layer with a UNIQUE color combination\n\nCOLOR SELECTION GUIDANCE - Use HEX colors (#RRGGBB format):\n\nWARM COLOR SCHEMES - Choose from diverse warm families:\n- Red family: #DC143C, #B22222, #8B0000, #CD5C5C\n- Orange family: #FF4500, #FF6347, #D2691E, #A0522D\n- Yellow family: #FFD700, #DAA520, #B8860B, #F4A460\n- Brown family: #A52A2A, #8B4513, #CD853F, #DEB887\n- Ensure HIGH CONTRAST between layers (avoid similar hues like #FFCC00 vs #FFB300)\n\nCOOL COLOR SCHEMES - Choose from diverse cool families:\n- Blue family: #0000FF, #4169E1, #1E90FF, #87CEEB\n- Green family: #008000, #228B22, #32CD32, #90EE90\n- Purple family: #800080, #9370DB, #8A2BE2, #DDA0DD\n- Teal family: #008080, #20B2AA, #48D1CC, #AFEEEE\n\nCOLORBLIND-SAFE SCHEMES - Use these proven combinations:\n- Orange: #E69F00, Sky Blue: #56B4E9, Green: #009E73\n- Yellow: #F0E442, Blue: #0072B2, Vermillion: #D55E00\n- Purple: #CC79A7, Grey: #999999\n\nEARTH TONE SCHEMES:\n- Browns: #8B4513, #A0522D, #CD853F, #DEB887\n- Greens: #556B2F, #6B8E23, #808000, #9ACD32\n- Tans: #D2B48C, #BC8F8F, #F5DEB3, #DDD8C7\n\nGENERAL PRINCIPLES:\n- Maintain 3:1 contrast ratio minimum between adjacent colors\n- Use darker stroke colors than fill colors for definition\n- Test color combinations for accessibility\n- Consider the map background when choosing colors\n- For 3+ layers, use colors from different families (red, blue, green, not red, pink, coral)\n\nFor uniform appearance (all layers same color):\n- Use one call without layer_names\n- Example: style_map_layers(fill_color="#FF0000", stroke_color="#8B0000")\n\nArgs:\n    layer_names: Target specific layers (REQUIRED for distinguishable styling)\n    fill_color: Fill color as hex (#RRGGBB) - agent should choose intelligently\n    stroke_color: Border color as hex (#RRGGBB) - should be darker than fill\n    stroke_width: Border width in pixels\n    fill_opacity: Fill transparency (0.0 to 1.0)\n    stroke_opacity: Border transparency (0.0 to 1.0)\n    radius: Point marker size\n    dash_pattern: Line dash pattern like "5,5"',
                },
                {
                    "name": "autostyle_new_layers",
                    "enabled": True,
                    "prompt_override": "Automatically apply intelligent styling to newly uploaded layers with default colors.\n\nThis tool directly applies appropriate cartographic colors based on layer names and descriptions,\nusing the comprehensive automatic styling system that analyzes layer names and applies contextually\nappropriate colors and styles for different geographic feature types.\n\nKey examples: hospitals→red family, rivers→blue family, forests→green family, roads→gray family.\n\nArgs:\n    layer_names: Specific layer names to auto-style (if None, styles all layers needing styling)",
                },
                {
                    "name": "check_and_autostyle",
                    "enabled": True,
                    "prompt_override": "Check for newly uploaded layers that have default styling (blue #3388ff colors) and need initial styling.\n\nIMPORTANT: This tool ONLY works for layers with default styling. Do NOT use this tool when:\n- Users want to change existing styled layers (use style_map_layers instead)\n- Users request colorblind-safe styling (use style_map_layers instead)\n- Users want to restyle any layers that already have custom colors (use style_map_layers instead)\n\nOnly use this tool proactively when detecting newly uploaded layers that need initial styling.",
                },
                {
                    "name": "apply_color_scheme",
                    "enabled": True,
                    "prompt_override": 'Apply intelligent color schemes to layers based on natural language requests.\n\nSupports:\n- "colorblind safe" or "accessible" - applies colorblind-safe palette\n- "Set1", "Set2", "Spectral" - applies ColorBrewer schemes\n- "warm colors" - applies warm color palette\n- "cool colors" - applies cool color palette\n\nEach layer gets a unique color from the scheme to ensure distinguishability.\n\nArgs:\n    scheme_request: Natural language color scheme request\n    layer_names: Specific layers to style (if None, styles all layers)',
                },
            ],
        },
        "query": "do the operation overlay with intersection and EPSG:3413 on both layers with name=greenland and name=aoi, both layers are already available in your state",
        "geodata_last_results": [],
        "geodata_layers": [
            {
                "id": "layer3",
                "data_source_id": "test",
                "data_type": "GeoJson",
                "data_origin": "TOOL",
                "data_source": "test",
                "data_link": "http://localhost:8000/upload/greenland.geojson",
                "name": "greenland",
                "title": "greenland",
                "description": "",
                "llm_description": "",
                "score": 0,
                "bounding_box": None,
                "layer_type": "GeoJSON",
                "properties": {},
            },
            {
                "id": "layer4",
                "data_source_id": "test",
                "data_type": "GeoJson",
                "data_origin": "TOOL",
                "data_source": "test",
                "data_link": "http://localhost:8000/upload/aoi.geojson",
                "name": "aoi",
                "title": "aoi",
                "description": "",
                "llm_description": "",
                "score": 0,
                "bounding_box": None,
                "layer_type": "GeoJSON",
                "properties": {},
            },
        ],
    }

    resp = client.post("/api/chat", json=payload)
    assert resp.status_code == 200

    body = resp.json()
    # Check that one buffered layer was returned
    assert "geodata_results" in body
    results = body["geodata_results"]
    # The returned GeoDataObject should point to our LOCAL_UPLOAD_DIR via BASE_URL
    result_link = results[0]["data_link"]
    print(results)
    assert result_link.startswith(BASE_URL)
    filename = result_link.split("/")[-1]
    saved_path = os.path.join(LOCAL_UPLOAD_DIR, filename)
    assert os.path.isfile(saved_path)

    with open(saved_path) as f:
        result_gj = json.load(f)

    # 3) build Shapely geometries for actual and expected
    actual = shape(result_gj["features"][0]["geometry"])
    actual_gdf = gpd.GeoDataFrame.from_features(result_gj)
    actual_gdf.set_crs("EPSG:4326", inplace=True)
    actual_gdf.to_crs("EPSG:3413", inplace=True)
    # your expected geometry dict (output_line) should be in scope here:
    expected = shape(intersection["features"][0]["geometry"])

    # 4) wrap them in GeoSeries
    actual_series = gpd.GeoSeries([actual], crs="EPSG:4326")
    actual_series.to_crs("EPSG:3413")
    area_actual = actual_gdf.area.iloc[0]
    area_actual_sq_km = area_actual / 1000000
    print(area_actual_sq_km)
    expected_series = gpd.GeoSeries([expected], crs="EPSG:4326")
    # 5a) using almost_equals with decimal precision:
    #    returns a boolean Series; assert all True
    assert actual_series.geom_equals_exact(expected_series, tolerance=1).all()
