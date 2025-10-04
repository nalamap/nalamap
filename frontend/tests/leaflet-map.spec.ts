import { test, expect, Page } from '@playwright/test';
import {
  germanyGeocodingResponse,
  brazilGeocodingResponse,
} from './fixtures/geocoding-fixtures';
import {
  brazilHospitalsOverpassResponse,
} from './fixtures/overpass-fixtures';
import {
  wmsLayerMetadata,
  wfsLayerMetadata,
  wfsFeatureCollectionResponse,
  wmtsLayerMetadata,
  wcsLayerMetadata,
  singleFeatureResponse,
  singleGeometryResponse,
  geometryCollectionResponse,
} from './fixtures/ogc-services-fixtures';

/**
 * Helper to setup API mocks for backend endpoints
 */
async function setupBackendMocks(page: Page) {
  // Mock backend health/initialization endpoints
  await page.route('**/api/**', (route) => {
    const url = route.request().url();
    
    // Mock health check
    if (url.includes('/health')) {
      route.fulfill({ status: 200, body: JSON.stringify({ status: 'ok' }) });
      return;
    }

    // Mock settings endpoint
    if (url.includes('/settings')) {
      route.fulfill({
        status: 200,
        body: JSON.stringify({
          agent_settings: { model: 'test-model' },
          available_models: ['test-model'],
        }),
      });
      return;
    }

    // Default: continue with original request
    route.continue();
  });
}

/**
 * Helper to add a layer to the map via the layer store
 */
async function addLayerViaStore(page: Page, layer: any) {
  await page.evaluate((layerData) => {
    // Access Zustand store directly
    const { useLayerStore } = window as any;
    if (useLayerStore) {
      useLayerStore.getState().addLayer(layerData);
    }
  }, layer);
}

/**
 * Helper to wait for map initialization
 */
async function waitForMapReady(page: Page) {
  // Wait for Leaflet map container
  await page.waitForSelector('.leaflet-container', { timeout: 10000 });
  // Wait for tiles to start loading
  await page.waitForTimeout(1000);
}

/**
 * Helper to check if layer is visible on map
 */
async function isLayerVisible(page: Page, layerId: string): Promise<boolean> {
  return page.evaluate((id) => {
    const { useLayerStore } = window as any;
    if (!useLayerStore) return false;
    
    const layers = useLayerStore.getState().layers;
    const layer = layers.find((l: any) => l.id === id);
    return layer?.visible === true;
  }, layerId);
}

/**
 * Helper to toggle layer visibility
 */
async function toggleLayerVisibility(page: Page, layerId: string) {
  await page.evaluate((id) => {
    const { useLayerStore } = window as any;
    if (useLayerStore) {
      useLayerStore.getState().toggleLayerVisibility(id);
    }
  }, layerId);
}

/**
 * Helper to get layer count
 */
async function getLayerCount(page: Page): Promise<number> {
  return page.evaluate(() => {
    const { useLayerStore } = window as any;
    if (!useLayerStore) return 0;
    return useLayerStore.getState().layers.length;
  });
}

test.describe('LeafletMapClient - Geocoding Tests', () => {
  test.beforeEach(async ({ page }) => {
    await setupBackendMocks(page);
    await page.goto('/');
    await waitForMapReady(page);
  });

  test('should display Germany geocoding result', async ({ page }) => {
    // Mock the geocoding endpoint
    await page.route('**/uploads/**', (route) => {
      if (route.request().url().includes('germany')) {
        route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(germanyGeocodingResponse),
        });
      } else {
        route.continue();
      }
    });

    // Create a layer object for Germany
    const germanyLayer = {
      id: 'germany-geocode-1',
      name: 'Germany',
      title: 'Germany Boundary',
      layer_type: 'UPLOADED',
      data_link: '/uploads/germany.geojson',
      visible: true,
      data_source_id: 'geocodeNominatim',
      bounding_box: [5.8663153, 47.2701114, 15.0419319, 55.099161],
    };

    // Add layer via store
    await addLayerViaStore(page, germanyLayer);

    // Wait for layer to be processed
    await page.waitForTimeout(2000);

    // Check that layer exists in store
    const layerCount = await getLayerCount(page);
    expect(layerCount).toBeGreaterThan(0);

    // Check that layer is visible
    const visible = await isLayerVisible(page, 'germany-geocode-1');
    expect(visible).toBe(true);

    // Check for GeoJSON layer rendering (Leaflet should have path elements)
    const geoJsonPaths = await page.locator('.leaflet-overlay-pane path').count();
    expect(geoJsonPaths).toBeGreaterThan(0);
  });

  test('should display Brazil geocoding result', async ({ page }) => {
    await page.route('**/uploads/**', (route) => {
      if (route.request().url().includes('brazil')) {
        route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(brazilGeocodingResponse),
        });
      } else {
        route.continue();
      }
    });

    const brazilLayer = {
      id: 'brazil-geocode-1',
      name: 'Brasil',
      title: 'Brazil Boundary',
      layer_type: 'UPLOADED',
      data_link: '/uploads/brazil.geojson',
      visible: true,
      data_source_id: 'geocodeNominatim',
      bounding_box: [-73.9872354804, -33.7683777809, -28.6341164537, 5.2842873],
    };

    await addLayerViaStore(page, brazilLayer);
    await page.waitForTimeout(2000);

    const visible = await isLayerVisible(page, 'brazil-geocode-1');
    expect(visible).toBe(true);

    const geoJsonPaths = await page.locator('.leaflet-overlay-pane path').count();
    expect(geoJsonPaths).toBeGreaterThan(0);
  });
});

test.describe('LeafletMapClient - Overpass Tests', () => {
  test.beforeEach(async ({ page }) => {
    await setupBackendMocks(page);
    await page.goto('/');
    await waitForMapReady(page);
  });

  test('should display Brazil hospitals from Overpass', async ({ page }) => {
    await page.route('**/uploads/**', (route) => {
      if (route.request().url().includes('brazil_hospitals')) {
        route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(brazilHospitalsOverpassResponse),
        });
      } else {
        route.continue();
      }
    });

    const hospitalsLayer = {
      id: 'brazil-hospitals-1',
      name: 'Hospitals in Brazil',
      title: 'Brazilian Hospitals',
      layer_type: 'UPLOADED',
      data_link: '/uploads/brazil_hospitals.geojson',
      visible: true,
      data_source_id: 'geocodeOverpassCollection',
    };

    await addLayerViaStore(page, hospitalsLayer);
    await page.waitForTimeout(2000);

    // Verify layer is added
    const layerCount = await getLayerCount(page);
    expect(layerCount).toBe(1);

    // Verify layer is visible
    const visible = await isLayerVisible(page, 'brazil-hospitals-1');
    expect(visible).toBe(true);

    // Check for markers/paths (hospitals should render as circle markers or polygons)
    const markers = await page.locator('.leaflet-marker-pane, .leaflet-overlay-pane path, .leaflet-overlay-pane circle').count();
    expect(markers).toBeGreaterThan(0);
  });

  test('BUG REPRODUCTION: Brazil hospitals visibility after toggle', async ({ page }) => {
    /**
     * This test reproduces the bug where layers only show after disable/re-enable
     * Expected: Layer shows immediately after adding
     * Actual: Layer might not show until toggled
     */
    await page.route('**/uploads/**', (route) => {
      if (route.request().url().includes('brazil_hospitals')) {
        route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(brazilHospitalsOverpassResponse),
        });
      } else {
        route.continue();
      }
    });

    const hospitalsLayer = {
      id: 'brazil-hospitals-toggle',
      name: 'Hospitals Toggle Test',
      title: 'Brazilian Hospitals Toggle',
      layer_type: 'UPLOADED',
      data_link: '/uploads/brazil_hospitals.geojson',
      visible: true,
      data_source_id: 'geocodeOverpassCollection',
    };

    // Add layer
    await addLayerViaStore(page, hospitalsLayer);
    await page.waitForTimeout(1500);

    // Check initial visibility
    const initialVisible = await isLayerVisible(page, 'brazil-hospitals-toggle');
    const initialMarkers = await page.locator('.leaflet-overlay-pane path, .leaflet-overlay-pane circle').count();
    
    console.log(`Initial state - Visible: ${initialVisible}, Markers: ${initialMarkers}`);

    // Toggle off
    await toggleLayerVisibility(page, 'brazil-hospitals-toggle');
    await page.waitForTimeout(500);

    const afterToggleOff = await isLayerVisible(page, 'brazil-hospitals-toggle');
    expect(afterToggleOff).toBe(false);

    // Toggle back on
    await toggleLayerVisibility(page, 'brazil-hospitals-toggle');
    await page.waitForTimeout(1500);

    const afterToggleOn = await isLayerVisible(page, 'brazil-hospitals-toggle');
    const markersAfterToggle = await page.locator('.leaflet-overlay-pane path, .leaflet-overlay-pane circle').count();

    console.log(`After toggle - Visible: ${afterToggleOn}, Markers: ${markersAfterToggle}`);

    // ASSERTION: Markers should appear after toggle
    expect(afterToggleOn).toBe(true);
    expect(markersAfterToggle).toBeGreaterThan(0);

    // BUG CHECK: If markers only appear after toggle but not initially, there's a bug
    if (initialMarkers === 0 && markersAfterToggle > 0) {
      console.warn('BUG DETECTED: Layer only renders after visibility toggle!');
    }
  });
});

test.describe('LeafletMapClient - OGC Services Tests', () => {
  test.beforeEach(async ({ page }) => {
    await setupBackendMocks(page);
    await page.goto('/');
    await waitForMapReady(page);
  });

  test('should display WMS layer', async ({ page }) => {
    await addLayerViaStore(page, wmsLayerMetadata);
    await page.waitForTimeout(2000);

    const visible = await isLayerVisible(page, 'wms-layer-1');
    expect(visible).toBe(true);

    // WMS layers should create tile layers
    const tileLayers = await page.locator('.leaflet-tile-pane img').count();
    expect(tileLayers).toBeGreaterThan(0);
  });

  test('should display WFS layer', async ({ page }) => {
    await page.route('**/geoserver/wfs**', (route) => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(wfsFeatureCollectionResponse),
      });
    });

    await addLayerViaStore(page, wfsLayerMetadata);
    await page.waitForTimeout(2000);

    const visible = await isLayerVisible(page, 'wfs-layer-1');
    expect(visible).toBe(true);

    // WFS layers should render as vector features
    const features = await page.locator('.leaflet-overlay-pane path').count();
    expect(features).toBeGreaterThan(0);
  });

  test('should display WMTS layer', async ({ page }) => {
    await addLayerViaStore(page, wmtsLayerMetadata);
    await page.waitForTimeout(2000);

    const visible = await isLayerVisible(page, 'wmts-layer-1');
    expect(visible).toBe(true);

    // WMTS layers should create tile layers
    const tileLayers = await page.locator('.leaflet-tile-pane img').count();
    expect(tileLayers).toBeGreaterThan(0);
  });

  test('should display WCS layer', async ({ page }) => {
    await addLayerViaStore(page, wcsLayerMetadata);
    await page.waitForTimeout(2000);

    const visible = await isLayerVisible(page, 'wcs-layer-1');
    expect(visible).toBe(true);

    // WCS layers are rendered as WMS (raster tiles)
    const tileLayers = await page.locator('.leaflet-tile-pane img').count();
    expect(tileLayers).toBeGreaterThan(0);
  });
});

test.describe('LeafletMapClient - GeoJSON Normalization Tests', () => {
  test.beforeEach(async ({ page }) => {
    await setupBackendMocks(page);
    await page.goto('/');
    await waitForMapReady(page);
  });

  test('should handle single Feature response', async ({ page }) => {
    await page.route('**/uploads/single-feature.geojson', (route) => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(singleFeatureResponse),
      });
    });

    const singleFeatureLayer = {
      id: 'single-feature-1',
      name: 'Single Feature',
      title: 'Single Feature Test',
      layer_type: 'UPLOADED',
      data_link: '/uploads/single-feature.geojson',
      visible: true,
      data_source_id: 'test',
    };

    await addLayerViaStore(page, singleFeatureLayer);
    await page.waitForTimeout(2000);

    const visible = await isLayerVisible(page, 'single-feature-1');
    expect(visible).toBe(true);

    // Should render as a marker
    const markers = await page.locator('.leaflet-overlay-pane circle, .leaflet-marker-pane').count();
    expect(markers).toBeGreaterThan(0);
  });

  test('should handle bare Geometry response', async ({ page }) => {
    await page.route('**/uploads/bare-geometry.geojson', (route) => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(singleGeometryResponse),
      });
    });

    const bareGeometryLayer = {
      id: 'bare-geometry-1',
      name: 'Bare Geometry',
      title: 'Bare Geometry Test',
      layer_type: 'UPLOADED',
      data_link: '/uploads/bare-geometry.geojson',
      visible: true,
      data_source_id: 'test',
    };

    await addLayerViaStore(page, bareGeometryLayer);
    await page.waitForTimeout(2000);

    const visible = await isLayerVisible(page, 'bare-geometry-1');
    expect(visible).toBe(true);

    const markers = await page.locator('.leaflet-overlay-pane circle, .leaflet-marker-pane').count();
    expect(markers).toBeGreaterThan(0);
  });

  test('should handle GeometryCollection response', async ({ page }) => {
    await page.route('**/uploads/geometry-collection.geojson', (route) => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(geometryCollectionResponse),
      });
    });

    const geometryCollectionLayer = {
      id: 'geometry-collection-1',
      name: 'Geometry Collection',
      title: 'Geometry Collection Test',
      layer_type: 'UPLOADED',
      data_link: '/uploads/geometry-collection.geojson',
      visible: true,
      data_source_id: 'test',
    };

    await addLayerViaStore(page, geometryCollectionLayer);
    await page.waitForTimeout(2000);

    const visible = await isLayerVisible(page, 'geometry-collection-1');
    expect(visible).toBe(true);

    // Should render multiple geometries
    const features = await page.locator('.leaflet-overlay-pane path, .leaflet-overlay-pane circle').count();
    expect(features).toBeGreaterThan(0);
  });
});

test.describe('LeafletMapClient - Layer Management Tests', () => {
  test.beforeEach(async ({ page }) => {
    await setupBackendMocks(page);
    await page.goto('/');
    await waitForMapReady(page);
  });

  test('should handle multiple layers', async ({ page }) => {
    await page.route('**/uploads/**', (route) => {
      const url = route.request().url();
      if (url.includes('layer1')) {
        route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(germanyGeocodingResponse),
        });
      } else if (url.includes('layer2')) {
        route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(brazilGeocodingResponse),
        });
      } else {
        route.continue();
      }
    });

    // Add first layer
    await addLayerViaStore(page, {
      id: 'multi-layer-1',
      name: 'Layer 1',
      title: 'First Layer',
      layer_type: 'UPLOADED',
      data_link: '/uploads/layer1.geojson',
      visible: true,
      data_source_id: 'test',
    });

    await page.waitForTimeout(1000);

    // Add second layer
    await addLayerViaStore(page, {
      id: 'multi-layer-2',
      name: 'Layer 2',
      title: 'Second Layer',
      layer_type: 'UPLOADED',
      data_link: '/uploads/layer2.geojson',
      visible: true,
      data_source_id: 'test',
    });

    await page.waitForTimeout(1000);

    // Check both layers exist
    const layerCount = await getLayerCount(page);
    expect(layerCount).toBe(2);

    // Both should be visible
    const visible1 = await isLayerVisible(page, 'multi-layer-1');
    const visible2 = await isLayerVisible(page, 'multi-layer-2');
    expect(visible1).toBe(true);
    expect(visible2).toBe(true);
  });

  test('should remove layer', async ({ page }) => {
    await page.route('**/uploads/**', (route) => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(germanyGeocodingResponse),
      });
    });

    const layer = {
      id: 'removable-layer',
      name: 'Removable Layer',
      title: 'Layer to Remove',
      layer_type: 'UPLOADED',
      data_link: '/uploads/removable.geojson',
      visible: true,
      data_source_id: 'test',
    };

    await addLayerViaStore(page, layer);
    await page.waitForTimeout(1000);

    let layerCount = await getLayerCount(page);
    expect(layerCount).toBe(1);

    // Remove layer
    await page.evaluate((id) => {
      const { useLayerStore } = window as any;
      if (useLayerStore) {
        useLayerStore.getState().removeLayer(id);
      }
    }, 'removable-layer');

    await page.waitForTimeout(500);

    layerCount = await getLayerCount(page);
    expect(layerCount).toBe(0);
  });
});
