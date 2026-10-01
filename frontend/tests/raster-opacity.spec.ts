import { test, expect, Page } from "@playwright/test";

/**
 * Raster (WMS/WMTS) layer opacity slider:
 * store update, propagation to the Leaflet tile layer container, retention
 * across visibility toggles, and absence on vector layers.
 */

// 1x1 transparent PNG
const PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==",
  "base64",
);

const wmsLayer = {
  id: "wms-opacity",
  data_source_id: "t",
  data_type: "LAYER",
  data_origin: "TOOL",
  data_source: "test",
  name: "WMS Opacity",
  title: "WMS Opacity",
  layer_type: "WMS",
  data_link:
    "https://wms.opacity-test.example/wms?service=WMS&layers=foo&format=image/png&transparent=true",
  visible: true,
};

const wmtsLayer = {
  id: "wmts-opacity",
  data_source_id: "t",
  data_type: "LAYER",
  data_origin: "TOOL",
  data_source: "test",
  name: "WMTS Opacity",
  title: "WMTS Opacity",
  layer_type: "WMTS",
  data_link:
    "https://wmts.opacity-test.example/wmts?service=WMTS&request=GetTile&layer=bar",
  properties: { tile_matrix_sets: "" as any },
  visible: true,
};

const vectorLayer = {
  id: "vec-opacity",
  data_source_id: "t",
  data_type: "LAYER",
  data_origin: "TOOL",
  data_source: "test",
  name: "Vector",
  title: "Vector",
  layer_type: "UPLOADED",
  data_link: "/vec-opacity.geojson",
  visible: true,
};

async function storeOpacity(page: Page, id: string) {
  return page.evaluate(
    (layerId) =>
      (window as any).useLayerStore
        .getState()
        .layers.find((l: any) => l.id === layerId)?.style?.raster_opacity,
    id,
  );
}

/** Opacity of the Leaflet tile layer container that holds tiles from `host`. */
async function mapOpacity(page: Page, host: string): Promise<number | null> {
  return page.evaluate((h) => {
    const img = Array.from(
      document.querySelectorAll<HTMLImageElement>(".leaflet-layer img"),
    ).find((i) => i.src.includes(h));
    const container = img?.closest(".leaflet-layer") as HTMLElement | null;
    return container ? parseFloat(container.style.opacity || "1") : null;
  }, host);
}

test.describe("Raster layer opacity slider", () => {
  test.beforeEach(async ({ page }) => {
    await page.route(/opacity-test\.example/, (route) =>
      route.fulfill({ status: 200, contentType: "image/png", body: PNG }),
    );
    await page.route("**/vec-opacity.geojson", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          type: "FeatureCollection",
          features: [
            {
              type: "Feature",
              properties: {},
              geometry: { type: "Point", coordinates: [0, 0] },
            },
          ],
        }),
      }),
    );
    await page.goto("/map");
    await page.waitForSelector(".leaflet-container", { timeout: 15000 });
    await page.waitForFunction(() => !!(window as any).useLayerStore);
    await page.evaluate(() => (window as any).useLayerStore.getState().resetLayers?.());
  });

  async function add(page: Page, layer: any) {
    await page.evaluate((l) => (window as any).useLayerStore.getState().addLayer(l), layer);
  }

  async function setSlider(page: Page, value: string) {
    const slider = page.locator('input[type="range"][max="1"]').first();
    await expect(slider).toBeVisible();
    await slider.evaluate((el: HTMLInputElement, v) => {
      const setter = Object.getOwnPropertyDescriptor(
        HTMLInputElement.prototype,
        "value",
      )!.set!;
      setter.call(el, v);
      el.dispatchEvent(new Event("input", { bubbles: true }));
    }, value);
  }

  for (const [label, layer, host] of [
    ["WMS", wmsLayer, "wms.opacity-test.example"],
    ["WMTS", wmtsLayer, "wmts.opacity-test.example"],
  ] as const) {
    test(`${label}: slider defaults to 100% and updates store + map and survives visibility toggle`, async ({
      page,
    }) => {
      await add(page, layer);
      await page.getByTitle("Style Layer").first().click();

      const slider = page.locator('input[type="range"][max="1"]').first();
      await expect(slider).toHaveValue("1");
      await expect(page.getByText("100%")).toBeVisible();
      await expect.poll(() => mapOpacity(page, host)).toBe(1);

      await setSlider(page, "0.4");
      await expect.poll(() => storeOpacity(page, layer.id)).toBeCloseTo(0.4, 5);
      await expect(page.getByText("40%")).toBeVisible();
      await expect.poll(() => mapOpacity(page, host)).toBeCloseTo(0.4, 5);

      // Bounds: min 0 and max 1
      await expect(slider).toHaveAttribute("min", "0");
      await expect(slider).toHaveAttribute("max", "1");
      await setSlider(page, "0");
      await expect.poll(() => storeOpacity(page, layer.id)).toBe(0);
      await expect.poll(() => mapOpacity(page, host)).toBe(0);
      await setSlider(page, "5"); // browser clamps to max
      await expect.poll(() => storeOpacity(page, layer.id)).toBe(1);
      await setSlider(page, "0.4");
      await expect.poll(() => storeOpacity(page, layer.id)).toBeCloseTo(0.4, 5);

      // Hide then show: opacity retained in store, slider and map
      await page.getByTitle("Toggle Visibility").first().click();
      await expect.poll(() => mapOpacity(page, host)).toBeNull();
      expect(await storeOpacity(page, layer.id)).toBeCloseTo(0.4, 5);
      await page.getByTitle("Toggle Visibility").first().click();
      await expect.poll(() => mapOpacity(page, host)).toBeCloseTo(0.4, 5);
      expect(await storeOpacity(page, layer.id)).toBeCloseTo(0.4, 5);
      await expect(slider).toHaveValue("0.4");
    });
  }

  test("vector layers do not show the raster opacity slider", async ({ page }) => {
    await add(page, vectorLayer);
    await page.getByTitle("Style Layer").first().click();
    await expect(page.getByText("Style Options")).toBeVisible();
    await expect(page.getByText("Opacity", { exact: true })).toHaveCount(0);
    await expect(page.getByText("Stroke Opacity")).toBeVisible();
    await expect(page.getByText("Stroke Weight")).toBeVisible();
  });
});
