import { test, expect, Page } from "@playwright/test";

/**
 * Test suite for Agent Chat Interface "Add to Map" button functionality
 *
 * BUG: When using AgentChatInterface and asking "geocode Hospitals in Brazil",
 * we get correct layers, but when clicking the "add layer" button,
 * it zooms in but does not show the layer.
 *
 * This test verifies that layers added via the "Add to Map" button
 * render correctly WITHOUT needing to toggle visibility or use workarounds.
 */

const mockSettings = {
  system_prompt: "You are a helpful assistant.",
  tool_options: {
    search: {
      default_prompt: "Search prompt",
      settings: {},
    },
  },
  search_portals: ["https://portal.example"],
  model_options: {
    MockProvider: [{ name: "mock-model", max_tokens: 999 }],
  },
};

// Mock hospital data from Brazil (similar to Overpass API results)
const brazilHospitalsPointsGeoJSON = {
  type: "FeatureCollection",
  features: [
    {
      type: "Feature",
      id: "node/1",
      geometry: {
        type: "Point",
        coordinates: [-43.1729, -22.9068], // Rio de Janeiro
      },
      properties: {
        name: "Hospital Municipal",
        amenity: "hospital",
        healthcare: "hospital",
      },
    },
    {
      type: "Feature",
      id: "node/2",
      geometry: {
        type: "Point",
        coordinates: [-43.2075, -22.9035],
      },
      properties: {
        name: "Hospital Central",
        amenity: "hospital",
        healthcare: "hospital",
      },
    },
    {
      type: "Feature",
      id: "node/3",
      geometry: {
        type: "Point",
        coordinates: [-43.1951, -22.9133],
      },
      properties: {
        name: "Clínica São Paulo",
        amenity: "hospital",
        healthcare: "hospital",
      },
    },
  ],
};

const brazilHospitalsAreasGeoJSON = {
  type: "FeatureCollection",
  features: [
    {
      type: "Feature",
      id: "way/1",
      geometry: {
        type: "Polygon",
        coordinates: [
          [
            [-43.18, -22.91],
            [-43.179, -22.91],
            [-43.179, -22.909],
            [-43.18, -22.909],
            [-43.18, -22.91],
          ],
        ],
      },
      properties: {
        name: "Hospital das Clínicas",
        amenity: "hospital",
        healthcare: "hospital",
        building: "hospital",
      },
    },
  ],
};

// Mock geodata objects that would be returned by the backend
const mockHospitalPointsLayer = {
  id: "hospital-points-test-123",
  name: "Hospital (Points) near Brazil",
  title: "Hospitals (Points) near Brazil",
  layer_type: "GeoJSON",
  data_link: "/uploads/test_hospital_points_brazil.geojson",
  data_source: "OpenStreetMap contributors",
  data_source_id: "geocodeOverpassCollection",
  data_type: "GEOJSON",
  data_origin: "TOOL",
  description: "3 hospitals (points) found near Brazil",
  llm_description:
    "3 hospitals (points) found matching amenity=hospital near Brazil",
  score: 0.85,
  bounding_box: [-43.2075, -22.9133, -43.1729, -22.9035],
  visible: true,
  properties: {
    feature_count: 3,
    query_amenity_key: "Hospital",
    query_location: "Brazil",
    geometry_type_collected: "Points",
  },
  sha256: "mock-hash-points",
  size: 1024,
};

const mockHospitalAreasLayer = {
  id: "hospital-areas-test-456",
  name: "Hospital (Areas) near Brazil",
  title: "Hospitals (Areas) near Brazil",
  layer_type: "GeoJSON",
  data_link: "/uploads/test_hospital_areas_brazil.geojson",
  data_source: "OpenStreetMap contributors",
  data_source_id: "geocodeOverpassCollection",
  data_type: "GEOJSON",
  data_origin: "TOOL",
  description: "1 hospital (area) found near Brazil",
  llm_description:
    "1 hospital (area) found matching amenity=hospital near Brazil",
  score: 0.85,
  bounding_box: [-43.18, -22.91, -43.179, -22.909],
  visible: true,
  properties: {
    feature_count: 1,
    query_amenity_key: "Hospital",
    query_location: "Brazil",
    geometry_type_collected: "Areas",
  },
  sha256: "mock-hash-areas",
  size: 512,
};

// Helper function to check if a layer is visible in the store
async function isLayerVisible(page: Page, layerId: string): Promise<boolean> {
  return await page.evaluate((id) => {
    const store = (window as any).useLayerStore;
    if (!store) return false;
    const layer = store.getState().layers.find((l: any) => l.id === id);
    return layer ? layer.visible : false;
  }, layerId);
}

// Helper function to get layer count
async function getLayerCount(page: Page): Promise<number> {
  return await page.evaluate(() => {
    const store = (window as any).useLayerStore;
    if (!store) return 0;
    return store.getState().layers.length;
  });
}

// Helper function to count rendered features on the map
async function countRenderedFeatures(page: Page): Promise<number> {
  // Wait a bit for rendering
  await page.waitForTimeout(1000);

  // Count SVG paths and circles (point features)
  const svgCount = await page
    .locator(".leaflet-overlay-pane path, .leaflet-overlay-pane circle")
    .count();

  return svgCount;
}

test.describe("Agent Chat Interface - Add Layer Button", () => {
  test.beforeEach(async ({ page }) => {
    // Mock settings endpoint
    await page.route("**/settings/options", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockSettings),
      });
    });

    // Mock GeoJSON file endpoints
    await page.route(
      "**/uploads/test_hospital_points_brazil.geojson",
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(brazilHospitalsPointsGeoJSON),
        });
      },
    );

    await page.route(
      "**/uploads/test_hospital_areas_brazil.geojson",
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(brazilHospitalsAreasGeoJSON),
        });
      },
    );
  });

  test("BUG REPRODUCTION: Add to Map button - layers should render immediately", async ({
    page,
  }) => {
    /**
     * This test reproduces the production bug where:
     * 1. User asks "geocode Hospitals in Brazil"
     * 2. Backend returns 2 layers (Points and Areas)
     * 3. User clicks "Add to Map" button
     * 4. BUG: Layer zooms in but doesn't show features
     * 5. User has to toggle visibility or click multiple times
     *
     * EXPECTED: Layers should render immediately after clicking "Add to Map"
     */

    // Mock the /api/chat endpoint to return hospital layers
    const mockChatResponse = {
      messages: [
        { type: "human", content: "geocode Hospitals in Brazil" },
        {
          type: "ai",
          content:
            "I found 2 layers with hospitals in Brazil: 3 point features and 1 area feature.",
        },
      ],
      geodata_results: [mockHospitalPointsLayer, mockHospitalAreasLayer],
      geodata_layers: [], // No layers added to map yet
    };

    await page.route("**/api/chat", async (route) => {
      console.log("Mock /api/chat route hit!");
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockChatResponse),
      });
    });

    // Navigate to the app
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    // Enter query in chat
    const chatInput = page.getByPlaceholder("Type a chat command...");
    await chatInput.fill("geocode Hospitals in Brazil");

    // Submit and wait for response
    await Promise.all([
      page.waitForResponse("**/chat"),
      chatInput.press("Enter"),
    ]);

    // Wait for results to appear
    await expect(page.getByText("I found 2 layers")).toBeVisible({
      timeout: 5000,
    });

    // Wait for Search Results section to appear
    await expect(page.getByText("Search Results:")).toBeVisible({
      timeout: 5000,
    });

    // Verify we have 2 results in the geoDataList (using title field)
    await expect(
      page.getByText("Hospitals (Points) near Brazil"),
    ).toBeVisible();
    await expect(page.getByText("Hospitals (Areas) near Brazil")).toBeVisible();

    // Check initial state - no layers should be in the store yet
    let layerCount = await getLayerCount(page);
    expect(layerCount).toBe(0);

    // Click "Add to Map" button for the Points layer
    const addToMapButtons = page.getByRole("button", { name: "Add to Map" });
    const firstAddButton = addToMapButtons.first();
    await firstAddButton.click();

    // Wait for layer to be added to store
    await page.waitForTimeout(500);

    // Verify layer was added to store
    layerCount = await getLayerCount(page);
    expect(layerCount).toBe(1);

    // Verify layer is marked as visible in store
    const isVisible = await isLayerVisible(page, "hospital-points-test-123");
    expect(isVisible).toBe(true);

    // ⚠️ CRITICAL TEST: Check if features are actually rendered on the map
    // WITHOUT needing to toggle visibility or click again
    const renderedFeatures = await countRenderedFeatures(page);

    console.log(`Rendered features after Add to Map: ${renderedFeatures}`);

    // We expect to see 3 point features rendered
    expect(renderedFeatures).toBeGreaterThan(0); // At least some features should be visible
    expect(renderedFeatures).toBeGreaterThanOrEqual(3); // Should have all 3 points

    // Add second layer (Areas)
    const secondAddButton = addToMapButtons.nth(1);
    await secondAddButton.click();

    await page.waitForTimeout(500);

    // Verify both layers are in store
    layerCount = await getLayerCount(page);
    expect(layerCount).toBe(2);

    // Verify areas layer is visible
    const areasVisible = await isLayerVisible(page, "hospital-areas-test-456");
    expect(areasVisible).toBe(true);

    // Check total rendered features (3 points + 1 area = 4 features)
    const totalFeatures = await countRenderedFeatures(page);
    console.log(
      `Total rendered features after adding both layers: ${totalFeatures}`,
    );

    expect(totalFeatures).toBeGreaterThanOrEqual(4); // All features should be visible
  });

  test("VERIFICATION: Toggle visibility works correctly after adding layer", async ({
    page,
  }) => {
    /**
     * After fixing the main bug, we should verify that:
     * 1. Layers render immediately when added
     * 2. Toggle visibility ON/OFF still works correctly
     * 3. No multiple clicks or workarounds needed
     */

    // Mock chat response
    const mockChatResponse = {
      messages: [
        { type: "human", content: "show hospitals" },
        { type: "ai", content: "Here are the hospitals." },
      ],
      geodata_results: [mockHospitalPointsLayer],
      geodata_layers: [],
    };

    await page.route("**/chat", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockChatResponse),
      });
    });

    await page.goto("/");
    await page.waitForLoadState("networkidle");

    // Submit query
    const chatInput = page.getByPlaceholder("Type a chat command...");
    await chatInput.fill("show hospitals");
    await chatInput.press("Enter");

    await page.waitForResponse("**/chat");
    await expect(page.getByText("Here are the hospitals.")).toBeVisible();

    // Add layer to map
    await page.getByRole("button", { name: "Add to Map" }).first().click();
    await page.waitForTimeout(500);

    // Verify initial render
    let features = await countRenderedFeatures(page);
    expect(features).toBeGreaterThan(0);
    console.log(`Initial features: ${features}`);

    // Now test toggling visibility
    // First, we need to open the LayerManagement sidebar to access the visibility toggle
    // (This might be a toggle button or the layer might be visible in the sidebar)

    // For now, let's verify the layer visibility state in the store
    let isVisible = await isLayerVisible(page, "hospital-points-test-123");
    expect(isVisible).toBe(true);

    // Toggle visibility off via store (simulating what the UI would do)
    await page.evaluate((layerId) => {
      const store = (window as any).useLayerStore;
      if (store) {
        store.getState().toggleLayerVisibility(layerId);
      }
    }, "hospital-points-test-123");

    await page.waitForTimeout(500);

    // Verify layer is hidden
    isVisible = await isLayerVisible(page, "hospital-points-test-123");
    expect(isVisible).toBe(false);

    // Features should not be rendered
    features = await countRenderedFeatures(page);
    expect(features).toBe(0);
    console.log(`Features after hiding: ${features}`);

    // Toggle visibility back on
    await page.evaluate((layerId) => {
      const store = (window as any).useLayerStore;
      if (store) {
        store.getState().toggleLayerVisibility(layerId);
      }
    }, "hospital-points-test-123");

    await page.waitForTimeout(500);

    // Verify layer is visible again
    isVisible = await isLayerVisible(page, "hospital-points-test-123");
    expect(isVisible).toBe(true);

    // Features should be rendered again
    features = await countRenderedFeatures(page);
    expect(features).toBeGreaterThan(0);
    console.log(`Features after showing again: ${features}`);
  });

  test("EDGE CASE: Multiple rapid Add to Map clicks should not cause issues", async ({
    page,
  }) => {
    /**
     * Test that clicking "Add to Map" multiple times in rapid succession
     * doesn't cause duplicate layers or render issues
     */

    const mockChatResponse = {
      messages: [
        { type: "human", content: "show data" },
        { type: "ai", content: "Here is your data." },
      ],
      geodata_results: [mockHospitalPointsLayer],
      geodata_layers: [],
    };

    await page.route("**/chat", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockChatResponse),
      });
    });

    await page.goto("/");
    await page.waitForLoadState("networkidle");

    const chatInput = page.getByPlaceholder("Type a chat command...");
    await chatInput.fill("show data");
    await chatInput.press("Enter");

    await page.waitForResponse("**/chat");

    // Click "Add to Map" multiple times rapidly
    const addButton = page.getByRole("button", { name: "Add to Map" }).first();

    await addButton.click();
    await addButton.click();
    await addButton.click();

    await page.waitForTimeout(1000);

    // Should only have 1 layer (addLayer deduplicates by ID)
    const layerCount = await getLayerCount(page);
    expect(layerCount).toBe(1);

    // Features should still render correctly
    const features = await countRenderedFeatures(page);
    expect(features).toBeGreaterThan(0);
  });
});
