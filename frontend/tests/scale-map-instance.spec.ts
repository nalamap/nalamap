import { test, expect } from '@playwright/test';

const mockSettings = {
  system_prompt: "You are a helpful assistant.",
  tool_options: {
    search: {
      default_prompt: "Search prompt",
      settings: {},
      enabled: true,
    },
  },
  example_geoserver_backends: [],
  model_options: {
    MockProvider: [{ name: "mock-model", max_tokens: 999 }],
  },
  session_id: "test-session",
};

test.describe("Scale Control Map Instance Access", () => {
  test.beforeEach(async ({ page }) => {
    await page.route("**/settings/options", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockSettings),
      });
    });

    await page.goto("/");
    
    // Wait for network to settle
    await page.waitForLoadState("networkidle");

    // Wait for map components to be visible
    await page.waitForSelector(".leaflet-container", { timeout: 10000 });
    await page.waitForSelector(".leaflet-control-scale", { state: "visible" });
    
    // Give map a moment to fully initialize
    await page.waitForTimeout(1000);
  });

  test('should investigate map instance availability', async ({ page }) => {
    // Try multiple ways to access the map instance
    const mapInfo = await page.evaluate(() => {
      const container = document.querySelector('.leaflet-container') as any;
      if (!container) return { error: 'No container found' };

      // Method 1: Standard _leaflet_map property (preferred)
      const mapInstance = container._leaflet_map;
      
      // Method 2: window.L global
      const L = (window as any).L;
      const hasLeaflet = !!L;
      
      return {
        hasContainer: true,
        hasLeaflet,
        hasMapInstance: !!mapInstance,
        mapCenter: mapInstance ? mapInstance.getCenter() : null,
        mapZoom: mapInstance ? mapInstance.getZoom() : null,
      };
    });

    console.log('Map Info:', JSON.stringify(mapInfo, null, 2));
    
    // Basic checks that should always pass
    expect(mapInfo.hasContainer).toBe(true);
    expect(mapInfo.hasLeaflet).toBe(true);
    
    // Note: Map instance may not be available via _leaflet_map in all scenarios
    // This is more of an investigation test to understand the map structure
    console.log(`Map instance via _leaflet_map: ${mapInfo.hasMapInstance ? 'Available' : 'Not available'}`);
  });

  test('should check scale control update mechanism', async ({ page }) => {
    // Get initial scale text
    const initialScale = await page.locator('.leaflet-control-scale-line').first().textContent();
    console.log('Initial scale:', initialScale);

    // Zoom in using the zoom button
    await page.click('a.leaflet-control-zoom-in');
    
    // Wait for scale to update after zoom
    await page.waitForFunction(
      (prevScale) => {
        const scaleElement = document.querySelector('.leaflet-control-scale-line');
        return scaleElement && scaleElement.textContent !== prevScale;
      },
      initialScale,
      { timeout: 3000 }
    );

    // Get new scale text
    const afterZoomScale = await page.locator('.leaflet-control-scale-line').first().textContent();
    console.log('After zoom scale:', afterZoomScale);

    // Check if scale actually changed
    expect(afterZoomScale).not.toBe(initialScale);
  });

  test('should manually trigger scale update', async ({ page }) => {
    // Get initial scale
    const initialScale = await page.locator('.leaflet-control-scale-line').first().textContent();
    console.log('Initial scale:', initialScale);

    // Use zoom controls to trigger scale update (more reliable than internal map access)
    const zoomInButton = page.locator('a.leaflet-control-zoom-in');
    await zoomInButton.click();
    
    // Wait for scale to update
    await page.waitForFunction(
      (prevScale) => {
        const scaleElement = document.querySelector('.leaflet-control-scale-line');
        return scaleElement && scaleElement.textContent !== prevScale;
      },
      initialScale,
      { timeout: 3000 }
    );

    const afterZoomScale = await page.locator('.leaflet-control-scale-line').first().textContent();
    console.log('After zoom scale:', afterZoomScale);

    // Verify scale changed after zoom
    expect(afterZoomScale).not.toBe(initialScale);
  });

  test('should check if scale control is bound to map events', async ({ page }) => {
    // Verify that scale updates when zoom changes (which proves event binding)
    const initialScale = await page.locator('.leaflet-control-scale-line').first().textContent();
    
    // Trigger a zoom event
    const zoomInButton = page.locator('a.leaflet-control-zoom-in');
    await zoomInButton.click();
    
    // Wait for scale to update (if events are bound, this will happen)
    await page.waitForFunction(
      (prevScale) => {
        const scaleElement = document.querySelector('.leaflet-control-scale-line');
        return scaleElement && scaleElement.textContent !== prevScale;
      },
      initialScale,
      { timeout: 3000 }
    );

    const afterZoomScale = await page.locator('.leaflet-control-scale-line').first().textContent();
    
    // If scale updated, events are properly bound
    expect(afterZoomScale).not.toBe(initialScale);
    console.log('Scale control is properly bound to map events (scale updated on zoom)');
  });
});
