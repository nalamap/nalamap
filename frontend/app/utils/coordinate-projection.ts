/**
 * Coordinate Projection Utility
 * 
 * Handles coordinate transformations between different projection systems,
 * particularly Web Mercator (EPSG:3857) and WGS84 (EPSG:4326).
 */

export class CoordinateProjection {
  private static readonly EARTH_RADIUS = 6378137; // meters
  private static readonly MAX_WEB_MERCATOR = 20050000; // meters (with padding)

  /**
   * Convert Web Mercator (EPSG:3857) coordinates to WGS84 (EPSG:4326)
   */
  static webMercatorToWGS84(x: number, y: number): [number, number] {
    const lon = (x / this.EARTH_RADIUS) * 180 / Math.PI;
    const lat = (2 * Math.atan(Math.exp(y / this.EARTH_RADIUS)) - Math.PI / 2) * 180 / Math.PI;
    return [lon, lat];
  }

  /**
   * Convert WGS84 (EPSG:4326) coordinates to Web Mercator (EPSG:3857)
   */
  static wgs84ToWebMercator(lon: number, lat: number): [number, number] {
    const x = this.EARTH_RADIUS * lon * Math.PI / 180;
    const y = this.EARTH_RADIUS * Math.log(Math.tan(Math.PI / 4 + lat * Math.PI / 360));
    return [x, y];
  }

  /**
   * Determine if coordinates appear to be in Web Mercator projection
   */
  static looksLikeWebMercator(x: number, y: number, declaredCrs?: string): boolean {
    // Check declared CRS first
    if (declaredCrs) {
      if (/3857|900913/i.test(declaredCrs)) return true;
      if (/4326/i.test(declaredCrs)) return false;
    }

    // Heuristic: Web Mercator values are large and outside lat/lon ranges
    const inWebMercatorRange = Math.abs(x) <= this.MAX_WEB_MERCATOR && 
                                Math.abs(y) <= this.MAX_WEB_MERCATOR;
    const outsideLatLonRange = Math.abs(x) > 180 || Math.abs(y) > 90;

    return inWebMercatorRange && outsideLatLonRange;
  }

  /**
   * Extract first coordinate pair from any geometry
   */
  static extractFirstCoordinate(geometry: any): [number, number] | null {
    if (!geometry?.coordinates) return null;

    const dive = (coords: any): any => {
      if (!Array.isArray(coords)) return null;
      if (typeof coords[0] === 'number' && typeof coords[1] === 'number') {
        return coords as [number, number];
      }
      return dive(coords[0]);
    };

    const result = dive(geometry.coordinates);
    return Array.isArray(result) && result.length >= 2 ? [result[0], result[1]] : null;
  }

  /**
   * Reproject an entire geometry from Web Mercator to WGS84
   */
  static reprojectGeometry(geometry: any): any {
    if (!geometry || !geometry.type) return geometry;

    const reprojectCoord = (coord: [number, number]): [number, number] => {
      return this.webMercatorToWGS84(coord[0], coord[1]);
    };

    const reprojectCoords = (coords: any): any => {
      if (!Array.isArray(coords)) return coords;
      if (typeof coords[0] === 'number') {
        return reprojectCoord(coords as [number, number]);
      }
      return coords.map(reprojectCoords);
    };

    switch (geometry.type) {
      case 'Point':
        return {
          type: 'Point',
          coordinates: reprojectCoord(geometry.coordinates),
        };

      case 'MultiPoint':
        return {
          type: 'MultiPoint',
          coordinates: geometry.coordinates.map((c: [number, number]) => reprojectCoord(c)),
        };

      case 'LineString':
        return {
          type: 'LineString',
          coordinates: geometry.coordinates.map((c: [number, number]) => reprojectCoord(c)),
        };

      case 'MultiLineString':
        return {
          type: 'MultiLineString',
          coordinates: geometry.coordinates.map((line: [number, number][]) =>
            line.map(reprojectCoord)
          ),
        };

      case 'Polygon':
        return {
          type: 'Polygon',
          coordinates: geometry.coordinates.map((ring: [number, number][]) =>
            ring.map(reprojectCoord)
          ),
        };

      case 'MultiPolygon':
        return {
          type: 'MultiPolygon',
          coordinates: geometry.coordinates.map((polygon: [number, number][][]) =>
            polygon.map((ring: [number, number][]) => ring.map(reprojectCoord))
          ),
        };

      default:
        return geometry;
    }
  }

  /**
   * Reproject an entire FeatureCollection from Web Mercator to WGS84
   */
  static reprojectFeatureCollection(featureCollection: any): any {
    if (!featureCollection?.features) return featureCollection;

    return {
      ...featureCollection,
      features: featureCollection.features.map((feature: any) => ({
        ...feature,
        geometry: this.reprojectGeometry(feature.geometry),
      })),
      crs: {
        type: 'name',
        properties: { name: 'EPSG:4326' },
      },
    };
  }

  /**
   * Validate that coordinates are within valid WGS84 ranges
   */
  static validateWGS84Coordinates(geometry: any): boolean {
    if (!geometry?.coordinates) return true;

    const validate = (coords: any): boolean => {
      if (!Array.isArray(coords)) return true;

      if (typeof coords[0] === 'number') {
        const [lon, lat] = coords;
        return Math.abs(lon) <= 180 && Math.abs(lat) <= 90;
      }

      return coords.every(validate);
    };

    return validate(geometry.coordinates);
  }

  /**
   * Auto-detect and reproject coordinates if needed
   */
  static autoReproject(featureCollection: any, declaredCrs?: string): any {
    if (!featureCollection?.features?.length) return featureCollection;

    // Extract first coordinate
    const firstFeature = featureCollection.features[0];
    const firstCoord = this.extractFirstCoordinate(firstFeature?.geometry);

    if (!firstCoord) return featureCollection;

    // Check if reprojection is needed
    const needsReprojection = this.looksLikeWebMercator(
      firstCoord[0],
      firstCoord[1],
      declaredCrs
    );

    if (!needsReprojection) return featureCollection;

    // Reproject
    console.log('Auto-reprojecting from Web Mercator (EPSG:3857) to WGS84 (EPSG:4326)');
    const reprojected = this.reprojectFeatureCollection(featureCollection);

    // Validate reprojection succeeded
    const firstReprojected = this.extractFirstCoordinate(reprojected.features[0]?.geometry);
    if (firstReprojected && !this.validateWGS84Coordinates({ coordinates: firstReprojected })) {
      console.warn('Reprojection produced invalid coordinates, returning original');
      return featureCollection;
    }

    return reprojected;
  }
}
