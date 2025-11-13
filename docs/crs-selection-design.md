# Intelligent CRS Selection for Geoprocessing

## Overview

NaLaMap implements a **smart planar CRS selection system** that automatically chooses optimal projections for geoprocessing operations based on data extent, location, and operation type. The system combines:
- **LLM-based planning**: The agent reasons about user intent, data characteristics, and operation types
- **Rule-based execution**: Deterministic projection selection with full transparency and auditability

This document describes the multi-factor decision algorithm, accuracy expectations, thresholds, and metadata design.

## Problem Statement

Using a single global projection (EPSG:3857 Web Mercator) for all geoprocessing operations causes:
- Large area errors at high latitudes (>10% at polar regions)
- Distance inaccuracies across UTM zone boundaries
- Topology artifacts (slivers/gaps) in overlays
- No support above ~85° latitude
- Poor buffer accuracy for large radii or high-latitude regions

## Solution Architecture

### LLM Role: Planning & Context
- Understands user intent from natural language queries
- Determines operation sequences and parameters
- Considers data characteristics and analysis goals
- Passes structured requests to rule-based projection system

### Rule-Based Role: Execution & Math
- Deterministic projection selection with transparent decision paths
- EPSG UTM for local/single-zone extents; WKT-based custom projections for regional/polar
- Smart planar CRS selection based on extent, latitude, and operation type
- Full metadata trace for reproducibility (includes WKT when used)

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
   - Equal-area ops → custom WKT LAEA (centered on pole)
   - Conformal ops → custom WKT Polar Stereographic
   - Expected error: 0-2%

3. **Local extent** (lon_extent ≤ 6° AND lat_extent ≤ 6°)
   - **UTM zone seam check**: If zone_span ≥ 2 AND lon_extent ≥ 3°, skip UTM
   - Otherwise: Use UTM zone at centroid (EPSG:326xx N, EPSG:327xx S)
   - Expected error: <0.1%

4. **Regional extent**
   - **EW-dominant check**: If orientation_ratio ≥ 1.5, prefer Lambert Conformal Conic (LCC)
   - **Large area check**: If area_km² ≥ 2,000,000, prefer equal-area (Albers/LAEA)
   - Otherwise: Use operation-appropriate projection:
     - Equal-area: custom WKT Albers (2SP), parameters from bbox
     - Conformal: custom WKT LCC (2SP), parameters from bbox
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

## Accuracy Expectations

The smart planar CRS selection system provides excellent accuracy for the vast majority of GIS use cases:

### Typical Accuracy Levels

| Scenario | CRS Selection | Expected Error | Use Cases |
|----------|---------------|----------------|-----------|
| **Local operations** (< 6° extent) | UTM zone | < 0.1% | Urban planning, site analysis, local studies |
| **Regional operations** (6-30° extent) | LCC/Albers | 0.5-1% | State/country analysis, regional conservation |
| **High latitude** (>80°) | Polar projections | 1-3% | Arctic/Antarctic research |
| **Trans-oceanic** (>30° extent) | Regional or Web Mercator | 2-5% | Ocean shipping, global analysis |

### When Accuracy May Be Reduced

The system remains highly accurate for 99% of use cases. Edge cases with inherent limitations include:

1. **Extreme polar regions** (>80° latitude)
   - All planar projections have 1-3% distortion
   - Selected: Arctic/Antarctic Polar Stereographic or LAEA
   - Still acceptable for most polar research applications

2. **Trans-oceanic spans** (crossing many UTM zones)
   - No single projection covers large ocean areas without distortion
   - Selected: Best regional projection or Web Mercator
   - 2-5% accuracy is typical for such extents

3. **Critical legal boundaries**
   - Maritime boundaries, international borders
   - May require <0.1% accuracy (survey-grade)
   - Consider specialized surveying tools for such applications

### Recommended Approach

For most users:
- **Enable `auto_optimize_crs=True`** (default in smart mode)
- System automatically selects best projection
- Check CRS metadata to understand which projection was used
- Accuracy is transparent and documented in results

## Operation → Projection Property Mapping

| Operation | Required Property | Notes |
|-----------|-------------------|-------|
| area | equal-area | Preserve area measurements |
| dissolve | equal-area | Preserve area during merge |
| buffer | conformal | Preserve distances and shapes |
| clip | conformal | Preserve topology |
| overlay | conformal | Preserve topology |
| simplify | conformal | Preserve shape |
| sjoin | compromise | Spatial joins less sensitive |
| sjoin_nearest | equidistant | Distance-based matching |

## Metadata Design

### CRS Metadata Fields

All operations return `_crs_metadata` with (EPSG or WKT depending on selection):

```json
{
  "authority": "EPSG",
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


## API

### Flags
- `auto_optimize_crs=True`: Enable smart CRS selection (default via `enable_smart_crs` setting)
- `projection_metadata=True`: Include full metadata in response
- `override_crs="EPSG:XXXX"`: Force specific CRS (disables auto-selection)
- `projection_priority=ProjectionProperty.EQUAL_AREA`: Override property selection

### Functions
- `decide_projection(bbox, operation_type, ...)`: Core decision algorithm
- `compute_bbox_metrics(bbox)`: Calculate all decision inputs
- `prepare_gdf_for_operation(gdf, operation_type, ...)`: Reproject with optimal CRS

## Testing

### Test Coverage
- `test_projection_decider.py`: Decision algorithm, thresholds, edge cases
- `test_projection_utils.py`: Helper functions, UTM zones, metrics
- Integration tests: End-to-end operation accuracy

### Test Scenarios
- UTM selection vs zone seam avoidance
- EW-dominant triggering LCC
- Large area triggering equal-area
- Polar region handling (Arctic/Antarctic, equal-area/conformal)
- Antimeridian crossing
- Planar buffer accuracy across extents
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

- **Dynamic thresholds**: User-configurable via settings
- **Projection caching**: Reduce overhead for repeated operations
- **Advanced heuristics**: Consider data density, feature count, analysis workflow
- **Performance optimizations**: Further improve transformation speed

## Examples

### Example 1: Local Buffer (Berlin)

**Input**: Point at (13.4°E, 52.5°N), 10 km buffer

**Decision**:
- bbox_metrics: local extent (3° × 2°), zone 33, mid-latitude
- decide_projection → EPSG:32633 (UTM 33N, conformal)
- Planar buffer in UTM 33N projection
- Expected error: <0.1%

### Example 2: High-Latitude Buffer (Arctic)

**Input**: Point at (10°E, 78°N), 10 km buffer

**Decision**:
- bbox_metrics: local extent, zone 33, high latitude (78°)
 - decide_projection → WKT Polar Stereographic (conformal)
 - Planar buffer in custom Polar Stereographic projection
- Expected error: ~1-2% (acceptable for most polar applications)

### Example 3: Wide EW Strip (US)

**Input**: Polygon covering (-120°W to -70°W, 35°N to 45°N), clip operation

**Decision**:
- bbox_metrics: 50° × 10° extent, EW-dominant ratio = 5.0
- decide_projection → WKT LCC (conformal)
- Reason: EW-dominant orientation favors LCC over Albers
- Expected error: ~1%

### Example 4: Large Area Dissolve (North America)

**Input**: Polygons covering (-130°W to -60°W, 25°N to 50°N), dissolve operation

**Decision**:
- bbox_metrics: area ~8 million km², regional extent
- decide_projection → WKT Albers (equal-area)
- Reason: Large area + equal-area operation
- Expected error: ~0.5% for area

### Example 5: Area Calculation (Arctic Polygon)

**Input**: Polygon at (10°E to 20°E, 78°N to 80°N), area calculation

**Decision**:
- bbox_metrics: high latitude (center_lat = 79°N), local extent
- decide_projection → WKT LAEA (equal-area)
- Planar area calculation in custom Polar LAEA
- Expected error: ~1-2% (acceptable for most polar applications)

### Example 6: Area Calculation (Local European Region)

**Input**: Polygon covering (10°E to 15°E, 48°N to 52°N), area calculation

**Decision**:
- bbox_metrics: local extent (5° × 4°), mid-latitude
- decide_projection → WKT Albers (equal-area)
- Planar area calculation in custom Albers projection
- Expected error: <0.5% for area

## References

- [EPSG Registry](https://epsg.io/)
- [pyproj Documentation](https://pyproj4.github.io/pyproj/)
- [Shapely Geodesic Operations](https://shapely.readthedocs.io/)
- [Map Projections Overview](https://en.wikipedia.org/wiki/List_of_map_projections)
