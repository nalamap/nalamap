"""
ECMWF Weather Data Tool for OSINT

This tool provides access to weather and climate data from ECMWF-style sources.
Uses Open-Meteo API as the primary data source (free, no authentication).

Data Sources:
- Open-Meteo Historical Weather API (uses ERA5 reanalysis)
- Open-Meteo Forecast API (uses ECMWF IFS model)
- Coverage: Global, ~30km resolution
- Historical data: 1940-present
- Forecast: Up to 16 days ahead

Use Cases:
- Historical weather analysis for specific locations/events
- Weather forecasts for planning and risk assessment
- Climate pattern analysis for OSINT
- Correlating weather with events/incidents
"""

import hashlib
import json
import logging
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

# Check if ECMWF packages are available for enhanced functionality
try:
    from ecmwf.opendata import Client as ECMWFClient  # noqa: F401
    import xarray  # noqa: F401
    import cfgrib  # noqa: F401

    ECMWF_AVAILABLE = True
except ImportError:
    ECMWF_AVAILABLE = False
    logger.info(
        "ECMWF Open Data packages not available. Using Open-Meteo API. "
        "For ECMWF data, install: poetry add ecmwf-opendata cfgrib xarray"
    )

# Map of friendly variable names to API parameter names
WEATHER_VARIABLES = {
    "temperature": {
        "cds_name": "2m_temperature",
        "ecmwf_open_name": "2t",
        "open_meteo_archive_name": "temperature_2m_mean",
        "open_meteo_forecast_name": ["temperature_2m_max", "temperature_2m_min"],
        "unit": "°C",
        "description": "Air temperature at 2 meters above surface",
        "forecast_available": True,
    },
    "precipitation": {
        "cds_name": "total_precipitation",
        "ecmwf_open_name": "tp",
        "open_meteo_archive_name": "precipitation_sum",
        "open_meteo_forecast_name": "precipitation_sum",
        "unit": "mm",
        "description": "Total precipitation (rain and snow)",
        "forecast_available": True,
    },
    "wind_speed": {
        "cds_name": ["10m_u_component_of_wind", "10m_v_component_of_wind"],
        "ecmwf_open_name": ["10u", "10v"],
        "open_meteo_archive_name": "wind_speed_10m_mean",
        "open_meteo_forecast_name": "wind_speed_10m_max",
        "unit": "m/s",
        "description": "Wind speed at 10 meters above surface",
        "forecast_available": True,
    },
    "pressure": {
        "cds_name": "surface_pressure",
        "ecmwf_open_name": "sp",
        "open_meteo_archive_name": "pressure_msl_mean",
        "open_meteo_forecast_name": "pressure_msl",
        "unit": "hPa",
        "description": "Surface atmospheric pressure",
        "forecast_available": True,
    },
    "humidity": {
        "cds_name": "2m_dewpoint_temperature",
        "ecmwf_open_name": "2d",
        "open_meteo_archive_name": "relative_humidity_2m_mean",
        "open_meteo_forecast_name": "relative_humidity_2m_mean",
        "unit": "%",
        "description": "Relative humidity at 2 meters",
        "forecast_available": True,
    },
    "cloud_cover": {
        "cds_name": "total_cloud_cover",
        "ecmwf_open_name": "tcc",
        "open_meteo_archive_name": "cloud_cover_mean",
        "open_meteo_forecast_name": "cloud_cover_mean",
        "unit": "%",
        "description": "Total cloud cover",
        "forecast_available": True,
    },
}


def geocode_location(location: str) -> Optional[Dict[str, float]]:
    """
    Geocode a location string to coordinates.

    Args:
        location: Location name or "lat,lon" string

    Returns:
        Dictionary with 'lat' and 'lon' keys, or None
    """
    # Check if already coordinates
    if "," in location:
        try:
            parts = location.split(",")
            lat = float(parts[0].strip())
            lon = float(parts[1].strip())
            return {"lat": lat, "lon": lon}
        except (ValueError, IndexError):
            pass

    # Use Nominatim geocoding
    try:
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            "q": location,
            "format": "json",
            "limit": 1,
        }
        headers = {"User-Agent": "NaLaMap-Weather/1.0"}

        response = requests.get(url, params=params, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()

        if data:
            return {
                "lat": float(data[0]["lat"]),
                "lon": float(data[0]["lon"]),
            }

    except Exception as e:
        logger.error(f"Geocoding failed for {location}: {e}")

    return None


def get_weather_data_simple(
    latitude: float,
    longitude: float,
    start_date: str,
    end_date: str,
    variables: List[str],
) -> Optional[Dict[str, Any]]:
    """
    Fetch historical weather data from Open-Meteo Archive API.

    Args:
        latitude: Latitude in decimal degrees
        longitude: Longitude in decimal degrees
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        variables: List of variable names to retrieve

    Returns:
        Dictionary with weather data or None on failure
    """
    # Build parameter list for ARCHIVE API
    params = []
    for var in variables:
        if var in WEATHER_VARIABLES:
            params.append(WEATHER_VARIABLES[var]["open_meteo_archive_name"])

    if not params:
        params = ["temperature_2m_mean", "precipitation_sum"]  # Default for archive

    # Construct API URL
    url = "https://archive-api.open-meteo.com/v1/archive"
    query_params = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": start_date,
        "end_date": end_date,
        "daily": ",".join(params),
        "timezone": "UTC",
    }

    try:
        response = requests.get(url, params=query_params, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Failed to fetch weather data: {e}")
        return None


def get_forecast_data(
    latitude: float,
    longitude: float,
    forecast_days: int,
    variables: List[str],
) -> Optional[Dict[str, Any]]:
    """
    Fetch weather forecast data from Open-Meteo Forecast API.

    Args:
        latitude: Latitude in decimal degrees
        longitude: Longitude in decimal degrees
        forecast_days: Number of days to forecast (1-16)
        variables: List of variable names to retrieve

    Returns:
        Dictionary with forecast data or None on failure
    """
    # Build parameter list for FORECAST API (different names!)
    params = []
    for var in variables:
        if var in WEATHER_VARIABLES:
            forecast_name = WEATHER_VARIABLES[var]["open_meteo_forecast_name"]
            if isinstance(forecast_name, list):
                params.extend(forecast_name)
            else:
                params.append(forecast_name)

    if not params:
        params = ["temperature_2m_max", "temperature_2m_min", "precipitation_sum"]

    # Construct API URL for forecast
    url = "https://api.open-meteo.com/v1/forecast"
    query_params = {
        "latitude": latitude,
        "longitude": longitude,
        "daily": ",".join(params),
        "forecast_days": max(1, min(forecast_days, 16)),
        "timezone": "UTC",
    }

    try:
        response = requests.get(url, params=query_params, timeout=30)
        response.raise_for_status()
        data = response.json()

        # Trim to requested number of days if needed
        if "daily" in data and "time" in data["daily"]:
            max_days = forecast_days
            for key in data["daily"]:
                if isinstance(data["daily"][key], list):
                    data["daily"][key] = data["daily"][key][:max_days]

        return data
    except Exception as e:
        logger.error(f"Failed to fetch forecast data: {e}")
        return None


def calculate_weather_statistics(weather_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate statistical summaries from weather data.

    Args:
        weather_data: Raw weather data from API

    Returns:
        Dictionary with statistics per variable
    """
    stats = {}
    daily = weather_data.get("daily", {})

    for key, values in daily.items():
        if key == "time" or not values:
            continue

        # Filter out None values
        valid_values = [v for v in values if v is not None]
        if not valid_values:
            continue

        stats[key] = {
            "mean": sum(valid_values) / len(valid_values),
            "min": min(valid_values),
            "max": max(valid_values),
            "total": sum(valid_values) if "precipitation" in key.lower() else None,
            "count": len(valid_values),
        }

    return stats


def create_weather_geojson(
    latitude: float,
    longitude: float,
    location_name: str,
    weather_data: Dict[str, Any],
    statistics: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Create GeoJSON representation of weather data.

    Args:
        latitude: Latitude
        longitude: Longitude
        location_name: Human-readable location name
        weather_data: Raw weather data
        statistics: Calculated statistics

    Returns:
        GeoJSON FeatureCollection
    """
    # Build properties from statistics
    properties = {
        "location": location_name,
        "latitude": latitude,
        "longitude": longitude,
    }

    for key, stat in statistics.items():
        # Clean up key name for display
        display_key = key.replace("_", " ").title()
        properties[f"{display_key} (Mean)"] = round(stat["mean"], 1)
        properties[f"{display_key} (Min)"] = round(stat["min"], 1)
        properties[f"{display_key} (Max)"] = round(stat["max"], 1)
        if stat.get("total") is not None:
            properties[f"{display_key} (Total)"] = round(stat["total"], 1)

    feature = {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [longitude, latitude],
        },
        "properties": properties,
    }

    return {
        "type": "FeatureCollection",
        "features": [feature],
        "properties": {
            "source": "ECMWF-style Weather Data (Open-Meteo)",
            "location": location_name,
            "statistics": statistics,
            "daily_data": weather_data.get("daily", {}),
        },
    }


@tool
def get_ecmwf_weather_data(
    location: Annotated[str, "Location name or 'lat,lon' coordinates"],
    start_date: Annotated[
        Optional[str],
        "Start date in YYYY-MM-DD format (e.g., '2024-01-01') for historical data. "
        "Leave empty for forecast mode. Must be in the past for historical data.",
    ] = None,
    end_date: Annotated[
        Optional[str],
        "End date in YYYY-MM-DD format (e.g., '2024-01-31') for historical data. "
        "Leave empty for forecast mode. Should be after start_date.",
    ] = None,
    forecast_days: Annotated[
        Optional[int],
        "Number of days to forecast (1-15). Use this for weather predictions. "
        "Leave empty for historical data mode.",
    ] = None,
    variables: Annotated[
        Optional[List[str]],
        "List of weather variables to retrieve. Options: "
        "'temperature', 'precipitation', 'wind_speed', 'pressure', 'humidity', 'cloud_cover'. "
        "If not specified, returns temperature and precipitation.",
    ] = None,
    state: Annotated[GeoDataAgentState, InjectedState] = None,
    tool_call_id: Annotated[str, InjectedToolCallId] = None,
) -> Command[Any]:
    """
    Retrieve weather data (historical or forecast) from ECMWF-style sources.

    **TWO MODES:**
    1. **Historical Mode**: Provide start_date and end_date to get past weather conditions
    2. **Forecast Mode**: Provide forecast_days to get future weather predictions

    Use for: OSINT analysis, operations planning, event analysis, and risk assessment.

    Strengths:
    * Historical data from reliable reanalysis datasets (1940-present)
    * Weather forecasts up to 15 days ahead
    * Global coverage with consistent quality
    * Multiple weather variables available
    * Returns both statistical summaries and map visualization

    Limitations:
    * Grid-based data (~30km resolution) - not hyper-local
    * Forecast accuracy decreases beyond 7 days
    * May have rate limits for API requests

    Examples:
    * Historical: "What was the weather in Kyiv on February 24, 2022?"
    * Forecast: "What will the weather be in Somalia over the next 7 days?"
    """
    try:
        # Determine mode
        is_forecast_mode = forecast_days is not None and forecast_days > 0

        # Validate parameters
        if not is_forecast_mode and (not start_date or not end_date):
            return Command(
                update={
                    "messages": [
                        ToolMessage(
                            content=(
                                "Please specify either:\n"
                                "- `start_date` and `end_date` for historical data, or\n"
                                "- `forecast_days` for weather forecast"
                            ),
                            tool_call_id=tool_call_id,
                        )
                    ]
                }
            )

        # Default variables if not specified
        if not variables:
            variables = ["temperature", "precipitation"]

        # Geocode location
        coords = geocode_location(location)
        if coords is None:
            return Command(
                update={
                    "messages": [
                        ToolMessage(
                            content=f"Could not geocode location: {location}. Please provide a "
                            "valid place name or coordinates in 'lat,lon' format.",
                            tool_call_id=tool_call_id,
                        )
                    ]
                }
            )

        location_name = location

        # Fetch weather data based on mode
        if is_forecast_mode:
            logger.info(
                f"Fetching {forecast_days}-day forecast for {location_name} "
                f"({coords['lat']}, {coords['lon']})"
            )

            weather_data = get_forecast_data(
                coords["lat"], coords["lon"], forecast_days, variables
            )

            data_type_label = "Forecast"
            date_range_str = f"{forecast_days} days ahead"
        else:
            logger.info(
                f"Fetching historical weather data for {location_name} "
                f"({coords['lat']}, {coords['lon']}) from {start_date} to {end_date}"
            )
            weather_data = get_weather_data_simple(
                coords["lat"], coords["lon"], start_date, end_date, variables
            )
            data_type_label = "Historical Weather Data"
            date_range_str = f"{start_date} to {end_date}"

        if weather_data is None:
            return Command(
                update={
                    "messages": [
                        ToolMessage(
                            content=f"Failed to retrieve {data_type_label.lower()}. "
                            "Please check your parameters and try again.",
                            tool_call_id=tool_call_id,
                        )
                    ]
                }
            )

        # Calculate statistics
        statistics = calculate_weather_statistics(weather_data)

        # Create GeoJSON
        geojson_data = create_weather_geojson(
            coords["lat"], coords["lon"], location_name, weather_data, statistics
        )

        # Store GeoJSON file
        geojson_str = json.dumps(geojson_data, indent=2)
        content_bytes = geojson_str.encode()
        sha256_hex = hashlib.sha256(content_bytes).hexdigest()
        size_bytes = len(content_bytes)

        # Generate filename based on mode
        mode_prefix = "forecast" if is_forecast_mode else "historical"
        if is_forecast_mode:
            filename = (
                f"weather_{mode_prefix}_{location.replace(' ', '_')}_"
                f"{forecast_days}days_{sha256_hex[:8]}.geojson"
            )
        else:
            filename = (
                f"weather_{mode_prefix}_{location.replace(' ', '_')}_"
                f"{start_date}_{end_date}_{sha256_hex[:8]}.geojson"
            )

        url, unique_id = store_file(filename, content_bytes)

        # Create bounding box string in WKT format
        lat_min = coords["lat"] - 0.1
        lat_max = coords["lat"] + 0.1
        lon_min = coords["lon"] - 0.1
        lon_max = coords["lon"] + 0.1
        bounding_box = (
            f"POLYGON(({lon_max} {lat_min},"
            f"{lon_max} {lat_max},"
            f"{lon_min} {lat_max},"
            f"{lon_min} {lat_min},"
            f"{lon_max} {lat_min}))"
        )

        # Create GeoDataObject
        data_source_label = (
            "ECMWF-style Forecast (Open-Meteo)"
            if is_forecast_mode
            else "ECMWF-style Weather Data (Open-Meteo)"
        )

        geo_obj = GeoDataObject(
            id=unique_id,
            data_source_id="ecmwfWeather",
            name=filename,
            title=f"{data_type_label}: {location_name} ({date_range_str})",
            description=f"{data_type_label} for {location_name}: {date_range_str}. "
            f"Variables: {', '.join(variables)}",
            llm_description=(
                f"{'Forecast' if is_forecast_mode else 'Historical'} weather conditions at "
                f"{location_name} for {date_range_str}"
            ),
            data_type=DataType.GEOJSON,
            data_origin=DataOrigin.TOOL,
            data_source=data_source_label,
            data_link=url,
            layer_type="point",
            bounding_box=bounding_box,
            sha256=sha256_hex,
            size=size_bytes,
        )

        # Format statistics for human-readable response
        emoji = "🔮" if is_forecast_mode else "📊"
        summary_lines = [
            f"{emoji} **{data_type_label} for {location_name}**",
            f"📍 Coordinates: {coords['lat']:.4f}, {coords['lon']:.4f}",
            f"📅 Period: {date_range_str}",
            "",
        ]

        for key, stat in statistics.items():
            display_name = key.replace("_", " ").title()
            unit = ""

            # Determine unit based on variable
            if "temperature" in key.lower():
                unit = "°C"
            elif "precipitation" in key.lower():
                unit = "mm"
            elif "wind" in key.lower():
                unit = "m/s"
            elif "pressure" in key.lower():
                unit = "hPa"
            elif "humidity" in key.lower() or "cloud" in key.lower():
                unit = "%"

            summary_lines.append(f"**{display_name}:**")
            summary_lines.append(f"  • Mean: {stat['mean']:.1f}{unit}")
            summary_lines.append(f"  • Range: {stat['min']:.1f} - {stat['max']:.1f}{unit}")
            if stat.get("total") is not None:
                summary_lines.append(f"  • Total: {stat['total']:.1f}{unit}")
            summary_lines.append("")

        summary_lines.extend(
            [
                "🗺️ Weather point has been added to the map.",
                "",
                "💡 **Tips:**",
                "- Combine with event data for context analysis",
                "- Forecast accuracy is best within 7 days",
                "- Use historical mode to analyze past events",
            ]
        )

        response_text = "\n".join(summary_lines)

        return Command(
            update={
                "geodata_results": [geo_obj],
                "messages": [ToolMessage(content=response_text, tool_call_id=tool_call_id)],
            }
        )

    except Exception as e:
        logger.exception(f"Error in ECMWF weather tool: {e}")
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content=f"Error retrieving weather data: {str(e)}",
                        tool_call_id=tool_call_id,
                    )
                ]
            }
        )
