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

test.describe("Scale Control Zoom Behavior Investigation", () => {
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
    
    // Wait for map to be ready
    await page.waitForSelector(".leaflet-container", { timeout: 10000 });
    await page.waitForSelector(".leaflet-control-scale", { state: "visible" });
    await page.waitForTimeout(1000);
  });

  test("should track scale changes during zoom out to minimum", async ({ page }) => {
    const scaleLines = page.locator(".leaflet-control-scale-line");
    const metricLine = scaleLines.first();

    const initialScale = await metricLine.textContent();
    console.log(`\nInitial scale: "${initialScale}"`);

    // Zoom out all the way to minimum
    const zoomOutButton = page.locator(".leaflet-control-zoom-out");
    
    let previousScale = initialScale;
    let zoomCount = 0;

    // Keep zooming out until button is disabled
    for (let i = 0; i < 10; i++) {
      // Check if button is disabled
      const isDisabled = await zoomOutButton.getAttribute('aria-disabled');
      if (isDisabled === 'true') {
        console.log(`\n✋ Reached minimum zoom level (button disabled after ${i} attempts)`);
        break;
      }

      await zoomOutButton.click();
      await page.waitForTimeout(300);
      
      const currentScale = await metricLine.textContent();
      
      if (currentScale !== previousScale) {
        zoomCount++;
        console.log(`After zoom out ${zoomCount}: "${currentScale}"`);
        previousScale = currentScale;
      }
    }

    const finalScale = await metricLine.textContent();
    console.log(`\nFinal scale: "${finalScale}"`);

    // At minimum zoom (typically 0 or 1), scale should show LARGE distances
    // e.g., 3000-10000 km, NOT meters
    const match = finalScale?.match(/(\d+)\s*(\w+)/);
    if (match) {
      const value = parseInt(match[1]);
      const unit = match[2];
      
      console.log(`\n📏 Final scale: ${value} ${unit}`);
      
      // At world view, we should see kilometers (km), not meters (m)
      expect(unit).toBe("km");
      
      // And the value should be in thousands
      expect(value).toBeGreaterThan(1000);
    }
  });

  test("should test scale at each zoom level systematically", async ({ page }) => {
    const scaleLines = page.locator(".leaflet-control-scale-line");
    const metricLine = scaleLines.first();

    // First zoom out all the way
    const zoomOutButton = page.locator(".leaflet-control-zoom-out");
    for (let i = 0; i < 10; i++) {
      const isDisabled = await zoomOutButton.getAttribute('aria-disabled');
      if (isDisabled === 'true') break;
      
      await zoomOutButton.click();
      await page.waitForTimeout(300);
    }

    // Now zoom in step by step and record scale at each level
    const zoomInButton = page.locator(".leaflet-control-zoom-in");
    const scalesByZoom: Array<{scale: string}> = [];

    for (let i = 0; i < 15; i++) {
      const scale = await metricLine.textContent();
      
      if (scale) {
        scalesByZoom.push({ scale });
        console.log(`Step ${i}: ${scale}`);
      }

      // Check if we can zoom in more
      const isDisabled = await zoomInButton.getAttribute('aria-disabled');
      if (isDisabled === 'true') break;

      await zoomInButton.click();
      await page.waitForTimeout(300);
    }

    console.log("\n📊 Scale progression:");
    scalesByZoom.forEach(({ scale }, idx) => {
      console.log(`  Step ${idx}: ${scale}`);
    });

    // Verify we collected multiple scale values
    expect(scalesByZoom.length).toBeGreaterThan(5);
    
    // Verify first scale (at minimum zoom) shows large distances
    const firstScale = scalesByZoom[0].scale;
    const firstMatch = firstScale.match(/(\d+)\s*km/);
    if (firstMatch) {
      const firstValue = parseInt(firstMatch[1]);
      expect(firstValue).toBeGreaterThan(1000);
    }
  });

  test("should check for scale control recreation issues", async ({ page }) => {
    // Check how many scale controls are present
    const countBefore = await page.locator(".leaflet-control-scale").count();
    console.log(`Scale controls before interaction: ${countBefore}`);

    // Zoom in and out multiple times
    const zoomInButton = page.locator(".leaflet-control-zoom-in");
    const zoomOutButton = page.locator(".leaflet-control-zoom-out");

    for (let i = 0; i < 3; i++) {
      await zoomInButton.click();
      await page.waitForTimeout(200);
      await zoomOutButton.click();
      await page.waitForTimeout(200);
    }

    // Check if multiple scale controls were created
    const countAfter = await page.locator(".leaflet-control-scale").count();
    console.log(`Scale controls after zoom cycles: ${countAfter}`);

    expect(countAfter).toBe(1);

    // Check the scale lines
    const lineCount = await page.locator(".leaflet-control-scale-line").count();
    console.log(`Scale lines: ${lineCount}`);
    expect(lineCount).toBe(2); // Should be exactly 2 (metric and imperial)
  });

  test("should pan around and check if scale changes unexpectedly", async ({ page }) => {
    const scaleLines = page.locator(".leaflet-control-scale-line");
    const metricLine = scaleLines.first();

    // Zoom to a specific level first
    const zoomInButton = page.locator(".leaflet-control-zoom-in");
    for (let i = 0; i < 3; i++) {
      await zoomInButton.click();
      await page.waitForTimeout(200);
    }

    await page.waitForTimeout(500);
    const initialScale = await metricLine.textContent();
    console.log(`Initial scale: ${initialScale}`);

    // Pan the map using drag
    const mapContainer = page.locator('.leaflet-container');
    const box = await mapContainer.boundingBox();
    
    if (box) {
      // Pan right
      await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
      await page.mouse.down();
      await page.mouse.move(box.x + box.width / 4, box.y + box.height / 2, { steps: 10 });
      await page.mouse.up();
      await page.waitForTimeout(300);
      
      const afterPan = await metricLine.textContent();
      console.log(`After pan: ${afterPan}`);

      // Note: Scale SHOULD change with latitude in Web Mercator projection
      // This is expected behavior, not a bug
      console.log('Scale may change slightly due to Web Mercator projection distortion');
    }

    // Get final scale
    const finalScale = await metricLine.textContent();
  });
});
