import { test, expect } from "@playwright/test";

const mockSettings = {
  system_prompt: "You are a helpful assistant.",
  tool_options: {
    search: {
      default_prompt: "Search prompt",
      settings: {},
    },
  },
  example_geoserver_backends: [
    {
      url: "https://geoserver.mapx.org/geoserver/",
      name: "MapX",
      description: "Test GeoServer",
    },
  ],
  model_options: {
    MockProvider: [{ name: "mock-model", max_tokens: 999 }],
  },
  session_id: "test-session-123",
};

test.describe("Settings page", () => {
  test("initializes settings from backend options", async ({ page }) => {
    await page.route("**/settings/options", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockSettings),
      });
    });

    await page.goto("/settings");
    await page.waitForLoadState("networkidle");

    await expect(
      page.getByRole("heading", { level: 1, name: "Settings" }),
    ).toBeVisible();

    // Expand Model Settings component first
    const modelSettingsButton = page.locator("button:has-text('Model Settings')");
    await modelSettingsButton.scrollIntoViewIfNeeded();
    await expect(modelSettingsButton).toBeVisible();
    await modelSettingsButton.click();

    // Wait for the section to expand
    await page.waitForTimeout(500);

    const providerSelect = page.locator("main select").first();
    await expect(providerSelect).toBeVisible({ timeout: 5000 });
    await expect(providerSelect).toContainText("MockProvider");
    await expect(providerSelect).toHaveValue("MockProvider");

    const modelSelect = page.locator("main select").nth(1);
    await expect(modelSelect).toContainText("mock-model");
    await expect(modelSelect).toHaveValue("mock-model");

    const maxTokensInput = page.locator('main input[type="number"]').first();
    await expect(maxTokensInput).toHaveValue("999");
  });

  test("example GeoServer shows loading bar and state when added", async ({
    page,
  }) => {
    // Mock settings with example GeoServers
    await page.route("**/settings/options", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockSettings),
      });
    });

    // Mock the preload endpoint
    await page.route("**/settings/geoserver/preload", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          session_id: "test-session-123",
          backend_url: "https://geoserver.mapx.org/geoserver",
          backend_name: "MapX",
          total_layers: 10,
          service_status: {},
          service_counts: {},
        }),
      });
    });

    // Mock the embedding-status endpoint to return waiting state
    let callCount = 0;
    await page.route("**/settings/geoserver/embedding-status*", async (route) => {
      const url = new URL(route.request().url());
      const backendUrls = url.searchParams.get("backend_urls")?.split(",") || [];

      callCount++;
      const backends: Record<string, any> = {};

      for (const backendUrl of backendUrls) {
        if (callCount === 1) {
          // First call: waiting state
          backends[backendUrl] = {
            total: 10,
            encoded: 0,
            percentage: 0,
            state: "waiting",
            in_progress: false,
            complete: false,
            error: null,
          };
        } else if (callCount === 2) {
          // Second call: processing state
          backends[backendUrl] = {
            total: 10,
            encoded: 5,
            percentage: 50,
            state: "processing",
            in_progress: true,
            complete: false,
            error: null,
          };
        } else {
          // Third call: completed state
          backends[backendUrl] = {
            total: 10,
            encoded: 10,
            percentage: 100,
            state: "completed",
            in_progress: false,
            complete: true,
            error: null,
          };
        }
      }

      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ session_id: "test-session-123", backends }),
      });
    });

    await page.goto("/settings");
    await page.waitForLoadState("networkidle");

    // Expand GeoServer Backends component first
    const geoserverButton = page.locator("button:has-text('GeoServer Backends')");
    await geoserverButton.scrollIntoViewIfNeeded();
    await expect(geoserverButton).toBeVisible();
    await geoserverButton.click();

    // Wait for the section to expand
    await page.waitForTimeout(500);

    // Find the Example GeoServers section within the expanded component
    const exampleSection = page.locator("h3:has-text('Example GeoServers')");
    await expect(exampleSection).toBeVisible({ timeout: 5000 });

    // Select MapX from the dropdown
    const dropdown = page.locator("select").filter({ hasText: "Select an example GeoServer" });
    await dropdown.selectOption("https://geoserver.mapx.org/geoserver/");

    // Click the "Add Example GeoServer" button
    await page.getByRole("button", { name: /Add Example GeoServer/i }).click();

    // Wait for the backend to be added to the list
    // The added backend should appear in the GeoServer Backends list
    const addedBackend = page.locator("li:has-text('MapX')");
    await expect(addedBackend).toBeVisible({ timeout: 5000 });

    // Check that the loading bar and state are visible
    // Should show "⏱️ Waiting to start" initially
    await expect(addedBackend.locator("text=/⏱️ Waiting to start/")).toBeVisible({
      timeout: 3000,
    });

    // Check that progress bar exists
    const progressBar = addedBackend.locator("div.bg-primary-200");
    await expect(progressBar).toBeVisible();

    // Check that the progress bar shows some width (should be 5% for waiting state)
    const progressFill = progressBar.locator("div.h-full");
    await expect(progressFill).toBeVisible();

    // Wait for processing state (polling interval is 10 seconds, so wait at least 12 seconds)
    await expect(addedBackend.locator("text=/⏳ Embedding in progress/")).toBeVisible({
      timeout: 15000,
    });

    // Check that the progress section shows layers count (e.g., "5 / 10 layers")
    await expect(addedBackend.locator("text=/\/ 10 layers/")).toBeVisible({ timeout: 3000 });

    // Wait for completion (another polling cycle)
    await expect(addedBackend.locator("text=/✓ Embedding complete/")).toBeVisible({
      timeout: 15000,
    });
  });

  test("preconfigured geoserver backends are auto-added and shown in dropdown", async ({
    page,
  }) => {
    // Mock settings with preconfigured GeoServers (from deployment config)
    const settingsWithPreconfigured = {
      ...mockSettings,
      preconfigured_geoserver_backends: [
        {
          url: "https://preconfigured.geoserver.org/geoserver/",
          name: "Preconfigured GeoServer",
          description: "Auto-added from deployment config",
        },
      ],
      deployment_config_name: "Test Deployment",
    };

    await page.route("**/settings/options", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(settingsWithPreconfigured),
      });
    });

    // Mock the preload endpoint
    await page.route("**/settings/geoserver/preload", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          session_id: "test-session-123",
          backend_url: "https://preconfigured.geoserver.org/geoserver/",
          backend_name: "Preconfigured GeoServer",
          total_layers: 5,
          service_status: {},
          service_counts: {},
        }),
      });
    });

    // Mock embedding status
    await page.route("**/settings/geoserver/embedding-status*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          session_id: "test-session-123",
          backends: {},
        }),
      });
    });

    await page.goto("/settings");
    await page.waitForLoadState("networkidle");

    // Expand GeoServer Backends component
    const geoserverButton = page.locator("button:has-text('GeoServer Backends')");
    await geoserverButton.scrollIntoViewIfNeeded();
    await expect(geoserverButton).toBeVisible();
    await geoserverButton.click();
    await page.waitForTimeout(500);

    // The preconfigured backend should be auto-added to the list
    const autoAddedBackend = page.locator("li:has-text('Preconfigured GeoServer')");
    await expect(autoAddedBackend).toBeVisible({ timeout: 5000 });

    // The preconfigured backend should also appear in the example dropdown
    const dropdown = page.locator("select").filter({ hasText: /Select an example GeoServer/ });
    await expect(dropdown).toBeVisible();
    
    // Check dropdown contains the preconfigured backend
    const options = await dropdown.locator("option").allTextContents();
    expect(options.some(opt => opt.includes("Preconfigured GeoServer"))).toBeTruthy();
    
    // Also verify the regular example is still there
    expect(options.some(opt => opt.includes("MapX"))).toBeTruthy();
  });
});
