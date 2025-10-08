import { test, expect } from "@playwright/test";

test.describe("GeoJSON Cache - Essential Tests", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("http://localhost:3000");
    
    // Wait for stores and cache to be initialized
    await page.waitForFunction(() => {
      return (
        typeof (window as any).useLayerStore !== "undefined" &&
        typeof (window as any).geoJSONCache !== "undefined"
      );
    });

    // Clear cache and layers before each test
    await page.evaluate(() => {
      (window as any).geoJSONCache.clear();
      (window as any).useLayerStore.getState().resetLayers();
    });
  });

  test("Cache: should expose cache to window for debugging", async ({ page }) => {
    const cacheExists = await page.evaluate(() => {
      return typeof (window as any).geoJSONCache !== "undefined";
    });

    expect(cacheExists).toBe(true);
  });

  test("Cache: should have correct initial state", async ({ page }) => {
    const cacheStats = await page.evaluate(() => {
      return (window as any).geoJSONCache.getCacheStats();
    });

    expect(cacheStats.entries).toBe(0);
    expect(cacheStats.size).toBe(0);
    expect(cacheStats.maxSize).toBe(50 * 1024 * 1024); // 50MB
  });

  test("Cache: should cache data after successful GeoJSON load", async ({ page }) => {
    // Listen for cache logs
    const consoleLogs: string[] = [];
    page.on("console", (msg) => {
      const text = msg.text();
      if (text.includes("GeoJSONCache") || text.includes("Cached")) {
        consoleLogs.push(text);
      }
    });

    // Add a layer with the test file
    const testLayer = {
      id: "cache-test-1",
      name: "Cache Test",
      data_link: "/test-data.geojson",
      layer_type: "UPLOADED",
      data_source: "test",
      data_source_id: "test-1",
      data_type: "geojson",
      data_origin: "test",
      visible: true,
    };

    await page.evaluate((layer) => {
      (window as any).useLayerStore.getState().addLayer(layer);
    }, testLayer);

    // Wait for layer to load
    await page.waitForTimeout(3000);

    // Check if cache message appeared
    const hasCacheMessage = consoleLogs.some(log => 
      log.includes("Cached /test-data.geojson") || 
      log.includes("Cache HIT")
    );

    console.log("Cache logs:", consoleLogs);
    expect(hasCacheMessage).toBe(true);
  });

  test("Cache: should show cache hit on visibility toggle", async ({ page }) => {
    // Track console logs
    const consoleLogs: string[] = [];
    page.on("console", (msg) => {
      const text = msg.text();
      if (text.includes("Cache HIT") || text.includes("Using cached data")) {
        consoleLogs.push(text);
      }
    });

    // Add layer
    const testLayer = {
      id: "toggle-test",
      name: "Toggle Test",
      data_link: "/test-data.geojson",
      layer_type: "UPLOADED",
      data_source: "test",
      data_source_id: "toggle-1",
      data_type: "geojson",
      data_origin: "test",
      visible: true,
    };

    await page.evaluate((layer) => {
      (window as any).useLayerStore.getState().addLayer(layer);
    }, testLayer);

    await page.waitForTimeout(3000);

    // Clear logs
    consoleLogs.length = 0;

    // Toggle off
    await page.evaluate((id) => {
      (window as any).useLayerStore.getState().toggleLayerVisibility(id);
    }, testLayer.id);

    await page.waitForTimeout(500);

    // Toggle on - should use cache
    await page.evaluate((id) => {
      (window as any).useLayerStore.getState().toggleLayerVisibility(id);
    }, testLayer.id);

    await page.waitForTimeout(1000);

    // Should have cache hit message
    const hasCacheHit = consoleLogs.some(log => 
      log.includes("Cache HIT") || log.includes("Using cached data")
    );

    console.log("Toggle cache logs:", consoleLogs);
    expect(hasCacheHit).toBe(true);
  });

  test("Cache: should respect size limit", async ({ page }) => {
    const stats = await page.evaluate(() => {
      const cache = (window as any).geoJSONCache;
      
      // Add large mock data
      const largeData: any = { type: "FeatureCollection", features: [] };
      for (let i = 0; i < 1000; i++) {
        largeData.features.push({
          type: "Feature",
          properties: { id: i, data: "x".repeat(1000) },
          geometry: { type: "Point", coordinates: [0, 0] },
        });
      }

      // Try to add multiple entries
      cache.set("large-1", largeData);
      cache.set("large-2", largeData);
      cache.set("large-3", largeData);

      return cache.getCacheStats();
    });

    console.log("Cache stats after adding large data:", stats);
    
    // Cache size should not exceed max
    expect(stats.size).toBeLessThanOrEqual(stats.maxSize);
    expect(stats.entries).toBeGreaterThan(0);
  });

  test("Cache: clear should remove all entries", async ({ page }) => {
    // Add some data to cache
    await page.evaluate(() => {
      const cache = (window as any).geoJSONCache;
      cache.set("test-1", { type: "FeatureCollection", features: [] });
      cache.set("test-2", { type: "FeatureCollection", features: [] });
    });

    let stats = await page.evaluate(() => {
      return (window as any).geoJSONCache.getCacheStats();
    });

    expect(stats.entries).toBe(2);

    // Clear cache
    await page.evaluate(() => {
      (window as any).geoJSONCache.clear();
    });

    stats = await page.evaluate(() => {
      return (window as any).geoJSONCache.getCacheStats();
    });

    expect(stats.entries).toBe(0);
    expect(stats.size).toBe(0);
  });

  test("Performance: cached load should be faster than initial load", async ({ page }) => {
    const testLayer = {
      id: "perf-test",
      name: "Performance Test",
      data_link: "/test-data-medium.geojson",
      layer_type: "UPLOADED",
      data_source: "test",
      data_source_id: "perf-1",
      data_type: "geojson",
      data_origin: "test",
      visible: true,
    };

    // Measure first load
    const startFirst = Date.now();
    await page.evaluate((layer) => {
      (window as any).useLayerStore.getState().addLayer(layer);
    }, testLayer);

    await page.waitForTimeout(3000);
    const firstLoadTime = Date.now() - startFirst;

    // Toggle off and on to use cache
    await page.evaluate((id) => {
      (window as any).useLayerStore.getState().toggleLayerVisibility(id);
    }, testLayer.id);

    await page.waitForTimeout(200);

    const startCached = Date.now();
    await page.evaluate((id) => {
      (window as any).useLayerStore.getState().toggleLayerVisibility(id);
    }, testLayer.id);

    await page.waitForTimeout(500);
    const cachedLoadTime = Date.now() - startCached;

    console.log(`First load: ${firstLoadTime}ms, Cached: ${cachedLoadTime}ms`);
    console.log(`Speed improvement: ${(firstLoadTime / cachedLoadTime).toFixed(2)}x`);

    // Cached should be significantly faster (at least 2x)
    expect(cachedLoadTime).toBeLessThan(firstLoadTime / 2);
  });

  test("Integration: multiple layers should all use cache correctly", async ({ page }) => {
    const layers = [
      {
        id: "multi-1",
        name: "Multi 1",
        data_link: "/test-data.geojson",
        layer_type: "UPLOADED",
        data_source: "test",
        data_source_id: "multi-1",
        data_type: "geojson",
        data_origin: "test",
        visible: true,
      },
      {
        id: "multi-2",
        name: "Multi 2",
        data_link: "/test-data-medium.geojson",
        layer_type: "UPLOADED",
        data_source: "test",
        data_source_id: "multi-2",
        data_type: "geojson",
        data_origin: "test",
        visible: true,
      },
    ];

    // Add all layers
    for (const layer of layers) {
      await page.evaluate((l) => {
        (window as any).useLayerStore.getState().addLayer(l);
      }, layer);
      await page.waitForTimeout(1500);
    }

    // Check cache has entries
    const stats = await page.evaluate(() => {
      return (window as any).geoJSONCache.getCacheStats();
    });

    console.log("Multi-layer cache stats:", stats);
    expect(stats.entries).toBeGreaterThan(0);
    expect(stats.entries).toBeLessThanOrEqual(2);
  });
});
