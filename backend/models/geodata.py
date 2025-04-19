from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any


class DataType(Enum):
    GEOJSON = "GeoJson"
    LAYER = "Layer"


class DataOrigin(Enum):
    UPLOAD = "upload"
    TOOL = "tool"
    GEPROCESSING = "geprocessing"


@dataclass
class GeoDataObject:
    # Required (key) fields
    id: str
    data_source_id: str   # e.g. database name
    data_type: DataType
    data_origin: DataOrigin

    # Required metadata
    data_source: str      # e.g. portal name
    data_link: str
    name: str

    # Optional fields
    title: Optional[str] = None
    description: Optional[str] = None
    llm_description: Optional[str] = None
    score: Optional[float] = None
    bounding_box: Optional[str] = None
    layer_type: Optional[str] = None
    properties: Dict[str, Any] = field(default_factory=dict)