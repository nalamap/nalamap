from langchain_core.tools import tool
import json
from langgraph.types import Command
import asyncio
from typing_extensions import Annotated
from typing import Any, Dict, List, Optional, Union
from langchain_core.tools import tool
from langchain_core.tools.base import InjectedToolCallId
from langchain_core.messages import ToolMessage
from langgraph.prebuilt import InjectedState
from services.database.database import close_db, get_db, init_db
from models.states import (
    GeoDataAgentState,
    get_medium_debug_state,
    get_minimal_debug_state,
)
from models.geodata import DataOrigin, DataType, GeoDataObject


@tool
def query_librarian_postgis(
    state: Annotated[GeoDataAgentState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
    query: str,
    maxRows: int = 10,
    portal_filter: Optional[str] = None,
    bbox_wkt: Optional[str] = None,
) -> Union[Dict[str, Any], Command]:
    """
    Tool to find geospatial layers and datasets for a given thematic query.
    Use for:
    * Finding datasets and layers that match a specific thematic query.
    * Finding datasets and layers that match a specific location given user data.
    * Finding datasets that cannot be found using geocoding tools.
    Strengths:
    * Provides a wide range of geospatial data sources, including maps, satellite imagery, and vector data.
    * Allows for flexible queries using natural language, allowing users to search for data by theme, location, or other criteria.
    Limitations:
    * The results are limited to the datasets, layers and regions available in the database.
    * The search is based on similarity, so the results may not always be exact matches to the query.
    query: the search string to send to the database for a similarity search, like "Rivers Namibia"
    maxRows: the maximum number of results to return, default is 10
    portal_filter: portal name (string) or null
    bbox_wkt: WKT polygon string or null like POLYGON((...)) to limit results to an area
    Inform the user that the results are limited to the datasets and layers available in the linked database.
    Inform the user about the total number of results for the query.
    Always use the bounding box to limit the results to a specific area.
    """

    async def _inner():
        async for cur in get_db():
            await cur.execute(
                """
                SELECT
                resource_id, source_type, name, title, description,
                access_url, portal, llm_description,
                ST_AsText(bounding_box) AS bbox_wkt, score
                FROM dataset_resources_search(
                %s,     -- searchquery
                %s,     -- num_results
                %s,     -- portal_filter
                ST_GeomFromText(%s,4326)  -- search_bbox
                )
                WHERE score <= 0.25
                """,
                (
                    query,
                    maxRows,
                    portal_filter,
                    bbox_wkt,
                ),
            )
            rows = await cur.fetchall()

        results = [
            GeoDataObject(
                id=str(row[0]),
                data_source_id="geoweaver.postgis",
                data_type=DataType.GEOJSON if row[1] == "geojson" else DataType.LAYER,
                data_origin=row[6],
                data_source=row[1],
                data_link=row[5],
                name=row[2],
                title=row[3],
                description=row[4],
                llm_description=row[7],
                score=1 - row[9],
                bounding_box=row[8],
                layer_type=row[1],
            )
            for row in rows
        ]

        new_global_geodata: List[GeoDataObject]

        if (
            "geodata_results" not in state
            or state["geodata_results"] is None
            or not isinstance(state["geodata_results"], List)
            or len(state["geodata_results"]) == 0
        ):
            new_global_geodata = results
        else:
            new_global_geodata = []
            # new_global_geodata.extend(state["global_geodata"])
            new_global_geodata.extend(results)

        return Command(
            update={
                "messages": [
                    *state["messages"],
                    ToolMessage(
                        name="query_librarian_postgis",
                        content=(
                            f"Retrieved {len(results)} results, "
                            "added GeoDataObjects into the global_state, "
                            "use id and data_source_id for reference: "
                            + json.dumps(
                                [
                                    {
                                        "id": r.id,
                                        "data_source_id": r.data_source_id,
                                        "title": r.title,
                                    }
                                    for r in results
                                ]
                            )
                        ),
                        tool_call_id=tool_call_id,
                    ),
                ],
                # "global_geodata": new_global_geodata,
                "geodata_results": new_global_geodata,
            }
        )

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        # no running loop; will create one
        return asyncio.run(_inner())

    if loop.is_running():
        # if we're already in an event loop (rare in sync contexts),
        # fall back to asyncio.run in a thread
        return asyncio.run(_inner())
    else:
        # safe to reuse the existing loop
        return loop.run_until_complete(_inner())


if __name__ == "__main__":
    asyncio.run(init_db())
    try:
        initial_state: GeoDataAgentState = get_minimal_debug_state(True)
        print(initial_state)
        print(
            query_librarian_postgis.invoke(
                {
                    "args": {
                        "state": initial_state,
                        "tool_call_id": "testcallid1234",
                        "query": "Rivers Africa",
                        "geojson": True,
                    },
                    "name": "geocode_nominatim",
                    "type": "tool_call",
                    "id": "id2",
                    "tool_call_id": "testcallid1234",
                }
            )
        )
        print(initial_state)
        asyncio.run(close_db())
    except:
        asyncio.run(close_db())
