"""
Dissolve operation: merge/dissolve geometries into a single unified geometry.
"""

import json
import logging
from typing import Any, Dict, List, Optional

import geopandas as gpd
from shapely.ops import unary_union

from services.tools.geoprocessing.utils import flatten_features

logger = logging.getLogger(__name__)


def op_dissolve(
    layers: List[Dict[str, Any]],
    by: Optional[str] = None,
    aggfunc: str = "first",
    crs: str = "EPSG:3857",
) -> List[Dict[str, Any]]:
    """
    Dissolve geometries into a unified geometry, optionally grouped by an attribute.

    This operation merges all geometries from one or more layers into a single
    geometry (or multiple geometries if grouping by an attribute).

    Args:
        layers: List of GeoJSON Feature or FeatureCollection dicts
        by: Optional attribute name to group by before dissolving
        aggfunc: Aggregation function for non-geometry columns ('first', 'last',
                'sum', 'mean', 'min', 'max')
        crs: Working CRS for the operation (default EPSG:3857)

    Returns:
        A list containing a single FeatureCollection with dissolved geometries
    """
    if not layers:
        logger.warning("op_dissolve called with no layers")
        return []

    # Flatten all features from all layers
    all_features = flatten_features(layers)
    if not all_features:
        logger.warning("No features found in layers")
        return []

    try:
        # Create GeoDataFrame from all features
        gdf = gpd.GeoDataFrame.from_features(all_features)
        if gdf.crs is None:
            gdf.set_crs("EPSG:4326", inplace=True)

        # Reproject to working CRS
        gdf = gdf.to_crs(crs)

        # Perform dissolve
        if by and by in gdf.columns:
            # Dissolve by attribute
            dissolved = gdf.dissolve(by=by, aggfunc=aggfunc)
            # Reset index to bring 'by' column back as regular column
            dissolved = dissolved.reset_index()
        else:
            # Dissolve all into a single geometry
            if len(gdf) == 0:
                return []

            # Create a single dissolved geometry
            dissolved_geom = unary_union(gdf.geometry)

            # Create a new GeoDataFrame with the dissolved geometry
            # Keep properties from the first feature
            props = {}
            if not gdf.empty and len(gdf.columns) > 1:
                # Get first row properties (excluding geometry)
                for col in gdf.columns:
                    if col != "geometry":
                        if aggfunc == "first":
                            props[col] = gdf[col].iloc[0]
                        elif aggfunc == "last":
                            props[col] = gdf[col].iloc[-1]
                        elif aggfunc == "sum":
                            props[col] = gdf[col].sum()
                        elif aggfunc == "mean":
                            props[col] = gdf[col].mean()
                        elif aggfunc == "min":
                            props[col] = gdf[col].min()
                        elif aggfunc == "max":
                            props[col] = gdf[col].max()

            dissolved = gpd.GeoDataFrame([props], geometry=[dissolved_geom], crs=gdf.crs)

        # Reproject back to EPSG:4326
        dissolved = dissolved.to_crs("EPSG:4326")

        # Convert to GeoJSON
        fc = json.loads(dissolved.to_json())
        return [fc]

    except Exception as exc:
        logger.exception(f"Error in op_dissolve: {exc}")
        return []
