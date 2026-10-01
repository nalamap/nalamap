import { test, expect } from "@playwright/test";
import * as fs from "fs";

const mockSettings = {
  system_prompt: "You are a helpful assistant.",
  tool_options: {
    search: { default_prompt: "Search prompt", settings: {} },
  },
  example_geoserver_backends: [],
  example_mcp_servers: [],
  model_options: {
    MockProvider: [{ name: "mock-model", max_tokens: 999 }],
  },
  session_id: "test-session-ogcapi",
};

const BACKEND_URL = "https://ogcapi.example.com/v1";

test.describe("OGC API backend settings", () => {
  test.beforeEach(async ({ page }) => {
    await page.route("**/settings/options", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockSettings),
      });
    });
  });

  async function addBackend(page: import("@playwright/test").Page) {
    await page.goto("/settings");
    await page.waitForLoadState("networkidle");
    const header = page.locator("button:has-text('OGC API Backends')");
    await header.scrollIntoViewIfNeeded();
    await header.click();
    await page.getByPlaceholder(/OGC API base URL/).fill(BACKEND_URL);
    await page.getByPlaceholder("Name (required)").fill("Example OGC");
    await page.getByRole("button", { name: "Add OGC API Backend" }).click();
    await expect(page.getByText(BACKEND_URL)).toBeVisible();
  }

  const getBackends = (page: import("@playwright/test").Page) =>
    page.evaluate(
      () => (window as any).useSettingsStore.getState().ogcapi_backends,
    );

  test("add, toggle and remove a backend", async ({ page }) => {
    await addBackend(page);
    expect(await getBackends(page)).toEqual([
      expect.objectContaining({
        url: BACKEND_URL,
        name: "Example OGC",
        enabled: true,
      }),
    ]);

    await page.getByLabel("Enabled").uncheck();
    expect((await getBackends(page))[0].enabled).toBe(false);

    await page.getByLabel(/Allow insecure SSL/).check();
    expect((await getBackends(page))[0].allow_insecure).toBe(true);

    await page.getByRole("button", { name: "Remove" }).click();
    await expect(page.getByText("No OGC API backends configured.")).toBeVisible();
    expect(await getBackends(page)).toEqual([]);
  });

  test("export keeps and import restores the backend", async ({ page }) => {
    await addBackend(page);

    const downloadPromise = page.waitForEvent("download");
    await page.getByRole("button", { name: "Export Settings" }).click();
    const download = await downloadPromise;
    const exportPath = await download.path();
    const exported = JSON.parse(fs.readFileSync(exportPath!, "utf-8"));
    expect(exported.ogcapi_backends).toEqual([
      expect.objectContaining({ url: BACKEND_URL, name: "Example OGC" }),
    ]);

    // Remove, then import the exported file and expect it back.
    await page.getByRole("button", { name: "Remove" }).click();
    expect(await getBackends(page)).toEqual([]);

    await page.locator('input[type="file"]').setInputFiles({
      name: "settings.json",
      mimeType: "application/json",
      buffer: Buffer.from(JSON.stringify(exported)),
    });
    await expect
      .poll(async () => (await getBackends(page)).length)
      .toBe(1);
    expect((await getBackends(page))[0].url).toBe(BACKEND_URL);
  });

  test("backend is included in the chat settings snapshot", async ({ page }) => {
    await addBackend(page);

    let requestBody: any = null;
    await page.route("**/chat/stream", async (route) => {
      requestBody = JSON.parse(route.request().postData() || "{}");
      await route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        body: `event: result\ndata: ${JSON.stringify({
          messages: [{ type: "ai", content: "ok" }],
          geodata_results: [],
          geodata_layers: [],
        })}\n\nevent: done\ndata: {"status":"complete"}\n\n`,
      });
    });

    // Client-side navigation keeps the in-memory settings store.
    await page.locator('a[href="/map"]:visible').first().click();
    const chatInput = page.getByPlaceholder(
      "Ask about maps, search for data, or request analysis...",
    );
    await chatInput.fill("find rivers");
    await chatInput.press("Enter");

    await expect.poll(() => requestBody).not.toBeNull();
    expect(requestBody.options.ogcapi_backends).toEqual([
      expect.objectContaining({ url: BACKEND_URL, name: "Example OGC", enabled: true }),
    ]);
  });
});
