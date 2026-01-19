"""
NASA FIRMS Fire Data Tool for OSINT

This tool provides access to active fire and thermal anomaly data from NASA's
Fire Information for Resource Management System (FIRMS).

Data Source:
- NASA FIRMS API: https://firms.modaps.eosdis.nasa.gov/api/
- Satellites: MODIS (Terra/Aqua), VIIRS (SNPP, NOAA-20, NOAA-21)
- Coverage: Global, near real-time (within 3 hours of observation)
- Resolution: MODIS ~1km, VIIRS ~375m

Use Cases:
- Wildfire monitoring and tracking
- Agricultural burning detection
- Deforestation monitoring
- Environmental hazard assessment
- Crisis response support

Note:
- Requires free MAP_KEY from NASA EARTHDATA
- Register at: https://firms.modaps.eosdis.nasa.gov/api/map_key/
- Set NASA_FIRMS_MAP_KEY environment variable
"""

import hashlib
import json
import logging
import os
from datetime import datetime
from io import StringIO
from typing import Any, Dict, List, Optional

import requests
from langchain_core.messages import ToolMessage
from langchain_core.tools import tool
from langchain_core.tools.base import InjectedToolCallId
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from typing_extensions import Annotated

from models.geodata import DataOrigin, DataType, GeoDataObject
from models.states import GeoDataAgentState
from services.storage.file_management import store_file

logger = logging.getLogger(__name__)

# NASA FIRMS API configuration
NASA_FIRMS_API_BASE = "https://firms.modaps.eosdis.nasa.gov/api/area"
NASA_FIRMS_MAP_KEY = os.environ.get("NASA_FIRMS_MAP_KEY", "")

# Available data sources
FIRMS_SOURCES = {
    "viirs_snpp": "VIIRS_SNPP_NRT",  # VIIRS Suomi-NPP Near Real-Time
    "viirs_noaa20": "VIIRS_NOAA20_NRT",  # VIIRS NOAA-20 NRT
    "viirs_noaa21": "VIIRS_NOAA21_NRT",  # VIIRS NOAA-21 NRT
    "modis": "MODIS_NRT",  # MODIS Near Real-Time
    "modis_sp": "MODIS_SP",  # MODIS Standard Processing
}

# Default source (best resolution for global coverage)
DEFAULT_SOURCE = "VIIRS_SNPP_NRT"

# Fire confidence levels
CONFIDENCE_LEVELS = {
    "low": "l",
    "nominal": "n",
    "high": "h",
}


def geocode_location_to_bbox(location: str) -> Optional[Dict[str, float]]:
    """
    Geocode a location name to a bounding box using Nominatim.

    Args:
        location: Place name (country, region, city)

    Returns:
        Dictionary with west, south, east, north coordinates or None
    """
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
            logger.warning(f"Could not geocode location: {location}")
            return None

        result = data[0]
        bbox = result.get("boundingbox", [])

        if len(bbox) >= 4:
            return {
                "south": float(bbox[0]),
                "north": float(bbox[1]),
                "west": float(bbox[2]),
                "east": float(bbox[3]),
            }
        return None

    except Exception as e:
        logger.error(f"Geocoding error for {location}: {e}")
        return None


def fetch_firms_data(
    bbox: Dict[str, float],
    source: str = DEFAULT_SOURCE,
    days_back: int = 1,
) -> Optional[List[Dict[str, Any]]]:
    """
    Fetch fire data from NASA FIRMS API.

    Args:
        bbox: Bounding box with west, south, east, north
        source: Data source (VIIRS_SNPP_NRT, MODIS_NRT, etc.)
        days_back: Number of days to query (1-10)

    Returns:
        List of fire detection records or None on failure
    """
    if not NASA_FIRMS_MAP_KEY:
        logger.error(
            "NASA_FIRMS_MAP_KEY not set. Register at: "
            "https://firms.modaps.eosdis.nasa.gov/api/map_key/"
        )
        return None

    # Constrain days_back to API limits
    days_back = max(1, min(days_back, 10))

    # Build area coordinates string: west,south,east,north
    area_coords = f"{bbox['west']},{bbox['south']},{bbox['east']},{bbox['north']}"

    # Build URL
    url = f"{NASA_FIRMS_API_BASE}/csv/{NASA_FIRMS_MAP_KEY}/{source}/{area_coords}/{days_back}"

    try:
        logger.info(f"Fetching FIRMS data: {source}, bbox={area_coords}, days={days_back}")
        response = requests.get(url, timeout=60)

        # Check for API key errors
        if response.status_code == 401:
            logger.error("Invalid NASA FIRMS MAP_KEY")
            return None
        elif response.status_code == 403:
            logger.error("NASA FIRMS API access denied - check MAP_KEY permissions")
            return None
        elif response.status_code == 429:
            logger.error("NASA FIRMS API rate limit exceeded")
            return None

        response.raise_for_status()

        # Parse CSV response
        import csv

        csv_data = StringIO(response.text)
        reader = csv.DictReader(csv_data)
        records = list(reader)

        logger.info(f"Retrieved {len(records)} fire detections")
        return records

    except requests.exceptions.Timeout:
        logger.error("NASA FIRMS API request timed out")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"NASA FIRMS API request failed: {e}")
        return None


def fire_data_to_geojson(
    records: List[Dict[str, Any]],
    min_confidence: str = "nominal",
) -> Dict[str, Any]:
    """
    Convert FIRMS fire records to GeoJSON format.

    Args:
        records: List of fire detection records from FIRMS API
        min_confidence: Minimum confidence level to include (low, nominal, high)

    Returns:
        GeoJSON FeatureCollection
    """
    confidence_order = ["l", "n", "h"]
    min_conf_index = confidence_order.index(CONFIDENCE_LEVELS.get(min_confidence, "n"))

    features = []
    stats = {
        "total_detections": 0,
        "high_confidence": 0,
        "nominal_confidence": 0,
        "low_confidence": 0,
        "total_frp": 0.0,
        "dates": set(),
        "detections_by_intensity": {
            "intense": 0,
            "moderate": 0,
            "low": 0,
            "anomaly": 0,
        },
    }

    for record in records:
        try:
            # Get confidence level
            confidence = record.get("confidence", "n").lower()
            if confidence not in confidence_order:
                confidence = "n"

            # Skip if below minimum confidence
            if confidence_order.index(confidence) < min_conf_index:
                continue

            # Parse coordinates
            lat = float(record.get("latitude", 0))
            lon = float(record.get("longitude", 0))

            if lat == 0 and lon == 0:
                continue

            # Parse fire attributes
            frp = float(record.get("frp", 0))
            brightness = float(record.get("bright_ti4", record.get("brightness", 0)))
            acq_date = record.get("acq_date", "")
            acq_time = record.get("acq_time", "")
            daynight = record.get("daynight", "D")
            satellite = record.get("satellite", record.get("instrument", "Unknown"))

            # Update statistics
            stats["total_detections"] += 1
            stats["total_frp"] += frp
            if acq_date:
                stats["dates"].add(acq_date)

            if confidence == "h":
                stats["high_confidence"] += 1
            elif confidence == "n":
                stats["nominal_confidence"] += 1
            else:
                stats["low_confidence"] += 1

            # Determine marker color based on FRP
            if frp >= 100:
                color = "#FF0000"  # Red - intense fire
                intensity = "intense"
            elif frp >= 50:
                color = "#FF6600"  # Orange - moderate fire
                intensity = "moderate"
            elif frp >= 10:
                color = "#FFCC00"  # Yellow - low intensity
                intensity = "low"
            else:
                color = "#FF9999"  # Light red - thermal anomaly
                intensity = "anomaly"

            stats["detections_by_intensity"][intensity] += 1

            feature = {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": {
                    "date": acq_date,
                    "time": acq_time,
                    "confidence": confidence,
                    "confidence_label": (
                        "high" if confidence == "h" else ("nominal" if confidence == "n" else "low")
                    ),
                    "frp": frp,
                    "frp_label": f"{frp:.1f} MW",
                    "brightness": brightness,
                    "daynight": "Day" if daynight == "D" else "Night",
                    "satellite": satellite,
                    "intensity": intensity,
                    "marker-color": color,
                    "source": "NASA FIRMS",
                },
            }
            features.append(feature)

        except (ValueError, KeyError) as e:
            logger.warning(f"Error parsing fire record: {e}")
            continue

    # Convert dates set to sorted list
    stats["dates"] = sorted(list(stats["dates"]))
    stats["date_range"] = f"{stats['dates'][0]} to {stats['dates'][-1]}" if stats["dates"] else ""
    stats["total_frp_mw"] = stats["total_frp"]

    return {
        "type": "FeatureCollection",
        "features": features,
        "properties": {
            "source": "NASA FIRMS",
            "total_detections": stats["total_detections"],
            "statistics": stats,
        },
    }


@tool
def get_nasa_fire_data(
    location: Annotated[
        str,
        "Location to search for fires. Can be a country name, region, or "
        "city. Examples: 'California', 'Amazon rainforest', 'Australia', 'Greece'",
    ],
    days_back: Annotated[
        int,
        "Number of days to look back (1-10). Default is 3 days.",
    ] = 3,
    source: Annotated[
        str,
        "Satellite data source. Options: 'viirs_snpp' (default, best resolution), "
        "'viirs_noaa20', 'viirs_noaa21', 'modis'. Default is viirs_snpp.",
    ] = "viirs_snpp",
    min_confidence: Annotated[
        str,
        "Minimum confidence level to include: 'low', 'nominal' (default), 'high'. "
        "Higher confidence means more certain fire detection.",
    ] = "nominal",
    state: Annotated[GeoDataAgentState, InjectedState] = None,
    tool_call_id: Annotated[str, InjectedToolCallId] = None,
) -> Command[Any]:
    """
    Retrieve active fire and thermal anomaly data from NASA FIRMS.

    NASA FIRMS provides near real-time satellite fire detection data from
    MODIS and VIIRS instruments with global coverage.

    Use for:
    * **Wildfire monitoring**: "Show active fires in California"
    * **Agricultural burning**: "Detect fires in Southeast Asia"
    * **Deforestation tracking**: "Fire activity in Amazon region"
    * **Disaster response**: "Current fire situation in Greece"

    Returns:
    * Map visualization with fire hotspots
    * Fire intensity based on Fire Radiative Power (FRP)
    * Confidence levels for each detection
    * Summary statistics

    Note: Requires NASA EARTHDATA MAP_KEY. Register free at:
    https://firms.modaps.eosdis.nasa.gov/api/map_key/
    """
    try:
        # Check for API key
        if not NASA_FIRMS_MAP_KEY:
            return Command(
                update={
                    "messages": [
                        ToolMessage(
                            content=(
                                "❌ NASA FIRMS API key not configured.\n\n"
                                "To use fire detection data:\n"
                                "1. Register for free at: "
                                "https://firms.modaps.eosdis.nasa.gov/api/map_key/\n"
                                "2. Set the NASA_FIRMS_MAP_KEY environment variable"
                            ),
                            tool_call_id=tool_call_id,
                        )
                    ]
                }
            )

        # Validate parameters
        days_back = max(1, min(days_back, 10))

        # Map source name to API source
        api_source = FIRMS_SOURCES.get(source.lower(), DEFAULT_SOURCE)

        logger.info(f"Fetching NASA FIRMS fire data for {location}, days_back={days_back}")

        # Geocode location to bounding box
        bbox = geocode_location_to_bbox(location)
        if not bbox:
            return Command(
                update={
                    "messages": [
                        ToolMessage(
                            content=(
                                f"Could not find location: {location}. "
                                "Please try a more specific place name."
                            ),
                            tool_call_id=tool_call_id,
                        )
                    ]
                }
            )

        # Fetch fire data
        records = fetch_firms_data(
            bbox=bbox,
            source=api_source,
            days_back=days_back,
        )

        if records is None:
            return Command(
                update={
                    "messages": [
                        ToolMessage(
                            content=(
                                f"Failed to retrieve fire data for {location}. "
                                "Please check your NASA FIRMS API key and try again."
                            ),
                            tool_call_id=tool_call_id,
                        )
                    ]
                }
            )

        if not records:
            return Command(
                update={
                    "messages": [
                        ToolMessage(
                            content=(
                                f"🔥 **No active fires detected in {location}**\n\n"
                                f"Searched the last {days_back} days using {api_source}.\n"
                                "This is good news! No fire activity was detected in the area."
                            ),
                            tool_call_id=tool_call_id,
                        )
                    ]
                }
            )

        # Convert to GeoJSON
        geojson = fire_data_to_geojson(records, min_confidence)
        statistics = geojson["properties"]["statistics"]

        if not geojson["features"]:
            return Command(
                update={
                    "messages": [
                        ToolMessage(
                            content=(
                                f"🔥 **No high-confidence fires detected in {location}**\n\n"
                                f"Found {len(records)} detections, but none met the "
                                f"'{min_confidence}' confidence threshold.\n"
                                "Try lowering min_confidence to 'low' to see more results."
                            ),
                            tool_call_id=tool_call_id,
                        )
                    ]
                }
            )

        # Store GeoJSON file
        geojson_str = json.dumps(geojson)
        geojson_bytes = geojson_str.encode("utf-8")
        sha256_hex = hashlib.sha256(geojson_bytes).hexdigest()
        size_bytes = len(geojson_bytes)

        # Calculate bounding box from fire points
        lons = [f["geometry"]["coordinates"][0] for f in geojson["features"]]
        lats = [f["geometry"]["coordinates"][1] for f in geojson["features"]]
        lat_min, lat_max = min(lats), max(lats)
        lon_min, lon_max = min(lons), max(lons)
        bounding_box = (
            f"POLYGON(({lon_max} {lat_min},"
            f"{lon_max} {lat_max},"
            f"{lon_min} {lat_max},"
            f"{lon_min} {lat_min},"
            f"{lon_max} {lat_min}))"
        )

        # Store file
        filename = f"fires_{location.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.geojson"
        file_url, unique_id = store_file(filename, geojson_bytes)

        geo_obj = GeoDataObject(
            id=unique_id,
            data_source_id="nasaFirms",
            name=f"fires_{location.replace(' ', '_').lower()}",
            title=f"Active Fires - {location}",
            description=(
                f"NASA FIRMS fire detections for {location} "
                f"({statistics['date_range']}). "
                f"{statistics['total_detections']} fire hotspots detected."
            ),
            llm_description=(
                f"Fire detection data showing {statistics['total_detections']} "
                f"active fires/thermal anomalies in {location}. "
                f"Data from NASA FIRMS {api_source}."
            ),
            data_origin=DataOrigin.TOOL,
            data_source="NASA FIRMS",
            data_type=DataType.GEOJSON,
            layer_type="point",
            data_link=file_url,
            bounding_box=bounding_box,
            sha256=sha256_hex,
            size=size_bytes,
        )

        # Format response text
        response_lines = [
            f"🔥 **NASA FIRMS Fire Data for {location}**",
            f"📅 Period: Last {days_back} days ({statistics['date_range']})",
            f"🛰️ Source: {api_source}",
            "",
            "**Summary:**",
            f"  • Total Fire Detections: {statistics['total_detections']:,}",
            f"  • Total Fire Radiative Power: {statistics['total_frp_mw']:,.1f} MW",
            "",
            "**By Confidence Level:**",
            f"  • High Confidence: {statistics['high_confidence']:,}",
            f"  • Nominal Confidence: {statistics['nominal_confidence']:,}",
            f"  • Low Confidence: {statistics['low_confidence']:,}",
        ]

        # Add intensity breakdown
        intensity_data = statistics.get("detections_by_intensity", {})
        if intensity_data:
            response_lines.extend(["", "**By Fire Intensity:**"])
            intensity_labels = {
                "intense": "🔴 Intense (FRP ≥100 MW)",
                "moderate": "🟠 Moderate (FRP 50-100 MW)",
                "low": "🟡 Low (FRP 10-50 MW)",
                "anomaly": "⚪ Thermal Anomaly (FRP <10 MW)",
            }
            for intensity, label in intensity_labels.items():
                count = intensity_data.get(intensity, 0)
                if count > 0:
                    response_lines.append(f"  • {label}: {count:,}")

        response_lines.extend(
            [
                "",
                "🗺️ Fire hotspots have been added to the map.",
                "",
                "💡 **Tips:**",
                "- Red markers indicate intense fires",
                "- Orange/yellow markers indicate moderate activity",
                "- Use with weather data to assess fire risk conditions",
            ]
        )

        response_text = "\n".join(response_lines)

        return Command(
            update={
                "geodata_results": [geo_obj],
                "messages": [ToolMessage(content=response_text, tool_call_id=tool_call_id)],
            }
        )

    except Exception as e:
        logger.exception(f"Error in NASA FIRMS fire data tool: {e}")
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content=f"Error retrieving fire data: {str(e)}",
                        tool_call_id=tool_call_id,
                    )
                ]
            }
        )
