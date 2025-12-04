# OSM Geometry Filtering System

## Overview

The OSM Geometry Filtering system ensures that geocoding queries return the correct geometry types (nodes, ways, relations) based on user intent. This solves the problem where queries like "highways" or "roads" would return point features (bus stops, traffic signals) instead of linear features (actual road segments).

## Problem Statement

In OpenStreetMap, many tag keys can have both point features (nodes) and linear/polygon features (ways/relations). For example:

- **Highway key**: 
  - Nodes: `highway=bus_stop`, `highway=traffic_signals`, `highway=crossing`
  - Ways: `highway=motorway`, `highway=primary`, `highway=secondary` (actual roads)

- **Railway key**:
  - Nodes: `railway=station`, `railway=signal`
  - Ways: `railway=rail` (actual tracks)

When users query for "highways" or "roads", they expect actual road segments (ways), not point infrastructure. The geometry filtering system ensures this by:

1. **Query-time filtering**: Excluding unwanted element types from Overpass queries (e.g., exclude nodes for highway queries)
2. **Result-time filtering**: Filtering out unwanted elements from query results (e.g., exclude nodes and excluded tag values)
3. **GeoJSON geometry filtering**: Excluding unwanted GeoJSON geometry types (e.g., exclude Polygon geometries for highway queries, keeping only LineString)

## How It Works

### Configuration-Based Approach

Geometry preferences are defined in `backend/services/tools/constants.py` in the `OSM_GEOMETRY_PREFERENCES` dictionary:

```python
OSM_GEOMETRY_PREFERENCES = {
    "highway": {
        "preferred_geometries": ["way", "relation"],
        "exclude_geometries": ["node"],
        "exclude_values": {"bus_stop", "traffic_signals", "crossing", ...},
        "description": "Roads are linear features (ways), not point infrastructure"
    },
    ...
}
```

### Configuration Options

Each OSM key can have:

- **`preferred_geometries`**: List of geometry types to include in queries (`["way", "relation"]`)
- **`exclude_geometries`**: List of geometry types to exclude (`["node"]`)
- **`exclude_values`**: Set of specific tag values to exclude (e.g., `{"bus_stop", "traffic_signals"}`)
- **`description`**: Human-readable description of the filtering logic

### Default Behavior

Keys not in `OSM_GEOMETRY_PREFERENCES` will:
- Include all geometry types (node, way, relation) in queries
- Not filter any elements from results

This ensures backward compatibility with existing queries.

## Currently Configured Keys

### Highway

- **Excludes**: 
  - OSM element types: Nodes (bus stops, traffic signals, crossings, etc.)
  - GeoJSON geometry types: Polygons (roads should be linear features, not areas)
- **Includes**: Ways and relations with LineString geometry (actual road segments)
- **Excluded values**: `bus_stop`, `traffic_signals`, `crossing`, `stop`, `give_way`, `mini_roundabout`, `motorway_junction`

**Example**: Querying `highway=*` returns only linear road segments (LineString), not bus stops (Point) or polygon areas (Polygon).

### Railway

- **Excludes**: 
  - OSM element types: Nodes (stations, signals, switches)
  - GeoJSON geometry types: Polygons (tracks should be linear features)
- **Includes**: Ways and relations with LineString geometry (railway tracks)
- **Excluded values**: `station`, `signal`, `switch`, `level_crossing`

**Example**: Querying `railway=*` returns only linear tracks (LineString), not stations (Point) or polygon areas (Polygon).

### Waterway

- **Excludes**: Nodes (weirs, locks, dams, waterfalls)
- **Includes**: Ways and relations (rivers, streams, canals)
- **Excluded values**: `weir`, `lock`, `dam`, `waterfall`

**Example**: Querying `waterway=*` returns only waterways, not point features.

### Aeroway

- **Excludes**: Nodes (gates)
- **Includes**: Ways and relations (runways, taxiways)
- **Excluded values**: `gate`

**Example**: Querying `aeroway=*` returns only aeroway features, not gates.

### Power

- **Excludes**: Nodes (towers, poles, substations, generators)
- **Includes**: Ways and relations (power lines)
- **Excluded values**: `tower`, `pole`, `substation`, `generator`

**Example**: Querying `power=*` returns only power lines, not infrastructure points.

## Adding New Keys

To add geometry filtering for a new OSM key:

1. **Open** `backend/services/tools/constants.py`

2. **Add entry** to `OSM_GEOMETRY_PREFERENCES`:

```python
OSM_GEOMETRY_PREFERENCES = {
    # ... existing entries ...
    "your_key": {
        "preferred_geometries": ["way", "relation"],  # or ["node", "way", "relation"]
        "exclude_geometries": ["node"],  # or [] if none
        "exclude_values": {"point_feature1", "point_feature2"},
        "description": "Your description here"
    },
}
```

3. **Test** your changes:

```bash
cd backend
poetry run pytest tests/test_osm_geometry_filtering.py -v
```

4. **Update tests** if needed in `backend/tests/test_osm_geometry_filtering.py`

## Implementation Details

### Helper Functions

Four helper functions in `backend/services/tools/geocoding.py` handle the filtering:

1. **`get_geometry_preferences(osm_key)`**: Returns preferences for a key, or defaults
2. **`should_include_element_in_query(osm_key, osm_value, element_type)`**: Determines if an element type should be queried
3. **`should_include_element_in_results(element, osm_key, osm_value)`**: Determines if an element should be included in results
4. **`should_include_geojson_geometry(geojson_geometry_type, osm_key)`**: Determines if a GeoJSON geometry type (Point, LineString, Polygon) should be included

### Query Construction

The Overpass query construction (lines 848-876 in `geocoding.py`) uses `should_include_element_in_query()` to conditionally add element types:

```python
if should_include_element_in_query(osm_query_key, osm_query_value, "node"):
    overpass_query_parts.append(f"  node{tag_filter}(area.search_area);")
if should_include_element_in_query(osm_query_key, osm_query_value, "way"):
    overpass_query_parts.append(f"  way{tag_filter}(area.search_area);")
# ...
```

### Result Processing

The result processing loop (line 1001 in `geocoding.py`) uses multiple filtering layers:

1. **Element-level filtering**: Uses `should_include_element_in_results()` to filter OSM elements:
```python
for element in overpass_data["elements"]:
    if not should_include_element_in_results(element, osm_query_key, osm_query_value):
        continue
    # ... process element ...
```

2. **GeoJSON geometry filtering**: Uses `should_include_geojson_geometry()` to filter GeoJSON geometry types:
```python
geom_type = feature_dict["geometry"]["type"]
if not should_include_geojson_geometry(geom_type, osm_query_key):
    continue
# ... add to appropriate collection ...
```

This ensures that for highway queries, only LineString geometries are returned (excluding Polygon areas).

## Examples

### Highway Query

**User query**: "add all roads from Paris to the map"

**OSM query**: `highway=*` in Paris area

**Before filtering**: Returns both:
- Point features: bus stops, traffic signals, crossings
- Linear features: motorways, primary roads, secondary roads

**After filtering**: Returns only:
- Linear features: motorways, primary roads, secondary roads

### Railway Query

**User query**: "show railway infrastructure in Berlin"

**OSM query**: `railway=*` in Berlin area

**Before filtering**: Returns both:
- Point features: stations, signals
- Linear features: railway tracks

**After filtering**: Returns only:
- Linear features: railway tracks

## Testing

Comprehensive test suite in `backend/tests/test_osm_geometry_filtering.py`:

- **Configuration tests**: Verify all preferences are properly defined
- **Helper function tests**: Test preference retrieval and filtering logic
- **Integration tests**: Test query construction with filtering
- **Edge case tests**: Handle missing data, empty lists, etc.

Run tests:

```bash
cd backend
poetry run pytest tests/test_osm_geometry_filtering.py -v
```

## Troubleshooting

### Issue: Query returns unexpected geometry types

**Solution**: Check if the OSM key is configured in `OSM_GEOMETRY_PREFERENCES`. If not, add it following the "Adding New Keys" section above.

### Issue: Specific values are incorrectly excluded

**Solution**: Check the `exclude_values` set for the key. Remove values that should be included, or add values that should be excluded.

### Issue: All elements are excluded

**Solution**: Verify that `preferred_geometries` is not empty and includes the geometry types you want.

## Related Documentation

- [AGENTS.md](../AGENTS.md) - Development guidelines
- [ARCHITECTURE.md](../ARCHITECTURE.md) - System architecture
- [README.md](../README.md) - Project overview

## Future Enhancements

Potential improvements:

1. **Value-specific preferences**: Different preferences for different tag values (e.g., `railway=station` should include nodes)
2. **User intent detection**: Automatically detect user intent from query context
3. **Performance optimization**: Cache preferences lookups
4. **Configuration validation**: Validate configuration at startup

