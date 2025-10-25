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
      description: "Example GeoServer",
    },
  ],
  model_options: {
    MockProvider: [{ name: "mock-model", max_tokens: 999 }],
  },
  session_id: "test-session",
};

test.describe("Chat interface", () => {
  test("sends a message and renders agent response", async ({ page }) => {
    await page.route("**/settings/options", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockSettings),
      });
    });

    const mockResponse = {
      messages: [
        { type: "human", content: "Hello agent!" },
        { type: "ai", content: "Mock agent response" },
      ],
      geodata_results: [],
      geodata_layers: [],
      metrics: {
        agent_execution_time: 1.5,
        token_usage: { total: 50, prompt: 25, completion: 25 },
      },
    };

    // Mock streaming endpoint
    await page.addInitScript((response) => {
      const originalFetch = window.fetch;
      (window as any).fetch = async function(input: RequestInfo | URL, init?: RequestInit) {
        const url = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url;
        
        if (url.includes('/chat/stream')) {
          console.log('[MOCK] Intercepting streaming chat request');
          const encoder = new TextEncoder();
          
          const stream = new ReadableStream({
            async start(controller) {
              // Send result event
              const resultMessage = `event: result\ndata: ${JSON.stringify(response)}\n\n`;
              controller.enqueue(encoder.encode(resultMessage));
              
              // Send done event
              const doneMessage = `event: done\ndata: ${JSON.stringify({ status: 'complete' })}\n\n`;
              controller.enqueue(encoder.encode(doneMessage));
              
              controller.close();
            }
          });
          
          return new Response(stream, {
            status: 200,
            headers: {
              'Content-Type': 'text/event-stream',
              'Cache-Control': 'no-cache'
            }
          });
        }
        
        return originalFetch(input, init);
      };
    }, mockResponse);

    await page.goto("/map");

    const chatInput = page.getByPlaceholder("Ask about maps, search for data, or request analysis...");
    await chatInput.fill("Hello agent!");
    await chatInput.press("Enter");
    
    // Wait for the streaming response to complete
    await page.waitForTimeout(500);

    await expect(page.getByText("Hello agent!").first()).toBeVisible();
    await expect(page.getByText("Mock agent response")).toBeVisible();
  });
});
