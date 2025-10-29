import json
import logging

import geopandas as gpd
from shapely.ops import unary_union

from services.tools.geoprocessing.projection_utils import (
    prepare_gdf_for_operation,
    OperationType,
)

logger = logging.getLogger(__name__)


def op_buffer(
    layers,
    radius=10000,
    buffer_crs="EPSG:3857",
    radius_unit="meters",
    dissolve=False,
    auto_optimize_crs: bool = False,
    projection_metadata: bool = False,
    override_crs: str | None = None,
):
    """
    Buffers features of a single input layer item individually or dissolved.
    If multiple layers are provided, this function will raise a ValueError.
    Input geometries are assumed in EPSG:4326. This function:
      1) Expects `layers` to be a list containing a single layer item
         (FeatureCollection or Feature).
      2) Converts radius to meters based on radius_unit (default is "meters").
      3) Extracts features from the single layer item.
      4) Creates a GeoDataFrame from these features.
      5) Reprojects the GeoDataFrame to buffer_crs (default EPSG:3857,
         which uses meters).
      6) Applies buffer to each feature geometry with the meter-based radius.
      7) Optionally dissolves all buffered geometries into a single geometry
         if dissolve=True.
      8) Reprojects the GeoDataFrame (with buffered features) back to
         EPSG:4326.
      9) Returns a list containing one FeatureCollection with the individually
         buffered features (or single dissolved feature if dissolve=True).
    Supported radius_unit: "meters", "kilometers", "miles".
    """
    if not layers:
        logger.warning("op_buffer called with no layers")
        return []  # No input layer, return empty list

    if len(layers) > 1:
        # Extract layer names/titles if available for better error information
        layer_info = []
        for i, layer in enumerate(layers):
            name = None
            if isinstance(layer, dict):
                props = layer.get("properties", {})
                if props:
                    name = props.get("name") or props.get("title")
                # Also try to get name from features if it's a FeatureCollection
                if not name and layer.get("type") == "FeatureCollection" and layer.get("features"):
                    first_feat = layer["features"][0] if layer["features"] else None
                    if first_feat and isinstance(first_feat, dict):
                        props = first_feat.get("properties", {})
                        if props:
                            name = props.get("name") or props.get("title")
            layer_info.append("Layer {i+1}" + (": {name}" if name else ""))

        layer_desc = ", ".join(layer_info)
        raise ValueError(
            f"Buffer operation error: Only one layer can be buffered at a time. Received {len(layers)} layers: {layer_desc}. Please specify a single target layer."
        )

    layer_item = layers[0]  # Process the single layer provided
    unit = radius_unit.lower()
    factor = {"meters": 1.0, "kilometers": 1000.0, "miles": 1609.34}.get(unit)
    if factor is None:
        logger.warning(f"Unknown radius_unit '{radius_unit}', assuming meters")
        factor = 1.0

    actual_radius_meters = float(radius) * factor

    current_features = []
    if isinstance(layer_item, dict):
        if layer_item.get("type") == "FeatureCollection":
            current_features = layer_item.get("features", [])
        elif layer_item.get("type") == "Feature":
            current_features = [layer_item]

    if not current_features:
        # This case might occur if the single layer_item was an empty FeatureCollection or invalid
        print(
            "Warning: The provided layer item is empty or not a recognizable Feature/FeatureCollection: {type(layer_item)}"
        )
        return []

    # Ensure all features have 'properties' field (GeoJSON spec requirement)
    # This prevents KeyError when geopandas tries to access feature["properties"]
    for feature in current_features:
        if isinstance(feature, dict) and "properties" not in feature:
            feature["properties"] = {}

    try:
        gdf = gpd.GeoDataFrame.from_features(current_features)
        gdf.set_crs("EPSG:4326", inplace=True)

        # Smart CRS selection / preparation
        if auto_optimize_crs:
            gdf_reprojected, crs_info = prepare_gdf_for_operation(
                gdf,
                OperationType.BUFFER,
                auto_optimize_crs=auto_optimize_crs,
                override_crs=override_crs or (None if buffer_crs == "EPSG:3857" else buffer_crs),
            )
        elif override_crs:
            # User specified a CRS explicitly
            gdf_reprojected = gdf.to_crs(override_crs)
            crs_info = {
                "epsg_code": override_crs,
                "selection_reason": "User-specified CRS",
                "auto_selected": False,
            }
        else:
            # Use default buffer_crs
            gdf_reprojected = gdf.to_crs(buffer_crs)
            crs_info = {
                "epsg_code": buffer_crs,
                "selection_reason": "Default CRS",
                "auto_selected": False,
            }

        gdf_reprojected["geometry"] = gdf_reprojected.geometry.buffer(actual_radius_meters)

        # If dissolve is True, merge all buffered geometries into one
        if dissolve:
            dissolved_geom = unary_union(gdf_reprojected.geometry)
            # Create a new GeoDataFrame with the dissolved geometry
            # Keep properties from the first feature
            props = {}
            if len(gdf.columns) > 1:
                for col in gdf.columns:
                    if col != "geometry":
                        props[col] = gdf[col].iloc[0]
            gdf_buffered_individual = gpd.GeoDataFrame(
                [props], geometry=[dissolved_geom], crs=gdf_reprojected.crs
            )
        else:
            gdf_buffered_individual = gdf_reprojected

        gdf_buffered_individual = gdf_buffered_individual.to_crs("EPSG:4326")

        if gdf_buffered_individual.empty:
            return []  # Resulting GeoDataFrame is empty

        fc = json.loads(gdf_buffered_individual.to_json())

        # Inject projection metadata if requested
        if projection_metadata and fc:
            # fc is a FeatureCollection dict
            if "properties" not in fc:
                fc["properties"] = {}
            fc["properties"]["_crs_metadata"] = crs_info

        return [fc]  # Return a list containing the single FeatureCollection
    except Exception as e:
        logger.exception(f"Error in op_buffer: {e}")
        return []
