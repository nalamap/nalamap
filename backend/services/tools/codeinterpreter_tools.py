from langchain_core.messages import HumanMessage, SystemMessage , ToolMessage
from langchain_core.tools import tool
from langchain_core.tools.base import InjectedToolCallId
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from typing_extensions import Annotated
import json
import logging
import requests
import os
import uuid
from typing import Any, Dict, List, Optional, Union
from langchain.agents import initialize_agent
import geopandas as gpd
from core.config import BASE_URL, LOCAL_UPLOAD_DIR
from models.geodata import DataOrigin, DataType, GeoDataObject
from models.states import GeoDataAgentState
from services.ai.llm_config import get_llm
import re
# Imports of operation functions from geoprocessing ops and utils
from services.tools.geoprocessing.utils import get_last_human_content
from langchain_experimental.utilities.python import PythonREPL
from langchain_experimental.tools.python.tool import PythonREPLTool


def strip_code_fences(code: str) -> str:
    """
    Remove leading ```python and trailing ``` from a code snippet.
    """
    # Remove leading ```python (and any whitespace/newlines after)
    code = re.sub(r"^\s*```python\s*\n?", "", code)
    # Remove trailing ``` (and any whitespace/newlines before)
    code = re.sub(r"\n?\s*```\s*$", "", code)
    return code

class FenceStrippingPythonREPLTool(PythonREPLTool):
    """
    A PythonREPLTool that first strips ```python … ``` fences.
    """
    def _run(self, code: str) -> str:
        # 1) strip any fences
        cleaned = strip_code_fences(code)
        # 2) delegate to the normal REPL
        return super()._run(cleaned)


@tool
def geoprocess_interpreter_tool(
    state: Annotated[GeoDataAgentState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId]
) -> Union[Dict[str, Any], Command]:
    """
    Geoprocessing interpreter tool using Python execution.

    Args:
        state: The agent state containing geodata_layers

    Returns:
        A dict with:
          - result_gdf: the processed GeoDataFrame
          - answer: textual summary of the operation and resulting dataset
    """
    layers = state.get("geodata_layers") or []
    serializable_layers = [
    {
        "id": layer.id,
        "data_source_id": layer.data_source_id,
        "name": layer.name,
    }
    for layer in layers
]
    messages = state.get("messages") or []
    query = get_last_human_content(messages)

    # Load GeoJSONs from either local disk or remote URL
    input_layers_dict: Dict[str, Any] = {}
    input_layers: List[Any] = []
    
    ###SHORT THIS UP (FOR FUTURE ME)
    for layer in layers:
        if layer.data_type not in (DataType.GEOJSON, DataType.UPLOADED):
            continue

        url = layer.data_link
        gj: Optional[Dict[str, Any]] = None

        # 1) If the URL matches BASE_URL/uploads/, load from LOCAL_UPLOAD_DIR
        if url.startswith(f"{BASE_URL}/uploads/"):
            filename = os.path.basename(url)
            local_path = os.path.join(LOCAL_UPLOAD_DIR, filename)
            try:
                with open(local_path, "r", encoding="utf-8") as f:
                    gj = json.load(f)
            except Exception as exc:
                return {
                    "update": {
                        "messages": [
                            ToolMessage(
                                name="geoprocess_tool",
                                content=f"Error: Failed to read local file '{local_path}': {exc}",
                                status="error",
                            )
                        ]
                    }
                }

        # 2) Else if url is a local filesystem path
        elif os.path.isfile(url):
            try:
                with open(url, "r", encoding="utf-8") as f:
                    gj = json.load(f)
            except Exception as exc:
                return {
                    "update": {
                        "messages": [
                            ToolMessage(
                                name="geoprocess_tool",
                                content=f"Error: Failed to read local file '{url}': {exc}",
                                status="error",
                            )
                        ]
                    }
                }

        # 3) Else if url is under LOCAL_UPLOAD_DIR by filename
        else:
            filename = os.path.basename(url)
            local_path = os.path.join(LOCAL_UPLOAD_DIR, filename)
            if os.path.isfile(local_path):
                try:
                    with open(local_path, "r", encoding="utf-8") as f:
                        gj = json.load(f)
                except Exception as exc:
                    return {
                        "update": {
                            "messages": [
                                ToolMessage(
                                    name="geoprocess_tool",
                                    content=f"Error: Failed to read local file '{local_path}': {exc}",
                                    status="error",
                                )
                            ]
                        }
                    }

        # 4) Else if it looks like a remote URL, fetch via requests
        if gj is None:
            if url.startswith("http://") or url.startswith("https://"):
                try:
                    resp = requests.get(url, timeout=20)
                    if resp.status_code != 200:
                        raise IOError(f"HTTP {resp.status_code} when fetching {url}")
                    gj = resp.json()
                except Exception as exc:
                    return {
                        "update": {
                            "messages": [
                                ToolMessage(
                                    name="geoprocess_tool",
                                    content=f"Error: Failed to fetch GeoJSON from '{url}': {exc}",
                                    status="error",
                                )
                            ]
                        }
                    }
            else:
                return {
                    "update": {
                        "messages": [
                            ToolMessage(
                                name="geoprocess_tool",
                                content=f"Error: GeoJSON path '{url}' is neither a local file nor a valid HTTP URL.",
                                status="error",
                            )
                        ]
                    }
                }
        # Normalize to FeatureCollection
        if isinstance(gj, list):
            gj = gj[0]
        if gj.get("type") == "FeatureCollection":
            #input_layers.append(gj)
            current_features = gj.get("features", [])
            gdf = gpd.GeoDataFrame.from_features(current_features)
            input_layers.append(gdf)
        elif gj.get("type") == "Feature":
            gdf = gpd.GeoDataFrame.from_features(gj)
            input_layers.append(gdf)
            
    result_gdf = None
    python_repl = PythonREPL(_globals={"input_layers": input_layers})
    repl_tool = FenceStrippingPythonREPLTool(
        python_repl=python_repl,
        description="A REPL that strips ```python…``` fences before executing.",
        verbose=True
        )  
    # 2) Prompt LLM to generate Python code
    system_prompt = (
        "You are a Python geospatial analyst. You have a list called 'input_layers' which values are GeoDataFrames. You don't have to load it the variable is already defined "
        "A user query describes a geospatial task. Write Python code that performs the task, using geopandas. "
        "Ensure you working with the right crs if not other mention the geodataframes set crs are EPSG:4326 as the source where geojson's. "
        "Also project the geodataframes to EPSG:3857 or more precise crs for the geospatial operations. In the end always reproject to EPSG:4326 "
        "Your code must assign the final GeoDataFrame to a variable named 'result_gdf'. "
        "Do not include any narrative or comments beyond necessary imports and code. Only output the code."
    )
    user_payload = {"layers": serializable_layers, "query": query}
    print("dicl")
    llm = get_llm()
    # Initialize a zero-shot agent with only the REPL tool
    #agent = initialize_agent(
    #    tools=[repl_tool],
    #    llm=llm,
    #    agent="zero-shot-react-description",
    #    verbose=True
    #)
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=json.dumps(user_payload))
    ]
    response = llm.generate([messages])
    #response = agent.invoke([messages])
    raw_code = response.generations[0][0].text
    code = strip_code_fences(raw_code)
    
    

    # 3) Execute generated code
    local_vars: Dict[str, Any] = {"input_layers": input_layers}
    try:
        exec(code, {}, local_vars)
    except Exception as e:
        raise RuntimeError(f"Error executing generated code: {e}\nCode:\n{code}")

    if "result_gdf" not in local_vars:
        raise ValueError("Generated code did not set 'result_gdf'.")
    result_gdf = local_vars["result_gdf"]

    fc = json.loads(result_gdf.to_json())
    
    # Build new GeoDataObjects
    new_geodata: List[GeoDataObject]
    if (
        "geodata_results" not in state
        or state["geodata_results"] is None
        or not isinstance(state["geodata_results"], List)
    ):
        new_geodata = []
    else:
        new_geodata = state["geodata_results"]
    out_urls: List[str] = []
    
    out_uuid = uuid.uuid4().hex
    filename = f"{out_uuid}_geoprocess.geojson"
    path = os.path.join(LOCAL_UPLOAD_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(fc, f)

    url = f"{BASE_URL}/uploads/{filename}"
    out_urls.append(url)
    new_geodata.append(
        GeoDataObject(
            id=out_uuid,
            data_source_id="geoprocess",
            data_type=DataType.GEOJSON,
            data_origin=DataOrigin.TOOL,
            data_source="NaLaMapGeoprocess",
            data_link=url,
            name=filename,
            title=filename,
            description=filename,
            llm_description=filename,
            score=0.2,
            bounding_box=None,
            layer_type="GeoJSON",
            properties=None
        )
    )

    print("check")
    return Command(
        update={
            "messages": [
                ToolMessage(
                    name="codeinterpreter_tool",
                    content=". Added GeoDataObjects into the global_state, use id and data_source_id",
                    tool_call_id=tool_call_id
                )
            ],
            # "global_geodata": new_geodata,
            "geodata_results": new_geodata,
        }
    )
