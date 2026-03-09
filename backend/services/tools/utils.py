import difflib
from typing import Any, Dict, List

from models.geodata import GeoDataObject


def get_all_available_layers(state: Dict[str, Any]) -> List[GeoDataObject]:
    """
    Return the combined pool of layers available for tool input:
    geodata_layers (user's map layers) + geodata_last_results (previous tool outputs).

    This enables multi-step plan chaining: a geoprocess tool can find
    geocoded results produced by a prior step.
    """
    layers = list(state.get("geodata_layers") or [])
    last_results = state.get("geodata_last_results") or []

    # Deduplicate by (id, data_source_id) — prefer geodata_layers entries
    seen = {(layer.id, layer.data_source_id) for layer in layers}
    for item in last_results:
        key = (item.id, item.data_source_id)
        if key not in seen:
            layers.append(item)
            seen.add(key)

    return layers


def match_layer_names(layers: List[Any], target_names: List[str], cutoff: float = 0.6) -> List[Any]:
    """
    Match user-provided layer names to available layers using fuzzy matching.

    Args:
        layers: List of layer objects with .name and .title attributes.
        target_names: List of names/titles to match.
        cutoff: Similarity threshold for fuzzy matching (0 to 1).

    Returns:
        A list of matched layer objects.
    """
    available_names = [layer.name for layer in layers]
    available_titles = [getattr(layer, "title", layer.name) for layer in layers]
    matched_layers: List[Any] = []
    unmatched: List[str] = []

    for name in target_names:
        # Try exact match first (case-insensitive)
        for layer in layers:
            if (
                layer.name.lower() == name.lower()
                or (getattr(layer, "title", "") or "").lower() == (name or "").lower()
            ):
                matched_layers.append(layer)
                break
        else:
            # Try fuzzy matching on names
            best_matches = difflib.get_close_matches(name, available_names, n=1, cutoff=cutoff)
            if best_matches:
                best_name = best_matches[0]
                matched_layer = next(layer for layer in layers if layer.name == best_name)
                matched_layers.append(matched_layer)
            else:
                # Try fuzzy matching on titles
                best_title_matches = difflib.get_close_matches(
                    name, available_titles, n=1, cutoff=cutoff
                )
                if best_title_matches:
                    best_title = best_title_matches[0]
                    matched_layer = next(
                        layer
                        for layer in layers
                        if getattr(layer, "title", layer.name) == best_title
                    )
                    matched_layers.append(matched_layer)
                else:
                    unmatched.append(name)

    return matched_layers
