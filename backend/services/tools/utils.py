import difflib
from typing import Any, List


def match_layer_names(layers: List[Any], target_names: List[str], cutoff: float = 0.6) -> List[Any]:
    """
    Match user-provided layer names to available layers using fuzzy matching.

    Args:
        layers: List of layer objects with a .name attribute.
        target_names: List of names to match.
        cutoff: Similarity threshold for fuzzy matching (0 to 1).

    Returns:
        A list of matched layer objects.
    """
    available_names = [layer.name for layer in layers]
    matched_layers: List[Any] = []
    unmatched: List[str] = []

    for name in target_names:
        # Find the closest match above the cutoff
        best_matches = difflib.get_close_matches(name, available_names, n=1, cutoff=cutoff)
        if best_matches:
            best_name = best_matches[0]
            # Retrieve the layer with this name
            matched_layer = next(layer for layer in layers if layer.name == best_name)
            matched_layers.append(matched_layer)
        else:
            unmatched.append(name)

    return matched_layers
