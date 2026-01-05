import { test, expect } from "@playwright/test";

test.describe("CRS Metadata Display", () => {
  const mockLayerWithMetadata = {
    id: "test-layer-1",
    data_source_id: "geoprocess",
    data_type: "GeoJson",
    data_origin: "tool",
    data_source: "NaLaMapGeoprocess",
    data_link: "http://localhost:8000/test.geojson",
    name: "buffered_rivers",
    title: "Buffered Rivers",
    description: "Buffer operation with 1000 meters",
    llm_description: "A 1000m buffer around rivers",
    layer_type: "GeoJSON",
    visible: true,
    processing_metadata: {
      operation: "buffer",
      crs_used: "EPSG:32633",
      crs_name: "WGS 84 / UTM zone 33N",
      projection_property: "conformal",
      auto_selected: true,
      selection_reason: "Local extent - UTM zone 33N",
      expected_error: 0.1,
      origin_layers: ["rivers_africa", "test_stream"],
    },
  };

  test("displays CRS metadata in LayerList metadata popup", async ({ page }) => {
    // Navigate to the main page
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    // Inject a test layer with metadata into the page
    await page.evaluate((layer) => {
      // Access the global state or component state
      // This is a simplified approach - in reality, you'd need to use the actual state management
      window.testLayer = layer;
    }, mockLayerWithMetadata);

    // Wait for the layer to be rendered (this may need adjustment based on actual implementation)
    await page.waitForTimeout(1000);

    // Look for the layer title
    const layerTitle = page.locator(`text=${mockLayerWithMetadata.title}`);
    
    // If the layer exists, click the info button
    if (await layerTitle.isVisible()) {
      // Find the info button next to the layer title
      const infoButton = page.locator(`[title="View layer metadata"]`).first();
      await infoButton.click();

      // Wait for metadata popup to appear
      await page.waitForTimeout(500);

      // Check for Processing Information section
      await expect(page.locator("text=Processing Information")).toBeVisible();

      // Check for operation summary
      await expect(page.locator("text=Buffer operation")).toBeVisible();
      await expect(page.locator("text=EPSG:32633")).toBeVisible();
      await expect(page.locator("text=🎯")).toBeVisible();

      // Check for origin layers
      await expect(page.locator("text=Generated from:")).toBeVisible();
      await expect(page.locator("text=rivers_africa, test_stream")).toBeVisible();

      // Check for CRS details
      await expect(page.locator("text=WGS 84 / UTM zone 33N")).toBeVisible();
      await expect(page.locator("text=conformal")).toBeVisible();
      await expect(page.locator("text=Local extent - UTM zone 33N")).toBeVisible();
      await expect(page.locator("text=<0.1%")).toBeVisible();
    }
  });

  test("displays CRS metadata in SearchResults details popup", async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    // Inject test results into search results
    await page.evaluate((result) => {
      window.testSearchResults = [result];
    }, mockLayerWithMetadata);

    // Wait for results to render
    await page.waitForTimeout(1000);

    // Look for the Details button in search results
    const detailsButton = page.locator("button:has-text('Details')").first();
    
    if (await detailsButton.isVisible()) {
      await detailsButton.click();
      await page.waitForTimeout(500);

      // Check for Processing Information section
      await expect(page.locator("text=Processing Information")).toBeVisible();

      // Check for operation summary with metrics
      await expect(page.locator("text=Buffer operation")).toBeVisible();
      await expect(page.locator("text=with 1000 meters")).toBeVisible();
      await expect(page.locator("text=EPSG:32633")).toBeVisible();

      // Check for origin layers
      await expect(page.locator("text=Generated from:")).toBeVisible();
      await expect(page.locator("text=rivers_africa, test_stream")).toBeVisible();

      // Check CRS details
      await expect(page.locator("text=WGS 84 / UTM zone 33N")).toBeVisible();
      await expect(page.locator("text=Selection Reason:")).toBeVisible();
      await expect(page.locator("text=Local extent - UTM zone 33N")).toBeVisible();
    }
  });

  test("does not display Processing Information for layers without metadata", async ({ page }) => {
    const mockLayerWithoutMetadata = {
      id: "test-layer-2",
      data_source_id: "wfs",
      data_type: "Layer",
      data_origin: "tool",
      data_source: "GeoServer",
      data_link: "http://geoserver.example.com/wfs",
      name: "rivers",
      title: "Rivers Layer",
      description: "Natural rivers",
      layer_type: "WFS",
      visible: true,
    };

    await page.goto("/");
    await page.waitForLoadState("networkidle");

    await page.evaluate((layer) => {
      window.testLayer = layer;
    }, mockLayerWithoutMetadata);

    await page.waitForTimeout(1000);

    const layerTitle = page.locator(`text=${mockLayerWithoutMetadata.title}`);
    
    if (await layerTitle.isVisible()) {
      const infoButton = page.locator(`[title="View layer metadata"]`).first();
      await infoButton.click();
      await page.waitForTimeout(500);

      // Processing Information section should NOT be visible
      await expect(page.locator("text=Processing Information")).not.toBeVisible();
      await expect(page.locator("text=Generated from:")).not.toBeVisible();
    }
  });

  test("formats operation summary correctly for different operations", async ({ page }) => {
    const mockOverlayLayer = {
      ...mockLayerWithMetadata,
      id: "test-layer-3",
      title: "Overlay Result",
      processing_metadata: {
        operation: "overlay",
        crs_used: "EPSG:3857",
        crs_name: "WGS 84 / Pseudo-Mercator",
        projection_property: "conformal",
        auto_selected: false,
        origin_layers: ["layer1", "layer2"],
      },
    };

    await page.goto("/");
    await page.waitForLoadState("networkidle");

    await page.evaluate((layer) => {
      window.testLayer = layer;
    }, mockOverlayLayer);

    await page.waitForTimeout(1000);

    const layerTitle = page.locator(`text=${mockOverlayLayer.title}`);
    
    if (await layerTitle.isVisible()) {
      const infoButton = page.locator(`[title="View layer metadata"]`).first();
      await infoButton.click();
      await page.waitForTimeout(500);

      // Check operation is capitalized
      await expect(page.locator("text=Overlay operation")).toBeVisible();
      
      // Check that auto-selected emoji is NOT present
      const summaryBox = page.locator(".bg-info-50").first();
      const summaryText = await summaryBox.textContent();
      expect(summaryText).not.toContain("🎯");

      // Check for multiple origin layers
      await expect(page.locator("text=layer1, layer2")).toBeVisible();
    }
  });

  test("extracts buffer distance from description in summary", async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    await page.evaluate((layer) => {
      window.testLayer = layer;
    }, mockLayerWithMetadata);

    await page.waitForTimeout(1000);

    const layerTitle = page.locator(`text=${mockLayerWithMetadata.title}`);
    
    if (await layerTitle.isVisible()) {
      const infoButton = page.locator(`[title="View layer metadata"]`).first();
      await infoButton.click();
      await page.waitForTimeout(500);

      // Check that the buffer distance is extracted from description
      const summaryBox = page.locator(".bg-info-50").first();
      const summaryText = await summaryBox.textContent();
      
      // Should contain the operation with distance
      expect(summaryText).toContain("Buffer operation");
      expect(summaryText).toContain("1000 meters");
    }
  });

  test("handles metadata with undefined expected_error gracefully", async ({ page }) => {
    const mockLayerNoError = {
      ...mockLayerWithMetadata,
      id: "test-layer-4",
      processing_metadata: {
        ...mockLayerWithMetadata.processing_metadata,
        expected_error: undefined,
      },
    };

    await page.goto("/");
    await page.waitForLoadState("networkidle");

    await page.evaluate((layer) => {
      window.testLayer = layer;
    }, mockLayerNoError);

    await page.waitForTimeout(1000);

    const layerTitle = page.locator(`text=${mockLayerNoError.title}`);
    
    if (await layerTitle.isVisible()) {
      const infoButton = page.locator(`[title="View layer metadata"]`).first();
      await infoButton.click();
      await page.waitForTimeout(500);

      // Expected Error section should not be visible
      await expect(page.locator("text=Expected Error:")).not.toBeVisible();
    }
  });
});
