"""
World Bank Indicators Tool for OSINT

This tool provides access to economic and development indicators from the
World Bank's open data API.

Data Source:
- World Bank Indicators API v2: https://api.worldbank.org/v2/
- Coverage: 200+ countries, 16,000+ indicators
- Historical data: Many series from 1960s to present
- No authentication required

Use Cases:
- Economic analysis (GDP, inflation, trade)
- Development indicators (poverty, education, health)
- Infrastructure metrics (internet, electricity access)
- Governance and institutional quality
- Environmental indicators

Key Indicator Categories:
- Economic: GDP, GDP growth, inflation, unemployment
- Social: Poverty rate, life expectancy, literacy
- Infrastructure: Internet access, electricity, roads
- Governance: Control of corruption, rule of law
- Environment: CO2 emissions, forest coverage, renewable energy
"""

import hashlib
import json
import logging
from datetime import datetime
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

# World Bank API configuration
WORLD_BANK_API_BASE = "https://api.worldbank.org/v2"

# Common indicator codes organized by category
INDICATOR_CATEGORIES = {
    "economic": {
        "NY.GDP.MKTP.CD": "GDP (current US$)",
        "NY.GDP.MKTP.KD.ZG": "GDP growth (annual %)",
        "NY.GDP.PCAP.CD": "GDP per capita (current US$)",
        "FP.CPI.TOTL.ZG": "Inflation, consumer prices (annual %)",
        "SL.UEM.TOTL.ZS": "Unemployment, total (% of labor force)",
        "NE.TRD.GNFS.ZS": "Trade (% of GDP)",
        "BX.KLT.DINV.WD.GD.ZS": "Foreign direct investment (% of GDP)",
        "GC.DOD.TOTL.GD.ZS": "Central government debt (% of GDP)",
    },
    "social": {
        "SI.POV.DDAY": "Poverty headcount ratio at $2.15/day (%)",
        "SI.POV.GINI": "Gini index (income inequality)",
        "SP.DYN.LE00.IN": "Life expectancy at birth (years)",
        "SE.ADT.LITR.ZS": "Literacy rate, adult total (%)",
        "SE.XPD.TOTL.GD.ZS": "Education expenditure (% of GDP)",
        "SH.XPD.CHEX.GD.ZS": "Health expenditure (% of GDP)",
        "SP.POP.TOTL": "Population, total",
        "SP.URB.TOTL.IN.ZS": "Urban population (% of total)",
    },
    "infrastructure": {
        "IT.NET.USER.ZS": "Individuals using the Internet (%)",
        "IT.CEL.SETS.P2": "Mobile cellular subscriptions (per 100)",
        "EG.ELC.ACCS.ZS": "Access to electricity (%)",
        "IS.ROD.PAVE.ZS": "Paved roads (% of total roads)",
        "IS.AIR.PSGR": "Air transport, passengers carried",
    },
    "governance": {
        "CC.EST": "Control of Corruption (estimate)",
        "GE.EST": "Government Effectiveness (estimate)",
        "PV.EST": "Political Stability (estimate)",
        "RQ.EST": "Regulatory Quality (estimate)",
        "RL.EST": "Rule of Law (estimate)",
        "VA.EST": "Voice and Accountability (estimate)",
    },
    "environment": {
        "EN.ATM.CO2E.PC": "CO2 emissions (metric tons per capita)",
        "AG.LND.FRST.ZS": "Forest area (% of land area)",
        "EG.FEC.RNEW.ZS": "Renewable energy consumption (%)",
        "ER.H2O.FWTL.ZS": "Annual freshwater withdrawals (%)",
        "EN.ATM.PM25.MC.M3": "PM2.5 air pollution (micrograms/m3)",
    },
    "conflict_risk": {
        "VC.IHR.PSRC.P5": "Intentional homicides (per 100,000)",
        "SM.POP.REFG": "Refugee population by origin",
        "SM.POP.REFG.OR": "Refugee population by country of asylum",
        "VC.BTL.DETH": "Battle-related deaths",
        "MS.MIL.XPND.GD.ZS": "Military expenditure (% of GDP)",
    },
}

# Flattened indicator lookup
ALL_INDICATORS = {}
for category, indicators in INDICATOR_CATEGORIES.items():
    for code, name in indicators.items():
        ALL_INDICATORS[code] = {"name": name, "category": category}

# Country code mapping (common names to ISO codes)
COUNTRY_CODES = {
    "united states": "USA",
    "usa": "USA",
    "uk": "GBR",
    "united kingdom": "GBR",
    "china": "CHN",
    "india": "IND",
    "germany": "DEU",
    "france": "FRA",
    "japan": "JPN",
    "brazil": "BRA",
    "russia": "RUS",
    "south africa": "ZAF",
    "nigeria": "NGA",
    "egypt": "EGY",
    "mexico": "MEX",
    "indonesia": "IDN",
    "australia": "AUS",
    "canada": "CAN",
    "saudi arabia": "SAU",
    "turkey": "TUR",
    "iran": "IRN",
    "pakistan": "PAK",
    "ukraine": "UKR",
    "yemen": "YEM",
    "syria": "SYR",
    "iraq": "IRQ",
    "afghanistan": "AFG",
    "somalia": "SOM",
    "sudan": "SDN",
    "south sudan": "SSD",
    "ethiopia": "ETH",
    "kenya": "KEN",
    "tanzania": "TZA",
}


def get_country_code(country_name: str) -> str:
    """
    Convert country name to ISO 3166-1 alpha-3 code.

    Args:
        country_name: Country name

    Returns:
        ISO 3-letter country code
    """
    # Check if already a code
    if len(country_name) == 3 and country_name.isupper():
        return country_name

    # Check lookup table
    normalized = country_name.lower().strip()
    if normalized in COUNTRY_CODES:
        return COUNTRY_CODES[normalized]

    # Try to fetch from World Bank API
    try:
        url = f"{WORLD_BANK_API_BASE}/country"
        params = {"format": "json", "per_page": 300}
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()

        data = response.json()
        if len(data) >= 2:
            countries = data[1]
            for c in countries:
                if normalized in c.get("name", "").lower():
                    return c.get("id", country_name)

    except Exception as e:
        logger.warning(f"Failed to lookup country code: {e}")

    # Return original if no match found
    return country_name.upper()[:3]


def fetch_world_bank_indicator(
    country: str,
    indicator: str,
    start_year: Optional[int] = None,
    end_year: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """
    Fetch indicator data from World Bank API.

    Args:
        country: Country code (ISO 3-letter) or 'all' for all countries
        indicator: Indicator code (e.g., 'NY.GDP.MKTP.CD')
        start_year: Start year for data
        end_year: End year for data

    Returns:
        Dictionary with indicator data or None on failure
    """
    url = f"{WORLD_BANK_API_BASE}/country/{country}/indicator/{indicator}"

    params = {
        "format": "json",
        "per_page": 1000,
    }

    if start_year and end_year:
        params["date"] = f"{start_year}:{end_year}"
    elif start_year:
        params["date"] = f"{start_year}:{datetime.now().year}"

    try:
        response = requests.get(url, params=params, timeout=60)

        if response.status_code == 404:
            logger.warning(f"Indicator {indicator} not found for {country}")
            return None

        response.raise_for_status()

        data = response.json()

        # World Bank API returns [metadata, data]
        if len(data) < 2 or not data[1]:
            logger.warning(f"No data returned for {indicator} in {country}")
            return None

        return {
            "metadata": data[0],
            "data": data[1],
        }

    except requests.exceptions.Timeout:
        logger.error("World Bank API request timed out")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"World Bank API request failed: {e}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse World Bank API response: {e}")
        return None


def fetch_multiple_indicators(
    country: str,
    indicators: List[str],
    start_year: Optional[int] = None,
    end_year: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Fetch multiple indicators for a country.

    Args:
        country: Country code
        indicators: List of indicator codes
        start_year: Start year
        end_year: End year

    Returns:
        Dictionary mapping indicator codes to their data
    """
    results = {}

    for indicator in indicators:
        data = fetch_world_bank_indicator(
            country=country,
            indicator=indicator,
            start_year=start_year,
            end_year=end_year,
        )
        if data:
            results[indicator] = data

    return results


def get_latest_value(data_points: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Get the most recent non-null value from indicator data.

    Args:
        data_points: List of data points from World Bank API

    Returns:
        Most recent data point with a value, or None
    """
    # Sort by date descending
    sorted_data = sorted(data_points, key=lambda x: x.get("date", ""), reverse=True)

    for point in sorted_data:
        if point.get("value") is not None:
            return point

    return None


def format_indicator_value(value: Any, indicator_code: str) -> str:
    """
    Format an indicator value for display.

    Args:
        value: The raw value
        indicator_code: The indicator code (for context)

    Returns:
        Formatted string
    """
    if value is None:
        return "N/A"

    try:
        num_value = float(value)

        # Large numbers (billions, millions)
        if abs(num_value) >= 1e12:
            return f"${num_value / 1e12:.2f}T"
        elif abs(num_value) >= 1e9:
            return f"${num_value / 1e9:.2f}B"
        elif abs(num_value) >= 1e6:
            return f"${num_value / 1e6:.2f}M"
        elif "ZS" in indicator_code or "ZG" in indicator_code:
            # Percentages
            return f"{num_value:.1f}%"
        elif "EST" in indicator_code:
            # Estimates (governance indicators)
            return f"{num_value:.2f}"
        elif abs(num_value) >= 1000:
            return f"{num_value:,.0f}"
        else:
            return f"{num_value:.2f}"

    except (ValueError, TypeError):
        return str(value)


def create_indicator_summary(
    country: str,
    indicators_data: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Create a summary of indicator data.

    Args:
        country: Country name/code
        indicators_data: Dictionary of indicator data

    Returns:
        Summary dictionary
    """
    summary = {
        "country": country,
        "indicators": [],
        "by_category": {},
    }

    for indicator_code, data in indicators_data.items():
        if not data or "data" not in data:
            continue

        latest = get_latest_value(data["data"])
        if not latest:
            continue

        indicator_info = ALL_INDICATORS.get(indicator_code, {})
        category = indicator_info.get("category", "other")

        indicator_summary = {
            "code": indicator_code,
            "name": indicator_info.get("name", indicator_code),
            "category": category,
            "value": latest.get("value"),
            "formatted_value": format_indicator_value(latest.get("value"), indicator_code),
            "year": latest.get("date"),
        }

        summary["indicators"].append(indicator_summary)

        if category not in summary["by_category"]:
            summary["by_category"][category] = []
        summary["by_category"][category].append(indicator_summary)

    return summary


def create_indicators_geojson(
    country: str,
    summary: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Create a GeoJSON representation for country indicators.

    Fetches country boundaries from Nominatim API to display as polygon on map.

    Args:
        country: Country name
        summary: Indicator summary

    Returns:
        GeoJSON FeatureCollection
    """
    # Get country boundary polygon from Nominatim
    geometry = None
    lat, lon = 0, 0
    bbox = None

    try:
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            "q": country,
            "format": "json",
            "limit": 1,
            "polygon_geojson": 1,  # Request polygon geometry
            "featuretype": "country",  # Specifically request country boundaries
        }
        headers = {"User-Agent": "NaLaMap-OSINT/1.0"}

        response = requests.get(url, params=params, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()

        if data:
            result = data[0]
            lat = float(result.get("lat", 0))
            lon = float(result.get("lon", 0))

            # Get bounding box
            if "boundingbox" in result:
                bb = result["boundingbox"]
                bbox = [float(bb[2]), float(bb[0]), float(bb[3]), float(bb[1])]

            # Get polygon geometry if available
            if "geojson" in result:
                geometry = result["geojson"]
                logger.info(f"Got {geometry.get('type', 'unknown')} geometry for {country}")
            else:
                # Fallback to point if no polygon available
                geometry = {"type": "Point", "coordinates": [lon, lat]}
                logger.warning(f"No polygon available for {country}, using point")
        else:
            geometry = {"type": "Point", "coordinates": [0, 0]}
            logger.warning(f"No results from Nominatim for {country}")

    except Exception as e:
        logger.error(f"Error fetching country geometry: {e}")
        geometry = {"type": "Point", "coordinates": [lon, lat]}

    # Build properties from indicators
    properties = {
        "country": summary["country"],
        "data_source": "World Bank",
    }

    for indicator in summary["indicators"]:
        # Use readable names as property keys
        key = indicator["name"].replace(" ", "_").replace("(", "").replace(")", "")[:50]
        properties[key] = indicator["formatted_value"]
        properties[f"{key}_year"] = indicator["year"]

    # Determine layer type based on geometry
    geom_type = geometry.get("type", "Point") if geometry else "Point"
    if geom_type in ["Polygon", "MultiPolygon"]:
        layer_type = "polygon"
    else:
        layer_type = "point"

    # Build chart data for frontend visualization
    chart_data = []
    chart_by_category = {}

    for indicator in summary["indicators"]:
        item = {
            "name": indicator["name"],
            "code": indicator["code"],
            "value": indicator["value"],
            "formatted_value": indicator["formatted_value"],
            "year": indicator["year"],
            "category": indicator["category"],
        }
        chart_data.append(item)

        category = indicator["category"]
        if category not in chart_by_category:
            chart_by_category[category] = []
        chart_by_category[category].append(item)

    # Create feature
    feature = {
        "type": "Feature",
        "geometry": geometry,
        "properties": properties,
    }

    return {
        "type": "FeatureCollection",
        "features": [feature],
        "properties": {
            "source": "World Bank Indicators API",
            "country": summary["country"],
            "indicator_count": len(summary["indicators"]),
            "chart_data": chart_data,
            "chart_by_category": chart_by_category,
            "layer_type": layer_type,
            "bbox": bbox,
            "centroid": [lon, lat],
        },
    }


@tool
def get_world_bank_data(
    country: Annotated[
        str,
        "Country name or ISO 3-letter code. Examples: 'Nigeria', 'USA', 'BRA', 'Germany'",
    ],
    category: Annotated[
        str,
        "Category of indicators to retrieve. Options: 'economic', 'social', "
        "'infrastructure', 'governance', 'environment', 'conflict_risk', or 'all'. "
        "Default is 'economic'.",
    ] = "economic",
    indicators: Annotated[
        Optional[str],
        "Comma-separated list of specific indicator codes. If provided, overrides category. "
        "Example: 'NY.GDP.MKTP.CD,FP.CPI.TOTL.ZG'",
    ] = None,
    years_back: Annotated[
        int,
        "Number of years of historical data to retrieve. Default is 5.",
    ] = 5,
    state: Annotated[GeoDataAgentState, InjectedState] = None,
    tool_call_id: Annotated[str, InjectedToolCallId] = None,
) -> Command[Any]:
    """
    Retrieve economic and development indicators from the World Bank.

    The World Bank API provides access to 16,000+ indicators covering economics,
    social development, infrastructure, governance, and environment.

    Use for:
    * **Economic analysis**: "Get GDP and inflation data for Brazil"
    * **Development assessment**: "Show poverty and education indicators for Nigeria"
    * **Governance evaluation**: "Get corruption and rule of law scores for Russia"
    * **Environmental monitoring**: "Show CO2 emissions for China"
    * **Comparative analysis**: Works well with conflict data for risk assessment

    Returns:
    * Latest values for selected indicators
    * Historical trends
    * Map marker at country location

    No API key required - World Bank data is freely accessible.
    """
    try:
        # Resolve country code
        country_code = get_country_code(country)

        logger.info(
            f"Fetching World Bank indicators for {country} ({country_code}), "
            f"category={category}, years_back={years_back}"
        )

        # Determine which indicators to fetch
        if indicators:
            # Use specific indicators if provided
            indicator_codes = [i.strip() for i in indicators.split(",")]
        elif category.lower() == "all":
            # Fetch key indicators from each category
            indicator_codes = []
            for cat, ind_dict in INDICATOR_CATEGORIES.items():
                # Take first 2-3 indicators from each category
                indicator_codes.extend(list(ind_dict.keys())[:3])
        elif category.lower() in INDICATOR_CATEGORIES:
            indicator_codes = list(INDICATOR_CATEGORIES[category.lower()].keys())
        else:
            # Default to economic
            indicator_codes = list(INDICATOR_CATEGORIES["economic"].keys())

        # Calculate year range
        current_year = datetime.now().year
        start_year = current_year - years_back

        # Fetch indicators
        indicators_data = fetch_multiple_indicators(
            country=country_code,
            indicators=indicator_codes,
            start_year=start_year,
            end_year=current_year,
        )

        if not indicators_data:
            return Command(
                update={
                    "messages": [
                        ToolMessage(
                            content=(
                                f"No indicator data found for {country}. "
                                "Please check the country name and try again."
                            ),
                            tool_call_id=tool_call_id,
                        )
                    ]
                }
            )

        # Create summary
        summary = create_indicator_summary(country, indicators_data)

        if not summary["indicators"]:
            return Command(
                update={
                    "messages": [
                        ToolMessage(
                            content=(
                                f"No recent data available for the requested "
                                f"indicators in {country}."
                            ),
                            tool_call_id=tool_call_id,
                        )
                    ]
                }
            )

        # Create GeoJSON
        geojson = create_indicators_geojson(country, summary)
        geojson_str = json.dumps(geojson)
        geojson_bytes = geojson_str.encode("utf-8")

        sha256_hex = hashlib.sha256(geojson_bytes).hexdigest()
        size_bytes = len(geojson_bytes)

        # Get bounding box from GeoJSON properties (calculated from Nominatim)
        geojson_props = geojson.get("properties", {})
        bbox_from_nominatim = geojson_props.get("bbox")
        layer_type = geojson_props.get("layer_type", "polygon")

        if bbox_from_nominatim:
            # Use bbox from Nominatim [minLon, minLat, maxLon, maxLat]
            bbox_list = bbox_from_nominatim
        else:
            # Fallback: try to get centroid and create small bbox around it
            centroid = geojson_props.get("centroid", [0, 0])
            bbox_list = [centroid[0] - 1, centroid[1] - 1, centroid[0] + 1, centroid[1] + 1]

        # Convert to WKT POLYGON string
        bounding_box = (
            f"POLYGON(({bbox_list[0]} {bbox_list[1]},"
            f"{bbox_list[2]} {bbox_list[1]},"
            f"{bbox_list[2]} {bbox_list[3]},"
            f"{bbox_list[0]} {bbox_list[3]},"
            f"{bbox_list[0]} {bbox_list[1]}))"
        )

        # Store file
        filename = (
            f"indicators_{country.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.geojson"
        )
        file_url, unique_id = store_file(filename, geojson_bytes)

        # Extract chart data from GeoJSON properties for frontend visualization
        chart_data = geojson_props.get("chart_data", [])
        chart_by_category = geojson_props.get("chart_by_category", {})

        geo_obj = GeoDataObject(
            id=unique_id,
            data_source_id="worldBankIndicators",
            name=f"indicators_{country.replace(' ', '_').lower()}",
            title=f"World Bank Indicators - {country}",
            description=(
                f"Economic and development indicators for {country} from World Bank. "
                f"{len(summary['indicators'])} indicators retrieved."
            ),
            llm_description=(
                f"World Bank indicator data for {country} including "
                f"{', '.join(category for category in summary['by_category'].keys())} metrics."
            ),
            data_origin=DataOrigin.TOOL,
            data_source="World Bank",
            data_type=DataType.GEOJSON,
            data_link=file_url,
            layer_type=layer_type,
            bounding_box=bounding_box,
            sha256=sha256_hex,
            size=size_bytes,
            properties={
                "country": country,
                "chart_data": chart_data,
                "chart_by_category": chart_by_category,
                "data_period": f"{start_year}-{current_year}",
            },
        )

        # Format response text
        response_lines = [
            f"📊 **World Bank Indicators for {country}**",
            f"📅 Data period: {start_year}-{current_year}",
            "",
        ]

        # Group by category for display
        for cat_name, cat_indicators in summary["by_category"].items():
            cat_display = cat_name.replace("_", " ").title()
            response_lines.append(f"**{cat_display}:**")

            for ind in cat_indicators:
                response_lines.append(
                    f"  • {ind['name']}: {ind['formatted_value']} ({ind['year']})"
                )

            response_lines.append("")

        response_lines.extend(
            [
                "🗺️ Country marker has been added to the map.",
                "",
                "💡 **Tips:**",
                "- Combine with conflict data for risk assessment",
                "- Use 'governance' category for institutional quality",
                "- Use 'all' category for comprehensive overview",
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
        logger.exception(f"Error in World Bank indicators tool: {e}")
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content=f"Error retrieving World Bank data: {str(e)}",
                        tool_call_id=tool_call_id,
                    )
                ]
            }
        )
