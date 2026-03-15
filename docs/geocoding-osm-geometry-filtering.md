# Geocoding OSM Geometry Filtering

## Overview

NaLaMap's geocoding module includes intelligent geometry filtering for OSM
(OpenStreetMap) queries. When users search for certain types of features, the
system automatically filters results to return the most appropriate geometry
types.

## How It Works

### Wildcard Queries

When users search for broad categories like "roads", "railways", or
"waterways", the system maps these to wildcard OSM queries (e.g.,
`highway=*`). This returns all features matching the key regardless of
specific value.

### Geometry Preferences

For certain OSM keys, the system has configured geometry preferences that
control which element types (node, way, relation) are queried and which
geometry types (Point, LineString, Polygon) are included in results:

| OSM Key    | Preferred Geometries | Excluded Geometries | Excluded Values                                    |
|------------|---------------------|--------------------|----------------------------------------------------|
| `highway`  | way, relation       | node               | bus_stop, traffic_signals, crossing, etc.           |
| `railway`  | way, relation       | node               | station, signal, switch, level_crossing             |
| `waterway` | way, relation       | node               | weir, lock, dam, waterfall                          |
| `aeroway`  | way, relation       | node               | gate                                                |
| `power`    | way, relation       | node               | tower, pole, substation, generator                  |

### Polygon Exclusion for Linear Features

For feature types that are inherently linear (roads, railways, waterways,
aeroways, power lines), Polygon geometries are automatically excluded from
results. This ensures that:

- Highway queries return LineString road segments, not polygon areas
- Railway queries return linear tracks, not polygon station buildings
- Waterway queries return linear rivers/streams, not polygon reservoirs

### Multi-Layer Filtering

The filtering operates at three levels:

1. **Query Construction**: Element types (node/way/relation) are
   selectively included in the Overpass query based on geometry preferences
2. **Element Filtering**: Raw elements from Overpass are filtered by
   geometry type and excluded values before GeoJSON conversion
3. **GeoJSON Geometry Filtering**: Converted GeoJSON features are filtered
   by geometry type (Point/LineString/Polygon)

## Supported Wildcard Mappings

Users can search using natural language terms that map to wildcard queries:

- **Roads**: "road", "roads", "street", "streets", "highway", "infrastructure"
- **Military**: "military", "defense", "defence", "armed forces"
- **Aviation**: "aeroway", "aviation", "air transport"
- **Natural**: "natural", "nature", "geographic feature", "landform"
- **Waterways**: "waterway", "water" (generic), "river", "stream" (specific)
- **Buildings**: "building", "structure", "construction"
- **Places**: "place", "location", "settlement"
- **Railway**: "railway", "rail"
- **Boundaries**: "boundary", "border", "administrative"
- **Land use**: "landuse", "land use", "zone"
