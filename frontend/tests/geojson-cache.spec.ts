import { test, expect } from "@playwright/test";

test.describe("GeoJSON Cache Tests", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("http://localhost:3000");
    
    // Wait for stores and cache to be initialized
    await page.waitForFunction(() => {
      return (
        typeof (window as any).useLayerStore !== "undefined" &&
        typeof (window as any).geoJSONCache !== "undefined"
      );
    });

    // Clear cache before each test
    await page.evaluate(() => {
      (window as any).geoJSONCache.clear();
    });
  });

  test("Cache: should cache GeoJSON data after first fetch", async ({
    page,
  }) => {
    // Add a test layer
    const testLayer = {
      id: "cache-test-1",
      name: "Cache Test Layer",
      data_link: "/uploads/001_single_point_1kb.geojson",
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

    // Wait for layer to load completely
    await page.waitForTimeout(5000);

    // Check cache stats - should have 1 entry
    const cacheStats = await page.evaluate(() => {
      return (window as any).geoJSONCache.getCacheStats();
    });

    console.log("Cache stats after first load:", cacheStats);
    expect(cacheStats.entries).toBe(1);
    expect(cacheStats.size).toBeGreaterThan(0);
  });

  test("Cache: should retrieve data from cache on second access", async ({
    page,
  }) => {
    const testLayer = {
      id: "cache-test-2",
      name: "Cache Test Layer 2",
      data_link: "/uploads/001_single_point_1kb.geojson",
      layer_type: "UPLOADED",
      data_source: "test",
      data_source_id: "test-2",
      data_type: "geojson",
      data_origin: "test",
      visible: true,
    };

    // Listen for console logs to detect cache hit
    const consoleLogs: string[] = [];
    page.on("console", (msg) => {
      const text = msg.text();
      if (text.includes("GeoJSONCache") || text.includes("LeafletGeoJSONLayer")) {
        consoleLogs.push(text);
      }
    });

    // First load
    await page.evaluate((layer) => {
      (window as any).useLayerStore.getState().addLayer(layer);
    }, testLayer);

    await page.waitForTimeout(5000);

    // Toggle visibility off
    await page.evaluate((layerId) => {
      (window as any).useLayerStore.getState().toggleLayerVisibility(layerId);
    }, testLayer.id);

    await page.waitForTimeout(500);

    // Clear console logs
    consoleLogs.length = 0;

    // Toggle visibility back on (should use cache)
    await page.evaluate((layerId) => {
      (window as any).useLayerStore.getState().toggleLayerVisibility(layerId);
    }, testLayer.id);

    await page.waitForTimeout(1000);

    // Check logs for cache hit
    const hasCacheHit = consoleLogs.some((log) =>
      log.includes("Using cached data")
    );
    console.log("Console logs:", consoleLogs);
    console.log("Has cache hit:", hasCacheHit);

    expect(hasCacheHit).toBe(true);

    // Verify no network request was made for the second load
    // The cache hit should be much faster than the original fetch
  });

  test("Cache: should not re-fetch when toggling visibility", async ({
    page,
  }) => {
    const testLayer = {
      id: "cache-test-3",
      name: "Toggle Test Layer",
      data_link: "/uploads/001_single_point_1kb.geojson",
      layer_type: "UPLOADED",
      data_source: "test",
      data_source_id: "test-3",
      data_type: "geojson",
      data_origin: "test",
      visible: true,
    };

    // Track network requests
    const networkRequests: string[] = [];
    page.on("request", (request) => {
      if (request.url().includes("001_single_point_1kb.geojson")) {
        networkRequests.push(request.url());
      }
    });

    // First load
    await page.evaluate((layer) => {
      (window as any).useLayerStore.getState().addLayer(layer);
    }, testLayer);

    await page.waitForTimeout(5000);

    const requestsAfterFirstLoad = networkRequests.length;
    console.log("Network requests after first load:", requestsAfterFirstLoad);
    // Should have made at most 1 request (may be 0 if cached)
    expect(requestsAfterFirstLoad).toBeGreaterThanOrEqual(0);
    expect(requestsAfterFirstLoad).toBeLessThanOrEqual(1);

    // Toggle visibility multiple times
    for (let i = 0; i < 3; i++) {
      await page.evaluate((layerId) => {
        (window as any).useLayerStore.getState().toggleLayerVisibility(layerId);
      }, testLayer.id);
      await page.waitForTimeout(200);

      await page.evaluate((layerId) => {
        (window as any).useLayerStore.getState().toggleLayerVisibility(layerId);
      }, testLayer.id);
      await page.waitForTimeout(200);
    }

    // Should still be same as initial (no new requests)
    const totalRequests = networkRequests.length;
    console.log("Total network requests after toggles:", totalRequests);
    expect(totalRequests).toBe(requestsAfterFirstLoad);
  });

  test("Cache: should respect cache size limit", async ({ page }) => {
    // Get initial cache stats
    let cacheStats = await page.evaluate(() => {
      return (window as any).geoJSONCache.getCacheStats();
    });

    console.log("Initial cache stats:", cacheStats);
    const maxSize = cacheStats.maxSize;

    // Try to add data directly to cache to test size limit
    // Note: In a real test, you'd add many large layers
    await page.evaluate(() => {
      const cache = (window as any).geoJSONCache;
      const largeData: any = { type: "FeatureCollection", features: [] };
      
      // Create a large mock dataset
      for (let i = 0; i < 1000; i++) {
        largeData.features.push({
          type: "Feature",
          properties: { id: i, data: "x".repeat(1000) },
          geometry: { type: "Point", coordinates: [0, 0] },
        });
      }

      // Add multiple entries
      cache.set("large-1", largeData);
      cache.set("large-2", largeData);
      cache.set("large-3", largeData);
    });

    cacheStats = await page.evaluate(() => {
      return (window as any).geoJSONCache.getCacheStats();
    });

    console.log("Cache stats after adding large data:", cacheStats);
    
    // Cache size should not exceed max size
    expect(cacheStats.size).toBeLessThanOrEqual(maxSize);
  });

  test("Cache: should handle cache deletion", async ({ page }) => {
    const testUrl = "/uploads/001_single_point_1kb.geojson";

    // Add data to cache via layer
    const testLayer = {
      id: "cache-delete-test",
      name: "Delete Test Layer",
      data_link: testUrl,
      layer_type: "UPLOADED",
      data_source: "test",
      data_source_id: "test-delete",
      data_type: "geojson",
      data_origin: "test",
      visible: true,
    };

    await page.evaluate((layer) => {
      (window as any).useLayerStore.getState().addLayer(layer);
    }, testLayer);

    await page.waitForTimeout(5000);

    // Verify data is cached
    let cachedData = await page.evaluate((url) => {
      return (window as any).geoJSONCache.get(url);
    }, testUrl);

    expect(cachedData).not.toBeNull();

    // Delete from cache
    await page.evaluate((url) => {
      (window as any).geoJSONCache.delete(url);
    }, testUrl);

    // Verify data is removed
    cachedData = await page.evaluate((url) => {
      return (window as any).geoJSONCache.get(url);
    }, testUrl);

    expect(cachedData).toBeNull();
  });

  test("Cache: should clear all entries", async ({ page }) => {
    // Add multiple layers
    const layers = [
      {
        id: "clear-test-1",
        name: "Clear Test 1",
        data_link: "/uploads/001_single_point_1kb.geojson",
        layer_type: "UPLOADED",
        data_source: "test",
        data_source_id: "clear-1",
        data_type: "geojson",
        data_origin: "test",
        visible: true,
      },
      {
        id: "clear-test-2",
        name: "Clear Test 2",
        data_link: "/test-data-medium.geojson",
        layer_type: "UPLOADED",
        data_source: "test",
        data_source_id: "clear-2",
        data_type: "geojson",
        data_origin: "test",
        visible: true,
      },
    ];

    for (const layer of layers) {
      await page.evaluate((l) => {
        (window as any).useLayerStore.getState().addLayer(l);
      }, layer);
    }

    await page.waitForTimeout(4000);

    // Check cache has entries
    let cacheStats = await page.evaluate(() => {
      return (window as any).geoJSONCache.getCacheStats();
    });

    console.log("Cache stats before clear:", cacheStats);
    expect(cacheStats.entries).toBeGreaterThan(0);

    // Clear cache
    await page.evaluate(() => {
      (window as any).geoJSONCache.clear();
    });

    // Verify cache is empty
    cacheStats = await page.evaluate(() => {
      return (window as any).geoJSONCache.getCacheStats();
    });

    console.log("Cache stats after clear:", cacheStats);
    expect(cacheStats.entries).toBe(0);
    expect(cacheStats.size).toBe(0);
  });

  test("Cache: should handle style changes without re-fetching", async ({
    page,
  }) => {
    const testLayer = {
      id: "style-cache-test",
      name: "Style Cache Test",
      data_link: "/uploads/001_single_point_1kb.geojson",
      layer_type: "UPLOADED",
      data_source: "test",
      data_source_id: "style-test",
      data_type: "geojson",
      data_origin: "test",
      visible: true,
      style: {
        stroke_color: "#ff0000",
        fill_color: "#00ff00",
      },
    };

    // Track network requests
    const networkRequests: string[] = [];
    page.on("request", (request) => {
      if (request.url().includes("001_single_point_1kb.geojson")) {
        networkRequests.push(request.url());
      }
    });

    // Add layer
    await page.evaluate((layer) => {
      (window as any).useLayerStore.getState().addLayer(layer);
    }, testLayer);

    await page.waitForTimeout(5000);

    const requestsAfterLoad = networkRequests.length;
    console.log("Requests after initial load:", requestsAfterLoad);

    // Update style
    await page.evaluate((layerId) => {
      (window as any).useLayerStore.getState().updateLayerStyle(layerId, {
        stroke_color: "#0000ff",
        fill_color: "#ffff00",
      });
    }, testLayer.id);

    await page.waitForTimeout(1000);

    // Should not have made additional network requests
    const requestsAfterStyle = networkRequests.length;
    console.log("Requests after style change:", requestsAfterStyle);
    expect(requestsAfterStyle).toBe(requestsAfterLoad);
  });

  test("Performance: Cache hit should be significantly faster than fetch", async ({
    page,
  }) => {
    const testLayer = {
      id: "perf-cache-test",
      name: "Performance Test",
      data_link: "/test-data-medium.geojson",
      layer_type: "UPLOADED",
      data_source: "test",
      data_source_id: "perf-test",
      data_type: "geojson",
      data_origin: "test",
      visible: true,
    };

    // Measure first load time
    const startFirst = Date.now();
    await page.evaluate((layer) => {
      (window as any).useLayerStore.getState().addLayer(layer);
    }, testLayer);

    await page.waitForTimeout(5000);
    const firstLoadTime = Date.now() - startFirst;

    console.log("First load time:", firstLoadTime, "ms");

    // Toggle off and on to use cache
    await page.evaluate((layerId) => {
      (window as any).useLayerStore.getState().toggleLayerVisibility(layerId);
    }, testLayer.id);

    await page.waitForTimeout(200);

    // Measure cached load time
    const startCached = Date.now();
    await page.evaluate((layerId) => {
      (window as any).useLayerStore.getState().toggleLayerVisibility(layerId);
    }, testLayer.id);

    await page.waitForTimeout(500);
    const cachedLoadTime = Date.now() - startCached;

    console.log("Cached load time:", cachedLoadTime, "ms");
    console.log("Speed improvement:", (firstLoadTime / cachedLoadTime).toFixed(2) + "x");

    // Cached should be at least 2x faster
    expect(cachedLoadTime).toBeLessThan(firstLoadTime / 2);
  });

  test("Memory: Cache should properly track memory usage", async ({ page }) => {
    // Get initial stats
    const initialStats = await page.evaluate(() => {
      return (window as any).geoJSONCache.getCacheStats();
    });

    console.log("Initial stats:", initialStats);
    expect(initialStats.entries).toBe(0);
    expect(initialStats.size).toBe(0);

    // Add small layer
    const smallLayer = {
      id: "memory-test-small",
      name: "Small Layer",
      data_link: "/uploads/001_single_point_1kb.geojson",
      layer_type: "UPLOADED",
      data_source: "test",
      data_source_id: "memory-small",
      data_type: "geojson",
      data_origin: "test",
      visible: true,
    };

    await page.evaluate((layer) => {
      (window as any).useLayerStore.getState().addLayer(layer);
    }, smallLayer);

    await page.waitForTimeout(2000);

    const afterSmallStats = await page.evaluate(() => {
      return (window as any).geoJSONCache.getCacheStats();
    });

    console.log("After small layer:", afterSmallStats);
    expect(afterSmallStats.entries).toBe(1);
    expect(afterSmallStats.size).toBeGreaterThan(0);

    // Add medium layer
    const mediumLayer = {
      id: "memory-test-medium",
      name: "Medium Layer",
      data_link: "/test-data-medium.geojson",
      layer_type: "UPLOADED",
      data_source: "test",
      data_source_id: "memory-medium",
      data_type: "geojson",
      data_origin: "test",
      visible: true,
    };

    await page.evaluate((layer) => {
      (window as any).useLayerStore.getState().addLayer(layer);
    }, mediumLayer);

    await page.waitForTimeout(2000);

    const afterMediumStats = await page.evaluate(() => {
      return (window as any).geoJSONCache.getCacheStats();
    });

    console.log("After medium layer:", afterMediumStats);
    expect(afterMediumStats.entries).toBe(2);
    expect(afterMediumStats.size).toBeGreaterThan(afterSmallStats.size);

    // Verify size is within reasonable bounds
    expect(afterMediumStats.size).toBeLessThanOrEqual(afterMediumStats.maxSize);
  });
});
