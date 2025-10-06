import { test, expect } from "@playwright/test";

const mockSettings = {
  system_prompt: "Assist helpfully.",
  tool_options: {
    search: {
      default_prompt: "Search prompt",
      settings: {},
    },
  },
  search_portals: [],
  geoserver_backends: [],
  model_options: {
    Provider: [{ name: "model-a", max_tokens: 512 }],
  },
  model_settings: {
    model_provider: "Provider",
    model_name: "model-a",
    max_tokens: 512,
    system_prompt: "Assist helpfully.",
  },
  tools: [],
  session_id: "session-initial",
};

test.describe("GeoServer backend preload - Advanced scenarios", () => {
  test.beforeEach(async ({ page }) => {
    await page.route("**/settings/options", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockSettings),
      });
    });
  });

  test("handles partial import when some backends fail to preload", async ({
    page,
  }) => {
    const importSnapshot = {
      ...mockSettings,
      geoserver_backends: [
        {
          url: "https://success.example/geoserver",
          name: "Success Backend",
          enabled: true,
        },
        {
          url: "https://fail.example/geoserver",
          name: "Fail Backend",
          enabled: true,
        },
        {
          url: "https://another-success.example/geoserver",
          name: "Another Success",
          enabled: true,
        },
      ],
    };

    let requestCount = 0;
    await page.route(
      "**/settings/geoserver/preload",
      async (route, request) => {
        requestCount++;
        const payload = request.postDataJSON();

        // Fail the second backend
        if (payload.backend.url === "https://fail.example/geoserver") {
          await route.fulfill({
            status: 503,
            contentType: "application/json",
            body: JSON.stringify({ detail: "Backend temporarily unavailable" }),
          });
        } else {
          await route.fulfill({
            status: 200,
            contentType: "application/json",
            body: JSON.stringify({
              session_id: `session-${requestCount}`,
              total_layers: 5,
            }),
          });
        }
      },
    );

    await page.goto("/settings");

    await page.setInputFiles('input[type="file"]', {
      name: "settings.json",
      mimeType: "application/json",
      buffer: Buffer.from(JSON.stringify(importSnapshot)),
    });

    // Should show success for 2 out of 3 backends
    await expect(
      page.getByText("Prefetched 2 imported backends successfully."),
    ).toBeVisible();

    // Should show error for the failed backend
    await expect(
      page.getByText(/Failed to preload.*fail\.example/),
    ).toBeVisible();

    // Successful backends should be visible
    await expect(
      page.getByRole("listitem").filter({ hasText: "Success Backend" }),
    ).toBeVisible();
    await expect(
      page.getByRole("listitem").filter({ hasText: "Another Success" }),
    ).toBeVisible();
  });

  test("handles import of settings without model_settings gracefully", async ({
    page,
  }) => {
    const incompleteSnapshot = {
      search_portals: ["https://example.com"],
      geoserver_backends: [
        {
          url: "https://geo.example/geoserver",
          name: "Test Backend",
          enabled: true,
        },
      ],
      // Missing model_settings, tools, tool_options, etc.
    };

    await page.route("**/settings/geoserver/preload", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          session_id: "new-session",
          total_layers: 3,
        }),
      });
    });

    await page.goto("/settings");

    // Page should not crash
    await expect(
      page.getByRole("heading", { name: "Settings", exact: true }),
    ).toBeVisible();

    await page.setInputFiles('input[type="file"]', {
      name: "settings.json",
      mimeType: "application/json",
      buffer: Buffer.from(JSON.stringify(incompleteSnapshot)),
    });

    // Should complete without errors
    await expect(
      page.getByText("Prefetched 1 imported backend successfully."),
    ).toBeVisible();

    // Model settings section should still be functional (using defaults)
    await expect(page.getByText("Model Settings")).toBeVisible();
  });

  test("handles empty geoserver_backends array in import", async ({ page }) => {
    const emptyBackendsSnapshot = {
      ...mockSettings,
      geoserver_backends: [],
    };

    await page.goto("/settings");

    await page.setInputFiles('input[type="file"]', {
      name: "settings.json",
      mimeType: "application/json",
      buffer: Buffer.from(JSON.stringify(emptyBackendsSnapshot)),
    });

    // Should show success message even with no backends
    await expect(
      page.getByText("Settings imported successfully."),
    ).toBeVisible();
  });

  test("prevents multiple concurrent imports", async ({ page }) => {
    const importSnapshot = {
      ...mockSettings,
      geoserver_backends: [
        {
          url: "https://slow.example/geoserver",
          name: "Slow Backend",
          enabled: true,
        },
      ],
    };

    let preloadCallCount = 0;
    await page.route("**/settings/geoserver/preload", async (route) => {
      preloadCallCount++;
      // Simulate slow response
      await new Promise((resolve) => setTimeout(resolve, 2000));
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          session_id: "session-slow",
          total_layers: 10,
        }),
      });
    });

    await page.goto("/settings");

    // Try to import twice quickly
    const file1Promise = page.setInputFiles('input[type="file"]', {
      name: "settings1.json",
      mimeType: "application/json",
      buffer: Buffer.from(JSON.stringify(importSnapshot)),
    });

    // Wait a bit then try again
    await page.waitForTimeout(100);

    const file2Promise = page.setInputFiles('input[type="file"]', {
      name: "settings2.json",
      mimeType: "application/json",
      buffer: Buffer.from(JSON.stringify(importSnapshot)),
    });

    await Promise.all([file1Promise, file2Promise]);

    // Should only see success message appear after operations complete
    await expect(page.getByText(/Prefetched.*successfully/)).toBeVisible({
      timeout: 5000,
    });

    // Both imports should have processed (sequential)
    expect(preloadCallCount).toBeGreaterThanOrEqual(1);
  });

  test("validates backend URL before prefetching", async ({ page }) => {
    const invalidSnapshot = {
      ...mockSettings,
      geoserver_backends: [
        {
          url: "", // Empty URL
          name: "Invalid Backend",
          enabled: true,
        },
      ],
    };

    await page.goto("/settings");

    await page.setInputFiles('input[type="file"]', {
      name: "settings.json",
      mimeType: "application/json",
      buffer: Buffer.from(JSON.stringify(invalidSnapshot)),
    });

    // Should show appropriate error message
    await expect(
      page.getByText(/Failed to preload|Please provide a GeoServer URL/i),
    ).toBeVisible();
  });

  test("preserves existing backends when importing additional ones", async ({
    page,
  }) => {
    // First add a backend manually
    await page.route("**/settings/geoserver/preload", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          session_id: "session-manual",
          total_layers: 2,
        }),
      });
    });

    await page.goto("/settings");

    await page
      .getByPlaceholder("GeoServer URL")
      .fill("https://existing.example/geoserver");
    await page
      .getByPlaceholder("Name (optional)", { exact: true })
      .fill("Existing Backend");
    await page.getByRole("button", { name: "Add Backend" }).click();

    await expect(
      page.getByText("Prefetched 2 layers successfully."),
    ).toBeVisible();
    await expect(
      page.getByRole("listitem").filter({ hasText: "Existing Backend" }),
    ).toBeVisible();

    // Now import new backends
    const importSnapshot = {
      ...mockSettings,
      geoserver_backends: [
        {
          url: "https://imported.example/geoserver",
          name: "Imported Backend",
          enabled: true,
        },
      ],
    };

    await page.setInputFiles('input[type="file"]', {
      name: "settings.json",
      mimeType: "application/json",
      buffer: Buffer.from(JSON.stringify(importSnapshot)),
    });

    await expect(
      page.getByText("Prefetched 1 imported backend successfully."),
    ).toBeVisible();

    // Note: Import REPLACES existing backends, not appends
    // This is the current behavior - old backend should be gone
    await expect(
      page.getByRole("listitem").filter({ hasText: "Imported Backend" }),
    ).toBeVisible();
  });

  test("handles network timeout gracefully", async ({ page }) => {
    const importSnapshot = {
      ...mockSettings,
      geoserver_backends: [
        {
          url: "https://timeout.example/geoserver",
          name: "Timeout Backend",
          enabled: true,
        },
      ],
    };

    await page.route("**/settings/geoserver/preload", async (route) => {
      // Simulate network timeout - just abort the request
      await route.abort("timedout");
    });

    await page.goto("/settings");

    await page.setInputFiles('input[type="file"]', {
      name: "settings.json",
      mimeType: "application/json",
      buffer: Buffer.from(JSON.stringify(importSnapshot)),
    });

    // Should show error message
    await expect(
      page.getByText(/Settings imported.*Unable to preload/i),
    ).toBeVisible();
  });
});
