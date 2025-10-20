import { test, expect, Page } from "@playwright/test";

// Helper function to expand the Model Settings section
async function expandModelSettings(page: Page) {
  const modelButton = page.locator("button:has-text('Model Settings')");
  await expect(modelButton).toBeVisible({ timeout: 5000 });
  await modelButton.click();
  await page.waitForTimeout(300);
}

const mockSettings = {
  system_prompt: "You are a helpful AI assistant.",
  tool_options: {},
  example_geoserver_backends: [],
  model_options: {
    openai: [
      {
        name: "gpt-4",
        max_tokens: 4000,
        input_cost_per_million: 30.0,
        output_cost_per_million: 60.0,
        supports_parallel_tool_calls: true,
      },
      {
        name: "gpt-3.5-turbo",
        max_tokens: 2000,
        input_cost_per_million: 0.5,
        output_cost_per_million: 1.5,
        supports_parallel_tool_calls: false,
      },
    ],
  },
  model_settings: {
    model_provider: "openai",
    model_name: "gpt-4",
    max_tokens: 4000,
    system_prompt: "You are a helpful AI assistant.",
    message_window_size: 20,
    enable_parallel_tools: false,
    enable_performance_metrics: true,
  },
  session_id: "test-session-123",
};

const mockMetricsData = {
  status: "success",
  data: {
    period_hours: 1,
    total_requests: 15,
    time_range: {
      start: "2025-10-21T10:00:00Z",
      end: "2025-10-21T11:00:00Z",
    },
    response_time: {
      min: 1.2,
      max: 5.8,
      avg: 3.2,
      median: 3.1,
      p50: 3.1,
      p95: 5.5,
      p99: 5.8,
    },
    agent_execution_time: {
      min: 0.8,
      max: 4.2,
      avg: 2.5,
      median: 2.4,
      p50: 2.4,
      p95: 4.0,
      p99: 4.2,
    },
    llm: {
      total_calls: 45,
      avg_calls_per_request: 3.0,
      total_time: 25.5,
      time_stats: {
        min: 0.3,
        max: 2.1,
        avg: 0.567,
      },
    },
    tools: {
      total_calls: 30,
      avg_calls_per_request: 2.0,
      top_tools: [
        {
          name: "search_osm",
          total_calls: 12,
          avg_time: 0.45,
          min_time: 0.2,
          max_time: 1.1,
        },
        {
          name: "get_wms_capabilities",
          total_calls: 10,
          avg_time: 0.35,
          min_time: 0.15,
          max_time: 0.8,
        },
        {
          name: "geocode",
          total_calls: 8,
          avg_time: 0.25,
          min_time: 0.1,
          max_time: 0.6,
        },
      ],
    },
    tokens: {
      total: 125000,
      avg_per_request: 8333,
      stats: {
        min: 3000,
        max: 15000,
        avg: 8333,
      },
    },
    message_pruning: {
      total_reduction: 120,
      avg_reduction: 8.0,
    },
    errors: {
      total: 1,
      rate: 0.067,
    },
  },
  storage_info: {
    total_entries: 15,
  },
};

const emptyMetricsData = {
  status: "success",
  data: {
    period_hours: 1,
    total_requests: 0,
    response_time: {
      min: 0,
      max: 0,
      avg: 0,
      median: 0,
      p50: 0,
      p95: 0,
      p99: 0,
    },
    agent_execution_time: {
      min: 0,
      max: 0,
      avg: 0,
      median: 0,
      p50: 0,
      p95: 0,
      p99: 0,
    },
    llm: {
      total_calls: 0,
      avg_calls_per_request: 0,
      total_time: 0,
      time_stats: {
        min: 0,
        max: 0,
        avg: 0,
      },
    },
    tools: {
      total_calls: 0,
      avg_calls_per_request: 0,
      top_tools: [],
    },
    tokens: {
      total: 0,
      avg_per_request: 0,
      stats: {
        min: 0,
        max: 0,
        avg: 0,
      },
    },
    message_pruning: {
      total_reduction: 0,
      avg_reduction: 0,
    },
    errors: {
      total: 0,
      rate: 0,
    },
  },
  storage_info: {
    total_entries: 0,
  },
};

test.describe("Metrics Page", () => {
  test.beforeEach(async ({ page }) => {
    // Mock settings endpoint
    await page.route("**/settings/options", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockSettings),
      });
    });

    // Mock metrics endpoint with data
    await page.route("**/metrics?hours=*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockMetricsData),
      });
    });
  });

  test("should show metrics link when performance metrics is enabled", async ({
    page,
  }) => {
    await page.goto("/settings");
    await page.waitForLoadState("networkidle");

    await expandModelSettings(page);

    // Check that the metrics checkbox exists (may or may not be checked depending on backend state)
    const metricsCheckbox = page.locator(
      'input[type="checkbox"]#enable-performance-metrics',
    );
    await expect(metricsCheckbox).toBeVisible();

    // Enable metrics if not already enabled
    const isChecked = await metricsCheckbox.isChecked();
    if (!isChecked) {
      await metricsCheckbox.check();
      await page.waitForTimeout(300);
    }

    // Check that the "View metrics dashboard" link is visible
    const metricsLink = page.locator('a:has-text("View metrics dashboard")');
    await expect(metricsLink).toBeVisible();
    await expect(metricsLink).toHaveAttribute("href", "/metrics");
  });

  test("should navigate to metrics page via link", async ({ page }) => {
    await page.goto("/settings");
    await page.waitForLoadState("networkidle");

    await expandModelSettings(page);

    // Enable metrics if not already enabled
    const metricsCheckbox = page.locator(
      'input[type="checkbox"]#enable-performance-metrics',
    );
    const isChecked = await metricsCheckbox.isChecked();
    if (!isChecked) {
      await metricsCheckbox.check();
      await page.waitForTimeout(300);
    }

    // Click the metrics dashboard link
    const metricsLink = page.locator('a:has-text("View metrics dashboard")');
    await expect(metricsLink).toBeVisible();
    await metricsLink.click();

    // Wait for navigation
    await page.waitForURL("**/metrics");
    await page.waitForLoadState("networkidle");

    // Verify we're on the metrics page
    await expect(page).toHaveURL(/\/metrics$/);
  });

  test("should display metrics page header and title", async ({ page }) => {
    await page.goto("/metrics");
    await page.waitForLoadState("networkidle");

    // Check for the main heading
    const heading = page.getByRole("heading", {
      level: 1,
      name: "Performance Metrics",
    });
    await expect(heading).toBeVisible();

    // Check for the description
    await expect(
      page.locator("text=Agent performance analytics and statistics"),
    ).toBeVisible();
  });

  test("should display time range selector", async ({ page }) => {
    await page.goto("/metrics");
    await page.waitForLoadState("networkidle");

    // Check that the time range selector is visible
    const timeRangeLabel = page.locator("label:has-text('Time Range:')");
    await expect(timeRangeLabel).toBeVisible();

    const timeRangeSelect = page.locator('select');
    await expect(timeRangeSelect).toBeVisible();

    // Check that all options are present
    await expect(timeRangeSelect).toContainText("Last Hour");
    await expect(timeRangeSelect).toContainText("Last 6 Hours");
    await expect(timeRangeSelect).toContainText("Last 24 Hours");
    await expect(timeRangeSelect).toContainText("Last Week");
  });

  test("should display summary cards with correct data", async ({ page }) => {
    await page.goto("/metrics");
    await page.waitForLoadState("networkidle");

    // Check Total Requests card
    await expect(page.locator("text=Total Requests")).toBeVisible();
    await expect(page.locator("text=15").first()).toBeVisible();

    // Check Avg Response Time card - use first() to avoid strict mode violation
    await expect(page.locator("text=Avg Response Time")).toBeVisible();
    await expect(page.locator("text=3.20s").first()).toBeVisible();

    // Check Total LLM Calls card
    await expect(page.locator("text=Total LLM Calls")).toBeVisible();
    await expect(page.locator("text=45").first()).toBeVisible();

    // Check Error Rate card - format is XX.XX%
    await expect(page.locator("text=Error Rate")).toBeVisible();
    await expect(page.locator("text=6.70%")).toBeVisible();
  });

  test("should display response time analysis", async ({ page }) => {
    await page.goto("/metrics");
    await page.waitForLoadState("networkidle");

    // Check Response Time Analysis section
    await expect(
      page.locator("text=Response Time Analysis").first(),
    ).toBeVisible();

    // Check percentile values
    await expect(page.locator("text=Min").first()).toBeVisible();
    await expect(page.locator("text=Average").first()).toBeVisible();
    await expect(page.locator("text=P95").first()).toBeVisible();
    await expect(page.locator("text=Max").first()).toBeVisible();
  });

  test("should display LLM performance metrics", async ({ page }) => {
    await page.goto("/metrics");
    await page.waitForLoadState("networkidle");

    // Check LLM Performance section
    await expect(page.locator("text=LLM Performance")).toBeVisible();

    // Check LLM stats
    await expect(page.locator("text=Total Calls").first()).toBeVisible();
    await expect(page.locator("text=Avg per Request").first()).toBeVisible();
    await expect(page.locator("text=Total Time").first()).toBeVisible();
    await expect(page.locator("text=Avg Time").first()).toBeVisible();
  });

  test("should display top tools ranking", async ({ page }) => {
    await page.goto("/metrics");
    await page.waitForLoadState("networkidle");

    // Check Top Tools section
    await expect(page.locator("text=Top Tools")).toBeVisible();

    // Check that tools are listed
    await expect(page.locator("text=search_osm")).toBeVisible();
    await expect(page.locator("text=get_wms_capabilities")).toBeVisible();
    await expect(page.locator("text=geocode")).toBeVisible();

    // Check tool ranking numbers
    await expect(page.locator("text=#1").first()).toBeVisible();
    await expect(page.locator("text=#2").first()).toBeVisible();
    await expect(page.locator("text=#3").first()).toBeVisible();
  });

  test("should display token usage with model-based cost estimation", async ({
    page,
  }) => {
    await page.goto("/metrics");
    await page.waitForLoadState("networkidle");

    // Check Token Usage section
    await expect(page.locator("text=Token Usage").first()).toBeVisible();

    // Check token stats
    await expect(page.locator("text=Total Tokens").first()).toBeVisible();
    await expect(page.locator("text=125,000")).toBeVisible();

    // Check that cost is calculated based on model
    await expect(page.locator("text=Estimated Cost").first()).toBeVisible();
    
    // Cost should be calculated: (125000 / 1000000) * ((30 + 60) / 2) = 0.125 * 45 = 5.625
    await expect(page.locator("text=$5.6250")).toBeVisible();

    // Check that model name is mentioned in cost description
    await expect(page.locator("text=Based on gpt-4")).toBeVisible();
  });

  test("should display message pruning statistics", async ({ page }) => {
    await page.goto("/metrics");
    await page.waitForLoadState("networkidle");

    // Check Message Pruning section
    await expect(
      page.locator("text=Message Pruning Effectiveness"),
    ).toBeVisible();

    // Check pruning stats
    await expect(page.locator("text=Total Messages Pruned")).toBeVisible();
    await expect(page.locator("text=120")).toBeVisible();
  });

  test("should have a refresh button that refetches metrics", async ({
    page,
  }) => {
    await page.goto("/metrics");
    await page.waitForLoadState("networkidle");

    // Find and click the refresh button
    const refreshButton = page.locator("button:has-text('Refresh')");
    await expect(refreshButton).toBeVisible();

    // Track the number of metrics API calls
    let metricsCallCount = 0;
    await page.route("**/metrics?hours=*", async (route) => {
      metricsCallCount++;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockMetricsData),
      });
    });

    await refreshButton.click();
    await page.waitForTimeout(500);

    // Verify that a new API call was made
    expect(metricsCallCount).toBeGreaterThan(0);
  });

  test("should update metrics when time range is changed", async ({ page }) => {
    let requestedHours = 1;

    await page.route("**/metrics?hours=*", async (route) => {
      const url = new URL(route.request().url());
      requestedHours = parseInt(url.searchParams.get("hours") || "1");

      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockMetricsData),
      });
    });

    await page.goto("/metrics");
    await page.waitForLoadState("networkidle");

    // Change time range to 6 hours
    const timeRangeSelect = page.locator('select');
    await timeRangeSelect.selectOption({ value: "6" });
    await page.waitForTimeout(500);

    // Verify the API was called with the new time range
    expect(requestedHours).toBe(6);

    // Change to 24 hours
    await timeRangeSelect.selectOption({ value: "24" });
    await page.waitForTimeout(500);

    expect(requestedHours).toBe(24);
  });

  test("should display empty state when no metrics are available", async ({
    page,
  }) => {
    // Override metrics endpoint to return empty data
    await page.route("**/metrics?hours=*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(emptyMetricsData),
      });
    });

    await page.goto("/metrics");
    await page.waitForLoadState("networkidle");

    // Check for empty state message
    await expect(page.locator("text=No Metrics Available")).toBeVisible();
    await expect(
      page.locator(
        "text=No metrics data for the selected time range. Enable performance metrics in settings and make some requests.",
      ),
    ).toBeVisible();
  });

  test("should display error state when metrics fetch fails", async ({
    page,
  }) => {
    // Override metrics endpoint to return error
    await page.route("**/metrics?hours=*", async (route) => {
      await route.abort("failed");
    });

    await page.goto("/metrics");
    await page.waitForTimeout(1000);

    // Check for error state message
    await expect(page.locator("text=Error Loading Metrics")).toBeVisible();

    // Check that retry button is visible
    const retryButton = page.locator("button:has-text('Retry')");
    await expect(retryButton).toBeVisible();
  });

  test("should display sidebar on metrics page", async ({ page }) => {
    await page.goto("/metrics");
    await page.waitForLoadState("networkidle");

    // Check that sidebar is present by looking for the Home button which is always visible on desktop
    const homeButton = page.locator("button[title='Home']").last();
    await expect(homeButton).toBeVisible();
  });

  test("should handle N/A cost when model costs are not available", async ({
    page,
  }) => {
    // Override settings to have a model without cost info
    const settingsWithoutCosts = {
      ...mockSettings,
      model_options: {
        openai: [
          {
            name: "test-model",
            max_tokens: 4000,
            input_cost_per_million: null,
            output_cost_per_million: null,
          },
        ],
      },
      model_settings: {
        ...mockSettings.model_settings,
        model_name: "test-model",
      },
    };

    await page.route("**/settings/options", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(settingsWithoutCosts),
      });
    });

    await page.goto("/metrics");
    await page.waitForLoadState("networkidle");

    // Check that cost shows N/A
    await expect(page.locator("text=Estimated Cost").first()).toBeVisible();
    await expect(page.locator("text=N/A").first()).toBeVisible();
    await expect(
      page.locator("text=Model costs not available"),
    ).toBeVisible();
  });

  test("should display storage info in header", async ({ page }) => {
    await page.goto("/metrics");
    await page.waitForLoadState("networkidle");

    // Check that storage info is displayed
    await expect(page.locator("text=15 entries stored")).toBeVisible();
  });
});
