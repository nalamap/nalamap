import { test, expect } from "@playwright/test";

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

test.describe("Scale Control Real World Test", () => {
  test.beforeEach(async ({ page }) => {
    await page.route("**/settings/options", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockSettings),
      });
    });

    await page.goto("/");
    await page.waitForLoadState("networkidle");
  });

  test("should show realistic scale for Germany at appropriate zoom", async ({ page }) => {
    // Wait for map to load
    await page.waitForSelector(".leaflet-container", { timeout: 10000 });
    await page.waitForTimeout(2000); // Give map time to initialize

    // Zoom in multiple times to get to Germany zoom level
    const zoomInButton = page.locator(".leaflet-control-zoom-in");
    
    // Click zoom in 4 times (from zoom 2 to zoom 6)
    for (let i = 0; i < 4; i++) {
      await zoomInButton.click();
      await page.waitForTimeout(500);
    }

    // Now check the scale
    const scaleLines = page.locator(".leaflet-control-scale-line");
    const metricLine = scaleLines.first();
    const metricText = await metricLine.textContent();

    console.log(`Scale after 4 zoom-ins (should be at zoom 6): "${metricText}"`);

    // At zoom 6 from world view, the scale should show something reasonable
    // Extract the number
    const match = metricText?.match(/(\d+)\s*km/);
    if (match) {
      const kmValue = parseInt(match[1]);
      console.log(`Scale shows: ${kmValue} km`);
      
      // At zoom 6, scale should be roughly 200-500 km, not 3000 km
      expect(kmValue).toBeLessThan(1000);
      console.log(`✅ Scale is showing reasonable distance: ${kmValue} km`);
    }
  });

  test("should update scale when manually panning and zooming", async ({ page }) => {
    await page.waitForSelector(".leaflet-container", { timeout: 10000 });
    await page.waitForTimeout(2000);

    // Get initial scale
    const scaleLines = page.locator(".leaflet-control-scale-line");
    const metricLine = scaleLines.first();
    const initialScale = await metricLine.textContent();
    console.log(`Initial scale (zoom 2): "${initialScale}"`);

    // Zoom in significantly
    const zoomInButton = page.locator(".leaflet-control-zoom-in");
    for (let i = 0; i < 6; i++) {
      await zoomInButton.click();
      await page.waitForTimeout(300);
    }

    // Check scale after zooming
    const afterZoomScale = await metricLine.textContent();
    console.log(`Scale after 6 zoom-ins (zoom 8): "${afterZoomScale}"`);

    // The scale should have changed significantly
    expect(afterZoomScale).not.toEqual(initialScale);

    // At zoom 8, scale should show much smaller distances (like 50-200 km)
    const match = afterZoomScale?.match(/(\d+)\s*km/);
    if (match) {
      const kmValue = parseInt(match[1]);
      console.log(`Scale at zoom 8: ${kmValue} km`);
      
      // At high zoom, scale should be smaller
      expect(kmValue).toBeLessThan(500);
    }
  });
});
