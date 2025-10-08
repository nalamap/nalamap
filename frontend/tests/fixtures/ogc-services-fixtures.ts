/**
 * Test fixtures for OGC services (WMS, WFS, WMTS, WCS)
 * Based on common GeoServer and other OGC service responses
 */

export const wmsLayerMetadata = {
  id: "wms-layer-1",
  name: "World Boundaries",
  title: "World Country Boundaries",
  layer_type: "WMS",
  data_link:
    "https://demo.geo-solutions.it/geoserver/wms?service=WMS&version=1.1.0&request=GetMap&layers=topp:states&styles=&bbox=-124.73142200000001,24.955967,-66.969849,49.371735&width=768&height=330&srs=EPSG:4326&format=image/png",
  bounding_box: [-180, -90, 180, 90],
  visible: true,
  data_source_id: "geoserver",
};

export const wfsLayerMetadata = {
  id: "wfs-layer-1",
  name: "US States",
  title: "United States State Boundaries",
  layer_type: "WFS",
  data_link:
    "https://demo.geo-solutions.it/geoserver/wfs?service=WFS&version=1.0.0&request=GetFeature&typeName=topp:states&outputFormat=application/json&srsName=EPSG:4326",
  bounding_box: [-124.73142200000001, 24.955967, -66.969849, 49.371735],
  visible: true,
  data_source_id: "geoserver",
};

export const wfsFeatureCollectionResponse = {
  type: "FeatureCollection",
  features: [
    {
      type: "Feature",
      id: "states.1",
      geometry: {
        type: "MultiPolygon",
        coordinates: [
          [
            [
              [-88.071564, 37.51099],
              [-88.087883, 37.476273],
              [-88.311707, 37.442852],
              [-88.359177, 37.409309],
              [-88.071564, 37.51099],
            ],
          ],
        ],
      },
      properties: {
        STATE_NAME: "Illinois",
        STATE_FIPS: "17",
        SUB_REGION: "E N Cen",
        STATE_ABBR: "IL",
        LAND_KM: 143986.61,
        WATER_KM: 1993.335,
      },
    },
    {
      type: "Feature",
      id: "states.2",
      geometry: {
        type: "MultiPolygon",
        coordinates: [
          [
            [
              [-95.774704, 35.395519],
              [-94.720764, 36.102715],
              [-94.436127, 36.501861],
              [-94.048164, 36.501861],
              [-95.774704, 35.395519],
            ],
          ],
        ],
      },
      properties: {
        STATE_NAME: "Oklahoma",
        STATE_FIPS: "40",
        SUB_REGION: "W S Cen",
        STATE_ABBR: "OK",
        LAND_KM: 177847.52,
        WATER_KM: 3185.517,
      },
    },
  ],
  totalFeatures: 49,
  numberMatched: 49,
  numberReturned: 2,
  timeStamp: "2025-01-01T12:00:00.000Z",
  crs: {
    type: "name",
    properties: {
      name: "urn:ogc:def:crs:EPSG::4326",
    },
  },
};

export const wmtsLayerMetadata = {
  id: "wmts-layer-1",
  name: "OSM Tiles",
  title: "OpenStreetMap WMTS Layer",
  layer_type: "WMTS",
  data_link: "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
  properties: {
    tile_matrix_sets: ["EPSG:3857", "GoogleMapsCompatible"],
  },
  bounding_box: [-180, -85.0511, 180, 85.0511],
  visible: true,
  data_source_id: "osm",
};

export const wcsLayerMetadata = {
  id: "wcs-layer-1",
  name: "DEM Elevation",
  title: "Digital Elevation Model",
  layer_type: "WCS",
  data_link:
    "https://demo.geo-solutions.it/geoserver/wcs?service=WCS&version=2.0.1&request=GetCoverage&coverageId=nurc__Arc_Sample&format=image/tiff",
  bounding_box: [-180, -90, 180, 90],
  visible: true,
  data_source_id: "geoserver",
};

// Mock GeoJSON responses for single features (testing normalization)
export const singleFeatureResponse = {
  type: "Feature",
  properties: {
    name: "Test Point",
    category: "test",
  },
  geometry: {
    type: "Point",
    coordinates: [10.0, 50.0],
  },
};

export const singleGeometryResponse = {
  type: "Point",
  coordinates: [10.0, 50.0],
  properties: {
    name: "Bare Geometry Point",
  },
};

export const geometryCollectionResponse = {
  type: "GeometryCollection",
  geometries: [
    {
      type: "Point",
      coordinates: [10.0, 50.0],
    },
    {
      type: "LineString",
      coordinates: [
        [10.0, 50.0],
        [11.0, 51.0],
      ],
    },
  ],
  properties: {
    name: "Mixed Geometry Collection",
  },
};
