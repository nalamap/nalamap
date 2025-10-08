"""
Automatic styling system that applies appropriate colors and styles based on layer names.
"""

import logging
import re
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional

try:
    import matplotlib.colors as mcolors
    import matplotlib.pyplot as plt

    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

try:
    import webcolors

    WEBCOLORS_AVAILABLE = True
except ImportError:
    WEBCOLORS_AVAILABLE = False

from models.geodata import LayerStyle

logger = logging.getLogger(__name__)


# =============================================================================
# COLOR INTELLIGENCE SYSTEM
# =============================================================================


def parse_intelligent_color(color_input: str) -> Optional[str]:
    """
    Intelligent color parsing that supports:
    - Basic color names (red, blue, etc.)
    - CSS/Web color names (darkslategray, etc.)
    - ColorBrewer schemes (Set1, Set2, Spectral, etc.)
    - Matplotlib colormap names
    - Hex codes

    Args:
        color_input: Color name, scheme, or hex code

    Returns:
        Hex color code or None if not found
    """
    if not color_input:
        return None

    color_input = color_input.strip().lower()

    # Handle hex codes
    if color_input.startswith("#"):
        return color_input

    # Basic color mapping
    basic_colors = {
        "red": "#ff0000",
        "blue": "#0000ff",
        "green": "#00ff00",
        "yellow": "#ffff00",
        "orange": "#ffa500",
        "purple": "#800080",
        "pink": "#ffc0cb",
        "brown": "#a52a2a",
        "black": "#000000",
        "white": "#ffffff",
        "gray": "#808080",
        "grey": "#808080",
        "cyan": "#00ffff",
        "magenta": "#ff00ff",
        "lime": "#00ff00",
        "navy": "#000080",
        "silver": "#c0c0c0",
        "maroon": "#800000",
        "olive": "#808000",
        "teal": "#008080",
        "aqua": "#00ffff",
    }

    if color_input in basic_colors:
        return basic_colors[color_input]

    # Try webcolors for extended CSS color names
    if WEBCOLORS_AVAILABLE:
        try:
            return webcolors.name_to_hex(color_input)
        except ValueError:
            pass

    # Try matplotlib colormap single color extraction
    if MATPLOTLIB_AVAILABLE:
        try:
            # Check if it's a matplotlib colormap
            if color_input in plt.colormaps():
                # Get first color from colormap
                cmap = plt.get_cmap(color_input)
                rgba = cmap(0.5)  # Get middle color
                return mcolors.rgb2hex(rgba[:3])
        except Exception:
            pass

    return None


def get_colorbrewer_scheme(scheme_name: str, n_colors: int = 5) -> List[str]:
    """
    Get ColorBrewer color scheme from matplotlib.

    Args:
        scheme_name: Name of the ColorBrewer scheme (e.g., 'Set1', 'Spectral', 'RdYlBu')
        n_colors: Number of colors to extract

    Returns:
        List of hex color codes
    """
    if not MATPLOTLIB_AVAILABLE:
        return []

    # Map common lowercase names to proper matplotlib names
    scheme_map = {
        "set1": "Set1",
        "set2": "Set2",
        "set3": "Set3",
        "spectral": "Spectral",
        "rdylbu": "RdYlBu",
        "rdylgn": "RdYlGn",
        "paired": "Paired",
        "dark2": "Dark2",
        "accent": "Accent",
        "pastel1": "Pastel1",
        "pastel2": "Pastel2",
        "rdbu": "RdBu",
        "rdgy": "RdGy",
        "rdpu": "RdPu",
        "bugn": "BuGn",
        "bupu": "BuPu",
        "gnbu": "GnBu",
        "orrd": "OrRd",
        "pubugn": "PuBuGn",
        "pubu": "PuBu",
        "purd": "PuRd",
        "ylgn": "YlGn",
        "ylgnbu": "YlGnBu",
        "ylorbr": "YlOrBr",
        "ylorrd": "YlOrRd",
    }

    # Normalize scheme name
    scheme_lower = scheme_name.lower()
    actual_scheme = scheme_map.get(scheme_lower, scheme_name)

    try:
        cmap = plt.get_cmap(actual_scheme)
        colors = []
        for i in range(n_colors):
            rgba = cmap(i / (n_colors - 1) if n_colors > 1 else 0.5)
            colors.append(mcolors.rgb2hex(rgba[:3]))
        return colors
    except Exception as e:
        logger.warning(f"Could not get ColorBrewer scheme '{scheme_name}': {e}")
        return []


def get_colorblind_safe_palette(n_colors: int = 5) -> List[str]:
    """
    Get a colorblind-safe color palette.

    Args:
        n_colors: Number of colors needed

    Returns:
        List of colorblind-safe hex colors
    """
    # Use ColorBrewer Set2 which is colorblind-safe
    colorblind_safe = get_colorbrewer_scheme("Set2", n_colors)

    if colorblind_safe:
        return colorblind_safe

    # Fallback to hardcoded colorblind-safe palette
    fallback_colors = [
        "#1f77b4",  # Blue
        "#ff7f0e",  # Orange
        "#2ca02c",  # Green
        "#d62728",  # Red
        "#9467bd",  # Purple
        "#8c564b",  # Brown
        "#e377c2",  # Pink
        "#7f7f7f",  # Gray
        "#bcbd22",  # Olive
        "#17becf",  # Cyan
    ]

    return fallback_colors[:n_colors]


def parse_color_scheme_request(request: str) -> Dict[str, Any]:
    """
    Parse natural language color scheme requests.

    Args:
        request: Natural language request (e.g., "colorblind safe", "warm colors", "Set1")

    Returns:
        Dictionary with scheme info and colors
    """
    request = request.lower().strip()

    # Colorblind safe requests
    if any(term in request for term in ["colorblind", "accessible", "safe"]):
        colors = get_colorblind_safe_palette()
        return {
            "type": "colorblind_safe",
            "name": "Colorblind Safe",
            "colors": colors,
            "description": "Colors safe for colorblind users",
        }

    # ColorBrewer scheme requests
    colorbrewer_map = {
        "set1": "Set1",
        "set2": "Set2",
        "set3": "Set3",
        "spectral": "Spectral",
        "rdylbu": "RdYlBu",
        "rdylgn": "RdYlGn",
        "paired": "Paired",
        "dark2": "Dark2",
        "accent": "Accent",
    }

    for key, scheme in colorbrewer_map.items():
        if key in request:
            colors = get_colorbrewer_scheme(key)
            return {
                "type": "colorbrewer",
                "name": scheme,
                "colors": colors,
                "description": f"ColorBrewer {scheme} scheme",
            }

    # Warm/cool color requests
    if "warm" in request:
        warm_colors = ["#d62728", "#ff7f0e", "#ff9800", "#ffc107", "#ffeb3b"]
        return {
            "type": "warm",
            "name": "Warm Colors",
            "colors": warm_colors,
            "description": "Warm color palette",
        }

    if "cool" in request:
        cool_colors = ["#1f77b4", "#2ca02c", "#00bcd4", "#9c27b0", "#3f51b5"]
        return {
            "type": "cool",
            "name": "Cool Colors",
            "colors": cool_colors,
            "description": "Cool color palette",
        }

    return {
        "type": "unknown",
        "name": "Unknown",
        "colors": [],
        "description": f"Could not parse color request: {request}",
    }


# =============================================================================
# FEATURE STYLES (existing code)
# =============================================================================

# Color schemes for different types of geographic features
FEATURE_STYLES = {
    "water": {
        "stroke_color": "#1E90FF",  # Deep sky blue
        "fill_color": "#87CEEB",  # Sky blue
        "stroke_weight": 2,
        "fill_opacity": 0.6,
        "stroke_opacity": 1.0,
    },
    "river": {
        "stroke_color": "#0066CC",  # Blue
        "fill_color": "#66CCFF",  # Light blue
        "stroke_weight": 3,
        "fill_opacity": 0.4,
        "stroke_opacity": 1.0,
    },
    "lake": {
        "stroke_color": "#1E90FF",  # Deep sky blue
        "fill_color": "#ADD8E6",  # Light blue
        "stroke_weight": 2,
        "fill_opacity": 0.7,
        "stroke_opacity": 1.0,
    },
    "ocean": {
        "stroke_color": "#0047ab",  # Cobalt blue
        "fill_color": "#4682b4",  # Steel blue
        "stroke_weight": 1,
        "fill_opacity": 0.8,
        "stroke_opacity": 1.0,
    },
    "forest": {
        "stroke_color": "#228b22",  # Forest green
        "fill_color": "#90ee90",  # Light green
        "stroke_weight": 1,
        "fill_opacity": 0.6,
        "stroke_opacity": 1.0,
    },
    "vegetation": {
        "stroke_color": "#32cd32",  # Lime green
        "fill_color": "#98fb98",  # Pale green
        "stroke_weight": 1,
        "fill_opacity": 0.5,
        "stroke_opacity": 1.0,
    },
    "park": {
        "stroke_color": "#006400",  # Dark green
        "fill_color": "#7cfc00",  # Lawn green
        "stroke_weight": 2,
        "fill_opacity": 0.4,
        "stroke_opacity": 1.0,
    },
    "urban": {
        "stroke_color": "#696969",  # Dim gray
        "fill_color": "#d3d3d3",  # Light gray
        "stroke_weight": 1,
        "fill_opacity": 0.7,
        "stroke_opacity": 1.0,
    },
    "building": {
        "stroke_color": "#8B4513",  # Saddle brown
        "fill_color": "#DDDDDD",  # Light gray
        "stroke_weight": 1,
        "fill_opacity": 0.8,
        "stroke_opacity": 1.0,
    },
    "road": {
        "stroke_color": "#2F4F4F",  # Dark slate gray
        "fill_color": "#696969",  # Dim gray
        "stroke_weight": 4,
        "fill_opacity": 0.0,  # Roads typically don't have fill
        "stroke_opacity": 1.0,
    },
    "transport": {
        "stroke_color": "#cc4400",  # Dark orange
        "fill_color": "#ff9966",  # Light orange
        "stroke_weight": 3,
        "fill_opacity": 0.3,
        "stroke_opacity": 1.0,
    },
    "agriculture": {
        "stroke_color": "#cc9900",  # Dark goldenrod
        "fill_color": "#ffcc66",  # Light goldenrod
        "stroke_weight": 1,
        "fill_opacity": 0.6,
        "stroke_opacity": 1.0,
    },
    "boundary": {
        "stroke_color": "#990000",  # Dark red
        "fill_color": "#ff9999",  # Light red
        "stroke_weight": 2,
        "fill_opacity": 0.1,
        "stroke_opacity": 1.0,
        "stroke_dash_array": "5,5",  # Dashed line for boundaries
    },
    "administrative": {
        "stroke_color": "#663399",  # Dark purple
        "fill_color": "#cc99ff",  # Light purple
        "stroke_weight": 2,
        "fill_opacity": 0.15,
        "stroke_opacity": 1.0,
        "stroke_dash_array": "10,5",
    },
    "elevation": {
        "stroke_color": "#8b4513",  # Saddle brown
        "fill_color": "#deb887",  # Burlywood (keep as is - already well aligned)
        "stroke_weight": 1,
        "fill_opacity": 0.5,
        "stroke_opacity": 1.0,
    },
    "infrastructure": {
        "stroke_color": "#cc3300",  # Dark red-orange
        "fill_color": "#ff9966",  # Light red-orange
        "stroke_weight": 2,
        "fill_opacity": 0.4,
        "stroke_opacity": 1.0,
    },
    "energy": {
        "stroke_color": "#cc4400",  # Dark orange
        "fill_color": "#ffaa66",  # Light orange
        "stroke_weight": 3,
        "fill_opacity": 0.3,
        "stroke_opacity": 1.0,
    },
    "power": {
        "stroke_color": "#cc0000",  # Dark red
        "fill_color": "#ff9999",  # Light red
        "stroke_weight": 3,
        "fill_opacity": 0.2,
        "stroke_opacity": 1.0,
    },
    "hospital": {
        "stroke_color": "#cc0000",  # Dark red
        "fill_color": "#ff9999",  # Light red
        "stroke_weight": 2,
        "fill_opacity": 0.6,
        "stroke_opacity": 1.0,
    },
    "healthcare": {
        "stroke_color": "#cc0000",  # Dark red
        "fill_color": "#ff9999",  # Light red
        "stroke_weight": 2,
        "fill_opacity": 0.5,
        "stroke_opacity": 1.0,
    },
    "default": {
        "stroke_color": "#3388FF",  # Default blue
        "fill_color": "#3388FF",
        "stroke_weight": 2,
        "fill_opacity": 0.15,  # Changed from 0.3 to 0.15 for less transparency
        "stroke_opacity": 0.85,  # Changed from 1.0 to 0.85 (85% opacity)
        "radius": 6,  # Changed from 4 to 6 pixels
    },
}

# Keywords for feature detection (order matters - more specific first)
FEATURE_KEYWORDS = {
    "water": [
        "water",
        "waters",
        "hydro",
        "hydrography",
        "aqua",
        "marine",
        "sea",
        "ocean",
        "bay",
        "gul",
        "strait",
        "lake",
        "lakes",
        "pond",
        "ponds",
        "reservoir",
        "reservoirs",
        "lagoon",
        "lagoons",
    ],
    "river": [
        "river",
        "rivers",
        "stream",
        "streams",
        "creek",
        "creeks",
        "brook",
        "brooks",
        "tributary",
        "tributaries",
        "waterway",
        "waterways",
        "drainage",
        "basin",
        "basins",
        "catchment",
    ],
    "forest": [
        "forest",
        "forests",
        "woodland",
        "woodlands",
        "trees",
        "tree",
        "timber",
        "jungle",
        "rainforest",
    ],
    "vegetation": [
        "vegetation",
        "green",
        "grass",
        "grassland",
        "meadow",
        "meadows",
        "pasture",
        "rangeland",
        "shrub",
        "shrubs",
    ],
    "park": [
        "park",
        "parks",
        "garden",
        "gardens",
        "recreation",
        "protected",
        "conservation",
        "reserve",
        "reserves",
        "wildlife",
        "nature",
        "sanctuary",
        "national_park",
    ],
    "urban": [
        "urban",
        "city",
        "cities",
        "town",
        "towns",
        "metropolitan",
        "settlement",
        "settlements",
        "residential",
        "commercial",
        "industrial",
        "developed",
        "development",
    ],
    "building": [
        "building",
        "buildings",
        "structure",
        "structures",
        "construction",
        "facility",
        "facilities",
        "infrastructure_building",
        "house",
        "houses",
        "office",
        "offices",
    ],
    "road": [
        "road",
        "roads",
        "highway",
        "highways",
        "street",
        "streets",
        "avenue",
        "route",
        "routes",
        "motorway",
        "freeway",
        "boulevard",
        "lane",
        "path",
        "paths",
    ],
    "transport": [
        "transport",
        "transportation",
        "traffic",
        "railway",
        "railroad",
        "rail",
        "metro",
        "subway",
        "transit",
        "airport",
        "port",
        "harbor",
        "station",
        "terminal",
    ],
    "agriculture": [
        "agriculture",
        "agricultural",
        "farm",
        "farms",
        "farming",
        "crop",
        "crops",
        "field",
        "fields",
        "cultivation",
        "livestock",
        "ranch",
        "pasture",
    ],
    "boundary": [
        "boundary",
        "boundaries",
        "border",
        "borders",
        "limit",
        "limits",
        "demarcation",
        "division",
        "administrative_boundary",
        "political",
    ],
    "administrative": [
        "administrative",
        "admin",
        "district",
        "districts",
        "region",
        "regions",
        "state",
        "states",
        "province",
        "provinces",
        "county",
        "counties",
        "municipality",
        "municipalities",
    ],
    "elevation": [
        "elevation",
        "dem",
        "dtm",
        "topography",
        "topographic",
        "contour",
        "contours",
        "height",
        "altitude",
        "terrain",
        "relie",
        "slope",
        "hill",
        "hills",
        "mountain",
        "mountains",
    ],
    "infrastructure": [
        "infrastructure",
        "utility",
        "utilities",
        "pipeline",
        "pipelines",
        "cable",
        "cables",
        "line",
        "lines",
        "grid",
        "network",
        "system",
        "telecommunications",
        "communication",
    ],
    "energy": [
        "energy",
        "power",
        "electric",
        "electrical",
        "transmission",
        "distribution",
        "substation",
        "substations",
    ],
    "power": [
        "power_line",
        "powerline",
        "transmission_line",
        "electrical_grid",
        "power_grid",
    ],
    "hospital": [
        "hospital",
        "hospitals",
        "medical",
        "clinic",
        "clinics",
        "emergency",
        "urgent_care",
        "medical_center",
        "health_center",
        "infirmary",
    ],
    "healthcare": [
        "healthcare",
        "health",
        "medical_facility",
        "pharmacy",
        "pharmacies",
        "doctor",
        "doctors",
        "dentist",
        "dental",
        "veterinary",
        "vet",
    ],
}


def detect_layer_type(layer_name: str, layer_description: str = None) -> str:
    """
    Detect the type of geographic feature based on layer name and description.
    Uses both exact matching and fuzzy matching for small misspellings.

    Args:
        layer_name: The name of the layer
        layer_description: Optional description of the layer

    Returns:
        The detected feature type or 'default' if no match found
    """
    # Combine name and description for analysis
    text_to_analyze = layer_name.lower()
    if layer_description:
        text_to_analyze += " " + layer_description.lower()

    logger.debug(f"Analyzing text for layer type: '{text_to_analyze}'")

    # First pass: Exact keyword matching (for performance)
    for feature_type, keywords in FEATURE_KEYWORDS.items():
        for keyword in keywords:
            # Use a more flexible pattern that handles underscores and other separators
            if re.search(r"\b" + re.escape(keyword) + r"(?=\W|_|$)", text_to_analyze):
                logger.debug(f"Detected layer type '{feature_type}' from exact keyword '{keyword}'")
                return feature_type

    # Second pass: Fuzzy matching for small misspellings
    # Extract individual words from the text to analyze
    words = re.findall(r"\b\w+\b", text_to_analyze)

    best_match_score = 0.0
    best_match_type = None
    best_keyword = None

    # Threshold for fuzzy matching (0.8 means 80% similarity)
    FUZZY_THRESHOLD = 0.8

    for word in words:
        if len(word) < 3:  # Skip very short words
            continue

        for feature_type, keywords in FEATURE_KEYWORDS.items():
            for keyword in keywords:
                if len(keyword) < 3:  # Skip very short keywords
                    continue

                # Calculate similarity ratio
                similarity = SequenceMatcher(None, word, keyword).ratio()

                if similarity >= FUZZY_THRESHOLD and similarity > best_match_score:
                    best_match_score = similarity
                    best_match_type = feature_type
                    best_keyword = keyword

    if best_match_type:
        logger.debug(
            f"Detected layer type '{best_match_type}' from fuzzy keyword '{best_keyword}' "
            f"(similarity: {best_match_score:.2f})"
        )
        return best_match_type

    logger.debug("No specific layer type detected, using default")
    return "default"


def generate_automatic_style(
    layer_name: str, layer_description: str = None, geometry_type: str = None
) -> LayerStyle:
    """
    Generate appropriate styling for a layer based on its name and description.

    Args:
        layer_name: The name of the layer
        layer_description: Optional description of the layer
        geometry_type: Optional geometry type (Point, LineString, Polygon, etc.)

    Returns:
        LayerStyle object with appropriate styling
    """
    # Detect the layer type
    layer_type = detect_layer_type(layer_name, layer_description)

    # Get base style for the detected type
    base_style = FEATURE_STYLES.get(layer_type, FEATURE_STYLES["default"]).copy()

    # Adjust styling based on geometry type
    if geometry_type:
        geometry_type = geometry_type.lower()

        # For line geometries (rivers, roads, etc.)
        if geometry_type in ["linestring", "multilinestring"]:
            base_style["fill_opacity"] = 0.0  # Lines don't need fill

            # Roads and transportation need thicker lines
            if layer_type in ["road", "transport"]:
                base_style["stroke_weight"] = max(base_style.get("stroke_weight", 2), 4)
            # Rivers need medium thickness
            elif layer_type in ["river", "water"]:
                base_style["stroke_weight"] = max(base_style.get("stroke_weight", 2), 3)

        # For point geometries
        elif geometry_type in ["point", "multipoint"]:
            base_style["radius"] = 6  # Changed from 4 to 6 pixels
            base_style["fill_opacity"] = max(
                base_style.get("fill_opacity", 0.15), 0.4
            )  # Adjusted base opacity
            base_style["stroke_opacity"] = 0.85  # Set default stroke opacity to 85%

            # Buildings and urban features need smaller points
            if layer_type in ["building", "urban"]:
                base_style["radius"] = 5  # Changed from 3 to 5
            # Infrastructure, energy, and healthcare need larger, more visible points
            elif layer_type in ["infrastructure", "energy", "power", "hospital", "healthcare"]:
                base_style["radius"] = 8  # Changed from 6 to 8

        # For polygon geometries
        elif geometry_type in ["polygon", "multipolygon"]:
            # Administrative boundaries need low fill opacity
            if layer_type in ["boundary", "administrative"]:
                base_style["fill_opacity"] = min(base_style.get("fill_opacity", 0.3), 0.2)
            # Water bodies need higher fill opacity
            elif layer_type in ["water", "lake", "ocean"]:
                base_style["fill_opacity"] = max(base_style.get("fill_opacity", 0.3), 0.6)

    # Create LayerStyle object
    style = LayerStyle(
        stroke_color=base_style.get("stroke_color"),
        fill_color=base_style.get("fill_color"),
        stroke_weight=base_style.get("stroke_weight"),
        fill_opacity=base_style.get("fill_opacity"),
        stroke_opacity=base_style.get("stroke_opacity"),
        radius=base_style.get("radius"),
        stroke_dash_array=base_style.get("stroke_dash_array"),
        line_cap="round",
        line_join="round",
    )

    logger.info("Generated automatic style for layer '{layer_name}' (type: {layer_type}): {style}")
    return style


def apply_automatic_styling_to_layer(layer_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply automatic styling to a layer dictionary.

    Args:
        layer_dict: Dictionary representation of a GeoDataObject

    Returns:
        Updated layer dictionary with automatic styling applied
    """
    # Extract layer information
    layer_name = layer_dict.get("name", "")
    layer_description = layer_dict.get("description") or layer_dict.get("title", "")

    # Try to detect geometry type from data_link if it's a GeoJSON
    geometry_type = None
    data_link = layer_dict.get("data_link", "")
    if data_link.lower().endswith((".geojson", ".json")):
        # Could implement geometry type detection here if needed
        pass

    # Generate automatic styling
    auto_style = generate_automatic_style(layer_name, layer_description, geometry_type)

    # Convert LayerStyle to dictionary
    style_dict = {
        "stroke_color": auto_style.stroke_color,
        "fill_color": auto_style.fill_color,
        "stroke_weight": auto_style.stroke_weight,
        "fill_opacity": auto_style.fill_opacity,
        "stroke_opacity": auto_style.stroke_opacity,
        "radius": auto_style.radius,
        "stroke_dash_array": auto_style.stroke_dash_array,
        "line_cap": auto_style.line_cap,
        "line_join": auto_style.line_join,
    }

    # Remove None values
    style_dict = {k: v for k, v in style_dict.items() if v is not None}

    # Apply the styling to the layer
    layer_dict["style"] = style_dict

    logger.info("Applied automatic styling to layer '{layer_name}'")
    return layer_dict
