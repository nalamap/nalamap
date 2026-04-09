"""Helpers for enriching OGC collection layer payloads."""

from typing import Any
from urllib.parse import urlparse, urlunparse

import core.config as core_config


def _is_ogc_collection_layer(data_link: Any, payload: dict[str, Any]) -> bool:
    properties = payload.get("properties")
    if isinstance(properties, dict):
        collection_id = properties.get("ogc_collection_id")
        if isinstance(collection_id, str) and collection_id.strip():
            return True
        for key in ("ogc_items_url", "ogc_tiles_url", "ogc_tiles_metadata_url"):
            value = properties.get(key)
            if isinstance(value, str) and "/collections/" in value:
                return True

    return isinstance(data_link, str) and "/collections/" in data_link


def _rewrite_ogcapi_url_to_public(url: Any) -> Any:
    if not isinstance(url, str) or not url.strip():
        return url

    public_base = (core_config.OGCAPI_PUBLIC_BASE_URL or core_config.OGCAPI_BASE_URL or "").rstrip(
        "/"
    )
    if not public_base:
        return url

    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return url

    runtime_base = (core_config.OGCAPI_BASE_URL or "").rstrip("/")
    runtime_parsed = urlparse(runtime_base) if runtime_base else None
    public_parsed = urlparse(public_base)

    hostname = (parsed.hostname or "").lower()
    runtime_hostname = (runtime_parsed.hostname or "").lower() if runtime_parsed else ""
    runtime_netloc = runtime_parsed.netloc if runtime_parsed else ""
    if hostname not in {"ogcapi", runtime_hostname} and parsed.netloc != runtime_netloc:
        return url

    new_path = parsed.path or ""
    public_prefix = (public_parsed.path or "").rstrip("/")
    if public_prefix and not new_path.startswith(public_prefix + "/") and new_path != public_prefix:
        if not new_path.startswith("/"):
            new_path = "/" + new_path
        new_path = f"{public_prefix}{new_path}"

    rewritten = parsed._replace(
        scheme=public_parsed.scheme or parsed.scheme,
        netloc=public_parsed.netloc or parsed.netloc,
        path=new_path,
    )
    return urlunparse(rewritten)


def _rewrite_layer_ogc_urls(layer_data: dict[str, Any]) -> dict[str, Any]:
    payload = layer_data.get("payload")
    payload_dict = payload if isinstance(payload, dict) else {}
    properties = payload_dict.get("properties")
    properties_dict = properties if isinstance(properties, dict) else {}

    changed = False
    rewritten_data_link = _rewrite_ogcapi_url_to_public(layer_data.get("data_link"))
    rewritten_properties = properties_dict

    for key in ("ogc_items_url", "ogc_tiles_url", "ogc_tiles_metadata_url", "file_url"):
        value = properties_dict.get(key)
        rewritten_value = _rewrite_ogcapi_url_to_public(value)
        if rewritten_value == value:
            continue
        if rewritten_properties is properties_dict:
            rewritten_properties = {**properties_dict}
        rewritten_properties[key] = rewritten_value
        changed = True

    if rewritten_data_link != layer_data.get("data_link"):
        changed = True

    if not changed:
        return layer_data

    rewritten_layer = {**layer_data, "data_link": rewritten_data_link}
    if rewritten_properties is not properties_dict:
        rewritten_layer["payload"] = {
            **payload_dict,
            "properties": rewritten_properties,
        }
    return rewritten_layer


def inject_ogc_vector_tile_threshold(layer_data: dict[str, Any]) -> dict[str, Any]:
    """Normalize OGC URLs and attach the active vector-tile threshold."""
    layer_data = _rewrite_layer_ogc_urls(layer_data)
    payload = layer_data.get("payload")
    payload_dict = payload if isinstance(payload, dict) else {}
    if not _is_ogc_collection_layer(layer_data.get("data_link"), payload_dict):
        return layer_data

    properties = payload_dict.get("properties")
    properties_dict = properties if isinstance(properties, dict) else {}
    if "ogc_vector_tile_feature_threshold" in properties_dict:
        return layer_data

    return {
        **layer_data,
        "payload": {
            **payload_dict,
            "properties": {
                **properties_dict,
                "ogc_vector_tile_feature_threshold": (
                    core_config.OGCAPI_VECTOR_TILE_FEATURE_THRESHOLD
                ),
            },
        },
    }


def normalize_ogc_geodata_payload(item: Any) -> Any:
    if hasattr(item, "model_dump"):
        layer_data = item.model_dump()
    elif isinstance(item, dict):
        layer_data = dict(item)
    else:
        return item

    if "data_link" not in layer_data:
        return layer_data

    return inject_ogc_vector_tile_threshold(layer_data)


def normalize_ogc_geodata_payloads(items: list[Any] | None) -> list[Any]:
    if not items:
        return []
    return [normalize_ogc_geodata_payload(item) for item in items]
