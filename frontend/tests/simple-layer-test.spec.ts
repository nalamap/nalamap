import { test, expect } from '@playwright/test';

test('simple layer rendering test', async ({ page }) => {
  // Capture console messages
  const consoleMessages: string[] = [];
  page.on('console', msg => {
    const text = msg.text();
    consoleMessages.push(`[${msg.type()}] ${text}`);
    console.log(`Browser [${msg.type()}]:`, text);
  });
  
  // Navigate to page
  await page.goto('/');
  
  // Wait for map
  await page.waitForSelector('.leaflet-container', { timeout: 10000 });
  await page.waitForTimeout(2000);
  
  // Add a simple GeoJSON layer
  const simpleLayer = {
    id: 'test-layer',
    name: 'Test Layer',
    title: 'Test',
    layer_type: 'UPLOADED',
    data_link: '/test-data.geojson',
    visible: true,
  };
  
  // Mock the data
  await page.route('**/test-data.geojson', (route) => {
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        type: 'FeatureCollection',
        features: [
          {
            type: 'Feature',
            properties: { name: 'Test Point' },
            geometry: {
              type: 'Point',
              coordinates: [0, 0]
            }
          }
        ]
      })
    });
  });
  
  // Add layer via store
  const result = await page.evaluate((layerData) => {
    const { useLayerStore } = window as any;
    if (!useLayerStore) {
      return { success: false, error: 'useLayerStore not found' };
    }
    try {
      useLayerStore.getState().addLayer(layerData);
      return { success: true };
    } catch (error: any) {
      return { success: false, error: error.message };
    }
  }, simpleLayer);
  
  console.log('Add layer result:', result);
  expect(result.success).toBe(true);
  
  // Wait for layer to render
  await page.waitForTimeout(5000);
  
  // Check map center and zoom
  const mapInfo = await page.evaluate(() => {
    const mapElements = document.querySelectorAll('.leaflet-container');
    if (mapElements.length === 0) return null;
    const mapElement: any = mapElements[0];
    const map = (mapElement as any)._leaflet_map;
    if (!map) return null;
    return {
      center: map.getCenter(),
      zoom: map.getZoom(),
      bounds: map.getBounds(),
      preferCanvas: map.options.preferCanvas
    };
  });
  console.log('Map info:', mapInfo);
  
  // Check if marker/path exists (both SVG and Canvas)
  const markerCount = await page.locator('.leaflet-overlay-pane path, .leaflet-overlay-pane circle, .leaflet-marker-pane img').count();
  console.log('SVG Marker count:', markerCount);
  
  // Check canvas elements
  const canvasCount = await page.locator('.leaflet-overlay-pane canvas').count();
  console.log('Canvas count:', canvasCount);
  
  // Also check the actual DOM
  const overlayPaneHTML = await page.locator('.leaflet-overlay-pane').innerHTML();
  console.log('Overlay pane HTML (first 1000 chars):', overlayPaneHTML.substring(0, 1000));
  
  // Check if the layer is in the store
  const layerInStore = await page.evaluate(() => {
    const { useLayerStore } = window as any;
    const layers = useLayerStore.getState().layers;
    return layers.map((l: any) => ({ id: l.id, visible: l.visible, name: l.name }));
  });
  console.log('Layers in store:', layerInStore);
  
  expect(markerCount).toBeGreaterThan(0);
});
