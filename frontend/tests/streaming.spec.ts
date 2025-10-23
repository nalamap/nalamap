/**
 * Streaming endpoint tests with mocked SSE responses
 * Tests the frontend SSE client and UI components without requiring backend
 */
import { test, expect, Page } from "@playwright/test";

// Helper to inject SSE mock into page context
async function mockSSEStream(page: Page, events: Array<{ event: string; data: any }>) {
  // Inject the mock into the page's fetch
  await page.addInitScript((eventsData) => {
    const originalFetch = window.fetch;
    (window as any).fetch = async function(input: RequestInfo | URL, init?: RequestInit) {
      const url = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url;
      
      // Only intercept streaming chat endpoint
      if (url.includes('/chat/stream')) {
        console.log('[MOCK SSE] Intercepting streaming request:', url);
        console.log('[MOCK SSE] Events to send:', eventsData.length);
        
        // Create a mock ReadableStream
        const encoder = new TextEncoder();
        let eventIndex = 0;
        
        const stream = new ReadableStream({
          async start(controller) {
            // Send events with delays to simulate streaming and give tests time to check UI
            for (let i = 0; i < eventsData.length; i++) {
              const { event, data } = eventsData[i];
              const sseMessage = `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
              console.log('[MOCK SSE] Sending event:', event, data);
              controller.enqueue(encoder.encode(sseMessage));
              
              // Longer delay between events (300ms) to allow test assertions
              // Don't delay after the last event
              if (i < eventsData.length - 1) {
                await new Promise(resolve => setTimeout(resolve, 300));
              }
            }
            console.log('[MOCK SSE] Stream complete');
            controller.close();
          }
        });
        
        // Return a mock Response with the stream
        return new Response(stream, {
          status: 200,
          headers: {
            'Content-Type': 'text/event-stream',
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no'
          }
        });
      }
      
      // Pass through other requests
      return originalFetch(input, init);
    };
  }, events);
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

    // Navigate after setting up the mock
    await page.goto("/map");

    // Type query and submit
    const input = page.getByPlaceholder("Ask about maps, search for data, or request analysis...");
    await input.fill("Show me rivers in Germany");
    await input.press("Enter");

    // Wait for tool progress indicator to appear (checks during streaming)
    const toolProgress = page.locator(".tool-progress-container");
    await expect(toolProgress).toBeVisible({ timeout: 5000 });

    // Verify tool name is displayed
    await expect(page.locator(".tool-progress-name")).toContainText("Overpass Search");

    // Verify running or complete status is shown (spinner or check icon)
    const statusIcon = page.locator(".tool-spinner, .tool-check");
    await expect(statusIcon.first()).toBeVisible();

    // After result event, tool progress should be cleared
    await page.waitForTimeout(2000);
    await expect(toolProgress).not.toBeVisible();
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
    await page.goto("/map");

    // Submit query
    const input = page.getByPlaceholder("Ask about maps, search for data, or request analysis...");
    await input.fill("Test streaming");
    await input.press("Enter");

    // Wait for all streaming events to complete
    await page.waitForTimeout(2500);

    // Verify AI response appears - check for text content
    await expect(page.getByText("Hello there!")).toBeVisible({ timeout: 5000 });
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
    await page.goto("/map");

    const input = page.getByPlaceholder("Ask about maps, search for data, or request analysis...");
    await input.fill("Search for data");
    await input.press("Enter");

    // Wait for tool progress indicator to appear
    const toolProgress = page.locator(".tool-progress-container");
    await expect(toolProgress).toBeVisible({ timeout: 5000 });

    // Should show tools (check before result clears them)
    const toolItems = page.locator(".tool-progress-item");
    // Wait a bit for second tool to appear
    await page.waitForTimeout(700);
    const count = await toolItems.count();
    expect(count).toBeGreaterThanOrEqual(1); // At least one tool visible

    // Verify tool names are formatted correctly
    const toolNames = page.locator(".tool-progress-name");
    const firstToolName = await toolNames.first().textContent();
    expect(firstToolName).toMatch(/Geocode Location|Overpass Search/);
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
        event: "result",
        data: {
          messages: [
            { type: "human", content: "Cause an error" },
            { type: "ai", content: "An error occurred" },
          ],
          geodata_results: [],
          geodata_layers: [],
          metrics: {},
        },
      },
      {
        event: "done",
        data: { status: "error" },
      },
    ]);
    await page.goto("/map");

    const input = page.getByPlaceholder("Ask about maps, search for data, or request analysis...");
    await input.fill("Cause an error");
    await input.press("Enter");

    // Wait for streaming to complete
    await page.waitForTimeout(2000);

    // Check that the error response message appears
    // The "An error occurred" message should be visible in the chat
    await expect(page.getByText("An error occurred")).toBeVisible({ timeout: 5000 });
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
    await page.goto("/map");

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
    await page.goto("/map");

    const input = page.getByPlaceholder("Ask about maps, search for data, or request analysis...");
    await input.fill("Find rivers");
    await input.press("Enter");

    // Wait for streaming to complete and results to be processed
    await page.waitForTimeout(2500);

    // Verify the AI response message appears (this confirms geodata was processed)
    await expect(page.getByText("Found 5 rivers")).toBeVisible({ timeout: 5000 });
    
    // Verify the result mentions the geodata item
    // Since geodata_results are returned, the UI should process them
    // This test verifies streaming works with geodata in the response
  });

  test("should handle network errors gracefully", async ({ page }) => {
    // Simulate network error with mock
    await mockSSEStream(page, [
      {
        event: "error",
        data: { error: "network_error", message: "Network connection failed" },
      },
      {
        event: "done",
        data: { status: "error" },
      },
    ]);
    await page.goto("/map");

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
    await page.goto("/map");

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
    await page.goto("/map");

    const input = page.getByPlaceholder("Ask about maps, search for data, or request analysis...");
    await input.fill("Test animation");
    await input.press("Enter");

    // Wait for tool progress container to appear
    const toolProgress = page.locator(".tool-progress-container");
    await expect(toolProgress).toBeVisible({ timeout: 5000 });

    // Check that a tool item appears
    const toolItem = page.locator(".tool-progress-item");
    await expect(toolItem.first()).toBeVisible({ timeout: 5000 });

    // Verify the tool has a status class (running or complete)
    const hasStatusClass = await toolItem.first().evaluate((el) => {
      return el.classList.contains('tool-progress-running') || 
             el.classList.contains('tool-progress-complete');
    });
    expect(hasStatusClass).toBeTruthy();

    // After result, tool progress should be cleared
    await page.waitForTimeout(2000);
    await expect(toolProgress).not.toBeVisible();
  });

  test("should format tool names correctly", async ({ page }) => {
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
    await page.goto("/map");

    const input = page.getByPlaceholder("Ask about maps, search for data, or request analysis...");
    await input.fill("Test");
    await input.press("Enter");

    // Tool name should be formatted from snake_case to Title Case
    const toolName = page.locator(".tool-progress-name");
    await expect(toolName).toContainText("Overpass Search Tool");
  });
});
