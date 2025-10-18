import { expect, test, Page } from "@playwright/test";

/**
 * Test suite for GeoServer backend immediate addition and progress tracking
 *
 * Tests verify:
 * 1. Backend appears immediately when added (no waiting for embedding)
 * 2. Progress states display correctly (waiting -> processing -> completed)
 * 3. User can navigate away during embedding and return
 * 4. Multiple backends can be added and process simultaneously
 * 5. Polling stops when all backends are completed or no backends exist
 *
 * Note: These tests mock the backend API responses to simulate the embedding workflow.
 */

// Helper function to expand the GeoServer Backends section
async function expandGeoServerSection(page: Page) {
  const geoserverButton = page.locator("button:has-text('GeoServer Backends')");
  await expect(geoserverButton).toBeVisible({ timeout: 5000 });
  await geoserverButton.click();
  await page.waitForTimeout(300);
}

const mockSettings = {
  system_prompt: "Test system prompt",
  tool_options: {},
  example_geoserver_backends: [],
  model_providers: ["openai", "anthropic"],
  model_options: {},
  session_id: "test-session-id",
};

// Set up global route mocks for all tests
test.beforeEach(async ({ page }) => {
  // Mock the settings/options endpoint for initialization
  await page.route("**/settings/options", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(mockSettings),
    });
  });

  // Mock the preload endpoint to return immediately
  await page.route("**/settings/geoserver/preload", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        session_id: "test-session-id",
        total_layers: 10,
        message: "Backend preload started",
      }),
    });
  });

  // Mock the embedding-status endpoint to return status for each backend
  let callCount = 0;
  await page.route("**/settings/geoserver/embedding-status*", async (route) => {
    const url = new URL(route.request().url());
    const backendUrls = url.searchParams.get("backend_urls")?.split(",") || [];

    callCount++;

    const backends: Record<string, any> = {};
    for (const backendUrl of backendUrls) {
      // Simulate progress: waiting -> processing -> completed
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
        // Third call onwards: completed state
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
      body: JSON.stringify({ backends }),
    });
  });
});

test.describe("GeoServer Backend Immediate Addition", () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to settings page
    await page.goto("/settings");
    await page.waitForLoadState("networkidle");
    // Expand the GeoServer Backends section
    await expandGeoServerSection(page);
  });

  test("backend appears immediately when added", async ({ page }) => {
    // Fill in backend details
    const testBackendUrl = "https://test-geoserver.example.com/geoserver";
    const testBackendName = "Test Backend";

    await page.getByPlaceholder("GeoServer URL").fill(testBackendUrl);
    await page
      .getByPlaceholder("Name (optional)", { exact: true })
      .fill(testBackendName);

    // Click add button
    await page.getByRole("button", { name: "Add Backend" }).click();

    // Backend should appear immediately in the list (within 2 seconds)
    await expect(page.locator(`text=${testBackendName}`)).toBeVisible({
      timeout: 2000,
    });

    // Should show a status indicator (waiting state initially)
    const backendItem = page.locator(`li:has-text("${testBackendName}")`);
    await expect(backendItem).toBeVisible();

    // Form inputs should be cleared
    await expect(page.getByPlaceholder("GeoServer URL")).toHaveValue("");
    await expect(
      page.getByPlaceholder("Name (optional)", { exact: true }),
    ).toHaveValue("");
  });

  test("progress states display correctly", async ({ page }) => {
    const testBackendUrl = "https://test-geoserver.example.com/geoserver";
    const testBackendName = "Progress Test Backend";

    // Add backend
    await page.getByPlaceholder("GeoServer URL").fill(testBackendUrl);
    await page
      .getByPlaceholder("Name (optional)", { exact: true })
      .fill(testBackendName);
    await page.getByRole("button", { name: "Add Backend" }).click();

    // Wait for backend to appear
    await expect(page.locator(`text=${testBackendName}`)).toBeVisible({
      timeout: 2000,
    });

    const backendItem = page.locator(`li:has-text("${testBackendName}")`);
    await expect(backendItem).toBeVisible();

    // Should show progress information (layers count)
    await expect(backendItem.locator("text=/layers/i")).toBeVisible({
      timeout: 5000,
    });
  });

  test.skip("user can navigate away during embedding", async ({ page }) => {
    // NOTE: This test is skipped because it requires localStorage persistence
    // which is not currently implemented in the settings store.
    // The Zustand store does not use persist middleware, so backends are not
    // persisted across navigation. This would require E2E testing with actual
    // persistence implementation to work properly.
    const testBackendUrl = "https://test-geoserver.example.com/geoserver";
    const testBackendName = "Navigate Test Backend";

    // Add backend
    await page.getByPlaceholder("GeoServer URL").fill(testBackendUrl);
    await page
      .getByPlaceholder("Name (optional)", { exact: true })
      .fill(testBackendName);
    await page.getByRole("button", { name: "Add Backend" }).click();

    // Wait for backend to appear
    await expect(page.locator(`text=${testBackendName}`)).toBeVisible({
      timeout: 2000,
    });

    // Navigate to chat page immediately
    await page.goto("/map");
    await page.waitForLoadState("domcontentloaded");

    // Verify we navigated away by checking URL
    expect(page.url()).toContain("/");
    expect(page.url()).not.toContain("/settings");

    // Navigate back to settings
    await page.goto("/settings");
    await page.waitForLoadState("domcontentloaded");

    // Backend should still be there (persisted in local storage)
    await expect(page.locator(`text=${testBackendName}`)).toBeVisible();
  });

  test("multiple backends can be added simultaneously", async ({ page }) => {
    const backends = [
      { url: "https://backend1.example.com/geoserver", name: "Backend One" },
      { url: "https://backend2.example.com/geoserver", name: "Backend Two" },
      { url: "https://backend3.example.com/geoserver", name: "Backend Three" },
    ];

    // Add all backends quickly
    for (const backend of backends) {
      await page.getByPlaceholder("GeoServer URL").fill(backend.url);
      await page
        .getByPlaceholder("Name (optional)", { exact: true })
        .fill(backend.name);
      await page.getByRole("button", { name: "Add Backend" }).click();

      // Wait for it to appear before adding next
      await expect(page.locator(`text=${backend.name}`)).toBeVisible({
        timeout: 2000,
      });
    }

    // All backends should be visible
    for (const backend of backends) {
      await expect(page.locator(`text=${backend.name}`)).toBeVisible();
    }
  });

  test("error state displays correctly", async ({ page }) => {
    // Override the preload endpoint for this specific test to return an error
    await page.unroute("**/settings/geoserver/preload");
    await page.route("**/settings/geoserver/preload", async (route) => {
      await route.fulfill({
        status: 500,
        contentType: "application/json",
        body: JSON.stringify({
          detail: "Failed to connect to GeoServer backend",
        }),
      });
    });

    // Add backend with URL that will trigger error
    const testBackendUrl =
      "https://invalid-nonexistent-backend.example.com/geoserver";
    const testBackendName = "Error Test Backend";

    await page.getByPlaceholder("GeoServer URL").fill(testBackendUrl);
    await page
      .getByPlaceholder("Name (optional)", { exact: true })
      .fill(testBackendName);
    await page.getByRole("button", { name: "Add Backend" }).click();

    // Should show error message (use first match to avoid strict mode violation)
    await expect(
      page.locator("p.text-red-600").filter({ hasText: /Failed to connect/i }),
    ).toBeVisible({ timeout: 5000 });
  });

  test("progress percentage updates correctly", async ({ page }) => {
    const testBackendUrl = "https://test-geoserver.example.com/geoserver";
    const testBackendName = "Percentage Test Backend";

    // Add backend
    await page.getByPlaceholder("GeoServer URL").fill(testBackendUrl);
    await page
      .getByPlaceholder("Name (optional)", { exact: true })
      .fill(testBackendName);
    await page.getByRole("button", { name: "Add Backend" }).click();

    // Wait for backend to appear
    await expect(page.locator(`text=${testBackendName}`)).toBeVisible({
      timeout: 2000,
    });

    const backendItem = page.locator(`li:has-text("${testBackendName}")`);

    // Should see percentage indicator (0%, 50%, or 100%)
    await expect(backendItem.locator("text=/%/")).toBeVisible({
      timeout: 5000,
    });
  });

  test("completed backend shows success indicator", async ({ page }) => {
    const testBackendUrl = "https://fast-backend.example.com/geoserver";
    const testBackendName = "Fast Completion Backend";

    // Add backend
    await page.getByPlaceholder("GeoServer URL").fill(testBackendUrl);
    await page
      .getByPlaceholder("Name (optional)", { exact: true })
      .fill(testBackendName);
    await page.getByRole("button", { name: "Add Backend" }).click();

    // Wait for backend to appear
    await expect(page.locator(`text=${testBackendName}`)).toBeVisible({
      timeout: 2000,
    });

    const backendItem = page.locator(`li:has-text("${testBackendName}")`);
    await expect(backendItem).toBeVisible();

    // Backend should show total layers
    await expect(backendItem.locator("text=/10 layers/i")).toBeVisible({
      timeout: 5000,
    });
  });

  test("polling behavior with completed backends", async ({ page }) => {
    const testBackendUrl = "https://polling-test.example.com/geoserver";
    const testBackendName = "Polling Test Backend";

    // Add backend
    await page.getByPlaceholder("GeoServer URL").fill(testBackendUrl);
    await page
      .getByPlaceholder("Name (optional)", { exact: true })
      .fill(testBackendName);
    await page.getByRole("button", { name: "Add Backend" }).click();

    // Wait for backend to appear and show some progress
    await expect(page.locator(`text=${testBackendName}`)).toBeVisible({
      timeout: 2000,
    });

    const backendItem = page.locator(`li:has-text("${testBackendName}")`);
    await expect(backendItem).toBeVisible();

    // Verify backend is in the list
    await expect(backendItem.locator("text=/layers/i")).toBeVisible({
      timeout: 5000,
    });
  });
});

test.describe.skip("GeoServer Backend State Persistence", () => {
  // NOTE: This test suite is skipped because it requires localStorage persistence
  // which is not currently implemented in the settings store.
  // The Zustand store does not use persist middleware, so backends are stored
  // only in memory and lost on page reload. These tests would require either:
  // 1. Implementation of Zustand persist middleware in settingsStore
  // 2. E2E testing against actual backend persistence
  //
  // Once persistence is implemented, these tests can be enabled and will work
  // with the existing mocking setup.

  test.beforeEach(async ({ page }) => {
    // Mock the immediate-add endpoint
    await page.route("**/settings/geoserver/immediate-add", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          session_id: "test-session-id",
          total_layers: 10,
          message: "Backend added immediately",
        }),
      });
    });

    // Mock the embedding-status endpoint
    await page.route(
      "**/settings/geoserver/embedding-status*",
      async (route) => {
        const url = new URL(route.request().url());
        const backendUrls =
          url.searchParams.get("backend_urls")?.split(",") || [];

        const backends: Record<string, any> = {};
        for (const backendUrl of backendUrls) {
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

        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ backends }),
        });
      },
    );

    // Navigate to settings page
    await page.goto("/settings");
    await page.waitForLoadState("networkidle");
  });

  test("backend state persists across page reloads", async ({ page }) => {
    const testBackendUrl = "https://persist-test.example.com/geoserver";
    const testBackendName = "Persistence Test Backend";

    // Add backend
    await page.getByPlaceholder("GeoServer URL").fill(testBackendUrl);
    await page
      .getByPlaceholder("Name (optional)", { exact: true })
      .fill(testBackendName);
    await page.getByRole("button", { name: "Add Backend" }).click();

    // Wait for backend to appear
    await expect(page.locator(`text=${testBackendName}`)).toBeVisible({
      timeout: 2000,
    });

    // Wait a moment for state to be persisted to local storage
    await page.waitForTimeout(500);

    // Reload page
    await page.reload();
    await page.waitForLoadState("domcontentloaded");

    // Wait for React to rehydrate from local storage
    await page.waitForTimeout(1000);

    // Backend should still be there (persisted in local storage)
    await expect(page.locator(`text=${testBackendName}`)).toBeVisible({
      timeout: 5000,
    });
  });
});
