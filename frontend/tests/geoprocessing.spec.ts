import { test, expect, Page } from "@playwright/test";

/**
 * Test suite for Geoprocessing functionality
 *
 * Tests the complete workflow of:
 * 1. Adding a layer to the map
 * 2. Running geoprocessing operations (buffer, merge, etc.)
 * 3. Verifying the result layers appear on the map
 */

// Mock settings for the test environment
const mockSettings = {
  system_prompt: "You are a helpful geospatial assistant.",
  tool_options: {
    search: {
      default_prompt: "Search prompt",
      settings: {},
    },
  },
  example_geoserver_backends: [
    {
      url: "https://geoserver.mapx.org/geoserver/",
      name: "MapX",
      description: "Example GeoServer",
    },
  ],
  model_options: {
    MockProvider: [{ name: "mock-model", max_tokens: 999 }],
  },
  session_id: "test-session",
};

// Mock hospital point data
const hospitalPointsGeoJSON = {
  type: "FeatureCollection",
  features: [
    {
      type: "Feature",
      id: "hospital-1",
      geometry: {
        type: "Point",
        coordinates: [10.0, 50.0],
      },
      properties: {
        name: "City Hospital",
        type: "hospital",
      },
    },
    {
      type: "Feature",
      id: "hospital-2",
      geometry: {
        type: "Point",
        coordinates: [10.1, 50.1],
      },
      properties: {
        name: "Regional Medical Center",
        type: "hospital",
      },
    },
  ],
};

// Mock buffer result (100km buffer around hospitals)
const hospitalBufferGeoJSON = {
  type: "FeatureCollection",
  features: [
    {
      type: "Feature",
      id: "buffer-1",
      geometry: {
        type: "Polygon",
        coordinates: [
          [
            [9.1, 49.1],
            [10.9, 49.1],
            [10.9, 50.9],
            [9.1, 50.9],
            [9.1, 49.1],
          ],
        ],
      },
      properties: {
        name: "100km buffer around City Hospital",
        radius: 100000,
        radius_unit: "meters",
      },
    },
    {
      type: "Feature",
      id: "buffer-2",
      geometry: {
        type: "Polygon",
        coordinates: [
          [
            [9.2, 49.2],
            [11.0, 49.2],
            [11.0, 51.0],
            [9.2, 51.0],
            [9.2, 49.2],
          ],
        ],
      },
      properties: {
        name: "100km buffer around Regional Medical Center",
        radius: 100000,
        radius_unit: "meters",
      },
    },
  ],
};

// Helper function to setup API mocks
async function setupMocks(page: Page) {
  // Mock settings endpoint
  await page.route("**/api/settings", (route) => {
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(mockSettings),
    });
  });

  // Mock hospital data endpoint
  await page.route("**/uploads/hospitals_*.geojson", (route) => {
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(hospitalPointsGeoJSON),
    });
  });

  // Mock Azure Blob Storage hospital data
  await page.route(
    "**/*.blob.core.windows.net/data/*hospitals*.json*",
    (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(hospitalPointsGeoJSON),
        headers: {
          "Access-Control-Allow-Origin": "*",
        },
      });
    },
  );

  // Mock buffer result endpoint
  await page.route("**/uploads/*buffer*.geojson", (route) => {
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(hospitalBufferGeoJSON),
    });
  });

  // Mock Azure Blob Storage buffer data
  await page.route(
    "**/*.blob.core.windows.net/data/*buffer*.json*",
    (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(hospitalBufferGeoJSON),
        headers: {
          "Access-Control-Allow-Origin": "*",
        },
      });
    },
  );

  // Mock geoprocessing API endpoint
  await page.route("**/api/tools/geoprocess", (route) => {
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        success: true,
        result_url: "/uploads/hospitals_100km_buffer_abc123.geojson",
        result_id: "buffer-result-1",
        operation: "buffer",
        message: "Successfully created 100km buffer around hospitals",
      }),
    });
  });
}

// Helper function to add a layer to the map
async function addLayerToMap(page: Page, layerData: any) {
  const result = await page.evaluate((layer) => {
    const { useLayerStore } = window as any;
    if (!useLayerStore) {
      return { success: false, error: "useLayerStore not found" };
    }
    try {
      useLayerStore.getState().addLayer(layer);
      return { success: true, layerId: layer.id };
    } catch (error: any) {
      return { success: false, error: error.message };
    }
  }, layerData);

  return result;
}

// Helper function to check if layer is visible on map
async function isLayerVisible(page: Page, layerId: string): Promise<boolean> {
  return await page.evaluate((id) => {
    const { useLayerStore } = window as any;
    if (!useLayerStore) return false;

    const layers = useLayerStore.getState().layers;
    const layer = layers.find((l: any) => l.id === id);
    return layer && layer.visible;
  }, layerId);
}

test.describe("Geoprocessing Operations", () => {
  test.beforeEach(async ({ page }) => {
    // Setup console logging
    page.on("console", (msg) => {
      console.log(`Browser [${msg.type()}]:`, msg.text());
    });

    // Setup mocks
    await setupMocks(page);

    // Navigate to page
    await page.goto("/");

    // Wait for map to be ready
    await page.waitForSelector(".leaflet-container", { timeout: 10000 });
    await page.waitForTimeout(2000);
  });

  test("should add a layer and render it on the map", async ({ page }) => {
    console.log("Test: Adding hospital layer to map");

    const hospitalLayer = {
      id: "hospitals-test",
      name: "Test Hospitals",
      title: "Test Hospitals in Region",
      layer_type: "GEOJSON",
      data_link: "/uploads/hospitals_test.geojson",
      visible: true,
      properties: {
        source: "test",
      },
    };

    // Add layer to map
    const addResult = await addLayerToMap(page, hospitalLayer);
    console.log("Add layer result:", addResult);
    expect(addResult.success).toBe(true);

    // Wait for layer to render
    await page.waitForTimeout(3000);

    // Verify layer is in store
    const layerInStore = await page.evaluate(() => {
      const { useLayerStore } = window as any;
      if (!useLayerStore) return null;
      return useLayerStore.getState().layers;
    });

    console.log("Layers in store:", layerInStore);
    expect(layerInStore).toBeTruthy();
    expect(Array.isArray(layerInStore)).toBe(true);
    expect(layerInStore.some((l: any) => l.id === "hospitals-test")).toBe(true);

    // Check if layer is visible
    const isVisible = await isLayerVisible(page, "hospitals-test");
    console.log("Layer visible:", isVisible);
    expect(isVisible).toBe(true);

    // Check for map features (markers or paths)
    const featureCount = await page
      .locator(
        ".leaflet-overlay-pane path, .leaflet-overlay-pane circle, .leaflet-marker-pane img, .leaflet-overlay-pane canvas",
      )
      .count();
    console.log("Feature count on map:", featureCount);
    expect(featureCount).toBeGreaterThan(0);
  });

  test("should perform buffer operation and display result", async ({
    page,
  }) => {
    console.log("Test: Buffer operation workflow");

    // Step 1: Add hospital layer
    const hospitalLayer = {
      id: "hospitals-for-buffer",
      name: "Hospitals for Buffer",
      title: "Hospitals",
      layer_type: "GEOJSON",
      data_link: "/uploads/hospitals_original.geojson",
      visible: true,
    };

    const addResult = await addLayerToMap(page, hospitalLayer);
    expect(addResult.success).toBe(true);
    await page.waitForTimeout(2000);

    // Step 2: Simulate buffer operation by adding buffer result layer
    const bufferLayer = {
      id: "hospitals-buffer-100km",
      name: "100km Buffer",
      title: "100km Buffer Around Hospitals",
      layer_type: "GEOJSON",
      data_link: "/uploads/hospitals_100km_buffer_abc123.geojson",
      visible: true,
      properties: {
        operation: "buffer",
        radius: 100000,
        radius_unit: "meters",
        source_layer: "hospitals-for-buffer",
      },
    };

    const bufferResult = await addLayerToMap(page, bufferLayer);
    console.log("Add buffer layer result:", bufferResult);
    expect(bufferResult.success).toBe(true);

    // Wait for buffer layer to render
    await page.waitForTimeout(3000);

    // Verify both layers are in store
    const layersInStore = await page.evaluate(() => {
      const { useLayerStore } = window as any;
      if (!useLayerStore) return [];
      return useLayerStore.getState().layers.map((l: any) => ({
        id: l.id,
        name: l.name,
        visible: l.visible,
      }));
    });

    console.log("All layers in store:", layersInStore);
    expect(layersInStore.length).toBeGreaterThanOrEqual(2);
    expect(
      layersInStore.some((l: any) => l.id === "hospitals-for-buffer"),
    ).toBe(true);
    expect(
      layersInStore.some((l: any) => l.id === "hospitals-buffer-100km"),
    ).toBe(true);

    // Check if buffer layer is visible
    const bufferVisible = await isLayerVisible(page, "hospitals-buffer-100km");
    console.log("Buffer layer visible:", bufferVisible);
    expect(bufferVisible).toBe(true);

    // Verify features are rendered
    const featureCount = await page
      .locator(".leaflet-overlay-pane path, .leaflet-overlay-pane polygon")
      .count();
    console.log("Feature count (including buffer):", featureCount);
    expect(featureCount).toBeGreaterThan(0);
  });

  test("should handle layer visibility toggle", async ({ page }) => {
    console.log("Test: Layer visibility toggle");

    const testLayer = {
      id: "toggle-test-layer",
      name: "Toggle Test",
      title: "Toggle Test Layer",
      layer_type: "GEOJSON",
      data_link: "/uploads/toggle_test.geojson",
      visible: true,
    };

    // Add layer
    await addLayerToMap(page, testLayer);
    await page.waitForTimeout(2000);

    // Verify initially visible
    let isVisible = await isLayerVisible(page, "toggle-test-layer");
    expect(isVisible).toBe(true);

    // Toggle visibility off
    await page.evaluate((layerId) => {
      const { useLayerStore } = window as any;
      useLayerStore.getState().toggleLayerVisibility(layerId);
    }, "toggle-test-layer");

    await page.waitForTimeout(1000);

    // Verify hidden
    isVisible = await isLayerVisible(page, "toggle-test-layer");
    expect(isVisible).toBe(false);

    // Toggle visibility back on
    await page.evaluate((layerId) => {
      const { useLayerStore } = window as any;
      useLayerStore.getState().toggleLayerVisibility(layerId);
    }, "toggle-test-layer");

    await page.waitForTimeout(1000);

    // Verify visible again
    isVisible = await isLayerVisible(page, "toggle-test-layer");
    expect(isVisible).toBe(true);
  });

  test("should support Azure Blob Storage URLs with SAS tokens", async ({
    page,
  }) => {
    console.log("Test: Azure Blob Storage with SAS tokens");

    const azureBlobLayer = {
      id: "azure-blob-test",
      name: "Azure Blob Test",
      title: "Azure Blob Storage Layer",
      layer_type: "GEOJSON",
      data_link:
        "https://stnalamapdev.blob.core.windows.net/data/hospitals_abc123.json?sv=2021-06-08&se=2025-10-06T10%3A30%3A00Z&sr=b&sp=r&sig=test",
      visible: true,
    };

    // Add layer with Azure Blob URL
    const result = await addLayerToMap(page, azureBlobLayer);
    console.log("Add Azure Blob layer result:", result);
    expect(result.success).toBe(true);

    // Wait for layer to load and render
    await page.waitForTimeout(3000);

    // Verify layer is in store and visible
    const isVisible = await isLayerVisible(page, "azure-blob-test");
    expect(isVisible).toBe(true);

    // Check for rendered features
    const featureCount = await page
      .locator(
        ".leaflet-overlay-pane path, .leaflet-overlay-pane circle, .leaflet-marker-pane img",
      )
      .count();
    console.log("Azure Blob layer feature count:", featureCount);
    expect(featureCount).toBeGreaterThan(0);
  });

  test("should handle geoprocessing result with multiple features", async ({
    page,
  }) => {
    console.log("Test: Geoprocessing with multiple result features");

    // Add buffer result with multiple features
    const multiFeatureBuffer = {
      id: "multi-buffer-result",
      name: "Multiple Buffers",
      title: "Buffer Result with Multiple Features",
      layer_type: "GEOJSON",
      data_link: "/uploads/multi_buffer_result.geojson",
      visible: true,
      properties: {
        operation: "buffer",
        feature_count: 2,
      },
    };

    const result = await addLayerToMap(page, multiFeatureBuffer);
    expect(result.success).toBe(true);

    await page.waitForTimeout(3000);

    // Verify layer loaded
    const layerInfo = await page.evaluate((layerId) => {
      const { useLayerStore } = window as any;
      if (!useLayerStore) return null;

      const layers = useLayerStore.getState().layers;
      const layer = layers.find((l: any) => l.id === layerId);
      return layer
        ? {
            id: layer.id,
            visible: layer.visible,
            properties: layer.properties,
          }
        : null;
    }, "multi-buffer-result");

    console.log("Multi-feature buffer layer info:", layerInfo);
    expect(layerInfo).toBeTruthy();
    expect(layerInfo?.visible).toBe(true);

    // Check map has features rendered
    const pathCount = await page.locator(".leaflet-overlay-pane path").count();
    console.log("Path count for multi-feature layer:", pathCount);
    expect(pathCount).toBeGreaterThan(0);
  });
});
