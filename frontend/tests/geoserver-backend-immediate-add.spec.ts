import { expect, test } from "@playwright/test";

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
 * Note: These tests mock the backend API responses to avoid requiring a running backend server
 */

// Set up global route mocks for all tests
test.beforeEach(async ({ page, context }) => {
  // Mock the settings/options endpoint for initialization
  await context.route("**/api/settings/options", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        session_id: "test-session-id",
        system_prompt: "Test system prompt",
        tool_options: {},
        search_portals: [],
        model_providers: ["openai", "anthropic"],
        model_options: {},
        available_model_names: ["gpt-4", "claude-3"],
        max_tokens: 4000,
      }),
    });
  });

  // Mock the preload endpoint to return immediately
  await context.route("**/api/settings/geoserver/preload", async (route) => {
    const request = route.request();
    const postData = request.postDataJSON();

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
  await context.route(
    "**/api/settings/geoserver/embedding-status*",
    async (route) => {
      const url = new URL(route.request().url());
      const backendUrls =
        url.searchParams.get("backend_urls")?.split(",") || [];

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
    },
  );
});

test.describe.skip("GeoServer Backend Immediate Addition", () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to settings page
    await page.goto("/settings");
    await page.waitForLoadState("domcontentloaded");

    // Wait for the form to be ready
    await page.waitForSelector('input[placeholder*="GeoServer URL"]', {
      timeout: 10000,
    });
  });

  test("backend appears immediately when added", async ({ page }) => {
    // Fill in backend details
    const testBackendUrl = "https://test-geoserver.example.com/geoserver";
    const testBackendName = "Test Backend";

    await page.fill('input[placeholder*="GeoServer URL"]', testBackendUrl);
    await page.fill('input[placeholder*="Backend Name"]', testBackendName);

    // Click add button
    await page.click('button:has-text("Add Backend")');

    // Backend should appear immediately in the list (within 2 seconds)
    await expect(page.locator(`text=${testBackendName}`)).toBeVisible({
      timeout: 2000,
    });
    await expect(page.locator(`text=${testBackendUrl}`)).toBeVisible();

    // Should show a status indicator (waiting state)
    const backendItem = page.locator(`li:has-text("${testBackendName}")`);
    await expect(backendItem).toBeVisible();
    await expect(backendItem.locator("text=/Waiting to start/")).toBeVisible({
      timeout: 3000,
    });

    // Form inputs should be cleared
    await expect(
      page.locator('input[placeholder*="GeoServer URL"]'),
    ).toHaveValue("");
    await expect(
      page.locator('input[placeholder*="Backend Name"]'),
    ).toHaveValue("");
  });

  test("progress states display correctly", async ({ page }) => {
    const testBackendUrl = "https://test-geoserver.example.com/geoserver";
    const testBackendName = "Progress Test Backend";

    // Add backend
    await page.fill('input[placeholder*="GeoServer URL"]', testBackendUrl);
    await page.fill('input[placeholder*="Backend Name"]', testBackendName);
    await page.click('button:has-text("Add Backend")');

    // Wait for backend to appear
    await expect(page.locator(`text=${testBackendName}`)).toBeVisible({
      timeout: 2000,
    });

    const backendItem = page.locator(`li:has-text("${testBackendName}")`);

    // Should show "Waiting to start" state initially
    await expect(backendItem.locator("text=/Waiting to start/")).toBeVisible({
      timeout: 3000,
    });

    // Wait for processing state (poll happens every 10 seconds, so wait up to 12 seconds)
    await expect(
      backendItem.locator("text=/Embedding in progress/"),
    ).toBeVisible({ timeout: 12000 });

    // Should show progress
    await expect(backendItem.locator("text=/layers/")).toBeVisible({
      timeout: 3000,
    });

    // Wait for completion (another poll cycle)
    await expect(backendItem.locator("text=/Embedding complete/")).toBeVisible({
      timeout: 12000,
    });
  });

  test("user can navigate away during embedding", async ({ page }) => {
    const testBackendUrl = "https://test-geoserver.example.com/geoserver";
    const testBackendName = "Navigate Test Backend";

    // Add backend
    await page.fill('input[placeholder*="GeoServer URL"]', testBackendUrl);
    await page.fill('input[placeholder*="Backend Name"]', testBackendName);
    await page.click('button:has-text("Add Backend")');

    // Wait for backend to appear
    await expect(page.locator(`text=${testBackendName}`)).toBeVisible({
      timeout: 2000,
    });

    // Navigate to chat page immediately
    await page.goto("/");
    await page.waitForLoadState("domcontentloaded");

    // Verify we're on the chat page
    await expect(page.locator('input[placeholder*="message"]')).toBeVisible();

    // Navigate back to settings
    await page.goto("/settings");
    await page.waitForLoadState("domcontentloaded");

    // Backend should still be there
    await expect(page.locator(`text=${testBackendName}`)).toBeVisible();

    // Progress status should still be updating
    const backendItem = page.locator(`li:has-text("${testBackendName}")`);
    await expect(
      backendItem.locator("text=/Embedding|Waiting|complete/"),
    ).toBeVisible({ timeout: 5000 });
  });

  test("multiple backends can be added simultaneously", async ({ page }) => {
    const backends = [
      { url: "https://backend1.example.com/geoserver", name: "Backend One" },
      { url: "https://backend2.example.com/geoserver", name: "Backend Two" },
      { url: "https://backend3.example.com/geoserver", name: "Backend Three" },
    ];

    // Add all backends quickly
    for (const backend of backends) {
      await page.fill('input[placeholder*="GeoServer URL"]', backend.url);
      await page.fill('input[placeholder*="Backend Name"]', backend.name);
      await page.click('button:has-text("Add Backend")');

      // Wait for it to appear before adding next
      await expect(page.locator(`text=${backend.name}`)).toBeVisible({
        timeout: 2000,
      });
    }

    // All backends should be visible
    for (const backend of backends) {
      await expect(page.locator(`text=${backend.name}`)).toBeVisible();
    }

    // Each should have its own progress indicator
    for (const backend of backends) {
      const backendItem = page.locator(`li:has-text("${backend.name}")`);
      await expect(
        backendItem.locator("text=/Embedding|Waiting|layers/"),
      ).toBeVisible({ timeout: 5000 });
    }
  });

  test("error state displays correctly", async ({ page, context }) => {
    // Override the preload endpoint for this specific test to return an error
    await context.unroute("**/api/settings/geoserver/preload");
    await context.route("**/api/settings/geoserver/preload", async (route) => {
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

    await page.fill('input[placeholder*="GeoServer URL"]', testBackendUrl);
    await page.fill('input[placeholder*="Backend Name"]', testBackendName);
    await page.click('button:has-text("Add Backend")');

    // Should show error message
    await expect(
      page.locator("text=/Failed to connect|Failed to preload/i"),
    ).toBeVisible({ timeout: 5000 });
  });

  test("progress percentage updates correctly", async ({ page }) => {
    const testBackendUrl = "https://test-geoserver.example.com/geoserver";
    const testBackendName = "Percentage Test Backend";

    // Add backend
    await page.fill('input[placeholder*="GeoServer URL"]', testBackendUrl);
    await page.fill('input[placeholder*="Backend Name"]', testBackendName);
    await page.click('button:has-text("Add Backend")');

    // Wait for backend to appear
    await expect(page.locator(`text=${testBackendName}`)).toBeVisible({
      timeout: 2000,
    });

    const backendItem = page.locator(`li:has-text("${testBackendName}")`);

    // Should see 0% initially (waiting state)
    await expect(backendItem.locator("text=/0%/")).toBeVisible({
      timeout: 5000,
    });

    // Wait for processing state
    await page.waitForTimeout(11000); // Wait for first poll

    // Should see 50% during processing
    await expect(backendItem.locator("text=/50%/")).toBeVisible({
      timeout: 3000,
    });

    // Wait for completion
    await page.waitForTimeout(11000); // Wait for second poll

    // Should see 100% when complete
    await expect(backendItem.locator("text=/100%/")).toBeVisible({
      timeout: 3000,
    });
  });

  test("completed backend shows checkmark", async ({ page }) => {
    const testBackendUrl = "https://fast-backend.example.com/geoserver";
    const testBackendName = "Fast Completion Backend";

    // Add backend
    await page.fill('input[placeholder*="GeoServer URL"]', testBackendUrl);
    await page.fill('input[placeholder*="Backend Name"]', testBackendName);
    await page.click('button:has-text("Add Backend")');

    // Wait for backend to appear
    await expect(page.locator(`text=${testBackendName}`)).toBeVisible({
      timeout: 2000,
    });

    const backendItem = page.locator(`li:has-text("${testBackendName}")`);

    // Wait for completion (after 2 poll cycles)
    await expect(
      backendItem.locator("text=/✓ Embedding complete/"),
    ).toBeVisible({ timeout: 25000 });

    // Progress bar should be green and at 100%
    const progressBar = backendItem.locator("div.bg-green-500");
    await expect(progressBar).toBeVisible();
  });

  test("polling stops when all backends completed", async ({
    page,
    context,
  }) => {
    const testBackendUrl = "https://polling-test.example.com/geoserver";
    const testBackendName = "Polling Test Backend";

    // Track number of status endpoint calls
    let statusCallCount = 0;
    await context.unroute("**/api/settings/geoserver/embedding-status*");
    await context.route(
      "**/api/settings/geoserver/embedding-status*",
      async (route) => {
        statusCallCount++;
        const url = new URL(route.request().url());
        const backendUrls =
          url.searchParams.get("backend_urls")?.split(",") || [];

        const backends: Record<string, any> = {};
        for (const backendUrl of backendUrls) {
          // Return completed state immediately
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

    // Add backend
    await page.fill('input[placeholder*="GeoServer URL"]', testBackendUrl);
    await page.fill('input[placeholder*="Backend Name"]', testBackendName);
    await page.click('button:has-text("Add Backend")');

    // Wait for backend to appear and show completed state
    await expect(page.locator(`text=${testBackendName}`)).toBeVisible({
      timeout: 2000,
    });
    const backendItem = page.locator(`li:has-text("${testBackendName}")`);
    await expect(backendItem.locator("text=/Embedding complete/")).toBeVisible({
      timeout: 5000,
    });

    // Get the initial call count (should be 1 - initial fetch)
    const initialCallCount = statusCallCount;

    // Wait 12 seconds (longer than polling interval of 10s)
    await page.waitForTimeout(12000);

    // Call count should not have increased significantly (maybe 1 more call at most)
    // since polling should stop when backend is completed
    expect(statusCallCount).toBeLessThanOrEqual(initialCallCount + 2);
  });
});

test.describe.skip("GeoServer Backend State Persistence", () => {
  test("backend state persists across page reloads", async ({ page }) => {
    const testBackendUrl = "https://persist-test.example.com/geoserver";
    const testBackendName = "Persistence Test Backend";

    // Add backend
    await page.goto("/settings");
    await page.waitForLoadState("domcontentloaded");
    await page.waitForSelector('input[placeholder*="GeoServer URL"]', {
      timeout: 10000,
    });

    await page.fill('input[placeholder*="GeoServer URL"]', testBackendUrl);
    await page.fill('input[placeholder*="Backend Name"]', testBackendName);
    await page.click('button:has-text("Add Backend")');

    // Wait for backend to appear
    await expect(page.locator(`text=${testBackendName}`)).toBeVisible({
      timeout: 2000,
    });

    // Reload page
    await page.reload();
    await page.waitForLoadState("domcontentloaded");
    await page.waitForSelector('input[placeholder*="GeoServer URL"]', {
      timeout: 10000,
    });

    // Backend should still be there (persisted in local storage)
    await expect(page.locator(`text=${testBackendName}`)).toBeVisible();

    // Progress should continue updating
    const backendItem = page.locator(`li:has-text("${testBackendName}")`);
    await expect(
      backendItem.locator("text=/Embedding|Waiting|processing/"),
    ).toBeVisible({ timeout: 12000 });
  });
});
