/**
 * Streaming endpoint tests with mocked SSE responses
 * Tests the frontend SSE client and UI components without requiring backend
 */
import { test, expect, Page } from "@playwright/test";

// Helper to simulate SSE event stream
async function mockSSEStream(page: Page, events: Array<{ event: string; data: any }>) {
  let routeHitCount = 0;
  
  await page.route("**/api/chat/stream", async (route) => {
    routeHitCount++;
    console.log(`[MOCK SSE] Route hit #${routeHitCount}: ${route.request().url()}`);
    
    // Create SSE response
    let responseBody = "";
    for (const { event, data } of events) {
      responseBody += `event: ${event}\n`;
      responseBody += `data: ${JSON.stringify(data)}\n\n`;
    }

    await route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      headers: {
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
      },
      body: responseBody,
    });
  });
  
  return () => routeHitCount;
}

test.describe("Streaming Chat Interface", () => {
  test.beforeEach(async ({ page }) => {
    // Mock settings endpoint
    await page.route("**/settings/options", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          model_settings: {
            llm_provider: "openai",
            model_name: "gpt-4o-mini",
            enable_performance_metrics: true,
          },
          tools: {},
        }),
      });
    });

    await page.goto("/map");
  });

  test("should display tool progress indicator when streaming", async ({ page }) => {
    // Mock streaming response with tool events
    await mockSSEStream(page, [
      {
        event: "tool_start",
        data: { tool: "overpass_search", input: {} },
      },
      {
        event: "llm_token",
        data: { token: "I found " },
      },
      {
        event: "llm_token",
        data: { token: "some rivers" },
      },
      {
        event: "tool_end",
        data: { tool: "overpass_search", output: "Success" },
      },
      {
        event: "result",
        data: {
          messages: [
            { type: "human", content: "Show me rivers" },
            { type: "ai", content: "I found some rivers in Germany" },
          ],
          geodata_results: [],
          geodata_layers: [],
          metrics: {
            agent_execution_time: 5.2,
            token_usage: { total: 150, prompt: 100, completion: 50 },
          },
        },
      },
      {
        event: "done",
        data: { status: "complete" },
      },
    ]);

    // Type query and submit
    const input = page.getByPlaceholder("Ask about maps, search for data, or request analysis...");
    await input.fill("Show me rivers in Germany");
    await input.press("Enter");

    // Wait a bit for the SSE processing to start
    await page.waitForTimeout(100);

    // Wait for tool progress indicator to appear
    const toolProgress = page.locator(".tool-progress-container");
    await expect(toolProgress).toBeVisible({ timeout: 5000 });

    // Verify tool name is displayed
    await expect(page.locator(".tool-progress-name")).toContainText("Overpass Search");

    // Verify running status (spinner should be visible)
    const spinner = page.locator(".tool-spinner");
    await expect(spinner).toBeVisible();

    // Wait for completion (check icon should appear)
    const checkIcon = page.locator(".tool-check");
    await expect(checkIcon).toBeVisible({ timeout: 5000 });
  });

  test("should stream LLM tokens in real-time", async ({ page }) => {
    const tokens = ["Hello", " there!", " I'm", " streaming", " tokens."];
    
    const events = [
      ...tokens.map((token) => ({
        event: "llm_token",
        data: { token },
      })),
      {
        event: "result",
        data: {
          messages: [
            { type: "human", content: "Test" },
            { type: "ai", content: tokens.join("") },
          ],
          geodata_results: [],
          geodata_layers: [],
          metrics: {},
        },
      },
      {
        event: "done",
        data: { status: "complete" },
      },
    ];

    await mockSSEStream(page, events);

    // Submit query
    const input = page.getByPlaceholder("Ask about maps, search for data, or request analysis...");
    await input.fill("Test streaming");
    await input.press("Enter");

    // Wait for streaming message container
    const streamingMessage = page.locator(".streaming-message");
    await expect(streamingMessage).toBeVisible({ timeout: 5000 });

    // Verify blinking cursor is present
    await expect(streamingMessage).toHaveCSS("position", "relative");

    // Wait for all tokens to be received
    await page.waitForTimeout(1000);

    // Verify final message appears in chat
    const finalMessage = page.locator(".chat-message").last();
    await expect(finalMessage).toContainText("Hello there! I'm streaming tokens.");
  });

  test("should handle multiple tool executions", async ({ page }) => {
    await mockSSEStream(page, [
      {
        event: "tool_start",
        data: { tool: "geocode_location", input: {} },
      },
      {
        event: "tool_end",
        data: { tool: "geocode_location", output: "Success" },
      },
      {
        event: "tool_start",
        data: { tool: "overpass_search", input: {} },
      },
      {
        event: "tool_end",
        data: { tool: "overpass_search", output: "Success" },
      },
      {
        event: "result",
        data: {
          messages: [
            { type: "human", content: "Search" },
            { type: "ai", content: "Found results" },
          ],
          geodata_results: [],
          geodata_layers: [],
          metrics: {},
        },
      },
      {
        event: "done",
        data: { status: "complete" },
      },
    ]);

    const input = page.getByPlaceholder("Ask about maps, search for data, or request analysis...");
    await input.fill("Search for data");
    await input.press("Enter");

    // Wait for tool progress
    await page.waitForTimeout(500);

    // Should show two tools
    const toolItems = page.locator(".tool-progress-item");
    await expect(toolItems).toHaveCount(2);

    // Verify both tool names
    const toolNames = page.locator(".tool-progress-name");
    await expect(toolNames.nth(0)).toContainText("Geocode Location");
    await expect(toolNames.nth(1)).toContainText("Overpass Search");
  });

  test("should display error state for failed tools", async ({ page }) => {
    await mockSSEStream(page, [
      {
        event: "tool_start",
        data: { tool: "failing_tool", input: {} },
      },
      {
        event: "error",
        data: { 
          error: "tool_error", 
          message: "Tool execution failed" 
        },
      },
      {
        event: "done",
        data: { status: "error" },
      },
    ]);

    const input = page.getByPlaceholder("Ask about maps, search for data, or request analysis...");
    await input.fill("Cause an error");
    await input.press("Enter");

    // Wait for error indicator
    const errorIcon = page.locator(".tool-error");
    await expect(errorIcon).toBeVisible({ timeout: 5000 });

    // Verify error message is displayed
    const errorText = page.locator(".tool-progress-error");
    await expect(errorText).toBeVisible();
  });

  test("should clear streaming state after completion", async ({ page }) => {
    await mockSSEStream(page, [
      {
        event: "tool_start",
        data: { tool: "test_tool", input: {} },
      },
      {
        event: "llm_token",
        data: { token: "Testing" },
      },
      {
        event: "tool_end",
        data: { tool: "test_tool", output: "Done" },
      },
      {
        event: "result",
        data: {
          messages: [
            { type: "human", content: "Test" },
            { type: "ai", content: "Testing" },
          ],
          geodata_results: [],
          geodata_layers: [],
          metrics: {},
        },
      },
      {
        event: "done",
        data: { status: "complete" },
      },
    ]);

    const input = page.getByPlaceholder("Ask about maps, search for data, or request analysis...");
    await input.fill("Test");
    await input.press("Enter");

    // Wait for streaming to complete
    await page.waitForTimeout(2000);

    // Tool progress should disappear after completion
    const toolProgress = page.locator(".tool-progress-container");
    await expect(toolProgress).not.toBeVisible();

    // Streaming message should be cleared
    const streamingMessage = page.locator(".streaming-message");
    await expect(streamingMessage).not.toBeVisible();

    // Input should be enabled again
    await expect(input).toBeEnabled();
  });

  test("should handle streaming with geodata results", async ({ page }) => {
    await mockSSEStream(page, [
      {
        event: "tool_start",
        data: { tool: "overpass_search", input: {} },
      },
      {
        event: "tool_end",
        data: { tool: "overpass_search", output: "Found 5 features" },
      },
      {
        event: "result",
        data: {
          messages: [
            { type: "human", content: "Find rivers" },
            { type: "ai", content: "Found 5 rivers" },
          ],
          geodata_results: [
            {
              id: "river-1",
              name: "Rhine River",
              title: "Rhine River",
              data_type: "geojson",
              visible: true,
            },
          ],
          geodata_layers: [],
          metrics: {
            agent_execution_time: 3.5,
            token_usage: { total: 120 },
          },
        },
      },
      {
        event: "done",
        data: { status: "complete" },
      },
    ]);

    const input = page.getByPlaceholder("Ask about maps, search for data, or request analysis...");
    await input.fill("Find rivers");
    await input.press("Enter");

    // Wait for results
    await page.waitForTimeout(2000);

    // Verify geodata results are displayed
    const resultsList = page.locator(".search-results");
    await expect(resultsList).toBeVisible();

    // Should show the river result
    await expect(page.locator("text=Rhine River")).toBeVisible();
  });

  test("should handle network errors gracefully", async ({ page }) => {
    // Simulate network error
    await page.route("**/api/chat/stream", async (route) => {
      await route.abort("failed");
    });

    const input = page.getByPlaceholder("Ask about maps, search for data, or request analysis...");
    await input.fill("Test error");
    await input.press("Enter");

    // Should show error message
    await page.waitForTimeout(1000);

    // Loading should stop
    await expect(input).toBeEnabled();
  });

  test("should disable input during streaming", async ({ page }) => {
    await mockSSEStream(page, [
      {
        event: "llm_token",
        data: { token: "Streaming..." },
      },
      {
        event: "result",
        data: {
          messages: [{ type: "ai", content: "Done" }],
          geodata_results: [],
          geodata_layers: [],
          metrics: {},
        },
      },
      {
        event: "done",
        data: { status: "complete" },
      },
    ]);

    const input = page.getByPlaceholder("Ask about maps, search for data, or request analysis...");
    await input.fill("Test");
    await input.press("Enter");

    // Input should be disabled during streaming
    await expect(input).toBeDisabled();

    // Wait for completion
    await page.waitForTimeout(2000);

    // Input should be enabled again
    await expect(input).toBeEnabled();
  });
});

test.describe("Tool Progress UI", () => {
  test("should animate tool completion", async ({ page }) => {
    await page.route("**/api/settings/options", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          model_settings: { llm_provider: "openai", model_name: "gpt-4o-mini" },
          tools: {},
        }),
      });
    });

    await page.goto("http://localhost:3000/map");
    await page.waitForLoadState("networkidle");

    await mockSSEStream(page, [
      {
        event: "tool_start",
        data: { tool: "test_tool", input: {} },
      },
      {
        event: "tool_end",
        data: { tool: "test_tool", output: "Success" },
      },
      {
        event: "result",
        data: {
          messages: [{ type: "ai", content: "Done" }],
          geodata_results: [],
          geodata_layers: [],
          metrics: {},
        },
      },
      {
        event: "done",
        data: { status: "complete" },
      },
    ]);

    const input = page.getByPlaceholder("Ask about maps, search for data, or request analysis...");
    await input.fill("Test animation");
    await input.press("Enter");

    // Wait for tool to appear
    const toolItem = page.locator(".tool-progress-item");
    await expect(toolItem).toBeVisible({ timeout: 5000 });

    // Check that it has the running class
    await expect(toolItem).toHaveClass(/tool-progress-running/);

    // Wait for completion
    await page.waitForTimeout(500);

    // Check that it has the complete class
    await expect(toolItem).toHaveClass(/tool-progress-complete/);
  });

  test("should format tool names correctly", async ({ page }) => {
    await page.route("**/api/settings/options", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          model_settings: { llm_provider: "openai", model_name: "gpt-4o-mini" },
          tools: {},
        }),
      });
    });

    await page.goto("http://localhost:3000/map");

    await mockSSEStream(page, [
      {
        event: "tool_start",
        data: { tool: "overpass_search_tool", input: {} },
      },
      {
        event: "tool_end",
        data: { tool: "overpass_search_tool", output: "Done" },
      },
      {
        event: "result",
        data: {
          messages: [{ type: "ai", content: "Done" }],
          geodata_results: [],
          geodata_layers: [],
          metrics: {},
        },
      },
      {
        event: "done",
        data: { status: "complete" },
      },
    ]);

    const input = page.getByPlaceholder("Ask about maps, search for data, or request analysis...");
    await input.fill("Test");
    await input.press("Enter");

    // Tool name should be formatted from snake_case to Title Case
    const toolName = page.locator(".tool-progress-name");
    await expect(toolName).toContainText("Overpass Search Tool");
  });
});
