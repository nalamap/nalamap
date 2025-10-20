import { test, expect } from "@playwright/test";

test("page should load without crashing", async ({ page }) => {
  // Listen for console messages but filter out expected warnings
  page.on("console", (msg) => {
    const text = msg.text();
    // Filter out expected warnings in test environment
    if (
      text.includes("Download the React DevTools") ||
      text.includes("webpack-hmr") ||
      text.includes("Exposed to window for testing") ||
      text.includes("Cache exposed to window")
    ) {
      return; // Skip logging expected messages
    }
    console.log(`[Browser ${msg.type()}]:`, text);
  });

  // Listen for page errors
  page.on("pageerror", (error) => {
    console.error("[Browser Error]:", error.message);
  });

  await page.goto("/map");

  // Wait for map to be ready
  const mapContainer = await page.locator(".leaflet-container");
  await expect(mapContainer).toBeVisible({ timeout: 10000 });

  console.log("Map container is visible");

  // Wait for stores to be exposed (dynamic import + useEffect)
  try {
    await page.waitForFunction(
      () => {
        return typeof (window as any).useLayerStore !== "undefined";
      },
      { timeout: 10000 },
    );

    console.log("Store is now available");

    // Try to add a layer
    const result = await page.evaluate(() => {
      const { useLayerStore } = window as any;
      const layer = {
        id: "test-1",
        name: "Test Layer",
        data_link: "https://example.com/test.geojson",
        layer_type: "GeoJSON",
        visible: true,
      };
      useLayerStore.getState().addLayer(layer);
      return {
        layerCount: useLayerStore.getState().layers.length,
      };
    });
    console.log("Layer added successfully, count:", result.layerCount);
    expect(result.layerCount).toBe(1);
  } catch (error) {
    console.log("Store wait timed out, checking what went wrong...");

    // Check if LeafletMapClient is loaded
    const componentCheck = await page.evaluate(() => {
      const checks = {
        hasMapContainer: !!document.querySelector(".leaflet-container"),
        hasLeafletTiles: !!document.querySelector(".leaflet-tile-container"),
        windowKeys: Object.keys(window).filter(
          (k) =>
            k.includes("use") || k.includes("Layer") || k.includes("Store"),
        ),
      };
      return checks;
    });
    console.log("Component check:", JSON.stringify(componentCheck, null, 2));
    throw error;
  }
});
