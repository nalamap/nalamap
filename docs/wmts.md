# WMTS Handling and WebMercator Filtering

The system prefers WMTS layers that provide WebMercator (EPSG:3857 family) tile matrix sets. 

## Environment Variable: `NALAMAP_FILTER_NON_WEBMERCATOR_WMTS`

Controls whether WMTS layers that do NOT advertise a WebMercator-compatible TileMatrixSet are filtered out server-side.

Default: `true` (enabled)

Accepted truthy values (case-insensitive): `true`, `1`, `yes`, `on`
Accepted falsy values: `false`, `0`, `no`, `off`

When enabled and a WMTS layer lacks any of these matrix set name patterns, it is excluded:
- `EPSG:3857`
- `900913`
- `GoogleMapsCompatible`
- `WebMercatorQuad`
- any name containing `google` or `mercator` (case-insensitive)

## Rationale
Displaying non-WebMercator tiles directly may lead to visual misalignment and projection inconsistency in the frontend map (which is configured for WebMercator). Filtering reduces user confusion.

## Overriding
To allow all WMTS layers regardless of projection:
```bash
export NALAMAP_FILTER_NON_WEBMERCATOR_WMTS=false
```

## Exposed Layer Properties (WMTS)
Each WMTS `GeoDataObject.properties` now includes:
- `tile_matrix_sets`: all advertised matrix set identifiers
- `webmercator_matrix_sets`: those matching WebMercator patterns
- `preferred_matrix_set`: the one chosen (prioritizing EPSG:3857)
- `has_webmercator`: boolean flag

## Generated KVP Template
If a preferred WebMercator matrix set exists, the backend constructs a KVP tile URL template of the form:
```
.../gwc/service/wmts?service=WMTS&version=1.0.0&request=GetTile&layer=<LAYER>&style=&tilematrixset=<MATRIXSET>&format=image/png&tilematrix=<MATRIXSET>:{z}&tilerow={y}&tilecol={x}
```
Placeholders `{z}`, `{x}`, `{y}` are replaced client-side by Leaflet.

## Frontend Behavior
The frontend additionally filters / selects WebMercator variants; this redundancy is intentional for safety and clearer UX.

## Warning
Disabling the filter can introduce layers that render with incorrect geographic alignment unless client-side reprojection is implemented for those tiles.
