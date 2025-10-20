import { test, expect } from "@playwright/test";

/**
 * Test suite for bounding_box crash fix in LayerList component
 * 
 * This tests the fix for the issue where clicking the info button on layers 
 * with object-based bounding_box (e.g., from geocoded results) caused a crash.
 * 
 * Background:
 * - bounding_box can be either an array (GeoJSON/WFS layers) or an object (geocoded layers)
 * - Original code assumed array format and called .join()
 * - This caused TypeError when bounding_box was an object
 * 
 * Fix:
 * - Added type guard: Array.isArray(layer.bounding_box)
 * - Arrays: use .join(', ')
 * - Objects: use JSON.stringify()
 */

test.describe("LayerList - Bounding Box Info Crash Fix", () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to map page and wait for it to load
    await page.goto("/map");
    await page.waitForSelector(".leaflet-container", { timeout: 10000 });
    await page.waitForTimeout(1000);
  });

  test("should not crash when opening info popup for layer with array bounding_box", async ({ page }) => {
    // Mock GeoJSON endpoint
    await page.route("**/test-array.geojson", (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          type: "FeatureCollection",
          features: [],
        }),
      });
    });

    // Add layer with array bounding_box (typical for GeoJSON/WFS layers)
    const testLayer = {
      id: "array-bbox-layer",
      name: "Test Array BBox",
      title: "Test Array BBox",
      layer_type: "GEOJSON",
      data_link: "/test-array.geojson",
      visible: true,
      bounding_box: [25.1, 55.2, 25.3, 55.4], // [minLat, minLon, maxLat, maxLon]
    };

    await page.evaluate((layer) => {
      const { useLayerStore } = window as any;
      useLayerStore.getState().addLayer(layer);
    }, testLayer);

    await page.waitForTimeout(1000);

    // Wait for layer title to be visible
    const layerTitle = page.getByText("Test Array BBox", { exact: true });
    await expect(layerTitle).toHaveCount(1);

    // Find and click the info button (using title attribute)
    const infoButton = page.locator('[title="View layer metadata"]').first();
    await infoButton.click();

    await page.waitForTimeout(300);

    // Verify metadata popup is visible (check for "Bounding Box:" label)
    const boundingBoxSection = page.locator('text=/Bounding Box:/');
    await expect(boundingBoxSection).toBeVisible();
    
    // Should contain the array values as comma-separated string
    const boundingBoxText = page.locator('text=/25.1.*55.2.*25.3.*55.4/');
    await expect(boundingBoxText).toBeVisible();
  });

  test("should not crash when opening info popup for layer with object bounding_box", async ({ page }) => {
    // Mock GeoJSON endpoint
    await page.route("**/test-object.geojson", (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          type: "FeatureCollection",
          features: [],
        }),
      });
    });

    // Add layer with object bounding_box (typical for geocoded layers)
    const testLayer = {
      id: "object-bbox-layer",
      name: "Test Object BBox",
      title: "Test Object BBox",
      layer_type: "GEOCODE",
      data_link: "/test-object.geojson",
      visible: true,
      bounding_box: {
        minLat: 25.1,
        maxLat: 25.3,
        minLon: 55.2,
        maxLon: 55.4
      },
    };

    await page.evaluate((layer) => {
      const { useLayerStore } = window as any;
      useLayerStore.getState().addLayer(layer);
    }, testLayer);

    await page.waitForTimeout(1000);

    const layerTitle = page.getByText("Test Object BBox", { exact: true });
    await expect(layerTitle).toHaveCount(1);

    const infoButton = page.locator('[title="View layer metadata"]').first();
    await infoButton.click();

    await page.waitForTimeout(300);

    // Verify metadata popup appeared without crashing (check for "Bounding Box:" label)
    const boundingBoxSection = page.locator('text=/Bounding Box:/');
    await expect(boundingBoxSection).toBeVisible();
    
    // Should contain the object properties
    const boundingBoxText = page.locator('text=/minLat|maxLat|minLon|maxLon/');
    await expect(boundingBoxText).toBeVisible();
  });

  test("should handle layer without bounding_box gracefully", async ({ page }) => {
    // Mock GeoJSON endpoint
    await page.route("**/test-nobbox.geojson", (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          type: "FeatureCollection",
          features: [],
        }),
      });
    });

    // Add layer without bounding_box
    const testLayer = {
      id: "no-bbox-layer",
      name: "No BBox Layer",
      title: "No BBox Layer",
      layer_type: "GEOJSON",
      data_link: "/test-nobbox.geojson",
      visible: true,
      // No bounding_box property
    };

    await page.evaluate((layer) => {
      const { useLayerStore } = window as any;
      useLayerStore.getState().addLayer(layer);
    }, testLayer);

    await page.waitForTimeout(1000);

    const layerTitle = page.getByText("No BBox Layer", { exact: true });
    await expect(layerTitle).toHaveCount(1);

    const infoButton = page.locator('[title="View layer metadata"]').first();
    await infoButton.click();

    await page.waitForTimeout(300);

    // Verify metadata popup appeared without crashing (check for "Title:" which is always shown)
    const titleSection = page.locator('text=/Title:/');
    await expect(titleSection).toBeVisible();

    // Bounding box section should not be present since layer has no bbox
    const boundingBoxSection = page.locator('text=/Bounding Box:/');
    const count = await boundingBoxSection.count();
    expect(count).toBe(0); // Should not be present
  });
});
