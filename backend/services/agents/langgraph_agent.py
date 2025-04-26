from fastapi import FastAPI, Body
from langgraph.graph import StateGraph, START
from services.ai.llm_config import get_llm
from pydantic import BaseModel, Field
from services.database.database import get_db
from langchain.schema import SystemMessage, HumanMessage
from models.geodata import GeoDataObject, DataType, DataOrigin
from typing import List, Optional
import json


## 1) System prompt now instructs the LLM to output JSON with exactly these keys.
SYSTEM_PROMPT = """
You are GeoSearchAgent. 
Given a free‐text user query, extract and return a JSON object with:
  - searchquery: the text to send to the database
  - portal_filter: portal name (strings) or null
  - bbox_wkt: WKT polygon string or null

Example output:
{"searchquery":"roads in africa","portal_filter":["fao"],"bbox_wkt":"POLYGON((...))"}
"""

llm = get_llm(system_prompt=SYSTEM_PROMPT)

# 2) State carries everything, but initially only `raw_query` is set.
class SearchState(BaseModel):
    raw_query: str
    searchquery: Optional[str] = None
    portal: Optional[str] = None
    bbox_wkt: Optional[str] = None
    num_results: int = Field(10, ge=1)
    results: List[GeoDataObject] = []

# 3) Node #1: parse the user's raw_query via LLM into our structured fields.
async def parse_llm(state: SearchState) -> SearchState:
    user_msg = state.raw_query
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=user_msg)
    ]
    # agenerate expects a list of message‐lists for batching:
    response = await llm.agenerate([messages])
    # pull out the text from the first generation:
    json_text = response.generations[0][0].text
    
    # parse it (you may want to add error‐handling here)
    parsed = json.loads(json_text)
    state.searchquery = parsed["searchquery"]
    state.portal     = parsed.get("portal", [])
    state.bbox_wkt     = parsed.get("bbox_wkt")
    # keep num_results at its default or override if you want the LLM to set it
    
    return state

# 4) Node #2: hit PostGIS, pushing the score‐filter into SQL
async def query_postgis(state: SearchState) -> SearchState:
    async for cur in get_db():
        await cur.execute(
            """
            SELECT
              resource_id, source_type, name, title, description,
              access_url, format, llm_description,
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
                state.searchquery,
                state.num_results,
                state.portal,
                state.bbox_wkt,
            )
        )
        rows = await cur.fetchall()

    state.results = [
        GeoDataObject(
            id=row[0],
            data_source_id="geoweaver.postgis",
            data_type=DataType.GEOJSON if row[1]=="geojson" else DataType.LAYER,
            data_origin=DataOrigin.TOOL,
            data_source=row[1],
            data_link=row[5],
            name=row[2],
            title=row[3],
            description=row[4],
            llm_description=row[7],
            score=row[9],
            bounding_box=row[8],
            layer_type=row[1],
        )
        for row in rows
    ]
    return state

# 5) Assemble the graph
graph = StateGraph(state_schema=SearchState, llm=llm)
graph.add_node("parse", parse_llm)
graph.add_node("query_postgis", query_postgis)
graph.add_edge(START, "parse")
graph.add_edge("parse", "query_postgis")
executor = graph.compile()