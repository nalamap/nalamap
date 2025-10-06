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
from services.ai.llm_config import get_llm
from services.storage.file_management import store_file
from services.tools.utils import match_layer_names

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# =========================
# CQL-lite tokenizer/parser
# =========================
_token = re.compile(
    r"""
    \s*(?:
        (?P<ident>[A-Za-z_][A-Za-z0-9_]*)
      | "(?P<identq>[^"]+)"
      | '(?P<string>[^']*)'
      | (?P<num>-?\d+(?:\.\d+)?)
      | (?P<op>>=|<=|!=|=|>|<)
      | (?P<kw>AND|OR|NOT|IN|IS|NULL)
      | (?P<lpar>\()
      | (?P<rpar>\))
      | (?P<comma>,)
    )
""",
    re.X,
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


def _suggest_next_steps(gdf: gpd.GeoDataFrame, schema_ctx: Dict[str, Any]) -> List[str]:
    tips = []
    # Note: geometry name could be used for field-specific suggestions if needed
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
        llm = get_llm()
        sys = (
            "You are a GIS data analysis assistant. "
            "Given the dataset context, suggest up to 6 concrete next steps for analysis or visualization."
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
            lines = [l.strip(" -") for l in text.splitlines() if l.strip()]
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


def describe_dataset_gdf(gdf: gpd.GeoDataFrame, schema_ctx: Dict[str, Any]) -> Dict[str, Any]:
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
        summary += f" Bounding box: [{bbox_vals[0]:.4f}, {bbox_vals[1]:.4f}, {bbox_vals[2]:.4f}, {bbox_vals[3]:.4f}]."

    next_steps = _suggest_next_steps(gdf, schema_ctx)
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
            "Respond in JSON with keys 'summary' (string) and 'suggested_next_steps' (list of strings)."
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
    if not (cur and cur.group("kw") == kw):
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
        if cur and cur.group("kw") == "IS":
            _advance(state, state["tokens"])
            cur = _peek(state)
            is_not = False
            if cur and cur.group("kw") == "NOT":
                is_not = True
                _advance(state, state["tokens"])
            _expect_kw(state, "NULL")
            return ("isnull", field, is_not)
        if cur and cur.group("kw") == "IN":
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
    if cur and cur.group("kw") == "NOT":
        _advance(state, state["tokens"])
        node = _parse_not(state)
        return ("not", node)
    return _parse_primary(state)


def _parse_and(state):
    node = _parse_not(state)
    while _peek(state) and _peek(state).group("kw") == "AND":
        _advance(state, state["tokens"])
        rhs = _parse_not(state)
        node = ("and", node, rhs)
    return node


def _parse_expr(state):
    node = _parse_and(state)
    while _peek(state) and _peek(state).group("kw") == "OR":
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
        # Download to temp file for reliable driver support
        resp = requests.get(link, timeout=30)
        resp.raise_for_status()
        tmp = os.path.join(LOCAL_UPLOAD_DIR, f"tmp_{uuid.uuid4().hex[:8]}.geojson")
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
    geom_col = gdf.geometry.name if keep_geometry and gdf.geometry is not None else None

    # Build clean properties (only JSON-serializable)
    prop_cols = [c for c in gdf.columns if c != geom_col] if geom_col else list(gdf.columns)
    for _, row in gdf.iterrows():
        props = {c: _jsonify_scalar(row[c]) for c in prop_cols}
        geom = mapping(row[geom_col]) if geom_col else None
        features.append({"type": "Feature", "properties": props, "geometry": geom})
    return {"type": "FeatureCollection", "features": features}


def _slug(text: str) -> str:
    text = (text or "attribute-result").lower().strip()
    text = re.sub(r"[^a-z0-9\-_ ]+", "", text).replace(" ", "-")
    text = re.sub(r"-+", "-", text).strip("-")
    return text or "attribute-result"


def _save_gdf_as_geojson(
    gdf: gpd.GeoDataFrame, display_title: str, keep_geometry: bool = True
) -> GeoDataObject:
    """Save a GeoDataFrame as GeoJSON using central file management."""
    fc = _fc_from_gdf(gdf, keep_geometry=keep_geometry)
    slug = _slug(display_title)
    filename = f"{slug}_{uuid.uuid4().hex[:8]}.geojson"

    # Convert to JSON bytes
    content = json.dumps(fc).encode("utf-8")

    # Use central file management (supports both local and Azure Blob)
    url, _ = store_file(filename, content)

    return GeoDataObject(
        id=uuid.uuid4().hex,
        data_source_id="attribute",
        data_type=DataType.GEOJSON,
        data_origin=DataOrigin.TOOL,
        data_source="NaLaMapAttribute",
        data_link=url,
        name=slug,
        title=display_title,
        description=f"Attribute operation: {display_title}",
        llm_description=display_title,
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

    # Cap total columns passed
    cols = list(sample.columns)[:max_cols]

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
    # Autocast numeric comparisons sensibly
    if pd.api.types.is_numeric_dtype(a):
        b_cast = pd.to_numeric(pd.Series([b]), errors="coerce").iloc[0]
    else:
        b_cast = b
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


def _eval_ast_to_mask(ast, gdf: gpd.GeoDataFrame) -> pd.Series:
    kind = ast[0]
    if kind == "cmp":
        _, fld, op, lit = ast
        if fld not in gdf.columns:
            raise ValueError(f"Unknown field: {fld}")
        s = gdf[fld]
        m = _series_cmp(s, op, lit)
        return m.fillna(False)
    if kind == "in":
        _, fld, values = ast
        if fld not in gdf.columns:
            raise ValueError(f"Unknown field: {fld}")
        s = gdf[fld]
        m = s.isin(set(values))
        return m.fillna(False)
    if kind == "isnull":
        _, fld, is_not = ast
        if fld not in gdf.columns:
            raise ValueError(f"Unknown field: {fld}")
        m = gdf[fld].isna()
        return (~m) if is_not else m
    if kind == "and":
        return (_eval_ast_to_mask(ast[1], gdf) & _eval_ast_to_mask(ast[2], gdf)).fillna(False)
    if kind == "or":
        return (_eval_ast_to_mask(ast[1], gdf) | _eval_ast_to_mask(ast[2], gdf)).fillna(False)
    if kind == "not":
        return (~_eval_ast_to_mask(ast[1], gdf)).fillna(False)
    raise ValueError(f"Unknown node {kind}")


def filter_where_gdf(gdf: gpd.GeoDataFrame, where: str) -> gpd.GeoDataFrame:
    ast = parse_where(where)
    mask = _eval_ast_to_mask(ast, gdf)
    return gdf[mask].copy()


# ===================================
# Planner (same as before)
# ===================================
ATTR_OPS_AND_PARAMS = [
    "operation: list_fields params: ",
    "operation: summarize params: fields=<list_of_strings>",
    "operation: unique_values params: field=<string>, top_k=<number|null>",
    "operation: filter_where params: where=<CQL_lite_string>",
    "operation: select_fields params: include=<list_of_strings|null>, exclude=<list_of_strings|null>, keep_geometry=<bool|true>",
    "operation: sort_by params: fields=<list_of_[field,asc|desc]>",
    "operation: describe_dataset params: ",
]

PLANNER_SCHEMA_EXAMPLE = """
Return ONLY JSON with EXACT structure:
{
  "operation": "<one of: list_fields | summarize | unique_values | filter_where | select_fields | sort_by | describe_dataset>",
  "params": { /* parameters for the chosen operation */ },
  "target_layer_names": ["optional layer name(s) if the user specifies which"] ,
  "result_handling": "<'chat' | 'layer'>"
}
Rules:
- If the user asks for a filter/subset, set result_handling = "layer".
- If the user wants a table/description/summary, set result_handling = "chat".
- If the user asks e.g. 'countries of layer A with gdp over 100', choose filter_where with where="gdp > 100" and result_handling="layer".
- If the user asks “what is this layer”, “explain/describe this dataset”, or seems unsure/naive, choose describe_dataset with result_handling = "chat".
- Prefer field names as they appear; do NOT invent fields. If unsure, use list_fields first with result_handling="chat".
- For unique categories or value counts -> unique_values (chat).
- For stats on numeric fields -> summarize (chat).
- For 'keep only columns X,Y' -> select_fields (layer).
- Sorting -> sort_by (layer).
"""


def attribute_plan_from_prompt(
    query: str, layer_meta: List[Dict[str, Any]], schema_context: Dict[str, Any]
) -> Dict[str, Any]:
    llm = get_llm()
    sys = (
        "You convert a user's natural-language request about a GeoJSON attribute table "
        "into ONE attribute operation. Use the provided COLUMN/VALUE context to pick the correct field(s) and value(s). "
        "If the referenced value clearly appears under a specific text column's top_values, use that column."
        "\nAvailable operations:\n"
        + json.dumps(ATTR_OPS_AND_PARAMS)
        + "\n"
        + PLANNER_SCHEMA_EXAMPLE
        + "\nGuidance:\n"
        "- Prefer exact matches between user-mentioned entity names and 'top_values' of text columns.\n"
        "- If multiple columns contain the same value, choose the one named like a name/label field (e.g., name, name_en, river, waterway, label).\n"
        "- If no plausible column is found, plan `list_fields` with result_handling='chat' and explain uncertainty.\n"
        "Use the provided schema_context to produce helpful explanations without guessing. Avoid inventing fields."
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
                        content="Error: No geodata layers found in state. Add/select a layer first.",
                        tool_call_id=tool_call_id,
                        status="error",
                    )
                ]
            }
        )

    layer_meta = [{"name": l.name, "title": l.title} for l in layers]

    def _last_user(ms):
        for m in reversed(ms):
            if getattr(m, "type", None) == "human" or m.__class__.__name__ == "HumanMessage":
                return m.content
        return ""

    query = _last_user(messages) or ""
    selected = match_layer_names(layers, target_layer_names) if target_layer_names else layers[:1]
    if not selected:
        avail = [{"name": l.name, "title": l.title} for l in layers]
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
    schema_ctx = build_schema_context(gdf)

    # Plan
    try:
        plan = attribute_plan_from_prompt(query, layer_meta, schema_ctx)
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
                                content=f"Error: Unknown fields in summarize: {missing}. Available: {sorted(gdf.columns.tolist())}",
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
                                content=f"Error: Unknown field '{fld}'. Available: {sorted(gdf.columns.tolist())}",
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
            try:
                out_gdf = filter_where_gdf(gdf, params["where"])
            except Exception as e:
                return Command(
                    update={
                        "messages": [
                            ToolMessage(
                                name="attribute_tool",
                                content=f"Error parsing/applying WHERE: {e}. Available fields: {sorted(gdf.columns.tolist())}",
                                tool_call_id=tool_call_id,
                                status="error",
                            )
                        ]
                    }
                )
            title = f"{layer.name}-filtered"
            obj = _save_gdf_as_geojson(out_gdf, title, keep_geometry=True)
            new_results = (state.get("geodata_results") or []) + [obj]
            return Command(
                update={
                    "messages": [
                        ToolMessage(
                            name="attribute_tool",
                            content=f"Filter applied. New layer: {obj.title}",
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
                                content=f"Error: Unknown fields in select_fields: {missing}. Available: {sorted(gdf.columns.tolist())}",
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
            obj = _save_gdf_as_geojson(
                out_gdf, f"{layer.name}-selected", keep_geometry=keep_geometry
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
            obj = _save_gdf_as_geojson(out_gdf, f"{layer.name}-sorted", keep_geometry=True)
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
            out = describe_dataset_gdf(gdf, schema_ctx)
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
