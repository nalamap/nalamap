/**
 * Test fixtures for Overpass API responses
 * Based on actual backend geocoding.py overpass responses
 */

export const brazilHospitalsOverpassResponse = {
  type: 'FeatureCollection',
  features: [
    {
      type: 'Feature',
      id: 'node/123456',
      properties: {
        '@id': 'node/123456',
        amenity: 'hospital',
        name: 'Hospital das Clínicas',
        emergency: 'yes',
        operator: 'State Government',
        'addr:city': 'São Paulo',
      },
      geometry: {
        type: 'Point',
        coordinates: [-46.6633, -23.5505],
      },
    },
    {
      type: 'Feature',
      id: 'way/789012',
      properties: {
        '@id': 'way/789012',
        amenity: 'hospital',
        name: 'Hospital São Paulo',
        emergency: 'yes',
        beds: '500',
      },
      geometry: {
        type: 'Polygon',
        coordinates: [
          [
            [-46.6650, -23.5520],
            [-46.6648, -23.5520],
            [-46.6648, -23.5518],
            [-46.6650, -23.5518],
            [-46.6650, -23.5520],
          ],
        ],
      },
    },
    {
      type: 'Feature',
      id: 'node/345678',
      properties: {
        '@id': 'node/345678',
        amenity: 'hospital',
        name: 'Hospital Albert Einstein',
        emergency: 'yes',
        operator: 'Private',
      },
      geometry: {
        type: 'Point',
        coordinates: [-46.7000, -23.5800],
      },
    },
  ],
};

export const parisRestaurantsOverpassResponse = {
  type: 'FeatureCollection',
  features: [
    {
      type: 'Feature',
      id: 'node/111222',
      properties: {
        '@id': 'node/111222',
        amenity: 'restaurant',
        name: 'Le Petit Bistro',
        cuisine: 'french',
      },
      geometry: {
        type: 'Point',
        coordinates: [2.3522, 48.8566],
      },
    },
    {
      type: 'Feature',
      id: 'node/333444',
      properties: {
        '@id': 'node/333444',
        amenity: 'restaurant',
        name: 'Chez Pierre',
        cuisine: 'french',
      },
      geometry: {
        type: 'Point',
        coordinates: [2.3500, 48.8550],
      },
    },
  ],
};
