from typing import Annotated
from models.agent_state import GeoDataAgentState, InjectedState

@tool_with_schema(
    name="geocode",
    default_prompt="Geocode this address",
    schema=[{"key": "region", "type": "string", "label": "Region", "default": "global"}]
)
def geocode_using_nominatim_to_geostate(
    state: Annotated[GeoDataAgentState, InjectedState],
    address: str,
    config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Geocode an address into geographic features.
    """
    # config['prompt'], config['region'], etc.
    # state holds chat/session-specific data, e.g. history or auth
    result = state.nominatim_geocode(address, region=config.get('region'))
    if config.get('as_geojson'):
        return state.to_geojson(result)
    return result
```
