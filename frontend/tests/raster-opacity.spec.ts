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

const wcsLayer = {
  id: "wcs-opacity",
  data_source_id: "t",
  data_type: "LAYER",
  data_origin: "TOOL",
  data_source: "test",
  name: "WCS Opacity",
  title: "WCS Opacity",
  layer_type: "WCS",
  // LeafletMapClient renders WCS as a WMS tile layer on the derived /wms endpoint
  data_link:
    "https://wcs.opacity-test.example/geoserver/wcs?service=WCS&coverageId=cov",
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
    ["WCS", wcsLayer, "wcs.opacity-test.example"],
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

  test("opacity changed while the layer is still being created is persisted", async ({
    page,
  }) => {
    const requests: { method: string; url: string; body: any }[] = [];
    let release!: () => void;
    const gate = new Promise<void>((r) => (release = r));
    await page.route(/\/layers\/?(\?.*)?$|\/layers\/[^/]+$/, async (route) => {
      const req = route.request();
      if (req.method() === "POST") {
        requests.push({
          method: "POST",
          url: req.url(),
          body: JSON.parse(req.postData() || "{}"),
        });
        await gate; // delay creation
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ id: "db-1" }),
        });
      } else if (req.method() === "PATCH") {
        requests.push({
          method: "PATCH",
          url: req.url(),
          body: JSON.parse(req.postData() || "{}"),
        });
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ id: "db-1" }),
        });
      } else {
        await route.fallback();
      }
    });

    await add(page, wmsLayer);
    await expect.poll(() => requests.length).toBe(1);
    await page.getByTitle("Style Layer").first().click();
    await setSlider(page, "0.3");
    await expect.poll(() => storeOpacity(page, wmsLayer.id)).toBeCloseTo(0.3, 5);
    expect(requests.some((r) => r.method === "PATCH")).toBe(false);

    release();
    await expect
      .poll(() => requests.find((r) => r.method === "PATCH")?.body?.style?.raster_opacity)
      .toBeCloseTo(0.3, 5);
    expect(
      requests.find((r) => r.method === "PATCH")!.url,
    ).toContain("/layers/db-1");
    expect(await storeOpacity(page, wmsLayer.id)).toBeCloseTo(0.3, 5);
  });

  test("opacity survives a backend layer update replacing the layer object", async ({
    page,
  }) => {
    await add(page, wmsLayer);
    await page.getByTitle("Style Layer").first().click();
    await setSlider(page, "0.6");
    await page.evaluate((l) => {
      const { style, ...fresh } = l as any;
      (window as any).useLayerStore.getState().updateLayersFromBackend([fresh]);
      (window as any).useLayerStore.getState().synchronizeLayersFromBackend([fresh]);
    }, wmsLayer);
    expect(await storeOpacity(page, wmsLayer.id)).toBeCloseTo(0.6, 5);
    await expect.poll(() => mapOpacity(page, "wms.opacity-test.example")).toBeCloseTo(0.6, 5);
  });

  test("backend sync/update: style keys come from backend, local raster_opacity is retained", async ({
    page,
  }) => {
    await add(page, wmsLayer);
    await page.getByTitle("Style Layer").first().click();
    await setSlider(page, "0.2");
    for (const fn of ["synchronizeLayersFromBackend", "updateLayersFromBackend"]) {
      await page.evaluate(
        ([l, f]) => {
          const stale = { ...(l as any), style: { raster_opacity: 1, fill_color: "#ff0000" } };
          (window as any).useLayerStore.getState()[f as string]([stale]);
        },
        [wmsLayer, fn] as const,
      );
      expect(await storeOpacity(page, wmsLayer.id)).toBeCloseTo(0.2, 5);
      expect(
        await page.evaluate(
          () => (window as any).useLayerStore.getState().layers[0].style.fill_color,
        ),
      ).toBe("#ff0000");
      await page.evaluate(() =>
        (window as any).useLayerStore.getState().updateLayerStyle("wms-opacity", { fill_color: "#000000" }),
      );
    }
  });

  test("many slider changes before POST resolves produce one catch-up PATCH with the latest value", async ({
    page,
  }) => {
    const calls: { method: string; opacity?: number }[] = [];
    let release!: () => void;
    const gate = new Promise<void>((r) => (release = r));
    await page.route(/\/layers\/?(\?.*)?$|\/layers\/[^/]+$/, async (route) => {
      const req = route.request();
      const m = req.method();
      if (m !== "POST" && m !== "PATCH") return route.fallback();
      const body = JSON.parse(req.postData() || "{}");
      calls.push({ method: m, opacity: body?.style?.raster_opacity });
      if (m === "POST") await gate;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ id: "db-2" }),
      });
    });

    await add(page, wmsLayer);
    await expect.poll(() => calls.length).toBe(1);
    await page.getByTitle("Style Layer").first().click();
    for (const v of ["0.8", "0.6", "0.4", "0.25"]) await setSlider(page, v);
    release();
    await expect.poll(() => calls.filter((c) => c.method === "PATCH").length).toBe(1);
    // A later db_id-based change is the final write and must not be overwritten
    await setSlider(page, "0.9");
    await expect
      .poll(() => calls.filter((c) => c.method === "PATCH").length)
      .toBe(2);
    await page.waitForTimeout(500);
    const patches = calls.filter((c) => c.method === "PATCH");
    expect(patches).toHaveLength(2);
    expect(patches[0].opacity).toBeCloseTo(0.25, 5);
    expect(patches[1].opacity).toBeCloseTo(0.9, 5);
  });

  async function streamResult(page: Page, result: any) {
    await page.route("**/chat/stream", (route) =>
      route.fulfill({
        status: 200,
        headers: { "Content-Type": "text/event-stream", "Cache-Control": "no-cache" },
        body:
          `event: result\ndata: ${JSON.stringify(result)}\n\n` +
          `event: done\ndata: ${JSON.stringify({ status: "complete" })}\n\n`,
      }),
    );
  }

  async function sendChat(page: Page, text: string) {
    const input = page.getByPlaceholder(
      "Ask about maps, search for data, or request analysis...",
    );
    await input.fill(text);
    await input.press("Enter");
  }

  test("streamed result (real payload shape, no tool messages): fill color updates, local raster_opacity retained", async ({
    page,
  }) => {
    await add(page, wmsLayer);
    await page.getByTitle("Style Layer").first().click();
    await setSlider(page, "0.3");
    // Backend only serializes human/ai/system messages and echoes the stale snapshot
    await streamResult(page, {
      messages: [
        { type: "human", content: "color it red" },
        { type: "ai", content: "Styled the layer" },
      ],
      geodata_results: [],
      geodata_layers: [
        { ...wmsLayer, style: { raster_opacity: 1, fill_color: "#ff0000" } },
      ],
    });
    await sendChat(page, "color it red");
    await expect(page.getByText("Styled the layer")).toBeVisible();
    expect(
      await page.evaluate(
        () => (window as any).useLayerStore.getState().layers[0].style.fill_color,
      ),
    ).toBe("#ff0000");
    expect(await storeOpacity(page, wmsLayer.id)).toBeCloseTo(0.3, 5);
    await expect
      .poll(() => mapOpacity(page, "wms.opacity-test.example"))
      .toBeCloseTo(0.3, 5);
  });

  test("catch-up PATCH is serialized with later opacity writes (final state = latest)", async ({
    page,
  }) => {
    const arrivals: { method: string; opacity?: number }[] = [];
    let releasePost!: () => void;
    let releasePatch1!: () => void;
    const postGate = new Promise<void>((r) => (releasePost = r));
    const patch1Gate = new Promise<void>((r) => (releasePatch1 = r));
    let patchCount = 0;
    await page.route(/\/layers\/?(\?.*)?$|\/layers\/[^/]+$/, async (route) => {
      const req = route.request();
      const m = req.method();
      if (m !== "POST" && m !== "PATCH") return route.fallback();
      const body = JSON.parse(req.postData() || "{}");
      arrivals.push({ method: m, opacity: body?.style?.raster_opacity });
      if (m === "POST") await postGate;
      if (m === "PATCH" && ++patchCount === 1) await patch1Gate;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ id: "db-3" }),
      });
    });

    await add(page, wmsLayer);
    await expect.poll(() => arrivals.length).toBe(1);
    await page.getByTitle("Style Layer").first().click();
    await setSlider(page, "0.4");
    releasePost();
    // Catch-up PATCH (0.4) is now held in flight
    await expect.poll(() => arrivals.filter((a) => a.method === "PATCH").length).toBe(1);
    await setSlider(page, "0.7"); // db_id-based write while catch-up in flight
    await page.waitForTimeout(400);
    // Serialized: the newer write must not reach the server before the older one finished
    expect(arrivals.filter((a) => a.method === "PATCH")).toHaveLength(1);
    releasePatch1();
    await expect.poll(() => arrivals.filter((a) => a.method === "PATCH").length).toBe(2);
    const patches = arrivals.filter((a) => a.method === "PATCH");
    expect(patches[0].opacity).toBeCloseTo(0.4, 5);
    expect(patches[1].opacity).toBeCloseTo(0.7, 5);
    await page.waitForTimeout(300);
    expect(arrivals.filter((a) => a.method === "PATCH")).toHaveLength(2);
  });
});
