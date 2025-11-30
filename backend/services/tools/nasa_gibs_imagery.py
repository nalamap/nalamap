"""
NASA GIBS (Global Imagery Browse Services) Tool for OSINT

This tool provides access to NASA's vast collection of satellite imagery layers
through the GIBS WMS/WMTS services.

Data Source:
- NASA GIBS: https://earthdata.nasa.gov/eosdis/science-system-description/eosdis-components/gibs
- Coverage: Global
- Update Frequency: Daily to hourly depending on layer
- Resolution: Varies from 250m to 2km

Categories Available:
- Fires & Thermal Anomalies
- Weather & Atmosphere
- Ocean & Sea Surface
- Land & Vegetation
- Cryosphere (Snow/Ice)
- True Color Imagery
- Nighttime Imagery

Use Cases:
- Real-time environmental monitoring
- Disaster response visualization
- Climate analysis
- Land use observation
- Ocean monitoring

Note:
- No API key required
- Data is freely available
- Updates happen automatically
"""

import logging
import uuid
from typing import Any, Optional

import requests
from langchain_core.messages import ToolMessage
from langchain_core.tools import tool
from langchain_core.tools.base import InjectedToolCallId
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from typing_extensions import Annotated

from models.geodata import DataOrigin, DataType, GeoDataObject
from models.states import GeoDataAgentState

logger = logging.getLogger(__name__)

# NASA GIBS WMS endpoints
NASA_GIBS_WMS_BASE = "https://gibs.earthdata.nasa.gov/wms/epsg3857/best/wms.cgi"

# Comprehensive catalog of NASA GIBS layers organized by category
NASA_GIBS_LAYERS = {
    # ==================== FIRES & THERMAL ====================
    "viirs_snpp_fire_day": {
        "name": "VIIRS_SNPP_Thermal_Anomalies_375m_Day",
        "title": "VIIRS SNPP Fire Detection (Day, 375m)",
        "category": "fire",
        "description": "High-resolution fire/thermal anomaly detections from VIIRS Suomi NPP",
    },
    "viirs_snpp_fire_night": {
        "name": "VIIRS_SNPP_Thermal_Anomalies_375m_Night",
        "title": "VIIRS SNPP Fire Detection (Night, 375m)",
        "category": "fire",
        "description": "Nighttime fire detections from VIIRS SNPP",
    },
    "viirs_noaa20_fire_day": {
        "name": "VIIRS_NOAA20_Thermal_Anomalies_375m_Day",
        "title": "VIIRS NOAA-20 Fire Detection (Day, 375m)",
        "category": "fire",
        "description": "Fire detections from VIIRS NOAA-20 satellite",
    },
    "modis_terra_fire_day": {
        "name": "MODIS_Terra_Thermal_Anomalies_Day",
        "title": "MODIS Terra Fire Detection (Day)",
        "category": "fire",
        "description": "Fire detections from MODIS Terra satellite",
    },
    "modis_aqua_fire_day": {
        "name": "MODIS_Aqua_Thermal_Anomalies_Day",
        "title": "MODIS Aqua Fire Detection (Day)",
        "category": "fire",
        "description": "Afternoon fire observations from MODIS Aqua",
    },

    # ==================== TRUE COLOR IMAGERY ====================
    "modis_terra_truecolor": {
        "name": "MODIS_Terra_CorrectedReflectance_TrueColor",
        "title": "MODIS Terra True Color",
        "category": "imagery",
        "description": "Natural color satellite imagery from MODIS Terra",
    },
    "modis_aqua_truecolor": {
        "name": "MODIS_Aqua_CorrectedReflectance_TrueColor",
        "title": "MODIS Aqua True Color",
        "category": "imagery",
        "description": "Natural color satellite imagery from MODIS Aqua (afternoon)",
    },
    "viirs_snpp_truecolor": {
        "name": "VIIRS_SNPP_CorrectedReflectance_TrueColor",
        "title": "VIIRS SNPP True Color",
        "category": "imagery",
        "description": "High-resolution true color from VIIRS Suomi NPP",
    },
    "viirs_noaa20_truecolor": {
        "name": "VIIRS_NOAA20_CorrectedReflectance_TrueColor",
        "title": "VIIRS NOAA-20 True Color",
        "category": "imagery",
        "description": "High-resolution true color from VIIRS NOAA-20",
    },

    # ==================== CLOUDS ====================
    "modis_terra_cloud_fraction": {
        "name": "MODIS_Terra_Cloud_Fraction_Day",
        "title": "MODIS Terra Cloud Fraction (Day)",
        "category": "weather",
        "description": "Cloud cover fraction from MODIS Terra satellite",
    },
    "modis_aqua_cloud_fraction": {
        "name": "MODIS_Aqua_Cloud_Fraction_Day",
        "title": "MODIS Aqua Cloud Fraction (Day)",
        "category": "weather",
        "description": "Cloud cover fraction from MODIS Aqua satellite",
    },

    # ==================== TEMPERATURE ====================
    "modis_lst_day": {
        "name": "MODIS_Terra_Land_Surface_Temp_Day",
        "title": "Land Surface Temperature (Day)",
        "category": "temperature",
        "description": "Daytime land surface temperature from MODIS Terra",
    },
    "modis_lst_night": {
        "name": "MODIS_Terra_Land_Surface_Temp_Night",
        "title": "Land Surface Temperature (Night)",
        "category": "temperature",
        "description": "Nighttime land surface temperature from MODIS Terra",
    },
    "sst_mur": {
        "name": "GHRSST_L4_MUR_Sea_Surface_Temperature",
        "title": "Sea Surface Temperature (MUR)",
        "category": "ocean",
        "description": "Multi-scale Ultra-high Resolution sea surface temperature",
    },
    "chlorophyll": {
        "name": "MODIS_Aqua_Chlorophyll_A",
        "title": "Chlorophyll-a Concentration",
        "category": "ocean",
        "description": "Ocean chlorophyll concentration indicating phytoplankton",
    },

    # ==================== SNOW & ICE ====================
    "modis_snow_cover": {
        "name": "MODIS_Terra_NDSI_Snow_Cover",
        "title": "Snow Cover (NDSI)",
        "category": "cryosphere",
        "description": "Snow cover extent from MODIS Normalized Difference Snow Index",
    },
    "viirs_snow_cover": {
        "name": "VIIRS_SNPP_NDSI_Snow_Cover",
        "title": "VIIRS Snow Cover",
        "category": "cryosphere",
        "description": "High-resolution snow cover from VIIRS",
    },

    # ==================== VEGETATION ====================
    "modis_ndvi": {
        "name": "MODIS_Terra_NDVI_8Day",
        "title": "Vegetation Index (NDVI)",
        "category": "vegetation",
        "description": "8-day composite Normalized Difference Vegetation Index",
    },
    "modis_evi": {
        "name": "MODIS_Terra_EVI_8Day",
        "title": "Enhanced Vegetation Index (EVI)",
        "category": "vegetation",
        "description": "8-day composite Enhanced Vegetation Index",
    },

    # ==================== ATMOSPHERE ====================
    "modis_aod": {
        "name": "MODIS_Terra_Aerosol_Optical_Depth",
        "title": "Aerosol Optical Depth",
        "category": "atmosphere",
        "description": "Atmospheric aerosol concentration from MODIS",
    },
    "omps_ai": {
        "name": "OMPS_Aerosol_Index",
        "title": "Aerosol Index (OMPS)",
        "category": "atmosphere",
        "description": "UV Aerosol Index showing smoke, dust plumes",
    },

    # ==================== NIGHTTIME ====================
    "viirs_dnb": {
        "name": "VIIRS_SNPP_DayNightBand_ENCC",
        "title": "Day/Night Band (City Lights)",
        "category": "night",
        "description": "Nighttime visible imagery showing city lights and fires",
    },

    # ==================== PRECIPITATION ====================
    "imerg_precipitation": {
        "name": "IMERG_Precipitation_Rate",
        "title": "Precipitation Rate (IMERG)",
        "category": "weather",
        "description": "Global precipitation rate estimate",
    },

    # ==================== GEOSTATIONARY ====================
    "goes_east_visible": {
        "name": "GOES-East_ABI_Band02_Red_Visible_1km",
        "title": "GOES-East Visible (10 min)",
        "category": "geostationary",
        "description": "Near real-time visible imagery from GOES-East (10 min updates)",
    },
    "goes_west_visible": {
        "name": "GOES-West_ABI_Band02_Red_Visible_1km",
        "title": "GOES-West Visible (10 min)",
        "category": "geostationary",
        "description": "Near real-time visible imagery from GOES-West (10 min updates)",
    },
}

# Category descriptions for user help
LAYER_CATEGORIES = {
    "fire": "🔥 Fire & Thermal Anomalies - Active fire and heat detection",
    "imagery": "🛰️ True Color Imagery - Natural satellite views",
    "weather": "☁️ Weather - Clouds and precipitation",
    "temperature": "🌡️ Temperature - Surface and air temperature",
    "ocean": "🌊 Ocean - Sea surface temperature and chlorophyll",
    "cryosphere": "❄️ Cryosphere - Snow and ice coverage",
    "vegetation": "🌿 Vegetation - Plant health and coverage",
    "atmosphere": "💨 Atmosphere - Aerosols and air quality",
    "night": "🌙 Nighttime - City lights and night imagery",
    "geostationary": "📡 Geostationary - Frequent updates (10 min)",
}


def geocode_location_to_bbox(location: str) -> Optional[dict]:
    """Geocode a location name to a bounding box using Nominatim."""
    try:
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            "q": location,
            "format": "json",
            "limit": 1,
        }
        headers = {"User-Agent": "NaLaMap-OSINT/1.0"}

        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()

        data = response.json()
        if not data:
            return None

        result = data[0]
        boundingbox = result.get("boundingbox")
        if boundingbox and len(boundingbox) == 4:
            return {
                "south": float(boundingbox[0]),
                "north": float(boundingbox[1]),
                "west": float(boundingbox[2]),
                "east": float(boundingbox[3]),
            }
        return None
    except Exception as e:
        logger.error(f"Geocoding error: {e}")
        return None


@tool
def get_nasa_gibs_layer(
    location: Annotated[
        str,
        "Location name to center the view on. Examples: 'California', 'Mediterranean', 'Amazon'",
    ],
    layer_id: Annotated[
        str,
        "Layer identifier. Use 'list' to see available layers. "
        "Examples: 'viirs_snpp_fire_day', 'modis_terra_truecolor', 'sst_mur'",
    ] = "list",
    category: Annotated[
        str,
        "Filter layers by category: 'fire', 'imagery', 'weather', 'temperature', 'ocean', "
        "'cryosphere', 'vegetation', 'atmosphere', 'night', 'geostationary', or 'all'",
    ] = "all",
    state: Annotated[GeoDataAgentState, InjectedState] = None,
    tool_call_id: Annotated[str, InjectedToolCallId] = None,
) -> Command[Any]:
    """
    Access NASA GIBS satellite imagery layers for visualization.

    NASA Global Imagery Browse Services (GIBS) provides access to over 1000 satellite
    data products for visualization. This tool adds WMS layers to the map.

    Use for:
    * **Fire monitoring**: "Show VIIRS fire detections for California"
    * **True color imagery**: "Add satellite imagery for the Amazon"
    * **Weather visualization**: "Display cloud cover over Europe"
    * **Ocean monitoring**: "Show sea surface temperature for the Gulf Stream"
    * **Snow/ice tracking**: "Add snow cover layer for the Alps"

    First call with layer_id='list' to see available layers, then select one.
    """
    try:
        logger.info(
            f"NASA GIBS request: location={location}, layer={layer_id}, "
            f"category={category}"
        )

        # If user wants to list available layers
        if layer_id == "list" or layer_id == "help":
            response_lines = ["🛰️ **NASA GIBS Available Layers**", ""]

            # Group layers by category
            layers_by_category = {}
            for lid, info in NASA_GIBS_LAYERS.items():
                cat = info["category"]
                if category != "all" and cat != category:
                    continue
                if cat not in layers_by_category:
                    layers_by_category[cat] = []
                layers_by_category[cat].append((lid, info))

            if not layers_by_category:
                response_lines.append(f"No layers found for category: {category}")
                response_lines.append("")
                response_lines.append("Available categories: " + ", ".join(LAYER_CATEGORIES.keys()))
            else:
                for cat, layers in sorted(layers_by_category.items()):
                    response_lines.append(f"**{LAYER_CATEGORIES.get(cat, cat)}**")
                    for lid, info in layers:
                        response_lines.append(f"  • `{lid}`: {info['title']}")
                    response_lines.append("")

            response_lines.extend([
                "---",
                "**Usage:** Call again with a specific `layer_id` to add it to the map.",
                f"**Example:** get_nasa_gibs_layer(location='{location}', "
                f"layer_id='viirs_snpp_fire_day')",
            ])

            return Command(
                update={
                    "messages": [
                        ToolMessage(content="\n".join(response_lines), tool_call_id=tool_call_id)
                    ]
                }
            )

        # Validate layer_id
        if layer_id not in NASA_GIBS_LAYERS:
            suggestions = [lid for lid in NASA_GIBS_LAYERS if layer_id.lower() in lid.lower()]
            msg = f"Layer '{layer_id}' not found."
            if suggestions:
                msg += f" Did you mean: {', '.join(suggestions[:3])}?"
            msg += " Use layer_id='list' to see all available layers."

            return Command(
                update={"messages": [ToolMessage(content=msg, tool_call_id=tool_call_id)]}
            )

        layer_info = NASA_GIBS_LAYERS[layer_id]
        layer_name = layer_info["name"]

        # Geocode location
        bbox_data = geocode_location_to_bbox(location)
        if not bbox_data:
            return Command(
                update={
                    "messages": [
                        ToolMessage(
                            content=f"Could not find location: {location}. Try a different name.",
                            tool_call_id=tool_call_id,
                        )
                    ]
                }
            )

        # Create WMS URL template
        wms_url = (
            f"{NASA_GIBS_WMS_BASE}?"
            f"service=WMS&request=GetMap&version=1.1.1&"
            f"layers={layer_name}&"
            f"styles=&format=image/png&transparent=true&"
            f"srs=EPSG:3857&width=256&height=256&"
            f"BBOX={{bbox-epsg-3857}}"
        )

        # Create bounding box WKT
        bounding_box = (
            f"POLYGON(({bbox_data['east']} {bbox_data['south']},"
            f"{bbox_data['east']} {bbox_data['north']},"
            f"{bbox_data['west']} {bbox_data['north']},"
            f"{bbox_data['west']} {bbox_data['south']},"
            f"{bbox_data['east']} {bbox_data['south']}))"
        )

        # Create unique ID
        unique_id = str(uuid.uuid4())[:8]

        # Get category emoji
        cat_emoji = {
            "fire": "🔥", "imagery": "🛰️", "weather": "☁️",
            "temperature": "🌡️", "ocean": "🌊", "cryosphere": "❄️",
            "vegetation": "🌿", "atmosphere": "💨", "night": "🌙",
            "geostationary": "📡"
        }.get(layer_info["category"], "🗺️")

        # Create GeoDataObject
        geo_obj = GeoDataObject(
            id=f"gibs_{layer_id}_{unique_id}",
            data_source_id="nasaGibs",
            name=f"gibs_{layer_id}_{location.replace(' ', '_').lower()}",
            title=f"{layer_info['title']} - {location}",
            description=layer_info["description"],
            llm_description=(
                f"NASA GIBS WMS layer: {layer_info['title']} for {location}. "
                f"{layer_info['description']}"
            ),
            data_origin=DataOrigin.TOOL,
            data_source="NASA GIBS",
            data_type=DataType.LAYER,
            data_link=wms_url,
            layer_type="WMS",
            bounding_box=bounding_box,
        )

        # Format response
        response_lines = [
            f"{cat_emoji} **NASA GIBS Layer Added: {layer_info['title']}**",
            "",
            f"**Location:** {location}",
            f"**Layer:** {layer_info['title']}",
            f"**Category:** {LAYER_CATEGORIES.get(layer_info['category'], layer_info['category'])}",
            "",
            "**Description:**",
            f"  {layer_info['description']}",
            "",
            "🗺️ The layer has been added to the map.",
            "",
            "💡 **Tips:**",
            "- Zoom in for more detail",
            "- Layer updates automatically with latest satellite data",
            "- Toggle layer visibility in the layer panel",
        ]

        result_msg = ToolMessage(
            content="\n".join(response_lines),
            tool_call_id=tool_call_id
        )
        return Command(
            update={
                "geodata_results": [geo_obj],
                "messages": [result_msg],
            }
        )

    except Exception as e:
        logger.exception(f"Error in NASA GIBS layer tool: {e}")
        err_msg = ToolMessage(
            content=f"Error adding GIBS layer: {str(e)}",
            tool_call_id=tool_call_id
        )
        return Command(
            update={"messages": [err_msg]}
        )


@tool
def list_nasa_gibs_layers(
    category: Annotated[
        str,
        "Filter by category: 'fire', 'imagery', 'weather', 'temperature', 'ocean', "
        "'cryosphere', 'vegetation', 'atmosphere', 'night', 'geostationary', or 'all'",
    ] = "all",
    state: Annotated[GeoDataAgentState, InjectedState] = None,
    tool_call_id: Annotated[str, InjectedToolCallId] = None,
) -> Command[Any]:
    """
    List all available NASA GIBS satellite imagery layers.

    Use this to discover what visualization layers are available before adding them.
    Layers are organized into categories for easy browsing.
    """
    try:
        response_lines = ["🛰️ **NASA GIBS Available Imagery Layers**", ""]

        # Group layers by category
        layers_by_category = {}
        for lid, info in NASA_GIBS_LAYERS.items():
            cat = info["category"]
            if category != "all" and cat != category:
                continue
            if cat not in layers_by_category:
                layers_by_category[cat] = []
            layers_by_category[cat].append((lid, info))

        if not layers_by_category:
            response_lines.append(f"No layers found for category: {category}")
            response_lines.append("")
            response_lines.append("**Available categories:**")
            for cat, desc in LAYER_CATEGORIES.items():
                response_lines.append(f"  • {cat}: {desc}")
        else:
            category_order = [
                "fire", "imagery", "weather", "temperature", "ocean",
                "cryosphere", "vegetation", "atmosphere", "night", "geostationary"
            ]
            for cat in category_order:
                if cat not in layers_by_category:
                    continue
                response_lines.append(f"**{LAYER_CATEGORIES.get(cat, cat)}**")
                for lid, info in layers_by_category[cat]:
                    response_lines.append(f"  • `{lid}`: {info['title']}")
                response_lines.append("")

        response_lines.extend([
            "---",
            "**To add a layer to the map:**",
            "Use `get_nasa_gibs_layer(location='YOUR_LOCATION', layer_id='LAYER_ID')`",
            "",
            f"**Total layers available:** {len(NASA_GIBS_LAYERS)}",
        ])

        result_msg = ToolMessage(
            content="\n".join(response_lines),
            tool_call_id=tool_call_id
        )
        return Command(
            update={"messages": [result_msg]}
        )

    except Exception as e:
        logger.exception(f"Error listing NASA GIBS layers: {e}")
        err_msg = ToolMessage(
            content=f"Error listing layers: {str(e)}",
            tool_call_id=tool_call_id
        )
        return Command(
            update={"messages": [err_msg]}
        )
