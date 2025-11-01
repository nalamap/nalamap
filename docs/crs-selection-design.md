# Intelligent CRS Selection for Geoprocessing

## Overview

NaLaMap implements a **hybrid intelligent CRS selection system** combining:
- **LLM-based planning**: The agent reasons about user intent, data characteristics, and operation types
- **Rule-based execution**: Deterministic projection selection with full transparency and auditability

This document describes the multi-factor decision algorithm, buffer strategy, thresholds, and metadata design.

## Problem Statement

Using a single global projection (EPSG:3857 Web Mercator) for all geoprocessing operations causes:
- Large area errors at high latitudes (>10% at polar regions)
- Distance inaccuracies across UTM zone boundaries
- Topology artifacts (slivers/gaps) in overlays
- No support above ~85° latitude
- Poor buffer accuracy for large radii or high-latitude regions

## Hybrid System Architecture

### LLM Role: Planning & Context
- Understands user intent from natural language queries
- Determines operation sequences and parameters
- Considers data characteristics and analysis goals
- Passes structured requests to rule-based subsystems

### Rule-Based Role: Execution & Math
- Deterministic projection selection with transparent decision paths
- Validated EPSG-only policy (no custom PROJ/WKT for debuggability)
- Geodesic vs planar buffer selection based on geometry and thresholds
- Full metadata trace for reproducibility

## Multi-Factor Decision Algorithm

### Inputs
The `decide_projection()` function considers:
- **Bounding box** (min_lon, min_lat, max_lon, max_lat in EPSG:4326)
- **Centroid** and **extremes** (latitude range)
- **Extents** (longitude/latitude span in degrees and km)
- **Area** (approximate km²)
- **Orientation ratio** (EW/NS; values >1 indicate EW-dominant)
- **UTM zone span** (number of zones crossed)
- **Antimeridian crossing** (boolean)
- **Region** (continental identification)
- **Operation type** (area, buffer, clip, etc.)

### Decision Order (with Thresholds)

1. **Validate bbox**
   - If out of range (-180 to 180, -90 to 90): fallback to EPSG:3857
   - If near-global (≥180° lon or ≥170° lat): fallback to EPSG:3857

2. **Polar regions** (|center_lat| ≥ 80° OR extremes beyond ±85°)
   - Equal-area ops → LAEA (EPSG:3571 Arctic, EPSG:3572 Antarctic)
   - Conformal ops → Polar Stereographic (EPSG:3995 Arctic, EPSG:3031 Antarctic)
   - Expected error: 0-2%

3. **Local extent** (lon_extent ≤ 6° AND lat_extent ≤ 6°)
   - **UTM zone seam check**: If zone_span ≥ 2 AND lon_extent ≥ 3°, skip UTM
   - Otherwise: Use UTM zone at centroid (EPSG:326xx N, EPSG:327xx S)
   - Expected error: <0.1%

4. **Regional extent**
   - **EW-dominant check**: If orientation_ratio ≥ 1.5, prefer Lambert Conformal Conic (LCC)
   - **Large area check**: If area_km² ≥ 2,000,000, prefer equal-area (Albers/LAEA)
   - Otherwise: Use operation-appropriate projection per region:
     - Equal-area: Albers (North America: EPSG:102008, Europe: EPSG:3035, etc.)
     - Conformal: LCC (North America: EPSG:102009, Europe: EPSG:3034, etc.)
   - Expected error: 0.5-1%

5. **Multi-zone or antimeridian crossing**
   - If zone_span ≥ 3 or antimeridian crossing: prefer regional equal-area
   - If spans hemispheres: fallback to EPSG:3857

6. **Fallback**: EPSG:3857 with logged reason

### Thresholds Summary

| Criteria | Threshold | Action |
|----------|-----------|--------|
| Local extent | Both extents ≤ 6° | Consider UTM |
| UTM zone seam | zone_span ≥ 2 AND lon_extent ≥ 3° | Avoid UTM, use regional |
| EW-dominant | orientation_ratio ≥ 1.5 | Prefer LCC |
| Large area | area_km² ≥ 2,000,000 | Prefer equal-area |
| Polar | \|center_lat\| ≥ 80° OR extremes beyond ±85° | Use polar projections |
| Near-equator | \|center_lat\| ≤ 10° | Favor UTM when local |

## Buffer Strategy: Hybrid Planar/Geodesic

### Method Selection

The `choose_buffer_method()` function selects:

**Geodesic (ellipsoid-based)** if ANY of:
- Radius > 50 km
- |center_lat| ≥ 75°
- zone_span ≥ 2 (crosses UTM zones)
- antimeridian crossing
- Non-local extent (lon_extent > 6° OR lat_extent > 6°)

**Otherwise: Planar (projection-based)**

### Buffer Implementation

#### Planar Path
- Use CRS selected by projection algorithm
- Apply standard `geometry.buffer(radius_m)` in projected space
- Fast and integrates seamlessly with other planar ops

#### Geodesic Path (Phase 1: Points only)
- For Point/MultiPoint: approximate geodesic circle via `pyproj.Geod`
  - Calculate points at regular azimuths (36-180 bearings based on radius)
  - Larger radii → more points for accuracy
- For LineString/Polygon: fallback to planar (logged) in Phase 1
- No reprojection; stays in EPSG:4326

### Buffer Metadata

All buffers include:
- `buffer_method`: "planar" or "geodesic"
- `buffer_method_reason`: Human-readable decision rationale
- `radius_m`: Radius in meters
- Plus standard CRS metadata (epsg_code, crs_name, etc.)

## Area Calculation Strategy: Hybrid Planar/Geodesic

### Method Selection

The `choose_area_method()` function selects:

**Geodesic (ellipsoid-based)** if ANY of:
- |center_lat| ≥ 75°
- zone_span ≥ 2 (crosses UTM zones)
- Antimeridian crossing
- Non-local extent (lon_extent > 6° OR lat_extent > 6°)

**Otherwise: Planar (projection-based)**

### Area Implementation

#### Planar Path
- Use equal-area CRS selected by projection algorithm
- Apply standard `geometry.area` in projected space
- Fast and accurate for local/regional extents

#### Geodesic Path
- For Polygon/MultiPolygon: calculate area on WGS84 ellipsoid via `pyproj.Geod`
- Handles exterior rings and interior holes correctly
- No reprojection; stays in EPSG:4326
- Accurate globally, especially for high latitudes and zone seams

### Area Metadata

All area calculations include:
- `area_method`: "planar" or "geodesic"
- `area_method_reason`: Human-readable decision rationale
- Plus standard CRS metadata (for planar) or geodesic indicator

### Area API

- `area_method="auto"` (default): Choose based on thresholds
- `area_method="planar"`: Force planar (uses equal-area CRS)
- `area_method="geodesic"`: Force geodesic (ellipsoid calculation)
- `projection_metadata=True`: Include full metadata in response

## Operation → Projection Property Mapping

| Operation | Required Property | Notes |
|-----------|-------------------|-------|
| area | equal-area (planar) or geodesic | Auto-select based on extent/latitude |
| dissolve | equal-area | Preserve area during merge |
| buffer | conformal (planar) or geodesic | Auto-select based on radius/latitude |
| clip | conformal | Preserve topology |
| overlay | conformal | Preserve topology |
| simplify | conformal | Preserve shape |
| sjoin | compromise | Spatial joins less sensitive |
| sjoin_nearest | equidistant | Distance-based matching |

## Metadata Design

### CRS Metadata Fields

All operations return `_crs_metadata` with:

```json
{
  "epsg_code": "EPSG:32633",
  "crs_name": "WGS 84 / UTM zone 33N",
  "projection_property": "conformal",
  "selection_reason": "Local extent - UTM zone 33N; <0.1% distance error",
  "expected_error": 0.1,
  "auto_selected": true,
  "decision_path": [
    "Computed bbox metrics: center=(13.50, 52.50)",
    "Operation buffer requires property=conformal",
    "Local extent: 3.0° × 2.0°",
    "Using UTM zone 33"
  ],
  "decision_inputs": {
    "bbox": [12.0, 51.5, 15.0, 53.5],
    "centroid": [13.5, 52.5],
    "extents_deg": [3.0, 2.0],
    "extents_km": [220.5, 222.6],
    "area_km2": 49078.3,
    "orientation_ratio": 0.99,
    "zone_span": 1,
    "operation_type": "buffer",
    "required_property": "conformal"
  }
}
```

### Buffer-Specific Metadata

For buffer operations, additional fields:

```json
{
  "buffer_method": "geodesic",
  "buffer_method_reason": "High latitude (78.5°); Large radius (100.0 km > 50 km)",
  "radius_m": 100000
}
```

## API

### Flags
- `auto_optimize_crs=True`: Enable smart CRS selection (default via `enable_smart_crs` setting)
- `projection_metadata=True`: Include full metadata in response
- `override_crs="EPSG:XXXX"`: Force specific CRS (disables auto-selection)
- `projection_priority=ProjectionProperty.EQUAL_AREA`: Override property selection

### Functions
- `decide_projection(bbox, operation_type, ...)`: Core decision algorithm
- `compute_bbox_metrics(bbox)`: Calculate all decision inputs
- `choose_buffer_method(gdf, radius_m, bbox_metrics)`: Select planar vs geodesic
- `prepare_gdf_for_operation(gdf, operation_type, ...)`: Reproject with optimal CRS

## Testing

### Test Coverage
- `test_projection_decider.py`: Decision algorithm, thresholds, edge cases
- `test_buffer_method_selection.py`: Buffer method selection, geodesic accuracy
- `test_projection_utils.py`: Helper functions, UTM zones, metrics
- Integration tests: End-to-end operation accuracy

### Test Scenarios
- UTM selection vs zone seam avoidance
- EW-dominant triggering LCC
- Large area triggering equal-area
- Polar region handling (Arctic/Antarctic, equal-area/conformal)
- Antimeridian crossing
- Geodesic vs planar buffer selection
- High-latitude geodesic buffer accuracy
- Metadata completeness

## Deployment & Rollout

### Backward Compatibility
- Default `auto_optimize_crs=True` when `enable_smart_crs` setting is enabled
- Legacy behavior preserved when `auto_optimize_crs=False`
- Existing `buffer_crs` parameter still supported as override

### Monitoring
- Full decision trace logged via `decision_path`
- Decision inputs captured for reproducibility
- Performance metrics for geodesic vs planar buffers

### Rollback
- Disable via `enable_smart_crs=False` in settings
- Per-operation override via `override_crs` or `auto_optimize_crs=False`

## Design Principles

1. **Transparency**: Every decision is logged with reasoning and inputs
2. **Reproducibility**: Same inputs → same outputs (deterministic)
3. **Auditability**: Full metadata trace in responses
4. **Debuggability**: EPSG-only policy (no opaque PROJ strings)
5. **Interoperability**: Validated CRS codes work across tools
6. **Performance**: Cached transforms, efficient heuristics
7. **Accuracy**: < 0.1% error for local ops, < 2% for regional/polar

## Future Work

- **Phase 2 Geodesic buffers**: Extend to LineString/Polygon geometries
- **Geodesic distance/area ops**: Direct ellipsoid calculations
- **Dynamic thresholds**: User-configurable via settings
- **Projection caching**: Reduce overhead for repeated operations
- **Advanced heuristics**: Consider data density, feature count, analysis workflow

## Examples

### Example 1: Local Buffer (Berlin)

**Input**: Point at (13.4°E, 52.5°N), 10 km buffer

**Decision**:
- bbox_metrics: local extent (3° × 2°), zone 33, mid-latitude
- choose_buffer_method → planar (local + moderate radius)
- decide_projection → EPSG:32633 (UTM 33N, conformal)
- Expected error: <0.1%

### Example 2: High-Latitude Buffer (Arctic)

**Input**: Point at (10°E, 78°N), 10 km buffer

**Decision**:
- bbox_metrics: local extent, zone 33, high latitude (78°)
- choose_buffer_method → geodesic (high latitude ≥ 75°)
- No projection (stays EPSG:4326, geodesic on ellipsoid)
- Expected error: <0.01% for distance

### Example 3: Wide EW Strip (US)

**Input**: Polygon covering (-120°W to -70°W, 35°N to 45°N), clip operation

**Decision**:
- bbox_metrics: 50° × 10° extent, EW-dominant ratio = 5.0
- decide_projection → EPSG:102009 (North America LCC, conformal)
- Reason: EW-dominant orientation favors LCC over Albers
- Expected error: ~1%

### Example 4: Large Area Dissolve (North America)

**Input**: Polygons covering (-130°W to -60°W, 25°N to 50°N), dissolve operation

**Decision**:
- bbox_metrics: area ~8 million km², regional extent
- decide_projection → EPSG:102008 (North America Albers, equal-area)
- Reason: Large area + equal-area operation
- Expected error: ~0.5% for area

### Example 5: Area Calculation (Arctic Polygon)

**Input**: Polygon at (10°E to 20°E, 78°N to 80°N), area calculation

**Decision**:
- bbox_metrics: high latitude (center_lat = 79°N)
- choose_area_method → geodesic (high latitude ≥ 75°)
- Method: pyproj.Geod.polygon_area_perimeter on WGS84 ellipsoid
- No projection; stays in EPSG:4326
- Expected error: <0.01% for area

### Example 6: Area Calculation (Local European Region)

**Input**: Polygon covering (10°E to 15°E, 48°N to 52°N), area calculation

**Decision**:
- bbox_metrics: local extent (5° × 4°), mid-latitude
- choose_area_method → planar (local extent suitable for equal-area projection)
- decide_projection → EPSG:3035 (Europe LAEA, equal-area)
- Expected error: <0.5% for area

## References

- [EPSG Registry](https://epsg.io/)
- [pyproj Documentation](https://pyproj4.github.io/pyproj/)
- [Shapely Geodesic Operations](https://shapely.readthedocs.io/)
- [Map Projections Overview](https://en.wikipedia.org/wiki/List_of_map_projections)
