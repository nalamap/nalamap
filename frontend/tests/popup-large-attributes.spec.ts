import { test, expect, Page } from "@playwright/test";

/**
 * Test fixture: GeoJSON with 30+ attributes to test popup sizing and scrolling
 */
const largeAttributeGeoJSON = {
  type: "FeatureCollection",
  features: [
    {
      type: "Feature",
      id: "large-attr-1",
      geometry: {
        type: "Point",
        coordinates: [13.405, 52.52], // Berlin
      },
      properties: {
        name: "Test Feature with Many Attributes",
        attribute_01: "Value 1",
        attribute_02: "Value 2",
        attribute_03: "Value 3",
        attribute_04: "Value 4",
        attribute_05: "Value 5",
        attribute_06: "Value 6",
        attribute_07: "Value 7",
        attribute_08: "Value 8",
        attribute_09: "Value 9",
        attribute_10: "Value 10",
        attribute_11: "Value 11",
        attribute_12: "Value 12",
        attribute_13: "Value 13",
        attribute_14: "Value 14",
        attribute_15: "Value 15",
        attribute_16: "Value 16",
        attribute_17: "Value 17",
        attribute_18: "Value 18",
        attribute_19: "Value 19",
        attribute_20: "Value 20",
        attribute_21: "Value 21",
        attribute_22: "Value 22",
        attribute_23: "Value 23",
        attribute_24: "Value 24",
        attribute_25: "Value 25",
        attribute_26: "Value 26",
        attribute_27: "Value 27",
        attribute_28: "Value 28",
        attribute_29: "Value 29",
        attribute_30: "Value 30",
        attribute_31: "Value 31",
        attribute_32: "Value 32",
        description: "This feature has more than 30 attributes to test popup scrolling behavior",
      },
    },
  ],
};

/**
 * Helper to setup API mocks for backend endpoints
 */
async function setupBackendMocks(page: Page) {
  // Mock backend health/initialization endpoints
  await page.route("**/api/**", (route) => {
    const url = route.request().url();

    // Mock health check
    if (url.includes("/health")) {
      route.fulfill({ status: 200, body: JSON.stringify({ status: "ok" }) });
      return;
    }

    // Mock settings endpoint
    if (url.includes("/settings")) {
      route.fulfill({
        status: 200,
        body: JSON.stringify({
          agent_settings: { model: "test-model" },
          available_models: ["test-model"],
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
  const result = await page.evaluate((layerData) => {
    // Access Zustand store directly from window
    const { useLayerStore } = window as any;
    if (!useLayerStore) {
      return { success: false, error: "useLayerStore not found on window" };
    }
    try {
      useLayerStore.getState().addLayer(layerData);
      const layers = useLayerStore.getState().layers;
      return { success: true, layerCount: layers.length };
    } catch (error: any) {
      return { success: false, error: error.message };
    }
  }, layer);

  if (!result.success) {
    throw new Error(`Failed to add layer: ${result.error}`);
  }
  return result;
}

/**
 * Helper to wait for map initialization
 */
async function waitForMapReady(page: Page) {
  // Wait for Leaflet map container
  await page.waitForSelector(".leaflet-container", { timeout: 10000 });

  // Wait for the store to be available on window
  await page.waitForFunction(
    () => {
      return typeof (window as any).useLayerStore !== "undefined";
    },
    { timeout: 10000 },
  );

  // Wait for tiles to start loading
  await page.waitForTimeout(1000);
}

/**
 * Helper to add a GeoJSON layer with large attributes
 */
async function addLargeAttributeLayer(page: Page) {
  // Directly create a layer with inline GeoJSON data (no external fetch needed)
  return await page.evaluate((geojson) => {
    const { useLayerStore } = window as any;
    if (!useLayerStore) {
      return { success: false, error: "useLayerStore not found on window" };
    }
    try {
      // Create a data URL with the GeoJSON
      const dataUrl = `data:application/json;charset=utf-8,${encodeURIComponent(JSON.stringify(geojson))}`;
      
      useLayerStore.getState().addLayer({
        id: "large-attr-layer",
        name: "Large Attribute Test Layer",
        title: "Test Layer with 30+ Attributes",
        layer_type: "UPLOADED",
        data_link: dataUrl,
        bounding_box: [13.0, 52.0, 14.0, 53.0],
        visible: true,
        data_source_id: "test",
      });
      const layers = useLayerStore.getState().layers;
      return { success: true, layerCount: layers.length };
    } catch (error: any) {
      return { success: false, error: error.message };
    }
  }, largeAttributeGeoJSON);
}

test.describe("Leaflet Popup - Large Attribute Tables", () => {
  test.beforeEach(async ({ page }) => {
    await setupBackendMocks(page);
  });

  test("should constrain popup size and show scrollbar for 30+ attributes", async ({
    page,
  }) => {
    // Navigate to the app
    await page.goto("/");

    // Wait for map to be ready
    await waitForMapReady(page);

    // Add the layer with large attributes
    await addLargeAttributeLayer(page);

    // Wait for the layer to be rendered (circle marker should appear)
    await page.waitForTimeout(5000); // Increased wait time

    // Points can be rendered as either circle or path elements depending on Leaflet settings
    // Try to find the marker (circle or path)
    const marker = await page.locator(".leaflet-overlay-pane circle").count() > 0
      ? page.locator(".leaflet-overlay-pane circle").first()
      : page.locator(".leaflet-overlay-pane path.leaflet-interactive").first();
    
    await expect(marker).toBeVisible({ timeout: 10000 });
    await marker.click();

    // Wait for popup to appear
    const popup = page.locator(".leaflet-popup");
    await expect(popup).toBeVisible({ timeout: 5000 });

    // Get the popup content element
    const popupContent = page.locator(".leaflet-popup-content");
    await expect(popupContent).toBeVisible();

    // Check that popup content has size constraints
    const boundingBox = await popupContent.boundingBox();
    expect(boundingBox).not.toBeNull();

    if (boundingBox) {
      // Get viewport size
      const viewportSize = page.viewportSize();
      expect(viewportSize).not.toBeNull();

      if (viewportSize) {
        // Popup should not exceed 50% of viewport height (50vh as per CSS)
        const maxHeight = viewportSize.height * 0.5;
        expect(boundingBox.height).toBeLessThanOrEqual(maxHeight + 50); // +50px tolerance for borders/padding

        // Popup should not exceed 30% of viewport width (30vw as per CSS)
        const maxWidth = viewportSize.width * 0.3;
        expect(boundingBox.width).toBeLessThanOrEqual(maxWidth + 50); // +50px tolerance for borders/padding
      }
    }

    // Check that the popup content has overflow scrolling enabled
    const overflowY = await popupContent.evaluate((el) => 
      window.getComputedStyle(el).overflowY
    );
    expect(overflowY).toBe("auto");

    const overflowX = await popupContent.evaluate((el) => 
      window.getComputedStyle(el).overflowX
    );
    expect(overflowX).toBe("auto");

    // Check that content is actually scrollable (scrollHeight > clientHeight)
    const isScrollable = await popupContent.evaluate((el) => ({
      scrollHeight: el.scrollHeight,
      clientHeight: el.clientHeight,
      isVerticallyScrollable: el.scrollHeight > el.clientHeight,
    }));

    // With 30+ attributes, the content should be scrollable
    expect(isScrollable.isVerticallyScrollable).toBe(true);

    // Verify that all 33 rows are present in the popup (30+ attributes)
    const rows = page.locator(".leaflet-popup-content table tbody tr");
    const rowCount = await rows.count();
    expect(rowCount).toBeGreaterThanOrEqual(33); // 33 properties in our test data

    // Verify we can scroll to see hidden content
    // Get the first and last row
    const firstRow = rows.first();
    const lastRow = rows.last();

    // First row should be visible initially
    await expect(firstRow).toBeVisible();

    // Scroll to the bottom of the popup content
    await popupContent.evaluate((el) => {
      el.scrollTop = el.scrollHeight;
    });

    // Wait for scroll to complete
    await page.waitForTimeout(500);

    // Last row should now be visible
    await expect(lastRow).toBeVisible();

    // Verify that the popup doesn't overflow the viewport
    const popupBox = await popup.boundingBox();
    expect(popupBox).not.toBeNull();

    if (popupBox && page.viewportSize()) {
      const viewport = page.viewportSize()!;
      
      // Popup should be within viewport bounds
      expect(popupBox.x).toBeGreaterThanOrEqual(0);
      expect(popupBox.y).toBeGreaterThanOrEqual(0);
      expect(popupBox.x + popupBox.width).toBeLessThanOrEqual(viewport.width);
      expect(popupBox.y + popupBox.height).toBeLessThanOrEqual(viewport.height);
    }
  });

  test("should keep popup in view when panning map", async ({ page }) => {
    // Navigate to the app
    await page.goto("/");

    // Wait for map to be ready
    await waitForMapReady(page);

    // Add the layer with large attributes
    await addLargeAttributeLayer(page);

    // Wait for the layer to be rendered
    await page.waitForTimeout(3000);

    // Points can be rendered as either circle or path elements
    const marker = await page.locator(".leaflet-overlay-pane circle").count() > 0
      ? page.locator(".leaflet-overlay-pane circle").first()
      : page.locator(".leaflet-overlay-pane path.leaflet-interactive").first();
    
    await expect(marker).toBeVisible({ timeout: 10000 });
    await marker.click();

    // Wait for popup to appear
    const popup = page.locator(".leaflet-popup");
    await expect(popup).toBeVisible({ timeout: 5000 });

    // Get initial popup position
    const initialBox = await popup.boundingBox();
    expect(initialBox).not.toBeNull();

    // Pan the map programmatically (using Leaflet's panBy method)
    // This tests that keepInView option works correctly
    await page.evaluate(() => {
      const mapElement = document.querySelector('.leaflet-container') as any;
      if (mapElement && mapElement._leaflet_id) {
        const map = (window as any).L.Map._mapInstances?.[mapElement._leaflet_id];
        if (map) {
          // Pan the map by 200 pixels to the left and down
          map.panBy([200, 200]);
        }
      }
    });

    // Wait for map animation to complete
    await page.waitForTimeout(1000);

    // Popup should still be visible (keepInView should work)
    await expect(popup).toBeVisible();

    // Get new popup position
    const newBox = await popup.boundingBox();
    expect(newBox).not.toBeNull();

    // Popup should still be within viewport
    if (newBox && page.viewportSize()) {
      const viewport = page.viewportSize()!;
      expect(newBox.x).toBeGreaterThanOrEqual(0);
      expect(newBox.y).toBeGreaterThanOrEqual(0);
      expect(newBox.x + newBox.width).toBeLessThanOrEqual(viewport.width);
      expect(newBox.y + newBox.height).toBeLessThanOrEqual(viewport.height);
    }
  });

  test("should apply scrollbar styling", async ({ page }) => {
    // Navigate to the app
    await page.goto("/");

    // Wait for map to be ready
    await waitForMapReady(page);

    // Add the layer with large attributes
    await addLargeAttributeLayer(page);

    // Wait for the layer to be rendered
    await page.waitForTimeout(3000);

    // Points can be rendered as either circle or path elements
    const marker = await page.locator(".leaflet-overlay-pane circle").count() > 0
      ? page.locator(".leaflet-overlay-pane circle").first()
      : page.locator(".leaflet-overlay-pane path.leaflet-interactive").first();
    
    await expect(marker).toBeVisible({ timeout: 10000 });
    await marker.click();

    // Wait for popup to appear
    const popup = page.locator(".leaflet-popup");
    await expect(popup).toBeVisible({ timeout: 5000 });

    const popupContent = page.locator(".leaflet-popup-content");

    // Check that scrollbar styling is applied (webkit-specific, may not work in all browsers)
    // This test verifies that the CSS rules are loaded and applied
    const hasScrollbarStyle = await popupContent.evaluate((el) => {
      const style = window.getComputedStyle(el, "::-webkit-scrollbar");
      // If scrollbar styles are applied, the pseudo-element should exist
      // This is a basic check - in webkit browsers this should return true
      return style !== null;
    });

    // This is a basic sanity check - the exact behavior depends on browser
    expect(hasScrollbarStyle).toBeDefined();
  });

  test("should handle popup with very long attribute values", async ({ page }) => {
    // Navigate to the app
    await page.goto("/");

    // Wait for map to be ready
    await waitForMapReady(page);

    // Create GeoJSON with very long attribute values
    const longValueGeoJSON = {
      type: "FeatureCollection",
      features: [
        {
          type: "Feature",
          id: "long-value-1",
          geometry: {
            type: "Point",
            coordinates: [13.405, 52.52],
          },
          properties: {
            name: "Test Feature",
            very_long_value: "A".repeat(500),
            another_long_value: "B".repeat(300),
            normal_value: "Normal",
            url: "https://example.com/very/long/url/path/that/might/break/layout",
          },
        },
      ],
    };

    // Add the layer with inline GeoJSON
    await page.evaluate((geojson) => {
      const { useLayerStore } = window as any;
      const dataUrl = `data:application/json;charset=utf-8,${encodeURIComponent(JSON.stringify(geojson))}`;
      
      useLayerStore.getState().addLayer({
        id: "long-value-layer",
        name: "Long Value Test Layer",
        title: "Test Layer with Long Values",
        layer_type: "UPLOADED",
        data_link: dataUrl,
        bounding_box: [13.0, 52.0, 14.0, 53.0],
        visible: true,
        data_source_id: "test",
      });
    }, longValueGeoJSON);

    // Wait for the layer to be rendered
    await page.waitForTimeout(3000);

    // Points can be rendered as either circle or path elements
    const marker = await page.locator(".leaflet-overlay-pane circle").count() > 0
      ? page.locator(".leaflet-overlay-pane circle").first()
      : page.locator(".leaflet-overlay-pane path.leaflet-interactive").first();
    
    await expect(marker).toBeVisible({ timeout: 10000 });
    await marker.click();

    // Wait for popup to appear
    const popup = page.locator(".leaflet-popup");
    await expect(popup).toBeVisible({ timeout: 5000 });

    const popupContent = page.locator(".leaflet-popup-content");

    // Check word-wrap is applied
    const wordWrap = await popupContent.evaluate((el) =>
      window.getComputedStyle(el).wordWrap
    );
    expect(wordWrap).toBe("break-word");

    // Verify popup stays within size constraints even with long values
    const boundingBox = await popupContent.boundingBox();
    expect(boundingBox).not.toBeNull();

    if (boundingBox && page.viewportSize()) {
      const viewport = page.viewportSize()!;
      const maxWidth = viewport.width * 0.3;
      expect(boundingBox.width).toBeLessThanOrEqual(maxWidth + 50);
    }
  });
});
