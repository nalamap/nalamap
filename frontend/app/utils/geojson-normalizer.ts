/**
 * GeoJSON Normalization Utility
 * 
 * Handles normalization of various GeoJSON formats into standard FeatureCollections
 * that can be consumed by Leaflet and other mapping libraries.
 * 
 * Supports:
 * - FeatureCollection (pass-through)
 * - Single Feature
 * - Bare Geometry (Point, LineString, Polygon, etc.)
 * - GeometryCollection
 * - Arrays of Features or Geometries
 */

export class GeoJSONNormalizer {
  private static readonly GEOMETRY_TYPES = new Set([
    'Point',
    'MultiPoint',
    'LineString',
    'MultiLineString',
    'Polygon',
    'MultiPolygon',
  ]);

  /**
   * Normalize any GeoJSON-like input into a valid FeatureCollection
   */
  static normalize(input: any): any | null {
    if (!input) return null;

    // Handle arrays of features/geometries
    if (Array.isArray(input)) {
      return this.normalizeArray(input);
    }

    if (typeof input !== 'object') return null;

    // Already a proper FeatureCollection
    if (input.type === 'FeatureCollection' && Array.isArray(input.features)) {
      return input;
    }

    // Single Feature
    if (input.type === 'Feature' && input.geometry) {
      return this.wrapInFeatureCollection([input], input.crs, input.bbox);
    }

    // GeometryCollection
    if (input.type === 'GeometryCollection' && Array.isArray(input.geometries)) {
      return this.normalizeGeometryCollection(input);
    }

    // Bare Geometry
    if (this.GEOMETRY_TYPES.has(input.type) && input.coordinates) {
      return this.normalizeBareGeometry(input);
    }

    // Object with features array but missing type
    if (Array.isArray(input.features)) {
      return { ...input, type: input.type || 'FeatureCollection' };
    }

    return null;
  }

  /**
   * Normalize an array of features or geometries
   */
  private static normalizeArray(input: any[]): any | null {
    const features = input
      .map((item: any, idx: number) => {
        if (!item) return null;

        // Already a Feature
        if (item.type === 'Feature' && item.geometry) {
          return item;
        }

        // Geometry object
        if (this.GEOMETRY_TYPES.has(item.type) && item.coordinates) {
          return this.geometryToFeature(item, idx);
        }

        return null;
      })
      .filter(Boolean);

    if (!features.length) return null;

    return this.wrapInFeatureCollection(features);
  }

  /**
   * Normalize a GeometryCollection into a FeatureCollection
   */
  private static normalizeGeometryCollection(input: any): any | null {
    const features = input.geometries
      .map((geom: any, idx: number) => {
        if (!geom?.type) return null;
        return {
          type: 'Feature',
          properties: { id: idx, ...(input.properties || {}) },
          geometry: geom,
        };
      })
      .filter(Boolean);

    if (!features.length) return null;

    return this.wrapInFeatureCollection(features, input.crs, input.bbox);
  }

  /**
   * Normalize a bare geometry object
   */
  private static normalizeBareGeometry(input: any): any {
    const feature = this.geometryToFeature(input, 1);
    return this.wrapInFeatureCollection([feature], input.crs, input.bbox);
  }

  /**
   * Convert a geometry object to a Feature
   */
  private static geometryToFeature(geometry: any, defaultId: number): any {
    const props = geometry.properties && typeof geometry.properties === 'object' 
      ? { ...geometry.properties } 
      : {};

    // Add default ID if properties are empty
    if (!Object.keys(props).length) {
      if (geometry.id !== undefined) {
        props.id = geometry.id;
      } else {
        props.id = defaultId;
      }
    }

    return {
      type: 'Feature',
      properties: props,
      geometry: {
        type: geometry.type,
        coordinates: geometry.coordinates,
      },
    };
  }

  /**
   * Wrap features in a FeatureCollection with optional CRS and bbox
   */
  private static wrapInFeatureCollection(
    features: any[],
    crs?: any,
    bbox?: any
  ): any {
    const fc: any = {
      type: 'FeatureCollection',
      features,
    };

    if (crs) fc.crs = crs;
    if (bbox) fc.bbox = bbox;

    return fc;
  }

  /**
   * Extract declared CRS from GeoJSON
   */
  static extractCRS(candidate: any): string | null {
    if (!candidate || typeof candidate !== 'object') return null;

    try {
      return (
        candidate.crs?.properties?.name ||
        candidate.crs?.name ||
        candidate.features?.[0]?.crs?.properties?.name ||
        candidate.features?.[0]?.crs?.name ||
        null
      );
    } catch {
      return null;
    }
  }

  /**
   * Validate that coordinates fall within valid lat/lon ranges
   */
  static validateLatLonCoordinates(featureCollection: any): boolean {
    if (!featureCollection?.features) return true;

    try {
      for (const feature of featureCollection.features.slice(0, 5)) {
        const flat: number[] = [];

        const walk = (arr: any) => {
          if (typeof arr[0] === 'number') {
            flat.push(arr[0], arr[1]);
            return;
          }
          for (const c of arr) walk(c);
        };

        walk(feature.geometry.coordinates);

        for (let i = 0; i < flat.length; i += 2) {
          const lon = flat[i];
          const lat = flat[i + 1];

          if (Math.abs(lon) > 180 || Math.abs(lat) > 90) {
            return false;
          }
        }
      }

      return true;
    } catch {
      return true; // If validation fails, assume coordinates are valid
    }
  }
}
