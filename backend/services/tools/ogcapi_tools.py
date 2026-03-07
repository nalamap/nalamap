import hashlib
import json
import logging
import os
from os import path as osp
from difflib import SequenceMatcher
import re
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union
from urllib.parse import urlparse, urlunparse

import requests
from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool, tool
from langchain_core.tools.base import InjectedToolCallId
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from typing_extensions import Annotated

from core.config import OGCAPI_BASE_URL, OGCAPI_TIMEOUT_SECONDS
from models.geodata import DataOrigin, DataType, GeoDataObject
from models.states import GeoDataAgentState

logger = logging.getLogger(__name__)

SUPPORTED_OUTPUT_MODES = {"features", "ids", "feature_ref", "stats_only"}
_SESSION_CACHE: Dict[str, Dict[str, Any]] = {}
_JOB_RESULTS_PATH_RE = re.compile(r"/processes/[^/]+/jobs/[^/]+/results")
_EXPLICIT_LAYER_REFS_JSON_RE = re.compile(
    r"\[EXPLICIT_LAYER_REFS_JSON\](.*?)\[/EXPLICIT_LAYER_REFS_JSON\]",
    flags=re.IGNORECASE | re.DOTALL,
)
_SINGLE_SOURCE_INPUT_KEYS = ("collection_id", "feature_collection", "feature_collection_path")
_SINGLE_SOURCE_PROCESSES = {"vector-buffer", "vector-clip", "vector-dissolve", "vector-simplify"}
_PROCESS_ID_ALIASES = {
    "buffer_geometries": "vector-buffer",
    "clip_geometries": "vector-clip",
    "dissolve_geometries": "vector-dissolve",
    "simplify_geometries": "vector-simplify",
    "spatial_join_geometries": "vector-spatial-join",
    "nearest_geometries": "vector-nearest",
}


@dataclass
class OGCAPIServerRuntime:
    url: str
    request_url: str
    name: Optional[str] = None
    description: Optional[str] = None
    api_key: Optional[str] = None
    headers: Optional[Dict[str, str]] = None


def _log_event(event: str, **kwargs: Any) -> None:
    payload = {"event": event, **kwargs}
    logger.info(json.dumps(payload, default=str))


def _normalize_url(url: str) -> str:
    return (url or "").strip().rstrip("/")


def _is_container_runtime() -> bool:
    return os.path.exists("/.dockerenv")


def _runtime_request_url(configured_url: str) -> str:
    normalized = _normalize_url(configured_url)
    parsed = urlparse(normalized)
    hostname = (parsed.hostname or "").lower()
    if hostname not in {"localhost", "127.0.0.1", "::1"} or not _is_container_runtime():
        return normalized

    configured_fallback = _normalize_url(OGCAPI_BASE_URL)
    fallback_parsed = urlparse(configured_fallback) if configured_fallback else None
    if fallback_parsed and fallback_parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        remapped = parsed._replace(
            scheme=fallback_parsed.scheme or parsed.scheme or "http",
            netloc=fallback_parsed.netloc,
        )
        if parsed.path in {"", "/"} and fallback_parsed.path:
            remapped = remapped._replace(path=fallback_parsed.path)
        runtime_url = _normalize_url(urlunparse(remapped))
        _log_event(
            "ogcapi.server_url.remapped",
            configured_url=normalized,
            runtime_url=runtime_url,
            reason="container_localhost_unreachable",
        )
        return runtime_url

    default_alias = parsed._replace(
        scheme=parsed.scheme or "http",
        netloc="ogcapi:8000",
    )
    if parsed.path in {"", "/"}:
        default_alias = default_alias._replace(path="/v1")
    runtime_url = _normalize_url(urlunparse(default_alias))
    _log_event(
        "ogcapi.server_url.remapped",
        configured_url=normalized,
        runtime_url=runtime_url,
        reason="container_default_ogcapi_alias",
    )
    return runtime_url


def _safe_session_token(session_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "", session_id or "session")[:64] or "session"


def _session_bucket(session_id: str) -> Dict[str, Any]:
    bucket = _SESSION_CACHE.setdefault(
        session_id,
        {
            "servers": {},
            "filtered": {},
            "results": {},
            "process_runs": {},
        },
    )
    return bucket


def _server_key(server: OGCAPIServerRuntime) -> str:
    return server.name or server.url


def _headers_for_server(
    server: OGCAPIServerRuntime, extra_headers: Optional[Dict[str, str]] = None
) -> Dict[str, str]:
    headers: Dict[str, str] = {}
    if server.api_key:
        headers["Authorization"] = f"Bearer {server.api_key}"
    if server.headers:
        headers.update(server.headers)
    if extra_headers:
        headers.update(extra_headers)
    return headers


def _strip_suffix_path(url: str, suffix_path: str) -> str:
    if not suffix_path:
        return _normalize_url(url)
    parsed = urlparse(url)
    path = parsed.path or ""
    if not path.endswith(suffix_path):
        return _normalize_url(url)
    new_path = path[: -len(suffix_path)] or "/"
    stripped = parsed._replace(path=new_path, params="", query="", fragment="")
    return _normalize_url(urlunparse(stripped))


def _join_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def _candidate_capabilities_urls(base_url: str) -> List[str]:
    normalized = _normalize_url(base_url)
    candidates = [_join_url(normalized, "/agent/capabilities")]
    if not normalized.endswith("/v1"):
        candidates.append(_join_url(normalized, "/v1/agent/capabilities"))
    return candidates


def _extract_request_context(resp: requests.Response) -> Dict[str, Optional[str]]:
    return {
        "request_id": resp.headers.get("x-request-id"),
        "trace_id": resp.headers.get("x-trace-id"),
    }


def _request_json(
    method: str,
    url: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, Any]] = None,
    json_body: Optional[Dict[str, Any]] = None,
    retries: int = 1,
) -> Tuple[requests.Response, Any]:
    timeout_seconds = max(5.0, float(OGCAPI_TIMEOUT_SECONDS))
    last_exc: Optional[Exception] = None

    for attempt in range(retries + 1):
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=json_body,
                timeout=timeout_seconds,
            )
            try:
                payload = response.json()
            except ValueError:
                payload = {"detail": response.text}

            if (
                response.status_code >= 500
                and attempt < retries
                and method.upper() in {"GET", "POST"}
            ):
                _log_event(
                    "ogcapi.http.retry",
                    method=method,
                    url=url,
                    status=response.status_code,
                    attempt=attempt + 1,
                )
                continue
            return response, payload
        except requests.RequestException as exc:
            last_exc = exc
            if attempt < retries:
                continue
            raise

    if last_exc:
        raise last_exc
    raise RuntimeError("Unexpected HTTP request failure")


def _error_payload(
    *,
    code: str,
    message: str,
    recoverable: bool = True,
    retryable: bool = False,
    suggested_action: str = "",
    detail: Any = None,
    request_context: Optional[Dict[str, Optional[str]]] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "status": "error",
        "error": {
            "code": code,
            "message": message,
            "recoverable": recoverable,
            "retryable": retryable,
            "suggestedAction": suggested_action or "inspect_server_logs",
        },
    }
    if detail is not None:
        payload["detail"] = detail
    if request_context:
        payload["error"]["requestId"] = request_context.get("request_id")
        payload["error"]["traceId"] = request_context.get("trace_id")
    return payload


def _error_command(
    tool_name: str,
    tool_call_id: str,
    *,
    code: str,
    message: str,
    recoverable: bool = True,
    retryable: bool = False,
    suggested_action: str = "",
    detail: Any = None,
    request_context: Optional[Dict[str, Optional[str]]] = None,
) -> Command:
    payload = _error_payload(
        code=code,
        message=message,
        recoverable=recoverable,
        retryable=retryable,
        suggested_action=suggested_action,
        detail=detail,
        request_context=request_context,
    )
    return Command(
        update={
            "messages": [
                ToolMessage(
                    name=tool_name,
                    content=json.dumps(payload, default=str),
                    tool_call_id=tool_call_id,
                    status="error",
                )
            ]
        }
    )


def _success_command(
    tool_name: str,
    tool_call_id: str,
    payload: Dict[str, Any],
    geodata_results: Optional[List[GeoDataObject]] = None,
) -> Command:
    update: Dict[str, Any] = {
        "messages": [
            ToolMessage(
                name=tool_name,
                content=json.dumps(payload, default=str),
                tool_call_id=tool_call_id,
            )
        ]
    }
    if geodata_results is not None:
        update["geodata_results"] = geodata_results
    return Command(update=update)


def _resolve_session_id(state: GeoDataAgentState, fallback: Optional[str]) -> str:
    options = state.get("options")
    if options is not None:
        if hasattr(options, "session_id") and getattr(options, "session_id"):
            return str(getattr(options, "session_id"))
        if isinstance(options, dict) and options.get("session_id"):
            return str(options["session_id"])
    return fallback or "default-session"


def _resolve_server(
    servers: List[OGCAPIServerRuntime], selector: Optional[str]
) -> Optional[OGCAPIServerRuntime]:
    if not servers:
        return None
    if not selector:
        return servers[0]
    normalized = selector.strip().lower()
    for server in servers:
        if server.url.lower() == normalized:
            return server
        if server.name and server.name.lower() == normalized:
            return server
    return None


def _ensure_manifest_cached(
    bucket: Dict[str, Any],
    server: OGCAPIServerRuntime,
    *,
    force_refresh: bool = False,
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    server_key = _server_key(server)
    server_cache = bucket["servers"].setdefault(server_key, {})
    if server_cache.get("manifest") and not force_refresh:
        return server_cache, None

    etag = server_cache.get("etag")
    extra_headers = {}
    if etag and force_refresh:
        extra_headers["If-None-Match"] = etag

    last_response: Optional[requests.Response] = None
    last_payload: Any = None

    for candidate in _candidate_capabilities_urls(server.request_url):
        response, payload = _request_json(
            "GET",
            candidate,
            headers=_headers_for_server(server, extra_headers),
            retries=1,
        )
        last_response = response
        last_payload = payload

        if response.status_code == 304 and server_cache.get("manifest"):
            _log_event(
                "ogcapi.capabilities.not_modified",
                server=server.url,
                etag=etag,
            )
            return server_cache, None

        if response.status_code == 200 and isinstance(payload, dict):
            api_prefix = payload.get("service", {}).get("apiPrefix")
            if not api_prefix:
                parsed = urlparse(candidate)
                suffix = "/agent/capabilities"
                api_prefix = parsed.path[: -len(suffix)] if parsed.path.endswith(suffix) else ""
            if api_prefix == "/":
                api_prefix = ""

            base_root = _strip_suffix_path(server.request_url, api_prefix or "")
            server_cache.update(
                {
                    "manifest": payload,
                    "etag": response.headers.get("ETag"),
                    "api_prefix": api_prefix or "",
                    "base_root_url": base_root,
                    "refreshed_at": time.time(),
                }
            )
            _log_event(
                "ogcapi.capabilities.cached",
                server=server.url,
                api_prefix=server_cache.get("api_prefix"),
                etag=server_cache.get("etag"),
            )
            return server_cache, None

    context = _extract_request_context(last_response) if last_response else None
    detail = last_payload if last_payload is not None else "Unable to fetch manifest"
    return None, _error_payload(
        code="capabilities_unavailable",
        message="Failed to fetch OGC API capabilities manifest.",
        recoverable=True,
        retryable=True,
        suggested_action="verify_ogc_server_url_and_retry",
        detail=detail,
        request_context=context,
    )


def _endpoint_url(server_cache: Dict[str, Any], path: str) -> str:
    prefix = server_cache.get("api_prefix", "") or ""
    base_root = server_cache.get("base_root_url", "") or ""
    effective_path = f"{prefix.rstrip('/')}{path}" if prefix else path
    return _join_url(base_root, effective_path)


def _public_endpoint_url(
    server_cache: Dict[str, Any], server: OGCAPIServerRuntime, path: str
) -> str:
    prefix = server_cache.get("api_prefix", "") or ""
    configured_root = _strip_suffix_path(server.url, prefix or "")
    effective_path = f"{prefix.rstrip('/')}{path}" if prefix else path
    return _join_url(configured_root, effective_path)


def _manifest_process_ids(server_cache: Dict[str, Any]) -> List[str]:
    manifest = server_cache.get("manifest") or {}
    items = (manifest.get("capabilities") or {}).get("processes") or []
    process_ids: List[str] = []
    seen: set[str] = set()
    for item in items:
        process_id = item.get("id") if isinstance(item, dict) else None
        if not isinstance(process_id, str):
            continue
        cleaned = process_id.strip()
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        process_ids.append(cleaned)
    return process_ids


def _normalize_process_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _suggest_process_ids(process_id: str, available_process_ids: List[str]) -> List[str]:
    request_tokens = {
        token
        for token in re.split(r"[^a-z0-9]+", process_id.lower())
        if token and token not in {"vector", "process", "geometry", "geometries"}
    }
    scored: List[Tuple[float, str]] = []
    normalized_request = _normalize_process_key(process_id)
    for candidate in available_process_ids:
        candidate_tokens = {
            token
            for token in re.split(r"[^a-z0-9]+", candidate.lower())
            if token and token not in {"vector", "process", "geometry", "geometries"}
        }
        overlap = len(request_tokens & candidate_tokens)
        similarity = SequenceMatcher(
            None, normalized_request, _normalize_process_key(candidate)
        ).ratio()
        score = (overlap * 2.0) + similarity
        if score >= 0.6:
            scored.append((score, candidate))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [candidate for _score, candidate in scored[:5]]


def _resolve_process_id(
    process_id: str, available_process_ids: List[str]
) -> Tuple[Optional[str], List[str], str]:
    requested = (process_id or "").strip()
    if not requested:
        return None, [], "empty"

    for candidate in available_process_ids:
        if candidate.lower() == requested.lower():
            return candidate, [], "exact"

    alias_target = _PROCESS_ID_ALIASES.get(requested.lower())
    if alias_target:
        for candidate in available_process_ids:
            if candidate.lower() == alias_target.lower():
                return candidate, [], "alias"

    normalized = _normalize_process_key(requested)
    for candidate in available_process_ids:
        if _normalize_process_key(candidate) == normalized:
            return candidate, [], "normalized"

    return None, _suggest_process_ids(requested, available_process_ids), "unknown"


def _collection_exists(
    server_cache: Dict[str, Any], server: OGCAPIServerRuntime, collection_id: str
) -> bool:
    url = _endpoint_url(server_cache, f"/collections/{collection_id}")
    try:
        response, _payload = _request_json(
            "GET",
            url,
            headers=_headers_for_server(server),
            retries=0,
        )
    except requests.RequestException:
        return False
    return response.status_code < 400


def _choose_collection_id(
    collections_payload: Any, requested_collection: Optional[str]
) -> Optional[str]:
    collections = []
    if isinstance(collections_payload, dict):
        collections = collections_payload.get("collections") or []
    if not isinstance(collections, list):
        return requested_collection

    if requested_collection:
        for item in collections:
            if isinstance(item, dict) and item.get("id") == requested_collection:
                return requested_collection
        return None

    if len(collections) == 1 and isinstance(collections[0], dict):
        return collections[0].get("id")
    return None


def _extract_filter_fields_from_cql2(expression: str) -> List[str]:
    if not expression:
        return []
    matches = re.findall(
        r"([A-Za-z_][A-Za-z0-9_]*)\s*(?:=|!=|<>|>=|<=|>|<|like|ilike|in)\s*",
        expression,
        flags=re.IGNORECASE,
    )
    return list(dict.fromkeys(matches))


def _parse_cql2_to_query_params(expression: str) -> Optional[Dict[str, str]]:
    if not expression:
        return {}

    operator_map = {
        "=": "",
        "==": "",
        "!=": "_ne",
        "<>": "_ne",
        ">": "_gt",
        ">=": "_gte",
        "<": "_lt",
        "<=": "_lte",
        "like": "_like",
        "ilike": "_ilike",
        "in": "_in",
    }

    result: Dict[str, str] = {}
    clauses = re.split(r"\s+and\s+", expression, flags=re.IGNORECASE)
    for clause in clauses:
        part = clause.strip().strip("()")
        match = re.match(
            r"^([A-Za-z_][A-Za-z0-9_]*)\s*(=|==|!=|<>|>=|<=|>|<|like|ilike|in)\s*(.+)$",
            part,
            flags=re.IGNORECASE,
        )
        if not match:
            return None
        field, op, raw_value = match.group(1), match.group(2).lower(), match.group(3).strip()
        value = raw_value.strip().strip("'").strip('"')
        suffix = operator_map[op]
        result[f"{field}{suffix}"] = value
    return result


def _build_attribute_params(
    attribute_filter: Optional[Union[str, Dict[str, Any]]],
) -> Tuple[Optional[Dict[str, str]], Optional[str], List[str]]:
    if attribute_filter is None:
        return {}, None, []

    if isinstance(attribute_filter, str):
        fields = _extract_filter_fields_from_cql2(attribute_filter)
        params = _parse_cql2_to_query_params(attribute_filter)
        if params is None:
            return None, "Only simple CQL2 expressions joined by AND are supported.", fields
        return params, None, fields

    if isinstance(attribute_filter, dict):
        if {"field", "operator", "value"} <= set(attribute_filter.keys()):
            field = str(attribute_filter["field"])
            operator = str(attribute_filter["operator"]).lower()
            value = attribute_filter.get("value")
            suffix_map = {
                "eq": "",
                "ne": "_ne",
                "gt": "_gt",
                "gte": "_gte",
                "lt": "_lt",
                "lte": "_lte",
                "like": "_like",
                "ilike": "_ilike",
                "in": "_in",
            }
            if operator not in suffix_map:
                return None, f"Unsupported structured filter operator '{operator}'.", [field]
            return {f"{field}{suffix_map[operator]}": str(value)}, None, [field]

        params = {str(key): str(value) for key, value in attribute_filter.items()}
        return params, None, list(params.keys())

    return None, "attribute_filter must be a CQL2 string or object.", []


def _sort_features(features: List[Dict[str, Any]], sortby: Optional[str]) -> List[Dict[str, Any]]:
    if not sortby:
        return features

    descending = False
    field = sortby
    if sortby.startswith("-"):
        descending = True
        field = sortby[1:]
    elif ":" in sortby:
        field, direction = sortby.split(":", 1)
        descending = direction.lower() == "desc"

    def _key(item: Dict[str, Any]) -> Any:
        props = item.get("properties") or {}
        return props.get(field)

    return sorted(features, key=_key, reverse=descending)


def _feature_stats(features: List[Dict[str, Any]]) -> Dict[str, Any]:
    geom_counts: Dict[str, int] = {}
    for feature in features:
        geom_type = ((feature.get("geometry") or {}).get("type")) or "Unknown"
        geom_counts[geom_type] = geom_counts.get(geom_type, 0) + 1
    return {
        "feature_count": len(features),
        "geometry_counts": geom_counts,
    }


def _resolve_input_placeholders(value: Any, refs: Dict[str, Any]) -> Any:
    if isinstance(value, str) and value in refs:
        return refs[value]
    if isinstance(value, dict):
        if "$ref" in value and value["$ref"] in refs:
            return refs[value["$ref"]]
        return {k: _resolve_input_placeholders(v, refs) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve_input_placeholders(item, refs) for item in value]
    return value


def _state_geodata_items(state: GeoDataAgentState) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for key in ("geodata_layers", "geodata_last_results", "geodata_results"):
        values = state.get(key) or []
        if not isinstance(values, list):
            continue
        for value in values:
            if isinstance(value, dict):
                items.append(value)
            elif hasattr(value, "model_dump"):
                try:
                    items.append(value.model_dump())
                except Exception:
                    continue
    return items


def _is_opaque_layer_identifier(value: str) -> bool:
    text = (value or "").strip().lower()
    if not text:
        return False
    if re.fullmatch(r"[0-9a-f]{24,64}", text):
        return True
    if re.fullmatch(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}",
        text,
    ):
        return True
    return False


def _strip_hex_prefix_filename(value: str) -> str:
    match = re.match(r"^[0-9a-f]{24,64}[_-](.+)$", value.strip(), flags=re.IGNORECASE)
    if not match:
        return value.strip()
    return match.group(1).strip() or value.strip()


def _layer_aliases(layer: Dict[str, Any]) -> List[str]:
    aliases: List[str] = []
    for key in ("name", "title", "id", "db_id", "data_source_id"):
        value = layer.get(key)
        if isinstance(value, str) and value.strip():
            alias = value.strip()
            if key in {"id", "db_id", "data_source_id"} and _is_opaque_layer_identifier(alias):
                continue
            aliases.append(alias)
            # Also expose cleaned upload-style names (e.g. "<hash>_roads.geojson" -> "roads.geojson")
            stripped_alias = _strip_hex_prefix_filename(alias)
            if stripped_alias and stripped_alias.lower() != alias.lower():
                aliases.append(stripped_alias)
            stem, _ext = osp.splitext(stripped_alias or alias)
            if stem:
                aliases.append(stem)
    data_link = layer.get("data_link")
    if isinstance(data_link, str) and data_link.strip():
        parsed = urlparse(data_link)
        basename = osp.basename(parsed.path or "")
        if basename:
            cleaned_basename = _strip_hex_prefix_filename(basename)
            if cleaned_basename:
                aliases.append(cleaned_basename)
            stem, _ext = osp.splitext(cleaned_basename or basename)
            if stem:
                aliases.append(stem)
    deduped: List[str] = []
    seen = set()
    for alias in aliases:
        normalized = alias.lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(alias)
    return deduped


def _normalize_ref(value: str) -> str:
    return value.strip().lower()


def _normalized_alias_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").lower())


def _alias_match_score(reference: str, alias: str) -> float:
    ref = (reference or "").strip().lower()
    candidate = (alias or "").strip().lower()
    if not ref or not candidate:
        return 0.0

    candidate_stem, _ = osp.splitext(candidate)
    if ref == candidate or (candidate_stem and ref == candidate_stem):
        return 1.0

    if (
        candidate in ref
        or ref in candidate
        or (candidate_stem and (candidate_stem in ref or ref in candidate_stem))
    ):
        return 0.92

    token_pattern = r"[a-z0-9]+"
    stopwords = {"geojson", "json", "layer", "layers", "dataset", "data", "file"}
    ref_tokens = {token for token in re.findall(token_pattern, ref) if token not in stopwords}
    candidate_tokens = {
        token for token in re.findall(token_pattern, candidate) if token not in stopwords
    }
    overlap = 0.0
    if candidate_tokens:
        overlap = len(ref_tokens & candidate_tokens) / len(candidate_tokens)

    similarity = SequenceMatcher(
        None, _normalized_alias_key(ref), _normalized_alias_key(candidate)
    ).ratio()
    if candidate_stem:
        similarity = max(
            similarity,
            SequenceMatcher(
                None, _normalized_alias_key(ref), _normalized_alias_key(candidate_stem)
            ).ratio(),
        )
    return max(similarity, (overlap * 0.75) + (similarity * 0.25))


def _extract_message_text(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: List[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return " ".join(part.strip() for part in parts if part.strip())
    return ""


def _latest_human_query(state: GeoDataAgentState) -> str:
    messages = state.get("messages") or []
    for message in reversed(messages):
        if isinstance(message, dict):
            msg_type = str(message.get("type", "")).lower()
            content = message.get("content")
        else:
            msg_type = str(getattr(message, "type", "")).lower()
            content = getattr(message, "content", None)
        if msg_type not in {"human", "user"}:
            continue
        text = _extract_message_text(content)
        if text:
            return text
    return ""


def _state_explicit_layer_refs(state: GeoDataAgentState) -> List[str]:
    raw_refs = state.get("explicit_layer_refs")
    if not isinstance(raw_refs, list):
        return []

    refs: List[str] = []
    seen = set()
    for value in raw_refs:
        if not isinstance(value, str):
            continue
        ref = value.strip()
        if not ref:
            continue
        lowered = ref.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        refs.append(ref)
    return refs


def _extract_explicit_layer_refs(query: str) -> List[str]:
    if not query:
        return []

    match = _EXPLICIT_LAYER_REFS_JSON_RE.search(query)
    if not match:
        return []

    raw_payload = (match.group(1) or "").strip()
    if not raw_payload:
        return []

    try:
        payload = json.loads(raw_payload)
    except json.JSONDecodeError:
        return []

    refs: List[str] = []
    layer_refs = payload.get("layer_refs") if isinstance(payload, dict) else None
    if isinstance(layer_refs, list):
        for item in layer_refs:
            if isinstance(item, str):
                normalized_item = _strip_hex_prefix_filename(item.strip())
                if normalized_item:
                    refs.append(normalized_item)
                continue
            if not isinstance(item, dict):
                continue
            for key in ("title", "name"):
                value = item.get(key)
                if isinstance(value, str) and value.strip():
                    refs.append(_strip_hex_prefix_filename(value.strip()))
            if not any(
                isinstance(item.get(key), str) and item.get(key).strip()
                for key in ("title", "name")
            ):
                value = item.get("id")
                if isinstance(value, str) and value.strip():
                    refs.append(_strip_hex_prefix_filename(value.strip()))

    deduped: List[str] = []
    seen = set()
    for ref in refs:
        lowered = ref.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        deduped.append(ref)
    return deduped


def _user_visible_aliases(aliases: List[str]) -> List[str]:
    cleaned: List[str] = []
    for alias in aliases:
        if not isinstance(alias, str):
            continue
        value = alias.strip()
        if not value:
            continue

        lowered = value.lower()
        # Hide opaque UUID/hash-like handles from user-facing hints.
        if re.fullmatch(r"[0-9a-f]{24,64}", lowered):
            continue

        prefixed_match = re.match(r"^[0-9a-f]{24,64}[_-](.+)$", value, flags=re.IGNORECASE)
        if prefixed_match:
            candidate = prefixed_match.group(1).strip()
            if candidate:
                cleaned.append(candidate)
            continue

        cleaned.append(value)

    deduped: List[str] = []
    seen = set()
    for alias in cleaned:
        key = alias.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(alias)
    return deduped


def _collection_id_from_data_link(data_link: Optional[str]) -> Optional[str]:
    if not data_link or not isinstance(data_link, str):
        return None
    match = re.search(r"/collections/([^/]+)", data_link)
    if not match:
        return None
    collection_id = match.group(1).strip()
    return collection_id or None


def _fetch_feature_collection(data_link: Optional[str]) -> Optional[Dict[str, Any]]:
    if not data_link or not isinstance(data_link, str):
        return None
    parsed = urlparse(data_link)
    if parsed.scheme not in {"http", "https"}:
        return None
    if "{bbox" in data_link.lower():
        # Templated tile URLs are not fetchable as feature collections.
        return None

    candidates: List[str] = [data_link]
    hostname = (parsed.hostname or "").lower()
    is_localhost = hostname in {"localhost", "127.0.0.1", "::1"}
    path = parsed.path or ""

    if _is_container_runtime() and is_localhost:
        # OGC API endpoints should use the OGC runtime remap.
        if path.startswith("/v1"):
            remapped_ogc_url = _runtime_request_url(data_link)
            if remapped_ogc_url not in candidates:
                candidates.append(remapped_ogc_url)

        # Backend upload stream URLs should target backend service alias.
        if path.startswith("/api/stream/"):
            backend_alias = parsed._replace(
                scheme=parsed.scheme or "http",
                netloc="backend:8000",
            )
            backend_url = _normalize_url(urlunparse(backend_alias))
            if backend_url not in candidates:
                candidates.append(backend_url)

            # Also try OGC upload endpoint with same file identifier.
            file_id = osp.basename(path)
            ogc_base_for_requests = _runtime_request_url(OGCAPI_BASE_URL) if OGCAPI_BASE_URL else ""
            if file_id and ogc_base_for_requests:
                ogc_upload_url = f"{ogc_base_for_requests.rstrip('/')}/uploads/files/{file_id}"
                if ogc_upload_url not in candidates:
                    candidates.append(ogc_upload_url)

    for request_url in candidates:
        try:
            response = requests.get(
                request_url,
                timeout=max(5.0, float(OGCAPI_TIMEOUT_SECONDS)),
                headers={"Accept": "application/geo+json,application/json"},
            )
        except requests.RequestException:
            continue
        if response.status_code >= 400:
            continue
        try:
            payload = response.json()
        except ValueError:
            continue
        if (
            isinstance(payload, dict)
            and payload.get("type") == "FeatureCollection"
            and isinstance(payload.get("features"), list)
        ):
            return payload
    return None


def _resolve_state_layer_ref(
    state: GeoDataAgentState,
    ref: str,
    *,
    allow_fuzzy: bool = True,
) -> Tuple[Optional[Any], Optional[str], List[str], Optional[str]]:
    normalized = _normalize_ref(ref)
    available_aliases: List[str] = []
    layer_candidates: List[Tuple[Dict[str, Any], List[str]]] = []

    for layer in _state_geodata_items(state):
        aliases = _layer_aliases(layer)
        layer_candidates.append((layer, aliases))
        available_aliases.extend(aliases)
        if normalized not in {_normalize_ref(alias) for alias in aliases}:
            continue

        return _resolve_state_layer_value(layer, aliases)

    if allow_fuzzy:
        fuzzy_ranked: List[Tuple[float, Dict[str, Any], List[str]]] = []
        for layer, aliases in layer_candidates:
            best_alias_score = max(
                (_alias_match_score(ref, alias) for alias in aliases), default=0.0
            )
            if best_alias_score > 0:
                fuzzy_ranked.append((best_alias_score, layer, aliases))

        fuzzy_ranked.sort(key=lambda item: item[0], reverse=True)
        if fuzzy_ranked:
            top_score, top_layer, top_aliases = fuzzy_ranked[0]
            second_score = fuzzy_ranked[1][0] if len(fuzzy_ranked) > 1 else 0.0
            if top_score >= 0.75 and (top_score - second_score) >= 0.08:
                return _resolve_state_layer_value(top_layer, top_aliases)

    deduped = []
    seen = set()
    for alias in available_aliases:
        key = alias.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(alias)
    return None, None, deduped, None


def _find_state_layer_by_ref_exact(
    state: GeoDataAgentState, ref: str
) -> Tuple[Optional[Dict[str, Any]], List[str]]:
    normalized = _normalize_ref(ref)
    available_aliases: List[str] = []
    for layer in _state_geodata_items(state):
        aliases = _layer_aliases(layer)
        available_aliases.extend(aliases)
        if normalized in {_normalize_ref(alias) for alias in aliases}:
            return layer, aliases

    deduped: List[str] = []
    seen = set()
    for alias in available_aliases:
        key = alias.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(alias)
    return None, deduped


def _resolve_state_layer_value(
    layer: Dict[str, Any], aliases: List[str]
) -> Tuple[Optional[Any], Optional[str], List[str], Optional[str]]:
    properties = layer.get("properties") or {}
    if isinstance(properties, dict):
        collection_id = properties.get("ogc_collection_id") or properties.get("collection_id")
        if isinstance(collection_id, str) and collection_id.strip():
            return collection_id.strip(), "collection_id", aliases, layer.get("data_link")

    collection_from_link = _collection_id_from_data_link(layer.get("data_link"))
    if collection_from_link:
        return collection_from_link, "collection_id", aliases, layer.get("data_link")

    feature_collection = _fetch_feature_collection(layer.get("data_link"))
    if feature_collection is not None:
        return feature_collection, "feature_collection", aliases, layer.get("data_link")

    data_link = layer.get("data_link")
    if isinstance(data_link, str) and data_link.strip():
        parsed_link = urlparse(data_link)
        if not parsed_link.scheme or _JOB_RESULTS_PATH_RE.search(data_link):
            return data_link.strip(), "feature_collection_path", aliases, data_link.strip()

    return None, None, aliases, layer.get("data_link")


def _single_source_input_from_layer(
    layer: Dict[str, Any],
    server_cache: Dict[str, Any],
    server: OGCAPIServerRuntime,
) -> Tuple[Optional[str], Optional[Any]]:
    properties = layer.get("properties") or {}
    collection_ids: List[str] = []
    if isinstance(properties, dict):
        for key in ("ogc_collection_id", "collection_id"):
            value = properties.get(key)
            if isinstance(value, str) and value.strip():
                collection_ids.append(value.strip())
    from_link = _collection_id_from_data_link(layer.get("data_link"))
    if from_link:
        collection_ids.append(from_link)

    seen_collection_ids: set[str] = set()
    for collection_id in collection_ids:
        normalized = collection_id.lower()
        if normalized in seen_collection_ids:
            continue
        seen_collection_ids.add(normalized)
        if _collection_exists(server_cache, server, collection_id):
            return "collection_id", collection_id

    feature_collection = _fetch_feature_collection(layer.get("data_link"))
    if feature_collection is not None:
        return "feature_collection", feature_collection

    data_link = layer.get("data_link")
    if isinstance(data_link, str) and data_link.strip():
        parsed_link = urlparse(data_link)
        if not parsed_link.scheme or _JOB_RESULTS_PATH_RE.search(data_link):
            return "feature_collection_path", data_link.strip()

    return None, None


def _has_single_source_input(inputs: Dict[str, Any]) -> bool:
    for key in _SINGLE_SOURCE_INPUT_KEYS:
        value = inputs.get(key)
        if value is not None:
            return True
    return False


def _single_source_input_count(inputs: Dict[str, Any]) -> int:
    count = 0
    for key in _SINGLE_SOURCE_INPUT_KEYS:
        if inputs.get(key) is not None:
            count += 1
    return count


def _autobind_single_source_input_from_state(
    state: GeoDataAgentState,
    server_cache: Dict[str, Any],
    server: OGCAPIServerRuntime,
) -> Tuple[Optional[str], Optional[Any], List[str]]:
    candidates: List[Tuple[str, Any, List[str]]] = []
    candidate_aliases: List[str] = []

    for layer in _state_geodata_items(state):
        if layer.get("visible") is False:
            continue
        aliases = _layer_aliases(layer)
        if aliases:
            candidate_aliases.extend(aliases)

        input_key, input_value = _single_source_input_from_layer(layer, server_cache, server)
        if input_key and input_value is not None:
            candidates.append((input_key, input_value, aliases))

    if len(candidates) == 1:
        key, value, aliases = candidates[0]
        return key, value, aliases

    deduped_aliases: List[str] = []
    seen = set()
    for alias in candidate_aliases:
        lowered = alias.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        deduped_aliases.append(alias)
    return None, None, deduped_aliases


def _autobind_single_source_input_from_query(
    state: GeoDataAgentState,
    server_cache: Dict[str, Any],
    server: OGCAPIServerRuntime,
) -> Tuple[Optional[str], Optional[Any], List[str]]:
    query = _latest_human_query(state)

    explicit_refs = _state_explicit_layer_refs(state)
    if not explicit_refs:
        explicit_refs = _extract_explicit_layer_refs(query)
    if explicit_refs:
        candidates: List[Tuple[str, Any, List[str]]] = []
        candidate_aliases: List[str] = []
        seen_layer_alias_sets: set[Tuple[str, ...]] = set()
        for ref in explicit_refs:
            layer, aliases = _find_state_layer_by_ref_exact(state, ref)
            if layer is None:
                continue
            alias_key = tuple(sorted(alias.lower() for alias in aliases))
            if alias_key in seen_layer_alias_sets:
                continue
            seen_layer_alias_sets.add(alias_key)
            input_key, input_value = _single_source_input_from_layer(layer, server_cache, server)
            if input_key and input_value is not None:
                candidates.append((input_key, input_value, aliases))
                candidate_aliases.extend(aliases)

        if len(candidates) == 1:
            key, value, aliases = candidates[0]
            return key, value, aliases
        if candidates:
            return None, None, _user_visible_aliases(candidate_aliases)
        return None, None, _user_visible_aliases(explicit_refs)

    if not query:
        return None, None, []

    ranked_layers: List[Tuple[float, Dict[str, Any], List[str]]] = []
    for layer in _state_geodata_items(state):
        if layer.get("visible") is False:
            continue
        aliases = _layer_aliases(layer)
        best_alias_score = max(
            (_alias_match_score(query, alias) for alias in aliases),
            default=0.0,
        )
        if best_alias_score <= 0.0:
            continue
        ranked_layers.append((best_alias_score, layer, aliases))

    ranked_layers.sort(key=lambda item: item[0], reverse=True)
    if not ranked_layers:
        return None, None, []

    top_score, top_layer, top_aliases = ranked_layers[0]
    second_score = ranked_layers[1][0] if len(ranked_layers) > 1 else 0.0
    if top_score < 0.72 or (top_score - second_score) < 0.08:
        return None, None, []

    input_key, input_value = _single_source_input_from_layer(top_layer, server_cache, server)
    if input_key and input_value is not None:
        return input_key, input_value, top_aliases

    return None, None, top_aliases


def _build_result_geodata(
    state: GeoDataAgentState,
    *,
    process_id: str,
    job_id: str,
    results_payload: Dict[str, Any],
    source_name: str,
    result_url: str,
) -> Optional[List[GeoDataObject]]:
    if results_payload.get("type") != "FeatureCollection":
        return None

    return _build_or_reuse_ogc_result_geodata(
        state,
        process_id=process_id,
        job_id=job_id,
        source_name=source_name,
        result_url=result_url,
        title=f"OGC API {process_id} result",
        description=f"Process '{process_id}' result (job {job_id}).",
        llm_description=f"Output of OGC API process '{process_id}'.",
        extra_properties={
            "ogc_job_status": "successful",
            "feature_count": len(list(results_payload.get("features") or [])),
        },
    )


def _build_or_reuse_ogc_result_geodata(
    state: GeoDataAgentState,
    *,
    process_id: str,
    job_id: str,
    source_name: str,
    result_url: str,
    title: str,
    description: str,
    llm_description: str,
    extra_properties: Optional[Dict[str, Any]] = None,
) -> List[GeoDataObject]:
    existing = list(state.get("geodata_results") or [])
    normalized_job_id = str(job_id).strip()
    normalized_url = (result_url or "").strip()

    for item in existing:
        if isinstance(item, dict):
            properties = item.get("properties")
            item_job_id = properties.get("ogc_job_id") if isinstance(properties, dict) else None
            item_data_link = item.get("data_link")
        else:
            properties = getattr(item, "properties", None)
            item_job_id = properties.get("ogc_job_id") if isinstance(properties, dict) else None
            item_data_link = getattr(item, "data_link", None)

        if isinstance(item_job_id, str) and item_job_id.strip() == normalized_job_id:
            return existing
        if isinstance(item_data_link, str) and item_data_link.strip() == normalized_url:
            return existing

    display_name = re.sub(r"[^a-zA-Z0-9_-]", "-", f"{process_id}-{job_id[:8]}").lower()
    properties = {
        "ogc_process_id": process_id,
        "ogc_job_id": job_id,
        "ogc_results_url": result_url,
    }
    if extra_properties:
        properties.update(extra_properties)

    geodata = GeoDataObject(
        id=uuid.uuid4().hex,
        data_source_id="ogcapi-process",
        data_type=DataType.GEOJSON,
        data_origin=DataOrigin.TOOL.value,
        data_source=source_name,
        data_link=result_url,
        name=display_name,
        title=title,
        description=description,
        llm_description=llm_description,
        layer_type="GeoJSON",
        properties=properties,
    )
    existing.append(geodata)
    return existing


def _build_pending_result_geodata(
    state: GeoDataAgentState,
    *,
    process_id: str,
    job_id: str,
    source_name: str,
    result_url: str,
) -> List[GeoDataObject]:
    return _build_or_reuse_ogc_result_geodata(
        state,
        process_id=process_id,
        job_id=job_id,
        source_name=source_name,
        result_url=result_url,
        title=f"OGC API {process_id} result (pending)",
        description=f"Process '{process_id}' job accepted (job {job_id}).",
        llm_description=(
            f"Accepted OGC API process '{process_id}' job. "
            "The endpoint points to the final FeatureCollection result."
        ),
        extra_properties={"ogc_job_status": "accepted"},
    )


def _build_runtime_servers(ogcapi_servers: List[Any]) -> List[OGCAPIServerRuntime]:
    runtimes: List[OGCAPIServerRuntime] = []
    for server in ogcapi_servers:
        url = _normalize_url(getattr(server, "url", ""))
        if not url:
            continue
        request_url = _runtime_request_url(url)
        runtimes.append(
            OGCAPIServerRuntime(
                url=url,
                request_url=request_url,
                name=getattr(server, "name", None),
                description=getattr(server, "description", None),
                api_key=getattr(server, "api_key", None),
                headers=getattr(server, "headers", None),
            )
        )
    return runtimes


def build_ogcapi_tools(
    ogcapi_servers: List[Any],
    default_session_id: Optional[str] = None,
    include_prepare: bool = True,
    include_filter: bool = True,
    include_process: bool = True,
) -> List[BaseTool]:
    servers = _build_runtime_servers(ogcapi_servers)
    if not servers:
        return []

    @tool
    def prepare_geospatial_context(
        state: Annotated[GeoDataAgentState, InjectedState],
        tool_call_id: Annotated[str, InjectedToolCallId],
        server: Optional[str] = None,
        force_refresh: bool = False,
    ) -> Union[Dict[str, Any], Command]:
        """
        Load and cache an OGC API capabilities manifest for this session.
        Call this once per server/session before running filter/process tools.

        Args:
            server: Optional server URL or configured server name.
            force_refresh: If true, revalidate cache with ETag.
        """
        session_id = _resolve_session_id(state, default_session_id)
        bucket = _session_bucket(session_id)
        target_server = _resolve_server(servers, server)
        if not target_server:
            return _error_command(
                "prepare_geospatial_context",
                tool_call_id,
                code="server_not_found",
                message="Requested OGC API server is not configured.",
                recoverable=True,
                retryable=False,
                suggested_action="choose_configured_ogcapi_server",
                detail={"configured_servers": [s.url for s in servers]},
            )

        server_cache, error = _ensure_manifest_cached(
            bucket,
            target_server,
            force_refresh=force_refresh,
        )
        if error:
            return _error_command(
                "prepare_geospatial_context",
                tool_call_id,
                code=error["error"]["code"],
                message=error["error"]["message"],
                recoverable=error["error"]["recoverable"],
                retryable=error["error"]["retryable"],
                suggested_action=error["error"]["suggestedAction"],
                detail=error.get("detail"),
                request_context={
                    "request_id": error["error"].get("requestId"),
                    "trace_id": error["error"].get("traceId"),
                },
            )

        manifest = server_cache.get("manifest", {})
        process_count = len((manifest.get("capabilities", {}) or {}).get("processes", []) or [])
        payload = {
            "status": "ok",
            "server": target_server.url,
            "session_id": session_id,
            "cached": True,
            "manifest_hash": (manifest.get("hashes") or {}).get("manifest"),
            "api_prefix": server_cache.get("api_prefix", ""),
            "process_count": process_count,
            "refreshed_at": server_cache.get("refreshed_at"),
        }
        return _success_command("prepare_geospatial_context", tool_call_id, payload)

    @tool
    def filter_geodata(
        state: Annotated[GeoDataAgentState, InjectedState],
        tool_call_id: Annotated[str, InjectedToolCallId],
        collection_id: Optional[str] = None,
        bbox: Optional[List[float]] = None,
        geometry: Optional[Dict[str, Any]] = None,
        datetime: Optional[str] = None,
        attribute_filter: Optional[Union[str, Dict[str, Any]]] = None,
        selected_properties: Optional[List[str]] = None,
        limit: int = 100,
        sortby: Optional[str] = None,
        output_mode: str = "feature_ref",
        server: Optional[str] = None,
    ) -> Union[Dict[str, Any], Command]:
        """
        Resolve a target collection, validate filters against queryables, apply filters,
        and return a server-side-like dataset handle for later processing.

        Args:
            collection_id: Target collection ID; optional only if server exposes one collection.
            bbox: [minx, miny, maxx, maxy] filter.
            geometry: Optional geometry filter placeholder (currently bbox is used for server query).
            datetime: Optional datetime range/value filter.
            attribute_filter: CQL2 string (simple AND clauses) or structured object.
            selected_properties: Optional subset of feature properties to retain.
            limit: Max features to request from server.
            sortby: Optional property sort key (field, -field, or field:desc).
            output_mode: One of features, ids, feature_ref, stats_only.
            server: Optional server URL or name.
        """
        session_id = _resolve_session_id(state, default_session_id)
        bucket = _session_bucket(session_id)
        target_server = _resolve_server(servers, server)
        if not target_server:
            return _error_command(
                "filter_geodata",
                tool_call_id,
                code="server_not_found",
                message="Requested OGC API server is not configured.",
                recoverable=True,
                retryable=False,
                suggested_action="choose_configured_ogcapi_server",
                detail={"configured_servers": [s.url for s in servers]},
            )

        server_cache, error = _ensure_manifest_cached(bucket, target_server, force_refresh=False)
        if error:
            return _error_command(
                "filter_geodata",
                tool_call_id,
                code=error["error"]["code"],
                message=error["error"]["message"],
                recoverable=error["error"]["recoverable"],
                retryable=error["error"]["retryable"],
                suggested_action=error["error"]["suggestedAction"],
                detail=error.get("detail"),
            )

        if output_mode not in SUPPORTED_OUTPUT_MODES:
            return _error_command(
                "filter_geodata",
                tool_call_id,
                code="invalid_output_mode",
                message=f"Unsupported output_mode '{output_mode}'.",
                recoverable=True,
                retryable=False,
                suggested_action="use_supported_output_mode",
                detail={"supported_modes": sorted(SUPPORTED_OUTPUT_MODES)},
            )

        collections_url = _endpoint_url(server_cache, "/collections")
        collections_response, collections_payload = _request_json(
            "GET",
            collections_url,
            headers=_headers_for_server(target_server),
            retries=1,
        )
        request_context = _extract_request_context(collections_response)
        resolved_collection = _choose_collection_id(collections_payload, collection_id)
        if not resolved_collection:
            available = []
            if isinstance(collections_payload, dict):
                for item in collections_payload.get("collections", []) or []:
                    if isinstance(item, dict) and item.get("id"):
                        available.append(item["id"])
            return _error_command(
                "filter_geodata",
                tool_call_id,
                code="collection_resolution_failed",
                message="Could not resolve a target collection.",
                recoverable=True,
                retryable=False,
                suggested_action="specify_collection_id_or_refresh_capabilities",
                detail={"requested": collection_id, "available_collections": available},
                request_context=request_context,
            )

        queryables_url = _endpoint_url(
            server_cache, f"/collections/{resolved_collection}/queryables"
        )
        queryables_response, queryables_payload = _request_json(
            "GET",
            queryables_url,
            headers=_headers_for_server(target_server),
            retries=1,
        )
        queryables_context = _extract_request_context(queryables_response)
        if queryables_response.status_code >= 400:
            return _error_command(
                "filter_geodata",
                tool_call_id,
                code="queryables_unavailable",
                message="Failed to load queryables for target collection.",
                recoverable=True,
                retryable=True,
                suggested_action="retry_or_verify_collection",
                detail=queryables_payload,
                request_context=queryables_context,
            )
        queryable_props = (
            ((queryables_payload or {}).get("properties") or {})
            if isinstance(queryables_payload, dict)
            else {}
        )
        queryable_keys = set(queryable_props.keys())

        attribute_params, parse_error, filter_fields = _build_attribute_params(attribute_filter)
        if parse_error:
            return _error_command(
                "filter_geodata",
                tool_call_id,
                code="unsupported_attribute_filter",
                message=parse_error,
                recoverable=True,
                retryable=False,
                suggested_action="use_simple_cql2_or_structured_filter",
                detail={"attribute_filter": attribute_filter},
            )
        unknown_fields = [field for field in filter_fields if field not in queryable_keys]
        if unknown_fields:
            return _error_command(
                "filter_geodata",
                tool_call_id,
                code="invalid_filter_fields",
                message="Filter uses properties not exposed by queryables.",
                recoverable=True,
                retryable=False,
                suggested_action="check_queryables_and_retry",
                detail={
                    "unknown_fields": unknown_fields,
                    "queryables_url": queryables_url,
                },
                request_context=queryables_context,
            )

        params: Dict[str, Any] = {"limit": max(1, min(limit, 1000))}
        if bbox:
            if len(bbox) != 4:
                return _error_command(
                    "filter_geodata",
                    tool_call_id,
                    code="invalid_bbox",
                    message="bbox must contain exactly 4 numeric values.",
                    recoverable=True,
                    retryable=False,
                    suggested_action="use_bbox_minx_miny_maxx_maxy",
                )
            params["bbox"] = ",".join(str(value) for value in bbox)
        if datetime:
            params["datetime"] = datetime
        if attribute_params:
            params.update(attribute_params)

        items_url = _endpoint_url(server_cache, f"/collections/{resolved_collection}/items")
        items_response, items_payload = _request_json(
            "GET",
            items_url,
            headers=_headers_for_server(target_server),
            params=params,
            retries=1,
        )
        items_context = _extract_request_context(items_response)
        if items_response.status_code >= 400:
            return _error_command(
                "filter_geodata",
                tool_call_id,
                code="filter_request_failed",
                message="Server rejected collection filter request.",
                recoverable=True,
                retryable=False,
                suggested_action="validate_queryables_and_filter_arguments",
                detail=items_payload,
                request_context=items_context,
            )

        if not isinstance(items_payload, dict):
            return _error_command(
                "filter_geodata",
                tool_call_id,
                code="invalid_items_payload",
                message="Collection items endpoint returned non-object payload.",
                recoverable=True,
                retryable=True,
                suggested_action="retry_items_request",
                detail=items_payload,
                request_context=items_context,
            )

        features = list(items_payload.get("features") or [])
        if sortby:
            features = _sort_features(features, sortby)
        if selected_properties:
            keep = set(selected_properties)
            for feature in features:
                props = feature.get("properties") or {}
                feature["properties"] = {k: v for k, v in props.items() if k in keep}

        normalized_fc = {
            **items_payload,
            "features": features,
            "numberReturned": len(features),
        }
        session_token = _safe_session_token(session_id)
        handle = f"tmp:{session_token}:subset{uuid.uuid4().hex[:8]}"
        bucket["filtered"][handle] = {
            "server": target_server.url,
            "collection_id": resolved_collection,
            "feature_collection": normalized_fc,
            "query": {
                "bbox": bbox,
                "geometry": geometry,
                "datetime": datetime,
                "attribute_filter": attribute_filter,
                "selected_properties": selected_properties,
                "limit": limit,
                "sortby": sortby,
            },
            "created_at": time.time(),
        }

        payload: Dict[str, Any] = {
            "status": "ok",
            "server": target_server.url,
            "collection_id": resolved_collection,
            "filtered_ref": handle,
            "feature_count": len(features),
            "output_mode": output_mode,
            "request": params,
            "requestId": items_context.get("request_id"),
            "traceId": items_context.get("trace_id"),
        }

        if output_mode == "features":
            preview_limit = min(len(features), 50)
            payload["preview_features"] = features[:preview_limit]
            payload["preview_truncated"] = len(features) > preview_limit
        elif output_mode == "ids":
            payload["ids"] = [
                feature.get("id") or (feature.get("properties") or {}).get("id")
                for feature in features
            ]
        elif output_mode == "stats_only":
            payload["stats"] = _feature_stats(features)

        _log_event(
            "ogcapi.filter.completed",
            session_id=session_id,
            server=target_server.url,
            collection_id=resolved_collection,
            filtered_ref=handle,
            feature_count=len(features),
            output_mode=output_mode,
        )
        return _success_command("filter_geodata", tool_call_id, payload)

    @tool
    def process_geodata(
        state: Annotated[GeoDataAgentState, InjectedState],
        tool_call_id: Annotated[str, InjectedToolCallId],
        process_id: str,
        inputs: Optional[Dict[str, Any]] = None,
        input_refs: Optional[List[str]] = None,
        prefer_async: bool = True,
        result_format: str = "feature_ref",
        server: Optional[str] = None,
    ) -> Union[Dict[str, Any], Command]:
        """
        Execute an OGC API process using direct inputs and/or filtered references.
        Validates inputs before execution and supports async-first execution.

        Args:
            process_id: OGC process identifier.
            inputs: Explicit process input object.
            input_refs: Optional filtered refs (tmp:... handles) to resolve into inputs.
            prefer_async: Return immediately with job reference when true.
            result_format: Response mode hint (feature_ref, features, stats_only).
            server: Optional server URL or name.

        Layer targeting:
            - If user mentions a layer already in state, pass it in `input_refs` using
              the layer `name` or `title` from `geodata_layers`.
            - For single-source processes (buffer/clip/dissolve/simplify), this tool can
              resolve one source from state automatically. Prefer state layers before asking
              the user for collection IDs.
        """
        session_id = _resolve_session_id(state, default_session_id)
        bucket = _session_bucket(session_id)
        target_server = _resolve_server(servers, server)
        if not target_server:
            return _error_command(
                "process_geodata",
                tool_call_id,
                code="server_not_found",
                message="Requested OGC API server is not configured.",
                recoverable=True,
                retryable=False,
                suggested_action="choose_configured_ogcapi_server",
                detail={"configured_servers": [s.url for s in servers]},
            )

        server_cache, error = _ensure_manifest_cached(bucket, target_server, force_refresh=False)
        if error:
            return _error_command(
                "process_geodata",
                tool_call_id,
                code=error["error"]["code"],
                message=error["error"]["message"],
                recoverable=error["error"]["recoverable"],
                retryable=error["error"]["retryable"],
                suggested_action=error["error"]["suggestedAction"],
                detail=error.get("detail"),
            )

        requested_process_id = (process_id or "").strip()
        if not requested_process_id:
            return _error_command(
                "process_geodata",
                tool_call_id,
                code="invalid_process_id",
                message="process_id is required.",
                recoverable=True,
                retryable=False,
                suggested_action="choose_process_from_capabilities",
            )

        available_process_ids = _manifest_process_ids(server_cache)
        resolved_process_id = requested_process_id
        if available_process_ids:
            matched_process_id, suggestions, resolution_mode = _resolve_process_id(
                requested_process_id, available_process_ids
            )
            if not matched_process_id:
                detail = {"available_processes": available_process_ids[:50]}
                if suggestions:
                    detail["suggested_processes"] = suggestions
                return _error_command(
                    "process_geodata",
                    tool_call_id,
                    code="unknown_process_id",
                    message=f"Process '{requested_process_id}' is not available on this OGC API server.",
                    recoverable=True,
                    retryable=False,
                    suggested_action="use_prepare_geospatial_context_and_select_available_process_id",
                    detail=detail,
                )
            resolved_process_id = matched_process_id
            if resolved_process_id != requested_process_id:
                _log_event(
                    "ogcapi.process_id.resolved",
                    requested_process_id=requested_process_id,
                    resolved_process_id=resolved_process_id,
                    mode=resolution_mode,
                    server=target_server.url,
                )

        working_inputs = dict(inputs or {})
        refs = input_refs or []
        resolved_refs: Dict[str, Any] = {}
        resolved_ref_kinds: Dict[str, str] = {}
        latest_query = _latest_human_query(state)
        explicit_refs_in_query = _state_explicit_layer_refs(state)
        if not explicit_refs_in_query:
            explicit_refs_in_query = _extract_explicit_layer_refs(latest_query)
        allow_fuzzy_layer_ref = not bool(explicit_refs_in_query)
        for ref in refs:
            entry = bucket["filtered"].get(ref) or bucket["results"].get(ref)
            if entry:
                if entry.get("feature_collection"):
                    resolved_refs[ref] = entry["feature_collection"]
                    resolved_ref_kinds[ref] = "feature_collection"
                elif entry.get("job_results_path"):
                    resolved_refs[ref] = entry["job_results_path"]
                    resolved_ref_kinds[ref] = "feature_collection_path"
                elif entry.get("results_payload"):
                    resolved_refs[ref] = entry["results_payload"]
                    resolved_ref_kinds[ref] = "feature_collection"
                continue

            state_value, state_input_key, available_aliases, state_data_link = (
                _resolve_state_layer_ref(
                    state,
                    ref,
                    allow_fuzzy=allow_fuzzy_layer_ref,
                )
            )
            if state_value is not None and state_input_key:
                if state_input_key == "collection_id" and isinstance(state_value, str):
                    collection_id = state_value.strip()
                    if collection_id and not _collection_exists(
                        server_cache, target_server, collection_id
                    ):
                        fallback_fc = _fetch_feature_collection(state_data_link)
                        if fallback_fc is not None:
                            resolved_refs[ref] = fallback_fc
                            resolved_ref_kinds[ref] = "feature_collection"
                            _log_event(
                                "ogcapi.input_ref.collection_fallback",
                                ref=ref,
                                collection_id=collection_id,
                                server=target_server.url,
                                reason="collection_not_found_using_layer_data_link",
                            )
                            continue
                        return _error_command(
                            "process_geodata",
                            tool_call_id,
                            code="collection_not_found",
                            message=f"Collection '{collection_id}' referenced by '{ref}' was not found.",
                            recoverable=True,
                            retryable=False,
                            suggested_action="re-upload_layer_or_use_feature_collection_ref",
                        )
                resolved_refs[ref] = state_value
                resolved_ref_kinds[ref] = state_input_key
                continue

            detail: Dict[str, Any] = {}
            visible_aliases = _user_visible_aliases(available_aliases)
            if visible_aliases:
                detail["available_refs"] = visible_aliases[:25]
            return _error_command(
                "process_geodata",
                tool_call_id,
                code="unknown_input_ref",
                message=f"Unknown input reference '{ref}'.",
                recoverable=True,
                retryable=False,
                suggested_action="run_filter_geodata_or_check_ref",
                detail=detail or None,
            )

        working_inputs = _resolve_input_placeholders(working_inputs, resolved_refs)
        if refs and not working_inputs:
            if len(refs) == 1:
                ref = refs[0]
                ref_kind = resolved_ref_kinds.get(ref) or "feature_collection"
                working_inputs[ref_kind] = resolved_refs[ref]
            else:
                working_inputs["feature_collections"] = [resolved_refs[ref] for ref in refs]

        if resolved_process_id in _SINGLE_SOURCE_PROCESSES:
            if "feature_collections" in working_inputs:
                return _error_command(
                    "process_geodata",
                    tool_call_id,
                    code="unsupported_multi_source_refs",
                    message=(
                        f"Process '{resolved_process_id}' accepts exactly one source input "
                        "(collection_id, feature_collection, or feature_collection_path)."
                    ),
                    recoverable=True,
                    retryable=False,
                    suggested_action="provide_single_input_ref_or_collection_id",
                )

            if _single_source_input_count(working_inputs) > 1:
                return _error_command(
                    "process_geodata",
                    tool_call_id,
                    code="ambiguous_source_inputs",
                    message=(
                        f"Process '{resolved_process_id}' received multiple source inputs. "
                        """Provide exactly one of collection_id,
                         feature_collection, or feature_collection_path."""
                    ),
                    recoverable=True,
                    retryable=False,
                    suggested_action="keep_exactly_one_source_input",
                    detail={
                        "provided_keys": [
                            k
                            for k in _SINGLE_SOURCE_INPUT_KEYS
                            if working_inputs.get(k) is not None
                        ]
                    },
                )

            if not _has_single_source_input(working_inputs):
                auto_key, auto_value, available_aliases = _autobind_single_source_input_from_state(
                    state, server_cache, target_server
                )
                if auto_key is None:
                    auto_key, auto_value, available_aliases = (
                        _autobind_single_source_input_from_query(state, server_cache, target_server)
                    )
                if auto_key and auto_value is not None:
                    working_inputs[auto_key] = auto_value
                    _log_event(
                        "ogcapi.process.source_autobound",
                        process_id=resolved_process_id,
                        input_key=auto_key,
                        aliases=_user_visible_aliases(available_aliases)[:5],
                    )
                else:
                    detail: Dict[str, Any] = {
                        "required_one_of": list(_SINGLE_SOURCE_INPUT_KEYS),
                    }
                    visible_aliases = _user_visible_aliases(available_aliases)
                    if visible_aliases:
                        detail["available_refs"] = visible_aliases[:25]
                    return _error_command(
                        "process_geodata",
                        tool_call_id,
                        code="missing_process_source_input",
                        message=(
                            f"Process '{resolved_process_id}' requires one source input: "
                            "collection_id, feature_collection, or feature_collection_path."
                        ),
                        recoverable=True,
                        retryable=False,
                        suggested_action="provide_input_refs_or_collection_id",
                        detail=detail,
                    )

            provided_collection_id = working_inputs.get("collection_id")
            if isinstance(provided_collection_id, str) and provided_collection_id.strip():
                candidate_collection_id = provided_collection_id.strip()
                if not _collection_exists(server_cache, target_server, candidate_collection_id):
                    auto_key, auto_value, available_aliases = (
                        _autobind_single_source_input_from_state(state, server_cache, target_server)
                    )
                    if auto_key and auto_value is not None:
                        working_inputs.pop("collection_id", None)
                        working_inputs[auto_key] = auto_value
                        _log_event(
                            "ogcapi.process.source_rebound",
                            process_id=resolved_process_id,
                            original_collection_id=candidate_collection_id,
                            rebound_input_key=auto_key,
                            aliases=_user_visible_aliases(available_aliases)[:5],
                            reason="collection_not_found",
                        )
                    else:
                        detail: Dict[str, Any] = {
                            "requested_collection_id": candidate_collection_id,
                        }
                        visible_aliases = _user_visible_aliases(available_aliases)
                        if visible_aliases:
                            detail["available_refs"] = visible_aliases[:25]
                        return _error_command(
                            "process_geodata",
                            tool_call_id,
                            code="collection_not_found",
                            message=f"""Collection '{candidate_collection_id}' was not found
                             on the target OGC API server.""",
                            recoverable=True,
                            retryable=False,
                            suggested_action="use_existing_collection_id_or_layer_ref",
                            detail=detail,
                        )

        execution_signature = hashlib.sha256(
            (
                f"{target_server.url}:{resolved_process_id}:{prefer_async}:"
                f"{json.dumps(working_inputs, sort_keys=True, default=str)}"
            ).encode("utf-8")
        ).hexdigest()[:40]
        process_runs = bucket.setdefault("process_runs", {})
        cached_execution = process_runs.get(execution_signature)
        if cached_execution and (prefer_async or cached_execution.get("status") == "ok"):
            replay_count = int(cached_execution.get("replay_count") or 0) + 1
            cached_execution["replay_count"] = replay_count
            cached_job_id = str(cached_execution.get("job_id") or "")
            cached_result_url = str(cached_execution.get("job_results_url") or "")

            payload: Dict[str, Any] = {
                "status": cached_execution.get("status") or "ok",
                "server": target_server.url,
                "process_id": resolved_process_id,
                "job_id": cached_execution.get("job_id"),
                "result_ref": cached_execution.get("result_ref"),
                "job_status_path": cached_execution.get("job_status_path"),
                "job_results_path": cached_execution.get("job_results_path"),
                "job_status_url": cached_execution.get("job_status_url"),
                "job_results_url": cached_execution.get("job_results_url"),
                "duplicate_call": True,
                "replay_count": replay_count,
                "next_action": "reuse_existing_result_and_respond",
                "message": (
                    "This process request already ran in the current session. "
                    "Reuse the existing result reference instead of rerunning it."
                ),
                "requestId": cached_execution.get("request_id"),
                "traceId": cached_execution.get("trace_id"),
            }
            if resolved_process_id != requested_process_id:
                payload["requested_process_id"] = requested_process_id

            cached_results_payload = cached_execution.get("results_payload")
            geodata_results_update: Optional[List[GeoDataObject]] = None
            if isinstance(cached_results_payload, dict):
                features = list(cached_results_payload.get("features") or [])
                if result_format == "features":
                    preview_limit = min(len(features), 50)
                    payload["preview_features"] = features[:preview_limit]
                    payload["preview_truncated"] = len(features) > preview_limit
                elif result_format == "stats_only":
                    payload["stats"] = _feature_stats(features)
                else:
                    payload["feature_count"] = len(features)
                if cached_job_id and cached_result_url:
                    geodata_results_update = _build_result_geodata(
                        state,
                        process_id=resolved_process_id,
                        job_id=cached_job_id,
                        results_payload=cached_results_payload,
                        source_name=target_server.name or target_server.url,
                        result_url=cached_result_url,
                    )
            elif cached_job_id and cached_result_url:
                geodata_results_update = _build_pending_result_geodata(
                    state,
                    process_id=resolved_process_id,
                    job_id=cached_job_id,
                    source_name=target_server.name or target_server.url,
                    result_url=cached_result_url,
                )

            _log_event(
                "ogcapi.process.duplicate_short_circuit",
                session_id=session_id,
                server=target_server.url,
                process_id=resolved_process_id,
                job_id=cached_execution.get("job_id"),
                status=cached_execution.get("status"),
                replay_count=replay_count,
            )
            return _success_command(
                "process_geodata",
                tool_call_id,
                payload,
                geodata_results=geodata_results_update,
            )

        validate_url = _endpoint_url(server_cache, f"/processes/{resolved_process_id}/validate")
        validate_response, validate_payload = _request_json(
            "POST",
            validate_url,
            headers=_headers_for_server(target_server),
            json_body={"inputs": working_inputs},
            retries=1,
        )
        validate_context = _extract_request_context(validate_response)
        if validate_response.status_code >= 400:
            return _error_command(
                "process_geodata",
                tool_call_id,
                code="process_validation_failed",
                message="Process input validation failed.",
                recoverable=True,
                retryable=False,
                suggested_action="inspect_validation_errors_and_retry",
                detail=validate_payload,
                request_context=validate_context,
            )

        normalized_inputs = (
            (validate_payload or {}).get("normalizedInputs")
            if isinstance(validate_payload, dict)
            else None
        )
        if isinstance(normalized_inputs, dict):
            working_inputs = normalized_inputs

        idempotency_key = hashlib.sha256(
            f"""{session_id}:{resolved_process_id}:
            {json.dumps(working_inputs, sort_keys=True, default=str)}""".encode(
                "utf-8"
            )
        ).hexdigest()[:32]
        execute_url = _endpoint_url(server_cache, f"/processes/{resolved_process_id}/jobs")
        execute_response, execute_payload = _request_json(
            "POST",
            execute_url,
            headers=_headers_for_server(target_server, {"Idempotency-Key": idempotency_key}),
            json_body={"inputs": working_inputs},
            retries=1,
        )
        execute_context = _extract_request_context(execute_response)
        if execute_response.status_code >= 400:
            return _error_command(
                "process_geodata",
                tool_call_id,
                code="process_execution_failed",
                message="Process job creation failed.",
                recoverable=True,
                retryable=False,
                suggested_action="check_process_contract_or_retry",
                detail=execute_payload,
                request_context=execute_context,
            )

        if not isinstance(execute_payload, dict):
            return _error_command(
                "process_geodata",
                tool_call_id,
                code="invalid_job_response",
                message="Process job creation returned invalid payload.",
                recoverable=True,
                retryable=True,
                suggested_action="retry_job_creation",
                detail=execute_payload,
                request_context=execute_context,
            )

        job_id = execute_payload.get("jobID")
        if not job_id:
            return _error_command(
                "process_geodata",
                tool_call_id,
                code="missing_job_id",
                message="Process response missing jobID.",
                recoverable=True,
                retryable=False,
                suggested_action="retry_job_creation",
                detail=execute_payload,
                request_context=execute_context,
            )

        session_token = _safe_session_token(session_id)
        result_ref = f"tmp:{session_token}:job{str(job_id)[:8]}"
        job_status_path = f"/processes/{resolved_process_id}/jobs/{job_id}"
        job_results_path = f"/processes/{resolved_process_id}/jobs/{job_id}/results"
        job_status_url = _public_endpoint_url(server_cache, target_server, job_status_path)
        job_results_url = _public_endpoint_url(server_cache, target_server, job_results_path)
        bucket["results"][result_ref] = {
            "server": target_server.url,
            "process_id": resolved_process_id,
            "job_id": job_id,
            "job_status_path": job_status_path,
            "job_results_path": job_results_path,
            "job_status_url": job_status_url,
            "job_results_url": job_results_url,
            "created_at": time.time(),
        }
        process_runs[execution_signature] = {
            "server": target_server.url,
            "process_id": resolved_process_id,
            "job_id": job_id,
            "result_ref": result_ref,
            "status": "accepted",
            "job_status_path": job_status_path,
            "job_results_path": job_results_path,
            "job_status_url": job_status_url,
            "job_results_url": job_results_url,
            "request_id": execute_context.get("request_id"),
            "trace_id": execute_context.get("trace_id"),
            "created_at": time.time(),
            "replay_count": 0,
        }

        if prefer_async:
            pending_geodata = _build_pending_result_geodata(
                state,
                process_id=resolved_process_id,
                job_id=str(job_id),
                source_name=target_server.name or target_server.url,
                result_url=job_results_url,
            )
            payload = {
                "status": "accepted",
                "server": target_server.url,
                "process_id": resolved_process_id,
                "job_id": job_id,
                "result_ref": result_ref,
                "job_status_path": job_status_path,
                "job_results_path": job_results_path,
                "job_status_url": job_status_url,
                "job_results_url": job_results_url,
                "requestId": execute_context.get("request_id"),
                "traceId": execute_context.get("trace_id"),
            }
            if resolved_process_id != requested_process_id:
                payload["requested_process_id"] = requested_process_id
            _log_event(
                "ogcapi.process.accepted",
                session_id=session_id,
                server=target_server.url,
                process_id=resolved_process_id,
                job_id=job_id,
                result_ref=result_ref,
            )
            return _success_command(
                "process_geodata",
                tool_call_id,
                payload,
                geodata_results=pending_geodata,
            )

        status_url = _endpoint_url(server_cache, job_status_path)
        final_status_payload: Dict[str, Any] = {}
        final_status_context: Dict[str, Optional[str]] = {}
        for _ in range(30):
            status_response, status_payload = _request_json(
                "GET",
                status_url,
                headers=_headers_for_server(target_server),
                retries=1,
            )
            final_status_context = _extract_request_context(status_response)
            if status_response.status_code >= 400:
                return _error_command(
                    "process_geodata",
                    tool_call_id,
                    code="job_status_failed",
                    message="Failed to poll process job status.",
                    recoverable=True,
                    retryable=True,
                    suggested_action="retry_job_status_poll",
                    detail=status_payload,
                    request_context=final_status_context,
                )
            if isinstance(status_payload, dict):
                final_status_payload = status_payload
                status_value = (status_payload.get("status") or "").lower()
                if status_value in {"successful", "failed"}:
                    break
            time.sleep(1.0)

        if (final_status_payload.get("status") or "").lower() != "successful":
            return _error_command(
                "process_geodata",
                tool_call_id,
                code="job_not_successful",
                message="Process job did not complete successfully.",
                recoverable=True,
                retryable=False,
                suggested_action="inspect_job_status_or_retry_with_adjusted_inputs",
                detail=final_status_payload,
                request_context=final_status_context,
            )

        results_url = _endpoint_url(server_cache, job_results_path)
        results_response, results_payload = _request_json(
            "GET",
            results_url,
            headers=_headers_for_server(target_server),
            retries=1,
        )
        results_context = _extract_request_context(results_response)
        if results_response.status_code >= 400 or not isinstance(results_payload, dict):
            return _error_command(
                "process_geodata",
                tool_call_id,
                code="job_results_failed",
                message="Failed to retrieve process job results.",
                recoverable=True,
                retryable=True,
                suggested_action="retry_results_fetch",
                detail=results_payload,
                request_context=results_context,
            )

        bucket["results"][result_ref]["results_payload"] = results_payload
        process_runs[execution_signature].update(
            {
                "status": "ok",
                "results_payload": results_payload,
                "feature_count": len(list(results_payload.get("features") or [])),
            }
        )
        new_geodata = _build_result_geodata(
            state,
            process_id=resolved_process_id,
            job_id=str(job_id),
            results_payload=results_payload,
            source_name=target_server.name or target_server.url,
            result_url=job_results_url,
        )

        payload: Dict[str, Any] = {
            "status": "ok",
            "server": target_server.url,
            "process_id": resolved_process_id,
            "job_id": job_id,
            "result_ref": result_ref,
            "result_format": result_format,
            "job_status_path": job_status_path,
            "job_results_path": job_results_path,
            "job_status_url": job_status_url,
            "job_results_url": job_results_url,
            "requestId": results_context.get("request_id"),
            "traceId": results_context.get("trace_id"),
        }
        if resolved_process_id != requested_process_id:
            payload["requested_process_id"] = requested_process_id

        if result_format == "features":
            features = list(results_payload.get("features") or [])
            preview_limit = min(len(features), 50)
            payload["preview_features"] = features[:preview_limit]
            payload["preview_truncated"] = len(features) > preview_limit
        elif result_format == "stats_only":
            payload["stats"] = _feature_stats(list(results_payload.get("features") or []))
        else:
            payload["feature_count"] = len(list(results_payload.get("features") or []))

        _log_event(
            "ogcapi.process.completed",
            session_id=session_id,
            server=target_server.url,
            process_id=resolved_process_id,
            job_id=job_id,
            result_ref=result_ref,
            feature_count=payload.get("feature_count"),
        )
        return _success_command(
            "process_geodata",
            tool_call_id,
            payload,
            geodata_results=new_geodata,
        )

    tools: List[BaseTool] = []
    if include_prepare:
        tools.append(prepare_geospatial_context)
    if include_filter:
        tools.append(filter_geodata)
    if include_process:
        tools.append(process_geodata)
    return tools
