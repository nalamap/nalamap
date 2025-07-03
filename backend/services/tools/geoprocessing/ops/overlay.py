import logging
import json
from typing import Any, Dict, List

import geopandas as gpd

from services.tools.geoprocessing.utils import flatten_features

logger = logging.getLogger(__name__)


def op_overlay(
    layers: List[Dict[str, Any]], how: str = "intersection", crs: str = "EPSG:3857"
) -> List[Dict[str, Any]]:
    """
    Perform a set-based overlay across N layers. Supports 'intersection', 'union',
    'difference', 'symmetric_difference', and 'identity'. For N > 2, applies the operation iteratively:
      result = overlay(layer1, layer2, how)
      result = overlay(result, layer3, how)
      crs : str, default "EPSG:3857"
        Working Coordinate Reference System used *internally* for the overlay.
        Provide a projected CRS (e.g. equal-area or Web Mercator) for more
        accurate operations. **The output will always be reprojected to
        EPSG:4326.**
      ...
    Returns a single FeatureCollection (in a list) of the final result.
    """
    if len(layers) < 2:
        # Not enough layers to overlay; return original layers unchanged
        return layers

    def _layer_to_gdf(layer: Dict[str, Any]) -> gpd.GeoDataFrame:
        feats = flatten_features([layer])
        gdf = gpd.GeoDataFrame.from_features(feats)
        if gdf.crs is None:
            gdf.set_crs("EPSG:4326", inplace=True)
        return gdf.to_crs(crs)

    try:
        result_gdf = _layer_to_gdf(layers[0])
    except Exception as exc:
        logger.exception("Error preparing base layer for overlay: %s", exc)
        return []

    for layer in layers[1:]:
        try:
            next_gdf = _layer_to_gdf(layer)
            result_gdf = gpd.overlay(result_gdf, next_gdf, how=how)

            # Exit early if the intermediate result is empty
            if result_gdf.empty:
                return [{"type": "FeatureCollection", "features": []}]

        except Exception as exc:
            logger.exception("Error during overlay with layer: %s", exc)
            return []

    try:
        if not result_gdf.empty:
            result_gdf = result_gdf.to_crs("EPSG:4326")
    except Exception as exc:
        logger.exception("Error reprojecting result to EPSG:4326: %s", exc)
        return [{"type": "FeatureCollection", "features": []}]

    fc = json.loads(result_gdf.to_json())
    return [fc]
