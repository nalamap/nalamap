import difflib
import json
import logging
import os
import re
import uuid
from typing import Any, Dict, List, Optional, Tuple, Union

import geopandas as gpd
import pandas as pd
import requests
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langchain_core.tools.base import InjectedToolCallId
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from shapely.geometry import mapping
from typing_extensions import Annotated

from core.config import BASE_URL, LOCAL_UPLOAD_DIR
from models.geodata import DataOrigin, DataType, GeoDataObject
from models.states import GeoDataAgentState
from services.ai.llm_config import get_llm, get_llm_for_provider
from services.storage.file_management import store_file
from services.tools.utils import match_layer_names

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


# =========================
# Helper: Get LLM from state options
# =========================
def _get_llm_from_options(state: Optional[GeoDataAgentState] = None):
    """
    Get LLM instance from state options, falling back to default get_llm().

    Args:
        state: Optional GeoDataAgentState containing options with model_settings

    Returns:
        LLM instance configured according to options or default
    """
    if state is None:
        return get_llm()

    options = state.get("options")
    if not options:
        return get_llm()

    model_settings = getattr(options, "model_settings", None)
    if not model_settings:
        return get_llm()

    provider = getattr(model_settings, "provider", None)
    model_name = getattr(model_settings, "model", None)
    max_tokens = getattr(model_settings, "max_tokens", 6000)

    if provider:
        try:
            return get_llm_for_provider(
                provider_name=provider, max_tokens=max_tokens, model_name=model_name
            )
        except Exception as e:
            logger.warning(f"Failed to get LLM for provider {provider}: {e}. Using default.")
            return get_llm()

    return get_llm()


# =========================
# CQL-lite tokenizer/parser
# =========================
_token = re.compile(
    r"""
    \s*(?:
        (?P<kw>AND|OR|NOT|IN|IS|NULL)\b
      | (?P<ident>[A-Za-z_][A-Za-z0-9_]*)
      | "(?P<identq>[^"]+)"
      | '(?P<string>[^']*)'
      | (?P<num>-?\d+(?:\.\d+)?)
      | (?P<op>>=|<=|!=|=|>|<)
      | (?P<lpar>\()
      | (?P<rpar>\))
      | (?P<comma>,)
    )
""",
    re.X | re.IGNORECASE,
)


def _tokenize(s: str):
    pos = 0
    while pos < len(s):
        m = _token.match(s, pos)
        if not m:
            raise ValueError(f"Bad token near: {s[pos:pos+20]}")
        pos = m.end()
        yield m


def _read(tokens):
    return next(tokens, None)


def _advance(state, tokens):
    state["cur"] = _read(tokens)
    return state["cur"]


def _peek(state):
    return state["cur"]


def _field_name(tok) -> str:
    if tok.group("ident"):
        return tok.group("ident")
    if tok.group("identq"):
        return tok.group("identq")
    raise ValueError("Expected field name")


# --- NEW: dataset description helpers ---------------------------------
def _geometry_type_counts(gdf: gpd.GeoDataFrame) -> Dict[str, int]:
    if gdf.geometry is None:
        return {}
    # robust type extraction (handles missing/empty geometries)
    types = gdf.geometry.geom_type.fillna("None")
    return types.value_counts().to_dict()


def _bbox(gdf: gpd.GeoDataFrame) -> Optional[List[float]]:
    try:
        minx, miny, maxx, maxy = gdf.total_bounds  # [minx, miny, maxx, maxy]
        if all(pd.notna([minx, miny, maxx, maxy])):
            return [float(minx), float(miny), float(maxx), float(maxy)]
    except Exception:
        pass
    return None


def _suggest_next_steps(gdf: gpd.GeoDataFrame, schema_ctx: Dict[str, Any], llm=None) -> List[str]:
    tips = []
    # Note: geometry name could be used for field-specific suggestions
    # if needed
    gtypes = set(_geometry_type_counts(gdf).keys())
    cols = [c["name"] for c in schema_ctx.get("columns", [])]

    # Geometry-driven ideas
    if {"LineString", "MultiLineString"} & gtypes:
        tips += [
            "Filter by name or class to focus on a single line feature.",
            "Compute length, then style lines by length or class.",
            "Buffer lines to model influence zones (e.g., 100–500 m).",
            "Spatial-join with places or admin areas to count overlaps.",
        ]
    if {"Point", "MultiPoint"} & gtypes:
        tips += [
            "Filter by category/status and map clusters or heatmaps.",
            "Aggregate points by admin areas (count per district).",
            "Nearest-neighbor join to the closest service or road.",
        ]
    if {"Polygon", "MultiPolygon"} & gtypes:
        tips += [
            "Filter polygons by attributes (e.g., type, protection).",
            "Compute area and style choropleth maps.",
            "Intersect/union with other layers to analyze overlaps.",
        ]
    if not gtypes:
        tips.append("No geometry detected; you can still filter and summarize attributes.")

    # Field-driven ideas
    lower_cols = [c.lower() for c in cols]
    if any(k in lower_cols for k in ["name", "name_en", "label", "title"]):
        tips.append("Search by a specific name (e.g., `filter name = '…'`).")
    if any(k in lower_cols for k in ["pop", "population", "inhabitants"]):
        tips.append("Style by population, or filter by thresholds.")
    if any(k in lower_cols for k in ["gdp", "gdp_pc", "gdp_per_capita"]):
        tips.append("Style by GDP, filter high/low GDP regions, or bin into classes.")
    if any(k in lower_cols for k in ["class", "type", "category", "status"]):
        tips.append("Filter by class/type and compute counts per category.")

    # Try an LLM-driven enhancement of next steps, falling back to simple heuristics
    context = {
        "row_count": int(len(gdf)),
        "geometry_types": gtypes,
        "columns": cols,
    }
    try:
        if llm is None:
            llm = get_llm()
        sys = (
            "You are a GIS data analysis assistant. "
            "Given the dataset context, suggest up to 6 concrete next steps "
            "for analysis or visualization."
        )
        human = f"Dataset context: {json.dumps(context)}"
        msgs = [SystemMessage(content=sys), HumanMessage(content=human)]
        resp = llm.generate([msgs])
        text = resp.generations[0][0].text.strip()
        # Expect JSON list, else split lines
        try:
            llm_tips = json.loads(text)
            if isinstance(llm_tips, list):
                return llm_tips
        except Exception:
            # fallback to splitting
            lines = [line.strip(" -") for line in text.splitlines() if line.strip()]
            return lines[:6]
    except Exception:
        pass
    # fallback simple heuristics: keep it short and unique
    seen = set()
    uniq = []
    for t in tips:
        if t not in seen:
            uniq.append(t)
            seen.add(t)
    return uniq[:6]


def describe_dataset_gdf(
    gdf: gpd.GeoDataFrame, schema_ctx: Dict[str, Any], llm=None
) -> Dict[str, Any]:
    """
    Returns a compact, chat-safe description of the dataset:
    - row_count, geometry types, CRS, bbox
    - key columns w/ examples
    - short natural-language summary text
    - suggested next steps (actions)
    """
    row_count = int(len(gdf))
    geom_col = gdf.geometry.name if gdf.geometry is not None else None
    geom_types = _geometry_type_counts(gdf)
    crs = str(gdf.crs) if gdf.crs is not None else None
    bbox_vals = _bbox(gdf)

    # Pick 5 "key" columns to preview (prefer name-like then numeric/text variety)
    cols_meta = schema_ctx.get("columns", [])
    name_like = [
        c
        for c in cols_meta
        if c.get("type") != "geometry" and re.search(r"(name|label|title)", c["name"], re.I)
    ]
    others = [c for c in cols_meta if c not in name_like and c.get("type") != "geometry"]
    key_cols = (name_like + others)[:5]
    # attach a few top values if present
    preview_cols = []
    for c in key_cols:
        entry = {"name": c["name"], "type": c.get("type")}
        if "top_values" in c:
            entry["examples"] = c["top_values"][:5]
        elif "min" in c or "max" in c:
            entry["range"] = {"min": c.get("min"), "max": c.get("max")}
        preview_cols.append(entry)

    # Natural-language one-liner (heuristic, no LLM needed here)
    if geom_types:
        top_geom = max(geom_types.items(), key=lambda kv: kv[1])[0]
        geom_phrase = top_geom.lower()
    else:
        geom_phrase = "attribute-only table"

    summary = f"This layer has {row_count} features, primarily {geom_phrase}."
    if crs:
        summary += f" CRS: {crs}."
    if bbox_vals:
        summary += (
            f" Bounding box: [{bbox_vals[0]:.4f}, {bbox_vals[1]:.4f}, "
            f"{bbox_vals[2]:.4f}, {bbox_vals[3]:.4f}]."
        )

    next_steps = _suggest_next_steps(gdf, schema_ctx, llm=llm)
    result = {
        "row_count": row_count,
        "geometry_column": geom_col,
        "geometry_types": geom_types,
        "crs": crs,
        "bbox": bbox_vals,
        "key_columns": preview_cols,
        "summary": summary,
        "suggested_next_steps": next_steps,
    }
    # Optionally enrich summary via LLM, including sample rows for richer context
    try:
        if llm is None:
            llm = get_llm()
        # Prepare sample rows: up to 3 from top and 2 from bottom (or all if fewer)
        total = len(gdf)
        if total >= 5:
            top_n = min(3, total)
            bot_n = min(2, total - top_n)
            sample_top = gdf.head(top_n)
            sample_bot = gdf.tail(bot_n)
            sample = pd.concat([sample_top, sample_bot])
        else:
            sample = gdf.head(total)
        # Drop geometry column for readability if present
        if geom_col in sample.columns:
            sample = sample.drop(columns=[geom_col])
        sample_rows = sample.to_dict(orient="records")

        sys = (
            "You are a GIS data assistant. "
            "Provide a concise description and practical next steps for this specific dataset. "
            "Respond in JSON with keys 'summary' (string) and "
            "'suggested_next_steps' (list of strings)."
        )
        context_obj = {"metadata": result, "sample_rows": sample_rows}
        human = f"Dataset context and sample rows: {json.dumps(context_obj, default=str)}"
        msgs = [SystemMessage(content=sys), HumanMessage(content=human)]
        resp = llm.generate([msgs])
        text = resp.generations[0][0].text.strip()
        # strip code fences and optional 'json' tag
        if text.startswith("```"):
            parts = text.split("```", 2)
            if len(parts) >= 2:
                text = parts[1]
        if text.strip().lower().startswith("json"):
            # remove leading 'json' keyword or header
            lines = text.split("\n", 1)
            text = lines[1] if len(lines) > 1 else ""
        data = json.loads(text)
        if isinstance(data, dict):
            result.update(
                {
                    "summary": data.get("summary", result.get("summary")),
                    "suggested_next_steps": data.get(
                        "suggested_next_steps", result.get("suggested_next_steps")
                    ),
                }
            )
    except Exception:
        pass
    return result


def _parse_literal(tok):
    if tok.group("string") is not None:
        return tok.group("string")
    if tok.group("num") is not None:
        s = tok.group("num")
        return float(s) if "." in s else int(s)
    return None


def _expect_kw(state, kw):
    cur = _peek(state)
    if not (cur and cur.group("kw") and cur.group("kw").upper() == kw.upper()):
        raise ValueError(f"Expected {kw}")
    _advance(state, state["tokens"])


def _expect_op(state, ops):
    cur = _peek(state)
    if not (cur and cur.group("op") in ops):
        raise ValueError(f"Expected one of {ops}")
    op = cur.group("op")
    _advance(state, state["tokens"])
    return op


def _parse_primary(state):
    cur = _peek(state)
    if cur and cur.group("lpar"):
        _advance(state, state["tokens"])
        node = _parse_expr(state)
        if not (_peek(state) and _peek(state).group("rpar")):
            raise ValueError("Missing )")
        _advance(state, state["tokens"])
        return node
    if cur and (cur.group("ident") or cur.group("identq")):
        field = _field_name(cur)
        _advance(state, state["tokens"])
        cur = _peek(state)
        if cur and cur.group("kw") and cur.group("kw").upper() == "IS":
            _advance(state, state["tokens"])
            cur = _peek(state)
            is_not = False
            if cur and cur.group("kw") and cur.group("kw").upper() == "NOT":
                is_not = True
                _advance(state, state["tokens"])
            _expect_kw(state, "NULL")
            return ("isnull", field, is_not)
        if cur and cur.group("kw") and cur.group("kw").upper() == "IN":
            _advance(state, state["tokens"])
            if not (_peek(state) and _peek(state).group("lpar")):
                raise ValueError("Expected ( after IN")
            _advance(state, state["tokens"])
            values = []
            while True:
                cur = _peek(state)
                if not cur:
                    raise ValueError("Unterminated IN list")
                if cur.group("rpar"):
                    _advance(state, state["tokens"])
                    break
                if cur.group("comma"):
                    _advance(state, state["tokens"])
                    continue
                v = _parse_literal(cur)
                if v is None:
                    raise ValueError("Expected literal in IN list")
                values.append(v)
                _advance(state, state["tokens"])
            return ("in", field, values)
        op = _expect_op(state, {">=", "<=", "!=", "=", ">", "<"})
        cur = _peek(state)
        if not cur:
            raise ValueError("Expected literal after op")
        lit = _parse_literal(cur)
        if lit is None:
            raise ValueError("Expected literal after op")
        _advance(state, state["tokens"])
        return ("cmp", field, op, lit)
    raise ValueError("Expected expression")


def _parse_not(state):
    cur = _peek(state)
    if cur and cur.group("kw") and cur.group("kw").upper() == "NOT":
        _advance(state, state["tokens"])
        node = _parse_not(state)
        return ("not", node)
    return _parse_primary(state)


def _parse_and(state):
    node = _parse_not(state)
    while _peek(state) and _peek(state).group("kw") and _peek(state).group("kw").upper() == "AND":
        _advance(state, state["tokens"])
        rhs = _parse_not(state)
        node = ("and", node, rhs)
    return node


def _parse_expr(state):
    node = _parse_and(state)
    while _peek(state) and _peek(state).group("kw") and _peek(state).group("kw").upper() == "OR":
        _advance(state, state["tokens"])
        rhs = _parse_and(state)
        node = ("or", node, rhs)
    return node


def parse_where(where: str):
    tokens = iter(_tokenize(where))
    state = {"tokens": tokens, "cur": None}
    _advance(state, tokens)
    ast = _parse_expr(state)
    if _peek(state):
        raise ValueError("Unexpected trailing tokens")
    return ast


# ===================================
# Field name fuzzy matching helper
# ===================================
def _find_closest_field(
    field_name: str, available_fields: List[str], cutoff: float = 0.6
) -> Tuple[Optional[str], bool]:
    """
    Find the closest matching field name in the available fields.

    Args:
        field_name: The field name to match
        available_fields: List of available field names
        cutoff: Similarity threshold for fuzzy matching (0 to 1)

    Returns:
        Tuple of (matched_field_name, is_exact_match)
        Returns (None, False) if no match found above cutoff
    """
    # Try exact match first (case-sensitive)
    if field_name in available_fields:
        return (field_name, True)

    # Try case-insensitive exact match
    for field in available_fields:
        if field.lower() == field_name.lower():
            return (field, True)

    # Try fuzzy matching
    matches = difflib.get_close_matches(field_name, available_fields, n=1, cutoff=cutoff)
    if matches:
        return (matches[0], False)

    return (None, False)


# ===================================
# GeoPandas-based operations & IO
# ===================================
def _load_gdf(link: str) -> gpd.GeoDataFrame:
    """Load GeoJSON (local or remote) into a GeoDataFrame.

    Supports:
    - Local upload directory files
    - BASE_URL/uploads/ URLs (local dev)
    - BASE_URL/api/stream/ URLs (local dev with central file management)
    - Azure Blob Storage URLs (SAS tokens supported)
    - HTTP/HTTPS URLs (external GeoJSON)
    - WFS URLs (adds srsName=EPSG:4326 if missing)
    - Local file paths
    """
    # Handle BASE_URL/uploads/ format (legacy local uploads)
    if link.startswith(f"{BASE_URL}/uploads/"):
        fn = os.path.basename(link)
        local_path = os.path.join(LOCAL_UPLOAD_DIR, fn)
        if os.path.isfile(local_path):
            return gpd.read_file(local_path)

    # Handle BASE_URL/api/stream/ format (central file management local)
    if link.startswith(f"{BASE_URL}/api/stream/"):
        fn = os.path.basename(link)
        local_path = os.path.join(LOCAL_UPLOAD_DIR, fn)
        if os.path.isfile(local_path):
            return gpd.read_file(local_path)

    # Handle direct local file paths
    if os.path.isfile(link):
        return gpd.read_file(link)

    # Handle HTTP/HTTPS URLs (including Azure Blob Storage with SAS tokens)
    if link.startswith("http://") or link.startswith("https://"):
        request_url = link
        # For WFS requests, ensure srsName=EPSG:4326 is set for consistent coordinate system
        try:
            from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

            parsed = urlparse(link)
            params = parse_qs(parsed.query)

            # Check if this is a WFS request
            is_wfs = (
                "wfs" in parsed.path.lower()
                or "wfs" in parsed.query.lower()
                or (params.get("service", [""])[0].upper() == "WFS")
            )

            # Add srsName if WFS and not already present
            if is_wfs and "srsName" not in params and "srsname" not in params:
                params["srsName"] = ["EPSG:4326"]
                # Rebuild URL with updated params
                new_query = urlencode(params, doseq=True)
                request_url = urlunparse(
                    (
                        parsed.scheme,
                        parsed.netloc,
                        parsed.path,
                        parsed.params,
                        new_query,
                        parsed.fragment,
                    )
                )
                logger.info(f"Added srsName=EPSG:4326 to WFS URL: {request_url}")
        except Exception as e:
            logger.warning(f"Failed to parse URL for WFS detection: {e}")

        # Download to temp file for reliable driver support
        resp = requests.get(request_url, timeout=30)
        resp.raise_for_status()
        # Ensure upload dir exists (CI environments or tests may not create it).
        # Use a local variable to avoid rebinding the module-level LOCAL_UPLOAD_DIR.
        upload_dir = LOCAL_UPLOAD_DIR or "."
        try:
            os.makedirs(upload_dir, exist_ok=True)
        except Exception:
            upload_dir = "."

        tmp = os.path.join(upload_dir, f"tmp_{uuid.uuid4().hex[:8]}.geojson")
        with open(tmp, "wb") as f:
            f.write(resp.content)
        try:
            return gpd.read_file(tmp)
        finally:
            try:
                os.remove(tmp)
            except Exception:
                pass

    raise IOError(f"Unsupported path or URL: {link}")


def _jsonify_scalar(v):
    # Convert numpy/pandas scalars to native JSON types
    if pd.isna(v):
        return None
    if hasattr(v, "item"):
        try:
            return v.item()
        except Exception:
            pass
    if isinstance(v, (pd.Timestamp,)):
        return v.isoformat()
    return v


def _fc_from_gdf(gdf: gpd.GeoDataFrame, keep_geometry: bool = True) -> Dict[str, Any]:
    """Convert a GeoDataFrame to a GeoJSON FeatureCollection dict."""
    features = []
    geom_col = gdf.geometry.name if gdf.geometry is not None else None

    # Build clean properties (only JSON-serializable, exclude geometry column)
    prop_cols = [c for c in gdf.columns if c != geom_col]
    for _, row in gdf.iterrows():
        props = {c: _jsonify_scalar(row[c]) for c in prop_cols}
        geom = mapping(row[geom_col]) if keep_geometry and geom_col else None
        features.append({"type": "Feature", "properties": props, "geometry": geom})
    return {"type": "FeatureCollection", "features": features}


def _slug(text: str) -> str:
    text = (text or "attribute-result").lower().strip()
    text = re.sub(r"[^a-z0-9\-_ ]+", "", text).replace(" ", "-")
    text = re.sub(r"-+", "-", text).strip("-")
    return text or "attribute-result"


def _save_gdf_as_geojson(
    gdf: gpd.GeoDataFrame,
    display_title: str,
    keep_geometry: bool = True,
    detailed_description: Optional[str] = None,
) -> GeoDataObject:
    """
    Save a GeoDataFrame as GeoJSON using central file management.

    Args:
        gdf: GeoDataFrame to save
        display_title: Short title for the layer
        keep_geometry: Whether to include geometry
        detailed_description: Optional detailed description of the operation performed

    Returns:
        GeoDataObject with the saved layer information
    """
    fc = _fc_from_gdf(gdf, keep_geometry=keep_geometry)
    slug = _slug(display_title)
    filename = f"{slug}_{uuid.uuid4().hex[:8]}.geojson"

    # Convert to JSON bytes
    content = json.dumps(fc).encode("utf-8")

    # Use central file management (supports both local and Azure Blob)
    url, _ = store_file(filename, content)

    # Use detailed description if provided, otherwise create a simple one
    description = (
        detailed_description if detailed_description else f"Attribute operation: {display_title}"
    )
    llm_desc = detailed_description if detailed_description else display_title

    return GeoDataObject(
        id=uuid.uuid4().hex,
        data_source_id="attribute",
        data_type=DataType.GEOJSON,
        data_origin=DataOrigin.TOOL,
        data_source="NaLaMapAttribute",
        data_link=url,
        name=slug,
        title=display_title,
        description=description,
        llm_description=llm_desc,
        score=0.2,
        bounding_box=None,
        layer_type="GeoJSON",
        properties=None,
    )


# ============ NEW: schema context from GeoDataFrame ============
def build_schema_context(
    gdf: gpd.GeoDataFrame,
    sample_rows: int = 5,
    topk_per_text_col: int = 12,
    max_cols: int = 40,
) -> Dict[str, Any]:
    """
    Produce a small, LLM-friendly snapshot of the table:
      - column names + dtype (geometry labeled as 'geometry')
      - for text-like columns: top-K frequent values (shortened)
      - for numeric columns: min/max (coerced)
    Geometry examples are never included.
    """
    geom_name = gdf.geometry.name if getattr(gdf, "geometry", None) is not None else None
    sample = gdf.head(sample_rows).copy()

    # Cap total columns passed, but always include geometry column
    all_cols = list(sample.columns)
    if len(all_cols) > max_cols:
        # Ensure geometry column is included even when capping
        non_geom_cols = [c for c in all_cols if c != geom_name]
        cols = non_geom_cols[: max_cols - 1]
        if geom_name:
            cols.append(geom_name)
    else:
        cols = all_cols

    # dtype map (humanized)
    dtypes = sample[cols].dtypes.astype(str).to_dict()
    if geom_name and geom_name in dtypes:
        dtypes[geom_name] = "geometry"

    cols_ctx = []
    for c in cols:
        if geom_name and c == geom_name:
            cols_ctx.append({"name": c, "type": "geometry"})
            continue

        ctype = dtypes[c]
        col_ctx = {"name": c, "type": ctype}

        # String-like -> show top-K values
        if pd.api.types.is_string_dtype(sample[c]) or ctype in ("object", "string"):
            vc = sample[c].dropna().astype(str).str.slice(0, 80)
            top_vals = vc.value_counts().head(topk_per_text_col)
            if not top_vals.empty:
                col_ctx["top_values"] = [idx for idx in top_vals.index.tolist()]
        # Numeric-like -> show min/max
        elif pd.api.types.is_numeric_dtype(sample[c]):
            s = pd.to_numeric(sample[c], errors="coerce").dropna()
            if not s.empty:
                col_ctx["min"] = float(s.min())
                col_ctx["max"] = float(s.max())

        cols_ctx.append(col_ctx)

    return {
        "row_count": int(len(gdf)),
        "geometry_column": geom_name,
        "columns": cols_ctx,
    }


# ---------- Attribute ops on GeoDataFrame ----------
def list_fields_gdf(gdf: gpd.GeoDataFrame, sample: int = 2000) -> Dict[str, Any]:
    sample_df = gdf.head(sample)
    dtypes = sample_df.dtypes.astype(str).to_dict()
    nulls = sample_df.isna().sum().to_dict()

    geom_name = gdf.geometry.name if getattr(gdf, "geometry", None) is not None else None
    # Make dtype readable
    if geom_name and geom_name in dtypes:
        dtypes[geom_name] = "geometry"

    examples: Dict[str, Any] = {}
    for c in sample_df.columns:
        if geom_name and c == geom_name:
            # Never include a geometry example in chat payloads
            examples[c] = None
            continue
        nonnull = sample_df[c].dropna()
        examples[c] = _jsonify_scalar(nonnull.iloc[0]) if not nonnull.empty else None

    fields = []
    for k in sorted(dtypes.keys()):
        fields.append(
            {
                "name": k,
                "type": dtypes[k],
                "null_count": int(nulls.get(k, 0)),
                "example": examples.get(k),  # will be None for geometry
            }
        )
    return {"fields": fields, "row_count": int(len(gdf)), "sampled": int(len(sample_df))}


def summarize_gdf(gdf: gpd.GeoDataFrame, fields: List[str]) -> Dict[str, Any]:
    out = {}
    for fld in fields:
        if fld not in gdf.columns:
            out[fld] = {"error": "field not found"}
            continue
        s = pd.to_numeric(gdf[fld], errors="coerce").dropna()
        if s.empty:
            out[fld] = {"count": 0}
            continue
        desc = s.describe()  # count, mean, std, min, 25%, 50%, 75%, max
        out[fld] = {
            "count": int(desc["count"]),
            "mean": float(desc["mean"]),
            "min": float(desc["min"]),
            "max": float(desc["max"]),
            "p25": float(desc["25%"]),
            "p50": float(desc["50%"]),
            "p75": float(desc["75%"]),
        }
    return out


def unique_values_gdf(
    gdf: gpd.GeoDataFrame, field: str, top_k: Optional[int] = None
) -> Dict[str, Any]:
    if field not in gdf.columns:
        return {"field": field, "error": "field not found"}
    counts = gdf[field].value_counts(dropna=True)
    if top_k:
        counts = counts.head(int(top_k))
    return {
        "field": field,
        "values": [
            {"value": _jsonify_scalar(idx), "count": int(val)} for idx, val in counts.items()
        ],
    }


def sort_by_gdf(gdf: gpd.GeoDataFrame, fields: List[Tuple[str, str]]) -> gpd.GeoDataFrame:
    cols = [c for c, _ in fields]
    for c in cols:
        if c not in gdf.columns:
            raise ValueError(f"Unknown field in sort_by: {c}")
    ascending = [(d or "asc").lower() != "desc" for _, d in fields]
    # Nones last: use na_position="last"
    return gdf.sort_values(by=cols, ascending=ascending, na_position="last")


def select_fields_gdf(
    gdf: gpd.GeoDataFrame, include=None, exclude=None, keep_geometry=True
) -> gpd.GeoDataFrame:
    # Start from all columns
    geom_name = gdf.geometry.name if gdf.geometry is not None else None
    cols = list(gdf.columns)
    if include:
        include = [c for c in include if c in cols or (geom_name and c == geom_name)]
        # ensure geometry column retained if keep_geometry True
        if keep_geometry and geom_name and geom_name not in include:
            include = include + [geom_name]
        gdf2 = gdf[include].copy()
    else:
        gdf2 = gdf.copy()
    if exclude:
        for c in exclude:
            if c in gdf2.columns and (not (keep_geometry and geom_name and c == geom_name)):
                gdf2 = gdf2.drop(columns=[c])
    if not keep_geometry and gdf2.geometry is not None:
        # Convert to regular DataFrame (geometry kept separately as null in export)
        gdf2 = gdf2.set_geometry(None)
    return gdf2


# ----- WHERE predicate -> boolean mask (vectorized) -----
def _series_cmp(a: pd.Series, op: str, b):
    """
    Compare series with value, handling type mismatches gracefully.

    Args:
        a: pandas Series to compare
        op: Comparison operator (=, !=, >, <, >=, <=)
        b: Value to compare against

    Returns:
        Boolean series with comparison results, False for type mismatches
    """
    # Autocast numeric comparisons sensibly
    if pd.api.types.is_numeric_dtype(a):
        b_cast = pd.to_numeric(pd.Series([b]), errors="coerce").iloc[0]
    else:
        b_cast = b

    # Handle type mismatches for relational operators
    # For non-numeric series compared to numeric values with >, <, >=, <=
    # return all False instead of crashing
    if op in (">", "<", ">=", "<="):
        if not pd.api.types.is_numeric_dtype(a) and isinstance(b, (int, float)):
            # String/object field compared to number - return all False
            logger.warning(
                f"Type mismatch: comparing non-numeric field to numeric value "
                f"with '{op}' - returning all False"
            )
            return pd.Series([False] * len(a), index=a.index)

    try:
        if op == "=":
            return a.eq(b_cast)
        if op == "!=":
            return a.ne(b_cast)
        if op == ">":
            return a.gt(b_cast)
        if op == "<":
            return a.lt(b_cast)
        if op == ">=":
            return a.ge(b_cast)
        if op == "<=":
            return a.le(b_cast)
        raise ValueError(f"Unsupported op {op}")
    except TypeError as e:
        # Catch any remaining type errors and return all False
        logger.warning(f"Type error in comparison '{op}': {e} - returning all False")
        return pd.Series([False] * len(a), index=a.index)


def _eval_ast_to_mask(
    ast, gdf: gpd.GeoDataFrame, field_suggestions: Optional[Dict[str, str]] = None
) -> pd.Series:
    """
    Evaluate AST to boolean mask with fuzzy field matching.

    Args:
        ast: Parsed WHERE clause AST
        gdf: GeoDataFrame to evaluate against
        field_suggestions: Dict to track {requested_field: actual_field} mappings

    Returns:
        Boolean series mask
    """
    if field_suggestions is None:
        field_suggestions = {}

    kind = ast[0]
    if kind == "cmp":
        _, fld, op, lit = ast
        # Try fuzzy field matching
        matched_field, is_exact = _find_closest_field(fld, list(gdf.columns))
        if matched_field is None:
            available = ", ".join(sorted(gdf.columns))
            raise ValueError(f"Field '{fld}' not found. Available fields: {available}")
        if not is_exact:
            field_suggestions[fld] = matched_field
            logger.info(f"Field '{fld}' not found, using close match '{matched_field}'")
        s = gdf[matched_field]
        m = _series_cmp(s, op, lit)
        return m.fillna(False)
    if kind == "in":
        _, fld, values = ast
        matched_field, is_exact = _find_closest_field(fld, list(gdf.columns))
        if matched_field is None:
            available = ", ".join(sorted(gdf.columns))
            raise ValueError(f"Field '{fld}' not found. Available fields: {available}")
        if not is_exact:
            field_suggestions[fld] = matched_field
            logger.info(f"Field '{fld}' not found, using close match '{matched_field}'")
        s = gdf[matched_field]
        m = s.isin(set(values))
        return m.fillna(False)
    if kind == "isnull":
        _, fld, is_not = ast
        matched_field, is_exact = _find_closest_field(fld, list(gdf.columns))
        if matched_field is None:
            available = ", ".join(sorted(gdf.columns))
            raise ValueError(f"Field '{fld}' not found. Available fields: {available}")
        if not is_exact:
            field_suggestions[fld] = matched_field
            logger.info(f"Field '{fld}' not found, using close match '{matched_field}'")
        m = gdf[matched_field].isna()
        return (~m) if is_not else m
    if kind == "and":
        return (
            _eval_ast_to_mask(ast[1], gdf, field_suggestions)
            & _eval_ast_to_mask(ast[2], gdf, field_suggestions)
        ).fillna(False)
    if kind == "or":
        return (
            _eval_ast_to_mask(ast[1], gdf, field_suggestions)
            | _eval_ast_to_mask(ast[2], gdf, field_suggestions)
        ).fillna(False)
    if kind == "not":
        return (~_eval_ast_to_mask(ast[1], gdf, field_suggestions)).fillna(False)
    raise ValueError(f"Unknown node {kind}")


def filter_where_gdf(gdf: gpd.GeoDataFrame, where: str) -> Tuple[gpd.GeoDataFrame, Dict[str, str]]:
    """
    Filter GeoDataFrame by WHERE clause with fuzzy field matching.

    Args:
        gdf: GeoDataFrame to filter
        where: WHERE clause string

    Returns:
        Tuple of (filtered_gdf, field_suggestions_dict)
        field_suggestions_dict maps {requested_field: actual_field_used}
    """
    ast = parse_where(where)
    field_suggestions: Dict[str, str] = {}
    mask = _eval_ast_to_mask(ast, gdf, field_suggestions)
    return gdf[mask].copy(), field_suggestions


def get_attribute_values_gdf(
    gdf: gpd.GeoDataFrame,
    columns: List[str],
    row_filter: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Get specific attribute values from the dataframe.

    This operation is useful for retrieving specific field values to construct
    natural language summaries (e.g., IUCN site descriptions, biodiversity assessments).

    Args:
        gdf: GeoDataFrame to query
        columns: List of column names to retrieve
        row_filter: Optional WHERE clause to filter rows first (e.g., "NAME = 'Marawah'")

    Returns:
        Dictionary with:
        - columns: Dict mapping column names to lists of values
        - row_count: Number of features in result
        - missing_columns: List of requested columns that don't exist (if any)
        - available_columns: All available columns (if any were missing)
        - field_suggestions: Dict of {requested_field: actual_field_used} for fuzzy matches

    Example:
        >>> result = get_attribute_values_gdf(
        ...     gdf,
        ...     columns=["NAME", "WDPA_PID", "DESIG_ENG", "REP_AREA"],
        ...     row_filter="NAME = 'Marawah Marine Biosphere Reserve'"
        ... )
        >>> # Result: {"columns": {"NAME": ["Marawah..."], ...}, "row_count": 1}
    """
    # Validate columns parameter
    if not columns or len(columns) == 0:
        return {
            "error": (
                "The 'columns' parameter is required and must contain " "at least one column name."
            ),
            "row_count": len(gdf),
        }

    # Apply filter if provided
    field_suggestions: Dict[str, str] = {}
    if row_filter:
        try:
            filtered_gdf, field_suggestions = filter_where_gdf(gdf, row_filter)
            if len(filtered_gdf) == 0:
                return {
                    "columns": {},
                    "error": "No features match the filter",
                    "filter": row_filter,
                    "row_count": 0,
                }
            gdf = filtered_gdf
        except Exception as e:
            return {"error": f"Filter error: {str(e)}", "filter": row_filter}

    # Get values for requested columns
    result: Dict[str, Any] = {"columns": {}}
    missing_cols = []

    for col in columns:
        # Try fuzzy matching for column names
        matched_col, is_exact = _find_closest_field(col, list(gdf.columns))
        if matched_col:
            if not is_exact:
                field_suggestions[col] = matched_col
            # Get all values for this column as a list
            values_list = gdf[matched_col].tolist()
            result["columns"][matched_col] = values_list
        else:
            missing_cols.append(col)

    # Add metadata
    result["row_count"] = int(len(gdf))

    if missing_cols:
        result["missing_columns"] = missing_cols
        result["available_columns"] = sorted([c for c in gdf.columns if c != gdf.geometry.name])

    if field_suggestions:
        result["field_suggestions"] = field_suggestions

    return result


def aggregate_attributes_across_layers(
    state: GeoDataAgentState,
    layer_names: List[str],
    columns_per_layer: Dict[str, List[str]],
    summary_type: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Aggregate attributes from multiple layers for comprehensive analysis.

    This function enables cross-layer attribute queries, useful for comparing
    data across different layers (e.g., comparing protected areas with land use).

    Args:
        state: Current agent state containing geodata_layers
        layer_names: List of layer names to query
        columns_per_layer: Dict mapping layer_name -> list of columns to retrieve
        summary_type: Optional summary type ('combine', 'compare', etc.)

    Returns:
        Dictionary with:
        - Results for each layer (layer_name -> get_attribute_values result)
        - combined_summary (if summary_type provided)

    Example:
        >>> result = aggregate_attributes_across_layers(
        ...     state,
        ...     layer_names=["Protected Areas", "Land Use"],
        ...     columns_per_layer={
        ...         "Protected Areas": ["NAME", "AREA"],
        ...         "Land Use": ["TYPE", "AREA"]
        ...     },
        ...     summary_type="compare"
        ... )
    """
    aggregated_results = {}

    for layer_name in layer_names:
        # Find and load the layer
        matching_layers = match_layer_names(state.get("geodata_layers", []), [layer_name])
        if not matching_layers:
            aggregated_results[layer_name] = {
                "error": f"Layer '{layer_name}' not found",
                "available_layers": [layer.name for layer in state.get("geodata_layers", [])],
            }
            continue

        layer = matching_layers[0]
        try:
            gdf = _load_gdf(layer.data_link)
            columns = columns_per_layer.get(layer_name, [])

            if not columns:
                aggregated_results[layer_name] = {
                    "error": f"No columns specified for layer '{layer_name}'",
                }
                continue

            result = get_attribute_values_gdf(gdf, columns)
            aggregated_results[layer_name] = result
        except Exception as e:
            aggregated_results[layer_name] = {
                "error": f"Error loading layer '{layer_name}': {str(e)}"
            }

    # Generate combined summary if needed
    if summary_type:
        combined_summary = _generate_combined_summary(aggregated_results, summary_type)
        aggregated_results["combined_summary"] = combined_summary

    return aggregated_results


def _generate_combined_summary(
    aggregated_results: Dict[str, Any], summary_type: str
) -> Dict[str, Any]:
    """
    Generate a combined summary across multiple layer results.

    Args:
        aggregated_results: Dict of layer_name -> get_attribute_values results
        summary_type: Type of summary ('combine', 'compare', 'stats')

    Returns:
        Combined summary dict
    """
    summary = {
        "summary_type": summary_type,
        "total_layers": len([k for k in aggregated_results.keys() if k != "combined_summary"]),
        "successful_layers": len(
            [
                k
                for k, v in aggregated_results.items()
                if k != "combined_summary" and "error" not in v
            ]
        ),
        "failed_layers": [],
    }

    # Collect errors
    for layer_name, result in aggregated_results.items():
        if layer_name == "combined_summary":
            continue
        if "error" in result:
            summary["failed_layers"].append({"layer": layer_name, "error": result["error"]})

    if summary_type == "compare":
        # Compare row counts across layers
        layer_counts = {}
        for layer_name, result in aggregated_results.items():
            if layer_name == "combined_summary" or "error" in result:
                continue
            layer_counts[layer_name] = result.get("row_count", 0)
        summary["layer_row_counts"] = layer_counts

    elif summary_type == "combine":
        # Combine all column names across layers
        all_columns = set()
        for layer_name, result in aggregated_results.items():
            if layer_name == "combined_summary" or "error" in result:
                continue
            if "columns" in result:
                all_columns.update(result["columns"].keys())
        summary["all_columns_across_layers"] = sorted(all_columns)

    elif summary_type == "stats":
        # Basic statistics across layers
        total_features = 0
        total_columns = 0
        for layer_name, result in aggregated_results.items():
            if layer_name == "combined_summary" or "error" in result:
                continue
            total_features += result.get("row_count", 0)
            if "columns" in result:
                total_columns += len(result["columns"])
        summary["total_features_across_layers"] = total_features
        summary["total_columns_retrieved"] = total_columns

    return summary


# ===================================
# Planner (same as before)
# ===================================
ATTR_OPS_AND_PARAMS = [
    "operation: list_fields params: ",
    "operation: summarize params: fields=<list_of_strings>",
    "operation: unique_values params: field=<string>, top_k=<number|null>",
    "operation: filter_where params: where=<CQL_lite_string>",
    "operation: select_fields params: include=<list_of_strings|null>, "
    "exclude=<list_of_strings|null>, keep_geometry=<bool|true>",
    "operation: sort_by params: fields=<list_of_[field,asc|desc]>",
    "operation: describe_dataset params: ",
    "operation: get_attribute_values params: columns=<list_of_strings>, "
    "row_filter=<CQL_lite_string|null>",
]

PLANNER_SCHEMA_EXAMPLE = """
Return ONLY JSON with EXACT structure:
{
  "operation": "<one of: list_fields | summarize | unique_values | "
  "filter_where | select_fields | sort_by | describe_dataset | get_attribute_values>",
  "params": { /* parameters for the chosen operation */ },
  "target_layer_names": ["optional layer name(s) if the user specifies which"] ,
  "result_handling": "<'chat' | 'layer'>"
}
Rules:
- If the user asks for a filter/subset, set result_handling = "layer".
- If the user wants a table/description/summary, set result_handling = "chat".
- If the user asks e.g. 'countries of layer A with gdp over 100', choose filter_where
  with where="gdp > 100" and result_handling="layer".
- If the user asks “what is this layer”, “explain/describe this dataset”, or seems unsure/naive,
  choose describe_dataset with result_handling = "chat".
- Prefer field names as they appear; do NOT invent fields. If unsure, use list_fields first
  with result_handling="chat".
- For unique categories or value counts -> unique_values (chat).
- For stats on numeric fields -> summarize (chat).
- For retrieving specific attribute values (e.g., "show me NAME and AREA")
  -> get_attribute_values (chat).
- For 'keep only columns X,Y' -> select_fields (layer).
- Sorting -> sort_by (layer).
"""


def attribute_plan_from_prompt(
    query: str, layer_meta: List[Dict[str, Any]], schema_context: Dict[str, Any], llm=None
) -> Dict[str, Any]:
    if llm is None:
        llm = get_llm()
    sys = (
        "You convert a user's natural-language request about a GeoJSON attribute table "
        "into ONE attribute operation. Use the provided COLUMN/VALUE context to pick the correct "
        "field(s) and value(s). "
        "If the referenced value clearly appears under a specific text column's top_values, "
        "use that column."
        "\nAvailable operations:\n"
        + json.dumps(ATTR_OPS_AND_PARAMS)
        + "\n"
        + PLANNER_SCHEMA_EXAMPLE
        + "\nGuidance:\n"
        "- Prefer exact matches between user-mentioned entity names and 'top_values' "
        "of text columns.\n"
        "- If multiple columns contain the same value, choose the one named like a name/label "
        "field (e.g., name, name_en, river, waterway, label).\n"
        "- If no plausible column is found, plan `list_fields` with result_handling='chat' "
        "and explain uncertainty.\n"
        "Use the provided schema_context to produce helpful explanations without guessing. "
        "Avoid inventing fields."
    )
    msg = {
        "query": query,
        "layers": [{"name": m.get("name"), "title": m.get("title")} for m in layer_meta],
        "schema_context": schema_context,  # <<--- new
    }
    messages = [SystemMessage(content=sys), HumanMessage(content=json.dumps(msg))]
    resp = llm.generate([messages])
    text = resp.generations[0][0].text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.strip().lower().startswith("json"):
            text = text.split("\n", 1)[1]
    plan = json.loads(text)
    if plan.get("operation") not in {
        "list_fields",
        "summarize",
        "unique_values",
        "filter_where",
        "select_fields",
        "sort_by",
        "describe_dataset",
        "get_attribute_values",
    }:
        raise ValueError(f"Planner chose unsupported operation: {plan.get('operation')}")
    return plan


# ===================================
# The Tool
# ===================================
@tool
def attribute_tool(
    state: Annotated[GeoDataAgentState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],  # <-- important
    target_layer_names: Optional[List[str]] = None,
) -> Union[Dict[str, Any], Command]:
    """
    Attribute table tool (GeoPandas-based) with built-in planner.
    - If result_handling='chat', replies with a ToolMessage summary.
    - If result_handling='layer', saves a new GeoJSON to uploads and appends to geodata_results.
    """
    layers = state.get("geodata_layers") or []
    messages = state.get("messages") or []
    if not layers:
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        name="attribute_tool",
                        content="Error: No geodata layers found in state. "
                        "Add/select a layer first.",
                        tool_call_id=tool_call_id,
                        status="error",
                    )
                ]
            }
        )

    layer_meta = [{"name": layer.name, "title": layer.title} for layer in layers]

    def _last_user(ms):
        for m in reversed(ms):
            if getattr(m, "type", None) == "human" or m.__class__.__name__ == "HumanMessage":
                return m.content
        return ""

    query = _last_user(messages) or ""
    selected = match_layer_names(layers, target_layer_names) if target_layer_names else layers[:1]
    if not selected:
        avail = [{"name": layer.name, "title": layer.title} for layer in layers]
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        name="attribute_tool",
                        content=f"Error: Target layer(s) not found. Available: {json.dumps(avail)}",
                        tool_call_id=tool_call_id,
                        status="error",
                    )
                ]
            }
        )
    layer = selected[0]
    if layer.data_type not in (DataType.GEOJSON, DataType.UPLOADED):
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        name="attribute_tool",
                        content=f"Error: Layer '{layer.name}' is not a GeoJSON-like dataset.",
                        tool_call_id=tool_call_id,
                        status="error",
                    )
                ]
            }
        )

    # Load as GeoDataFrame
    try:
        gdf = _load_gdf(layer.data_link)
    except Exception as e:
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        name="attribute_tool",
                        content=f"Error loading GeoJSON into GeoDataFrame: {e}",
                        tool_call_id=tool_call_id,
                        status="error",
                    )
                ]
            }
        )

    # Get LLM from state options for consistent model usage
    llm = _get_llm_from_options(state)

    schema_ctx = build_schema_context(gdf)

    # Plan
    try:
        plan = attribute_plan_from_prompt(query, layer_meta, schema_ctx, llm=llm)
    except Exception as e:
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        name="attribute_tool",
                        content=f"Error planning attribute operation: {e}",
                        tool_call_id=tool_call_id,
                        status="error",
                    )
                ]
            }
        )

    op = plan.get("operation")
    params = plan.get("params") or {}
    # result_handling = plan.get("result_handling") or "chat"  # Not used in current logic

    # Validate fields where meaningful
    def _check_fields(names: List[str]) -> List[str]:
        return [n for n in names if n not in gdf.columns]

    try:
        if op == "list_fields":
            out = list_fields_gdf(gdf)
            return Command(
                update={
                    "messages": [
                        ToolMessage(
                            name="attribute_tool",
                            content=json.dumps(
                                {"operation": "list_fields", "layer": layer.name, "result": out}
                            ),
                            tool_call_id=tool_call_id,
                        )
                    ]
                }
            )

        if op == "summarize":
            missing = _check_fields(params.get("fields", []))
            if missing:
                return Command(
                    update={
                        "messages": [
                            ToolMessage(
                                name="attribute_tool",
                                content=(
                                    f"Error: Unknown fields in summarize: {missing}. "
                                    f"Available: {sorted(gdf.columns.tolist())}"
                                ),
                                tool_call_id=tool_call_id,
                                status="error",
                            )
                        ]
                    }
                )
            out = summarize_gdf(gdf, params.get("fields", []))
            return Command(
                update={
                    "messages": [
                        ToolMessage(
                            name="attribute_tool",
                            content=json.dumps(
                                {"operation": "summarize", "layer": layer.name, "result": out}
                            ),
                            tool_call_id=tool_call_id,
                        )
                    ]
                }
            )

        if op == "unique_values":
            fld = params.get("field")
            if not fld or fld not in gdf.columns:
                return Command(
                    update={
                        "messages": [
                            ToolMessage(
                                name="attribute_tool",
                                content=(
                                    f"Error: Unknown field '{fld}'. "
                                    f"Available: {sorted(gdf.columns.tolist())}"
                                ),
                                tool_call_id=tool_call_id,
                                status="error",
                            )
                        ]
                    }
                )
            out = unique_values_gdf(gdf, fld, params.get("top_k"))
            return Command(
                update={
                    "messages": [
                        ToolMessage(
                            name="attribute_tool",
                            content=json.dumps(
                                {"operation": "unique_values", "layer": layer.name, "result": out}
                            ),
                            tool_call_id=tool_call_id,
                        )
                    ]
                }
            )

        if op == "filter_where":
            field_suggestions = {}
            try:
                out_gdf, field_suggestions = filter_where_gdf(gdf, params["where"])
            except Exception as e:
                return Command(
                    update={
                        "messages": [
                            ToolMessage(
                                name="attribute_tool",
                                content=(
                                    f"Error parsing/applying WHERE: {e}. "
                                    f"Available fields: {sorted(gdf.columns.tolist())}"
                                ),
                                tool_call_id=tool_call_id,
                                status="error",
                            )
                        ]
                    }
                )

            # Check if filter returned any features
            if len(out_gdf) == 0:
                return Command(
                    update={
                        "messages": [
                            ToolMessage(
                                name="attribute_tool",
                                content=(
                                    f"Filter applied to '{layer.name}' but no features matched "
                                    f"the condition: {params['where']}. "
                                    f"Original layer had {len(gdf)} features."
                                ),
                                tool_call_id=tool_call_id,
                            )
                        ]
                    }
                )

            title = f"{layer.title or layer.name} (filtered)"

            # Create detailed description
            detailed_desc = (
                f"Filtered features from '{layer.title or layer.name}' using condition: "
                f"{params['where']}. Result contains {len(out_gdf)} feature(s) out of "
                f"{len(gdf)} original features."
            )

            obj = _save_gdf_as_geojson(
                out_gdf, title, keep_geometry=True, detailed_description=detailed_desc
            )
            new_results = (state.get("geodata_results") or []) + [obj]

            # Build actionable layer info with field suggestions
            actionable_layer_info = {
                "name": obj.name,
                "title": obj.title,
                "id": obj.id,
                "data_source_id": obj.data_source_id,
                "feature_count": len(out_gdf),
                "original_count": len(gdf),
                "filter": params["where"],
            }

            # Add field suggestion info if fuzzy matching was used
            suggestion_info = ""
            if field_suggestions:
                suggestion_info = "\n\nNote: Field name corrections were applied:\n" + "\n".join(
                    [f"  - '{req}' → '{actual}'" for req, actual in field_suggestions.items()]
                )

            # Provide user guidance similar to geocoding tools
            tool_message_content = (
                f"Successfully filtered '{layer.name}' using condition: {params['where']}. "
                f"Result contains {len(out_gdf)} feature(s) out of {len(gdf)} original features. "
                f"New layer '{obj.title}' created and stored in geodata_results. "
                f"Actionable layer details: {json.dumps(actionable_layer_info)}. "
                f"{suggestion_info}"
                f"User response guidance: Call 'set_result_list' to make this filtered layer "
                f"available for the user to select. In your textual response to the user, "
                f"confirm the filtering success and mention the number of features that matched. "
                f"State that the filtered layer is now listed and can be selected by the user "
                f"to be added to the map. Ensure your response clearly indicates the user needs "
                f"to take an action to add the layer to the map. Do NOT state or imply that the "
                f"layer has already been added to the map. Do NOT include direct file paths, "
                f"sandbox links, or any other internal storage paths in your textual response."
            )

            return Command(
                update={
                    "messages": [
                        ToolMessage(
                            name="attribute_tool",
                            content=tool_message_content,
                            tool_call_id=tool_call_id,
                        )
                    ],
                    "geodata_results": new_results,
                }
            )

        if op == "select_fields":
            include = params.get("include")
            exclude = params.get("exclude")
            missing = _check_fields((include or []) + (exclude or []))
            if missing:
                return Command(
                    update={
                        "messages": [
                            ToolMessage(
                                name="attribute_tool",
                                content=(
                                    f"Error: Unknown fields in select_fields: {missing}. "
                                    f"Available: {sorted(gdf.columns.tolist())}"
                                ),
                                tool_call_id=tool_call_id,
                                status="error",
                            )
                        ]
                    }
                )
            keep_geometry = bool(params.get("keep_geometry", True))
            out_gdf = select_fields_gdf(
                gdf, include=include, exclude=exclude, keep_geometry=keep_geometry
            )

            # Create detailed description
            field_info = []
            if include:
                field_info.append(f"included fields: {', '.join(include)}")
            if exclude:
                field_info.append(f"excluded fields: {', '.join(exclude)}")
            detailed_desc = (
                f"Selected fields from '{layer.title or layer.name}'. "
                f"{'; '.join(field_info) if field_info else 'Field selection applied'}. "
                f"Result has {len(out_gdf.columns)} columns."
            )

            obj = _save_gdf_as_geojson(
                out_gdf,
                f"{layer.name}-selected",
                keep_geometry=keep_geometry,
                detailed_description=detailed_desc,
            )
            new_results = (state.get("geodata_results") or []) + [obj]
            return Command(
                update={
                    "messages": [
                        ToolMessage(
                            name="attribute_tool",
                            content=f"Projection applied. New layer: {obj.title}",
                            tool_call_id=tool_call_id,
                        )
                    ],
                    "geodata_results": new_results,
                }
            )

        if op == "sort_by":
            fields = params.get("fields", [])
            out_gdf = sort_by_gdf(gdf, fields)

            # Create detailed description
            sort_desc = ", ".join([f"{fld} {order}" for fld, order in fields])
            detailed_desc = (
                f"Sorted '{layer.title or layer.name}' by: {sort_desc}. "
                f"Result contains {len(out_gdf)} features in sorted order."
            )

            obj = _save_gdf_as_geojson(
                out_gdf,
                f"{layer.name}-sorted",
                keep_geometry=True,
                detailed_description=detailed_desc,
            )
            new_results = (state.get("geodata_results") or []) + [obj]
            return Command(
                update={
                    "messages": [
                        ToolMessage(
                            name="attribute_tool",
                            content=f"Sorting applied. New layer: {obj.title}",
                            tool_call_id=tool_call_id,
                        )
                    ],
                    "geodata_results": new_results,
                }
            )

        if op == "describe_dataset":
            # Use schema context + gdf to produce a friendly overview
            out = describe_dataset_gdf(gdf, schema_ctx, llm=llm)
            # Optional: add a short, humanized paragraph on top
            # out["summary"] already has a one-liner; keep the payload JSON-safe.
            return Command(
                update={
                    "messages": [
                        ToolMessage(
                            name="attribute_tool",
                            content=json.dumps(
                                {
                                    "operation": "describe_dataset",
                                    "layer": layer.name,
                                    "result": out,
                                }
                            ),
                            tool_call_id=tool_call_id,
                        )
                    ]
                }
            )

        if op == "get_attribute_values":
            columns = params.get("columns", [])
            row_filter = params.get("row_filter")

            # Validate columns parameter
            if not columns:
                return Command(
                    update={
                        "messages": [
                            ToolMessage(
                                name="attribute_tool",
                                content=(
                                    "Error: 'columns' parameter is required for "
                                    "get_attribute_values operation."
                                ),
                                tool_call_id=tool_call_id,
                                status="error",
                            )
                        ]
                    }
                )

            # Execute the operation
            try:
                out = get_attribute_values_gdf(gdf, columns, row_filter)
            except Exception as e:
                return Command(
                    update={
                        "messages": [
                            ToolMessage(
                                name="attribute_tool",
                                content=(
                                    f"Error retrieving attribute values: {e}. "
                                    f"Available fields: {sorted(gdf.columns.tolist())}"
                                ),
                                tool_call_id=tool_call_id,
                                status="error",
                            )
                        ]
                    }
                )

            # Check if operation was successful
            if out.get("error"):
                return Command(
                    update={
                        "messages": [
                            ToolMessage(
                                name="attribute_tool",
                                content=(
                                    f"Error: {out['error']}. "
                                    f"Suggestions: {', '.join(out.get('suggestions', []))}"
                                ),
                                tool_call_id=tool_call_id,
                                status="error",
                            )
                        ]
                    }
                )

            # Return successful result
            return Command(
                update={
                    "messages": [
                        ToolMessage(
                            name="attribute_tool",
                            content=json.dumps(
                                {
                                    "operation": "get_attribute_values",
                                    "layer": layer.name,
                                    "result": out,
                                }
                            ),
                            tool_call_id=tool_call_id,
                        )
                    ]
                }
            )

        return Command(
            update={
                "messages": [
                    ToolMessage(
                        name="attribute_tool",
                        content=f"Error: Unsupported operation '{op}'.",
                        tool_call_id=tool_call_id,
                        status="error",
                    )
                ]
            }
        )

    except Exception as e:
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        name="attribute_tool",
                        content=f"Error executing attribute op '{op}': {e}",
                        tool_call_id=tool_call_id,
                        status="error",
                    )
                ]
            }
        )
