import { test, expect } from "@playwright/test";

/**
 * Test suite for LayerManagement component
 * 
 * Covers:
 * - Layer visibility toggling
 * - Layer removal
 * - Layer reordering (drag-drop simulation)
 * - Style panel opening/closing
 * - Zoom to layer functionality
 * - Basemap switching
 * - Upload UI presence and validation
 * - File size validation
 */

test.describe("LayerManagement Component", () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to map page
    await page.goto("/map");
    
    // Wait for the map to load
    await page.waitForSelector(".leaflet-container", { timeout: 10000 });
    await page.waitForTimeout(1000);
  });

  test("should display layer management section", async ({ page }) => {
    // Check if the layer management header is present
    const heading = await page.locator("text=Layer Management");
    await expect(heading).toBeVisible();
    
    // Check for upload section
    const uploadSection = await page.locator("text=Upload Data");
    await expect(uploadSection).toBeVisible();
    
    // Check for basemap section
    const basemapSection = await page.locator("text=Basemap");
    await expect(basemapSection).toBeVisible();
  });

  test("should show upload drop area", async ({ page }) => {
    // Check upload drop area is visible
    const dropArea = await page.locator("text=Drag & drop or click to upload GeoJSON files");
    await expect(dropArea).toBeVisible();
    
    // Check file size limit is displayed
    const sizeLimit = await page.locator("text=/Max size: 100.0 MB/");
    await expect(sizeLimit).toBeVisible();
    
    // Check format information
    const formatInfo = await page.locator("text=Format: .geojson only");
    await expect(formatInfo).toBeVisible();
  });

  test("should display basemap selector with options", async ({ page }) => {
    // Find the basemap select element
    const basemapSelect = await page.locator("select");
    await expect(basemapSelect).toBeVisible();
    
    // Check that basemap options are present
    const osmOption = await basemapSelect.locator("option[value='osm']");
    await expect(osmOption).toBeVisible();
    
    const cartoPositronOption = await basemapSelect.locator("option[value='carto-positron']");
    await expect(cartoPositronOption).toBeVisible();
  });

  test("should change basemap when option is selected", async ({ page }) => {
    const basemapSelect = await page.locator("select");
    
    // Change to OSM basemap
    await basemapSelect.selectOption("osm");
    await page.waitForTimeout(500);
    
    // Verify basemap changed by checking tile URLs
    const tileURLs = await page.evaluate(() => {
      const mapElements = document.querySelectorAll(".leaflet-container");
      if (mapElements.length === 0) return [];
      const mapElement: any = mapElements[0];
      const map = (mapElement as any)._leaflet_map;
      if (!map) return [];
      
      const tileLayers: any[] = [];
      map.eachLayer((layer: any) => {
        if (layer._url) {
          tileLayers.push(layer._url);
        }
      });
      return tileLayers;
    });
    
    // OSM tiles should contain openstreetmap.org
    const hasOSMTiles = tileURLs.some(url => url.includes("openstreetmap.org"));
    expect(hasOSMTiles).toBe(true);
  });

  test("should add a layer and display it in the list", async ({ page }) => {
    // Mock GeoJSON data
    await page.route("**/test-layer.geojson", (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          type: "FeatureCollection",
          features: [
            {
              type: "Feature",
              properties: { name: "Test Feature" },
              geometry: {
                type: "Point",
                coordinates: [0, 0],
              },
            },
          ],
        }),
      });
    });

    // Add layer programmatically
    const testLayer = {
      id: "test-layer-1",
      name: "Test Layer 1",
      title: "Test Layer 1",
      data_type: "uploaded",
      data_link: "/test-layer.geojson",
      visible: true,
    };

    await page.evaluate((layer) => {
      const { useLayerStore } = window as any;
      useLayerStore.getState().addLayer(layer);
    }, testLayer);

    await page.waitForTimeout(1000);

    // Check if layer appears in the list
    const layerItem = await page.locator("text=Test Layer 1");
    await expect(layerItem).toBeVisible();
  });

  test("should toggle layer visibility", async ({ page }) => {
    // Mock and add a layer
    await page.route("**/visibility-test.geojson", (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          type: "FeatureCollection",
          features: [
            {
              type: "Feature",
              properties: { name: "Visibility Test" },
              geometry: {
                type: "Point",
                coordinates: [10, 10],
              },
            },
          ],
        }),
      });
    });

    const testLayer = {
      id: "visibility-layer",
      name: "Visibility Test Layer",
      title: "Visibility Test Layer",
      data_type: "uploaded",
      data_link: "/visibility-test.geojson",
      visible: true,
    };

    await page.evaluate((layer) => {
      const { useLayerStore } = window as any;
      useLayerStore.getState().addLayer(layer);
    }, testLayer);

    await page.waitForTimeout(1000);

    // Find the visibility toggle button (Eye icon)
    const visibilityButton = await page.locator("button[title='Toggle Visibility']").first();
    await expect(visibilityButton).toBeVisible();

    // Click to toggle visibility
    await visibilityButton.click();
    await page.waitForTimeout(500);

    // Check if layer visibility changed in store
    const layerState = await page.evaluate(() => {
      const { useLayerStore } = window as any;
      const layers = useLayerStore.getState().layers;
      return layers.find((l: any) => l.id === "visibility-layer");
    });

    expect(layerState.visible).toBe(false);

    // Toggle back
    await visibilityButton.click();
    await page.waitForTimeout(500);

    const layerStateAfter = await page.evaluate(() => {
      const { useLayerStore } = window as any;
      const layers = useLayerStore.getState().layers;
      return layers.find((l: any) => l.id === "visibility-layer");
    });

    expect(layerStateAfter.visible).toBe(true);
  });

  test("should remove a layer when delete button is clicked", async ({ page }) => {
    // Mock and add a layer
    await page.route("**/delete-test.geojson", (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          type: "FeatureCollection",
          features: [],
        }),
      });
    });

    const testLayer = {
      id: "delete-layer",
      name: "Delete Test Layer",
      title: "Delete Test Layer",
      data_type: "uploaded",
      data_link: "/delete-test.geojson",
      visible: true,
    };

    await page.evaluate((layer) => {
      const { useLayerStore } = window as any;
      useLayerStore.getState().addLayer(layer);
    }, testLayer);

    await page.waitForTimeout(1000);

    // Confirm layer is in the list
    const layerItem = await page.locator("text=Delete Test Layer");
    await expect(layerItem).toBeVisible();

    // Find and click the remove button
    const removeButton = await page.locator("button[title='Remove Layer']").first();
    await removeButton.click();
    await page.waitForTimeout(500);

    // Check that layer is removed from the list
    await expect(layerItem).not.toBeVisible();

    // Verify layer is removed from store
    const layersInStore = await page.evaluate(() => {
      const { useLayerStore } = window as any;
      return useLayerStore.getState().layers;
    });

    const deletedLayer = layersInStore.find((l: any) => l.id === "delete-layer");
    expect(deletedLayer).toBeUndefined();
  });

  test("should open and close style panel", async ({ page }) => {
    // Mock and add a layer
    await page.route("**/style-test.geojson", (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          type: "FeatureCollection",
          features: [
            {
              type: "Feature",
              properties: { name: "Style Test" },
              geometry: {
                type: "Polygon",
                coordinates: [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
              },
            },
          ],
        }),
      });
    });

    const testLayer = {
      id: "style-layer",
      name: "Style Test Layer",
      title: "Style Test Layer",
      data_type: "uploaded",
      data_link: "/style-test.geojson",
      visible: true,
    };

    await page.evaluate((layer) => {
      const { useLayerStore } = window as any;
      useLayerStore.getState().addLayer(layer);
    }, testLayer);

    await page.waitForTimeout(1000);

    // Find and click the style button
    const styleButton = await page.locator("button[title='Style Layer']").first();
    await styleButton.click();
    await page.waitForTimeout(500);

    // Check if style panel is visible
    const stylePanel = await page.locator("text=Style Options");
    await expect(stylePanel).toBeVisible();

    // Check if style controls are present
    const strokeColorLabel = await page.locator("text=Stroke Color");
    await expect(strokeColorLabel).toBeVisible();

    const fillColorLabel = await page.locator("text=Fill Color");
    await expect(fillColorLabel).toBeVisible();

    // Close the style panel by clicking the button again
    await styleButton.click();
    await page.waitForTimeout(500);

    // Verify panel is closed
    await expect(stylePanel).not.toBeVisible();
  });

  test("should update stroke color using style panel", async ({ page }) => {
    // Mock and add a layer
    await page.route("**/color-test.geojson", (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          type: "FeatureCollection",
          features: [
            {
              type: "Feature",
              properties: { name: "Color Test" },
              geometry: {
                type: "LineString",
                coordinates: [[0, 0], [1, 1]],
              },
            },
          ],
        }),
      });
    });

    const testLayer = {
      id: "color-layer",
      name: "Color Test Layer",
      title: "Color Test Layer",
      data_type: "uploaded",
      data_link: "/color-test.geojson",
      visible: true,
      style: {
        stroke_color: "#3388ff",
      },
    };

    await page.evaluate((layer) => {
      const { useLayerStore } = window as any;
      useLayerStore.getState().addLayer(layer);
    }, testLayer);

    await page.waitForTimeout(1000);

    // Open style panel
    const styleButton = await page.locator("button[title='Style Layer']").first();
    await styleButton.click();
    await page.waitForTimeout(500);

    // Find stroke color input
    const colorInputs = await page.locator("input[type='color']");
    const strokeColorInput = colorInputs.first();

    // Change color to red
    await strokeColorInput.fill("#ff0000");
    await page.waitForTimeout(500);

    // Verify color changed in store
    const layerAfterColorChange = await page.evaluate(() => {
      const { useLayerStore } = window as any;
      const layers = useLayerStore.getState().layers;
      return layers.find((l: any) => l.id === "color-layer");
    });

    expect(layerAfterColorChange.style.stroke_color).toBe("#ff0000");
  });

  test("should have quick preset buttons in style panel", async ({ page }) => {
    // Mock and add a layer
    await page.route("**/preset-test.geojson", (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          type: "FeatureCollection",
          features: [
            {
              type: "Feature",
              properties: {},
              geometry: {
                type: "Point",
                coordinates: [0, 0],
              },
            },
          ],
        }),
      });
    });

    const testLayer = {
      id: "preset-layer",
      name: "Preset Test Layer",
      title: "Preset Test Layer",
      data_type: "uploaded",
      data_link: "/preset-test.geojson",
      visible: true,
    };

    await page.evaluate((layer) => {
      const { useLayerStore } = window as any;
      useLayerStore.getState().addLayer(layer);
    }, testLayer);

    await page.waitForTimeout(1000);

    // Open style panel
    const styleButton = await page.locator("button[title='Style Layer']").first();
    await styleButton.click();
    await page.waitForTimeout(500);

    // Check for preset buttons
    const redButton = await page.locator("button:has-text('Red')");
    await expect(redButton).toBeVisible();

    const blueButton = await page.locator("button:has-text('Blue')");
    await expect(blueButton).toBeVisible();

    const dashedButton = await page.locator("button:has-text('Dashed')");
    await expect(dashedButton).toBeVisible();
  });

  test("should trigger zoom when zoom button is clicked", async ({ page }) => {
    // Mock and add a layer with specific bounds
    await page.route("**/zoom-test.geojson", (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          type: "FeatureCollection",
          features: [
            {
              type: "Feature",
              properties: { name: "Zoom Test" },
              geometry: {
                type: "Point",
                coordinates: [10, 50], // Specific location
              },
            },
          ],
        }),
      });
    });

    const testLayer = {
      id: "zoom-layer",
      name: "Zoom Test Layer",
      title: "Zoom Test Layer",
      data_type: "uploaded",
      data_link: "/zoom-test.geojson",
      visible: true,
    };

    await page.evaluate((layer) => {
      const { useLayerStore } = window as any;
      useLayerStore.getState().addLayer(layer);
    }, testLayer);

    await page.waitForTimeout(2000);

    // Click the zoom button
    const zoomButton = await page.locator("button[title='Zoom to this layer']").first();
    await zoomButton.click();
    await page.waitForTimeout(1000);

    // Verify that zoomTo was set in the store
    const zoomToState = await page.evaluate(() => {
      const { useLayerStore } = window as any;
      return useLayerStore.getState().zoomTo;
    });

    expect(zoomToState).toBe("zoom-layer");
  });

  test("should display multiple layers in correct order", async ({ page }) => {
    // Add multiple layers
    const layers = [
      {
        id: "layer-1",
        name: "First Layer",
        title: "First Layer",
        data_type: "uploaded",
        data_link: "/layer1.geojson",
        visible: true,
      },
      {
        id: "layer-2",
        name: "Second Layer",
        title: "Second Layer",
        data_type: "uploaded",
        data_link: "/layer2.geojson",
        visible: true,
      },
      {
        id: "layer-3",
        name: "Third Layer",
        title: "Third Layer",
        data_type: "uploaded",
        data_link: "/layer3.geojson",
        visible: true,
      },
    ];

    // Mock routes for all layers
    for (const layer of layers) {
      await page.route(`**/${layer.data_link}`, (route) => {
        route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            type: "FeatureCollection",
            features: [],
          }),
        });
      });
    }

    // Add all layers
    for (const layer of layers) {
      await page.evaluate((l) => {
        const { useLayerStore } = window as any;
        useLayerStore.getState().addLayer(l);
      }, layer);
    }

    await page.waitForTimeout(1000);

    // Check if all layers are visible
    for (const layer of layers) {
      const layerItem = await page.locator(`text=${layer.name}`);
      await expect(layerItem).toBeVisible();
    }

    // Verify layer count in store
    const layerCount = await page.evaluate(() => {
      const { useLayerStore } = window as any;
      return useLayerStore.getState().layers.length;
    });

    expect(layerCount).toBe(3);
  });

  test("should show layer data type information", async ({ page }) => {
    // Mock and add a layer
    await page.route("**/info-test.geojson", (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          type: "FeatureCollection",
          features: [],
        }),
      });
    });

    const testLayer = {
      id: "info-layer",
      name: "Info Test Layer",
      title: "Info Test Layer",
      data_type: "uploaded",
      layer_type: "UPLOADED",
      data_link: "/info-test.geojson",
      visible: true,
    };

    await page.evaluate((layer) => {
      const { useLayerStore } = window as any;
      useLayerStore.getState().addLayer(layer);
    }, testLayer);

    await page.waitForTimeout(1000);

    // Check if data type is displayed
    const dataTypeInfo = await page.locator("text=/uploaded.*UPLOADED/i");
    await expect(dataTypeInfo).toBeVisible();
  });

  test("should show user layers section heading", async ({ page }) => {
    const userLayersHeading = await page.locator("text=User Layers");
    await expect(userLayersHeading).toBeVisible();
  });

  test("should show empty state when no layers are added", async ({ page }) => {
    // Make sure no layers exist
    await page.evaluate(() => {
      const { useLayerStore } = window as any;
      const store = useLayerStore.getState();
      // Clear all layers
      store.layers.forEach((layer: any) => {
        store.removeLayer(layer.id);
      });
    });

    await page.waitForTimeout(500);

    // Check for empty state message
    const emptyMessage = await page.locator("text=No layers added yet.");
    await expect(emptyMessage).toBeVisible();
  });

  test("should have drag handle icon for layer reordering", async ({ page }) => {
    // Mock and add a layer
    await page.route("**/drag-test.geojson", (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          type: "FeatureCollection",
          features: [],
        }),
      });
    });

    const testLayer = {
      id: "drag-layer",
      name: "Drag Test Layer",
      title: "Drag Test Layer",
      data_type: "uploaded",
      data_link: "/drag-test.geojson",
      visible: true,
    };

    await page.evaluate((layer) => {
      const { useLayerStore } = window as any;
      useLayerStore.getState().addLayer(layer);
    }, testLayer);

    await page.waitForTimeout(1000);

    // Check for the grip/drag handle icon (GripVertical component)
    // The icon itself may not have accessible text, so we check for its parent container
    const layerItems = await page.locator("li").filter({ hasText: "Drag Test Layer" });
    await expect(layerItems.first()).toBeVisible();
    
    // Verify the layer has draggable attribute
    const isDraggable = await layerItems.first().locator("div[draggable='true']").count();
    expect(isDraggable).toBeGreaterThan(0);
  });

  test("upload section should not accept invalid file types", async ({ page }) => {
    // This test verifies that the file input has the correct accept attribute
    const fileInput = await page.locator("input[type='file']");
    const acceptAttribute = await fileInput.getAttribute("accept");
    expect(acceptAttribute).toBe(".geojson");
  });

  test("upload section should support multiple files", async ({ page }) => {
    // Verify that the file input has the multiple attribute
    const fileInput = await page.locator("input[type='file']");
    const hasMultiple = await fileInput.getAttribute("multiple");
    expect(hasMultiple).not.toBeNull();
  });
});
