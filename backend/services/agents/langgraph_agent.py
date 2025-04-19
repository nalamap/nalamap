from fastapi import FastAPI, Body
from langgraph.graph import StateGraph, START
from pydantic import BaseModel
from services.database.database import get_db
from models.geodata import GeoDataObject, DataType, DataOrigin


# Define the state schema for the search operation.
class SearchState(BaseModel):
    query: str
    results: list = []

async def query_postgis(state: SearchState) -> SearchState:
    """
    Executes a PostGIS SQL function using LangGraph.
    Given a query in the state, it retrieves matching rows from the database,
    maps each row to a GeoDataObject instance, and returns the updated state.
    """
    query = state.query
    async for cur in get_db():  # Fetch a database cursor
        await cur.execute("SELECT resource_id, source_type, name, title, description, access_url, format, llm_description, ST_AsText(bounding_box), score FROM dataset_resources_search(%s, %s)", (query, 10))
        rows = await cur.fetchall()

    state.results = [
        GeoDataObject(
            id=row[0],
            data_source_id="geoweaver.postgis",  
            data_type=DataType.GEOJSON,
            data_origin=DataOrigin.TOOL,  
            data_source=row[1],
            data_link=row[5],
            name=row[2],
            title=row[3],
            description=row[4],
            llm_description=row[7],
            score=row[9],
            bounding_box=row[8],
        )
        for row in rows
    ]
    return state

# Set up the LangGraph pipeline using SearchState as the state schema.
graph = StateGraph(state_schema=SearchState)
graph.add_node("query_postgis", query_postgis)
graph.add_edge(START, "query_postgis")

# Compile the graph to obtain an executor.
executor = graph.compile()