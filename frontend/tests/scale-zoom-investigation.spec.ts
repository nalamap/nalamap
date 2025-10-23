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
  });

  test("should track scale changes during zoom out to minimum", async ({ page }) => {
    await page.waitForSelector(".leaflet-container", { timeout: 10000 });
    await page.waitForTimeout(2000);

    const scaleLines = page.locator(".leaflet-control-scale-line");
    const metricLine = scaleLines.first();

    // Get current zoom level and scale
    const getMapInfo = async () => {
      return await page.evaluate(() => {
        const mapContainer = document.querySelector('.leaflet-container') as any;
        if (mapContainer && mapContainer._leaflet_map) {
          const map = mapContainer._leaflet_map;
          return {
            zoom: map.getZoom(),
            center: map.getCenter(),
            minZoom: map.getMinZoom(),
            maxZoom: map.getMaxZoom(),
          };
        }
        return null;
      });
    };

    const initialInfo = await getMapInfo();
    const initialScale = await metricLine.textContent();
    console.log(`\nInitial state (zoom ${initialInfo?.zoom}): "${initialScale}"`);

    // Zoom out all the way to minimum
    const zoomOutButton = page.locator(".leaflet-control-zoom-out");
    
    let previousScale = initialScale;
    let zoomCount = 0;

    // Keep zooming out until we can't anymore
    for (let i = 0; i < 10; i++) {
      await zoomOutButton.click();
      await page.waitForTimeout(500);
      
      const currentInfo = await getMapInfo();
      const currentScale = await metricLine.textContent();
      
      if (currentScale !== previousScale) {
        zoomCount++;
        console.log(`After zoom out ${zoomCount} (zoom ${currentInfo?.zoom}): "${currentScale}"`);
        previousScale = currentScale;
      }
      
      // Check if we've reached minimum zoom
      if (currentInfo && currentInfo.zoom <= currentInfo.minZoom) {
        console.log(`\n✋ Reached minimum zoom level: ${currentInfo.minZoom}`);
        break;
      }
    }

    const finalInfo = await getMapInfo();
    const finalScale = await metricLine.textContent();
    console.log(`\nFinal state (zoom ${finalInfo?.zoom}): "${finalScale}"`);

    // At minimum zoom (typically 0 or 1), scale should show LARGE distances
    // e.g., 3000-5000 km, NOT meters
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
    await page.waitForSelector(".leaflet-container", { timeout: 10000 });
    await page.waitForTimeout(2000);

    const scaleLines = page.locator(".leaflet-control-scale-line");
    const metricLine = scaleLines.first();

    // First zoom out all the way
    const zoomOutButton = page.locator(".leaflet-control-zoom-out");
    for (let i = 0; i < 10; i++) {
      await zoomOutButton.click();
      await page.waitForTimeout(300);
    }

    // Now zoom in step by step and record scale at each level
    const zoomInButton = page.locator(".leaflet-control-zoom-in");
    const scalesByZoom: Array<{zoom: number, scale: string}> = [];

    for (let i = 0; i < 15; i++) {
      const info = await page.evaluate(() => {
        const mapContainer = document.querySelector('.leaflet-container') as any;
        if (mapContainer && mapContainer._leaflet_map) {
          return { zoom: mapContainer._leaflet_map.getZoom() };
        }
        return null;
      });

      const scale = await metricLine.textContent();
      
      if (info && scale) {
        scalesByZoom.push({ zoom: info.zoom, scale });
        console.log(`Zoom ${info.zoom}: ${scale}`);
      }

      await zoomInButton.click();
      await page.waitForTimeout(500);
    }

    console.log("\n📊 Scale progression:");
    scalesByZoom.forEach(({ zoom, scale }) => {
      console.log(`  Zoom ${zoom.toFixed(0)}: ${scale}`);
    });

    // Verify scale decreases as we zoom in
    for (let i = 1; i < scalesByZoom.length; i++) {
      const prevValue = parseInt(scalesByZoom[i-1].scale.match(/(\d+)/)?.[1] || "0");
      const currValue = parseInt(scalesByZoom[i].scale.match(/(\d+)/)?.[1] || "0");
      
      // Generally scale should decrease as zoom increases (with unit conversions)
      // At minimum zoom, we expect thousands of km
      if (scalesByZoom[i-1].zoom <= 2) {
        const prevUnit = scalesByZoom[i-1].scale.match(/\w+$/)?.[0];
        expect(prevUnit).toBe("km");
        expect(prevValue).toBeGreaterThan(1000);
      }
    }
  });

  test("should check for scale control recreation issues", async ({ page }) => {
    await page.waitForSelector(".leaflet-container", { timeout: 10000 });
    await page.waitForTimeout(2000);

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
    await page.waitForSelector(".leaflet-container", { timeout: 10000 });
    await page.waitForTimeout(2000);

    const scaleLines = page.locator(".leaflet-control-scale-line");
    const metricLine = scaleLines.first();

    // Set a specific zoom level
    await page.evaluate(() => {
      const mapContainer = document.querySelector('.leaflet-container') as any;
      if (mapContainer && mapContainer._leaflet_map) {
        const map = mapContainer._leaflet_map;
        map.setView([0, 0], 5); // Equator, zoom 5
      }
    });

    await page.waitForTimeout(1000);
    const scaleAtEquator = await metricLine.textContent();
    console.log(`Scale at Equator (0°N, zoom 5): ${scaleAtEquator}`);

    // Pan to different latitudes and check scale
    const locations = [
      { name: "Germany", lat: 51, lon: 10 },
      { name: "Northern Canada", lat: 70, lon: -100 },
      { name: "Antarctica", lat: -70, lon: 0 },
      { name: "Back to Equator", lat: 0, lon: 0 },
    ];

    for (const loc of locations) {
      await page.evaluate((location) => {
        const mapContainer = document.querySelector('.leaflet-container') as any;
        if (mapContainer && mapContainer._leaflet_map) {
          const map = mapContainer._leaflet_map;
          map.setView([location.lat, location.lon], 5);
        }
      }, loc);

      await page.waitForTimeout(1000);
      const scale = await metricLine.textContent();
      console.log(`Scale at ${loc.name} (${loc.lat}°N, zoom 5): ${scale}`);
    }

    // The scale SHOULD change with latitude (Web Mercator distortion)
    // But it should remain in reasonable ranges (e.g., 300-500 km at zoom 5)
    const finalScale = await metricLine.textContent();
    const match = finalScale?.match(/(\d+)\s*km/);
    if (match) {
      const value = parseInt(match[1]);
      expect(value).toBeGreaterThan(100);
      expect(value).toBeLessThan(1000);
    }
  });
});
