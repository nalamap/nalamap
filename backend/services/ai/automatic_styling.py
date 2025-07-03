"""
Automatic styling system that applies appropriate colors and styles based on layer names.
"""

import logging
import re
from typing import Any, Dict

from models.geodata import LayerStyle

logger = logging.getLogger(__name__)

# Color schemes for different types of geographic features
FEATURE_STYLES = {
    "water": {
        "stroke_color": "#1e90f",  # Deep sky blue
        "fill_color": "#87ceeb",  # Sky blue
        "stroke_weight": 2,
        "fill_opacity": 0.6,
        "stroke_opacity": 1.0,
    },
    "river": {
        "stroke_color": "#0066cc",  # Blue
        "fill_color": "#66ccf",  # Light blue
        "stroke_weight": 3,
        "fill_opacity": 0.4,
        "stroke_opacity": 1.0,
    },
    "lake": {
        "stroke_color": "#1e90f",  # Deep sky blue
        "fill_color": "#add8e6",  # Light blue
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
        "stroke_color": "#8b4513",  # Saddle brown
        "fill_color": "#ddd",  # Light gray
        "stroke_weight": 1,
        "fill_opacity": 0.8,
        "stroke_opacity": 1.0,
    },
    "road": {
        "stroke_color": "#2f4f4",  # Dark slate gray
        "fill_color": "#696969",  # Dim gray
        "stroke_weight": 4,
        "fill_opacity": 0.0,  # Roads typically don't have fill
        "stroke_opacity": 1.0,
    },
    "transport": {
        "stroke_color": "#ff6347",  # Tomato
        "fill_color": "#ffa07a",  # Light salmon
        "stroke_weight": 3,
        "fill_opacity": 0.3,
        "stroke_opacity": 1.0,
    },
    "agriculture": {
        "stroke_color": "#daa520",  # Goldenrod
        "fill_color": "#f0e68c",  # Khaki
        "stroke_weight": 1,
        "fill_opacity": 0.6,
        "stroke_opacity": 1.0,
    },
    "boundary": {
        "stroke_color": "#8b0000",  # Dark red
        "fill_color": "#ff6b6b",  # Light red
        "stroke_weight": 2,
        "fill_opacity": 0.1,
        "stroke_opacity": 1.0,
        "stroke_dash_array": "5,5",  # Dashed line for boundaries
    },
    "administrative": {
        "stroke_color": "#800080",  # Purple
        "fill_color": "#dda0dd",  # Plum
        "stroke_weight": 2,
        "fill_opacity": 0.15,
        "stroke_opacity": 1.0,
        "stroke_dash_array": "10,5",
    },
    "elevation": {
        "stroke_color": "#8b4513",  # Saddle brown
        "fill_color": "#deb887",  # Burlywood
        "stroke_weight": 1,
        "fill_opacity": 0.5,
        "stroke_opacity": 1.0,
    },
    "infrastructure": {
        "stroke_color": "#ff4500",  # Orange red
        "fill_color": "#ffa500",  # Orange
        "stroke_weight": 2,
        "fill_opacity": 0.4,
        "stroke_opacity": 1.0,
    },
    "energy": {
        "stroke_color": "#ff6347",  # Tomato
        "fill_color": "#ffb347",  # Light orange
        "stroke_weight": 3,
        "fill_opacity": 0.3,
        "stroke_opacity": 1.0,
    },
    "power": {
        "stroke_color": "#ff0000",  # Red
        "fill_color": "#ff9999",  # Light red
        "stroke_weight": 3,
        "fill_opacity": 0.2,
        "stroke_opacity": 1.0,
    },
    "default": {
        "stroke_color": "#3388f",  # Default blue
        "fill_color": "#3388f",
        "stroke_weight": 2,
        "fill_opacity": 0.15,  # Changed from 0.3 to 0.15 for less transparency
        "stroke_opacity": 0.85,  # Changed from 1.0 to 0.85 (85% opacity)
        "radius": 4,  # Added default radius of 4 (half size)
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
}


def detect_layer_type(layer_name: str, layer_description: str = None) -> str:
    """
    Detect the type of geographic feature based on layer name and description.

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

    # Check keywords in order of specificity
    for feature_type, keywords in FEATURE_KEYWORDS.items():
        for keyword in keywords:
            if re.search(r"\b" + re.escape(keyword) + r"\b", text_to_analyze):
                logger.debug(
                    f"Detected layer type '{feature_type}' from keyword '{keyword}'"
                )
                return feature_type

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
    base_style = FEATURE_STYLES.get(
        layer_type, FEATURE_STYLES["default"]
    ).copy()

    # Adjust styling based on geometry type
    if geometry_type:
        geometry_type = geometry_type.lower()

        # For line geometries (rivers, roads, etc.)
        if geometry_type in ["linestring", "multilinestring"]:
            base_style["fill_opacity"] = 0.0  # Lines don't need fill

            # Roads and transportation need thicker lines
            if layer_type in ["road", "transport"]:
                base_style["stroke_weight"] = max(
                    base_style.get("stroke_weight", 2), 4
                )
            # Rivers need medium thickness
            elif layer_type in ["river", "water"]:
                base_style["stroke_weight"] = max(
                    base_style.get("stroke_weight", 2), 3
                )

        # For point geometries
        elif geometry_type in ["point", "multipoint"]:
            base_style["radius"] = 4  # Changed from 8 to 4 (half size)
            base_style["fill_opacity"] = max(
                base_style.get("fill_opacity", 0.15), 0.4
            )  # Adjusted base opacity
            base_style["stroke_opacity"] = (
                0.85  # Set default stroke opacity to 85%
            )

            # Buildings and urban features need smaller points
            if layer_type in ["building", "urban"]:
                base_style["radius"] = 3  # Changed from 6 to 3
            # Infrastructure and energy need larger, more visible points
            elif layer_type in ["infrastructure", "energy", "power"]:
                base_style["radius"] = 6  # Changed from 10 to 6

        # For polygon geometries
        elif geometry_type in ["polygon", "multipolygon"]:
            # Administrative boundaries need low fill opacity
            if layer_type in ["boundary", "administrative"]:
                base_style["fill_opacity"] = min(
                    base_style.get("fill_opacity", 0.3), 0.2
                )
            # Water bodies need higher fill opacity
            elif layer_type in ["water", "lake", "ocean"]:
                base_style["fill_opacity"] = max(
                    base_style.get("fill_opacity", 0.3), 0.6
                )

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

    logger.info(
        f"Generated automatic style for layer '{layer_name}' (type: {layer_type}): {style}"
    )
    return style


def apply_automatic_styling_to_layer(
    layer_dict: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Apply automatic styling to a layer dictionary.

    Args:
        layer_dict: Dictionary representation of a GeoDataObject

    Returns:
        Updated layer dictionary with automatic styling applied
    """
    # Extract layer information
    layer_name = layer_dict.get("name", "")
    layer_description = layer_dict.get("description") or layer_dict.get(
        "title", ""
    )

    # Try to detect geometry type from data_link if it's a GeoJSON
    geometry_type = None
    data_link = layer_dict.get("data_link", "")
    if data_link.lower().endswith((".geojson", ".json")):
        # Could implement geometry type detection here if needed
        pass

    # Generate automatic styling
    auto_style = generate_automatic_style(
        layer_name, layer_description, geometry_type
    )

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

    logger.info(f"Applied automatic styling to layer '{layer_name}'")
    return layer_dict
