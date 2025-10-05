/**
 * Test fixtures for geocoding responses
 * Based on actual backend geocoding.py responses
 */

export const germanyGeocodingResponse = {
  type: 'Feature',
  properties: {
    place_id: 364179,
    osm_type: 'relation',
    osm_id: 51477,
    display_name: 'Deutschland',
    place_rank: 4,
    category: 'boundary',
    type: 'administrative',
    importance: 0.9,
  },
  geometry: {
    type: 'Polygon',
    coordinates: [
      [
        [13.8338, 48.7758],
        [13.8339, 48.7757],
        [13.8344, 48.7754],
        [13.8338, 48.7758],
      ],
    ],
  },
  bbox: [5.8663153, 47.2701114, 15.0419319, 55.099161],
};

export const berlinGeocodingResponse = {
  type: 'Feature',
  properties: {
    place_id: 240109189,
    osm_type: 'relation',
    osm_id: 62422,
    display_name: 'Berlin, Deutschland',
    place_rank: 12,
    category: 'boundary',
    type: 'administrative',
    importance: 0.8,
  },
  geometry: {
    type: 'Point',
    coordinates: [13.404954, 52.520008],
  },
  bbox: [13.088346, 52.338234, 13.761118, 52.675499],
};

export const brazilGeocodingResponse = {
  type: 'Feature',
  properties: {
    place_id: 298318294,
    osm_type: 'relation',
    osm_id: 59470,
    display_name: 'Brasil',
    place_rank: 4,
    category: 'boundary',
    type: 'administrative',
    importance: 0.9,
  },
  geometry: {
    type: 'Polygon',
    coordinates: [
      [
        [-34.7935, -7.9389],
        [-34.7936, -7.9388],
        [-34.7940, -7.9385],
        [-34.7935, -7.9389],
      ],
    ],
  },
  bbox: [-73.9872354804, -33.7683777809, -28.6341164537, 5.2842873],
};
