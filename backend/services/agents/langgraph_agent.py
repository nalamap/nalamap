from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel
import json
from services.database.database import get_db

# Define your state schema
class GeoState(BaseModel):
    query: str
    results: list = []
    
# Define the schema for LangGraph state
class SearchState(BaseModel):
    query: str
    results: list = []
    
async def query_postgis(state: SearchState) -> SearchState:
    """Executes a PostGIS SQL function using LangGraph."""
    query = state.query
    async for cur in get_db():  # Fetch database cursor
        await cur.execute("SELECT * FROM dataset_metadata_search(%s, %s)", (query, 10))
        rows = await cur.fetchall()

    state.results = [{"id": row[0], "source_type": row[1], "access_url": row[2], "llm_description": row[3], "bounding_box": row[4], "score": row[5]} for row in rows]
    return state
# Define LangGraph execution pipeline
graph = StateGraph(state_schema=SearchState)
graph.add_node("query_postgis", query_postgis)  # Add the query function as a node
graph.add_edge(START, "query_postgis")

# Build the graph
executor = graph.compile()
