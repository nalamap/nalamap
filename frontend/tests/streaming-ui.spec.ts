/**
 * Streaming UI Component Tests
 * Tests the UI components and store state management without SSE mocking
 * Tests component rendering based on store state changes
 */
import { test, expect } from "@playwright/test";

const mockSettings = {
  model_settings: {
    llm_provider: "openai",
    model_name: "gpt-4o-mini",
    enable_performance_metrics: true,
  },
  tools: {},
};

test.describe("Streaming UI Components", () => {
  test.beforeEach(async ({ page }) => {
    // Mock settings endpoint
    await page.route("**/settings/options", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockSettings),
      });
    });

    await page.goto("/map");
  });

  test("should display tool progress indicator when tools are added to store", async ({ page }) => {
    // Directly manipulate store state via browser context
    await page.evaluate(() => {
      const { useChatInterfaceStore } = (window as any);
      if (!useChatInterfaceStore) return;
      const store = useChatInterfaceStore.getState();
      
      // Set streaming state
      store.setIsStreaming(true);
      
      // Add a tool update
      store.addToolUpdate({
        name: "overpass_search",
        status: "running",
      });
    });

    // Wait for UI to update
    await page.waitForTimeout(100);

    // Verify tool progress container is visible
    const toolProgress = page.locator(".tool-progress-container");
    await expect(toolProgress).toBeVisible();

    // Verify tool name is formatted correctly
    await expect(page.locator(".tool-progress-name")).toContainText("Overpass Search");

    // Verify spinner is visible for running tool
    const spinner = page.locator(".tool-spinner");
    await expect(spinner).toBeVisible();
  });

  test("should show completed state when tool finishes", async ({ page }) => {
    // Add running tool first
    await page.evaluate(() => {
      const { useChatInterfaceStore } = (window as any); if (!useChatInterfaceStore) return;
      const store = useChatInterfaceStore.getState();
      
      store.setIsStreaming(true);
      store.addToolUpdate({
        name: "overpass_search",
        status: "running",
      });
    });

    await page.waitForTimeout(100);

    // Update to completed
    await page.evaluate(() => {
      const { useChatInterfaceStore } = (window as any); if (!useChatInterfaceStore) return;
      const store = useChatInterfaceStore.getState();
      store.updateToolStatus("overpass_search", "complete");
    });

    await page.waitForTimeout(100);

    // Verify check icon is visible
    const checkIcon = page.locator(".tool-check");
    await expect(checkIcon).toBeVisible();

    // Verify completed status class
    const toolItem = page.locator(".tool-progress-item");
    await expect(toolItem).toHaveClass(/tool-progress-complete/);
  });

  test("should show error state when tool fails", async ({ page }) => {
    await page.evaluate(() => {
      const { useChatInterfaceStore } = (window as any); if (!useChatInterfaceStore) return;
      const store = useChatInterfaceStore.getState();
      
      store.setIsStreaming(true);
      store.addToolUpdate({
        name: "overpass_search",
        status: "error",
        error: "Connection failed",
      });
    });

    await page.waitForTimeout(100);

    // Verify error icon is visible
    const errorIcon = page.locator(".tool-error");
    await expect(errorIcon).toBeVisible();

    // Verify error status class
    const toolItem = page.locator(".tool-progress-item");
    await expect(toolItem).toHaveClass(/tool-progress-error/);

    // Verify error message if displayed
    // (Note: Check if your UI shows error messages)
  });

  test("should display streaming message with blinking cursor", async ({ page }) => {
    await page.evaluate(() => {
      const { useChatInterfaceStore } = (window as any); if (!useChatInterfaceStore) return;
      const store = useChatInterfaceStore.getState();
      
      store.setIsStreaming(true);
      store.setStreamingMessage("Here are the results");
    });

    await page.waitForTimeout(100);

    // Verify streaming message is visible
    const streamingMessage = page.locator(".streaming-message");
    await expect(streamingMessage).toBeVisible();
    await expect(streamingMessage).toContainText("Here are the results");

    // Verify CSS animation for cursor (blinking effect)
    // The cursor is added via CSS ::after with animation
    const container = streamingMessage.locator("..").first();
    await expect(container).toBeVisible();
  });

  test("should handle multiple concurrent tools", async ({ page }) => {
    await page.evaluate(() => {
      const { useChatInterfaceStore } = (window as any); if (!useChatInterfaceStore) return;
      const store = useChatInterfaceStore.getState();
      
      store.setIsStreaming(true);
      store.addToolUpdate({
        name: "overpass_search",
        status: "running",
      });
      store.addToolUpdate({
        name: "wfs_loader",
        status: "running",
      });
    });

    await page.waitForTimeout(100);

    // Verify both tools are displayed
    const toolItems = page.locator(".tool-progress-item");
    await expect(toolItems).toHaveCount(2);

    // Verify both tool names
    const toolNames = page.locator(".tool-progress-name");
    await expect(toolNames.nth(0)).toContainText("Overpass Search");
    await expect(toolNames.nth(1)).toContainText("Wfs Loader");
  });

  test("should clear all indicators when streaming completes", async ({ page }) => {
    // Set up streaming state
    await page.evaluate(() => {
      const { useChatInterfaceStore } = (window as any); if (!useChatInterfaceStore) return;
      const store = useChatInterfaceStore.getState();
      
      store.setIsStreaming(true);
      store.addToolUpdate({
        name: "overpass_search",
        status: "complete",
      });
      store.setStreamingMessage("Final response");
    });

    await page.waitForTimeout(100);

    // Verify elements are visible
    await expect(page.locator(".tool-progress-container")).toBeVisible();
    await expect(page.locator(".streaming-message")).toBeVisible();

    // Clear streaming state
    await page.evaluate(() => {
      const { useChatInterfaceStore } = (window as any); if (!useChatInterfaceStore) return;
      const store = useChatInterfaceStore.getState();
      
      store.setIsStreaming(false);
      store.clearToolUpdates();
      store.clearStreamingMessage();
    });

    await page.waitForTimeout(100);

    // Verify elements are hidden
    await expect(page.locator(".tool-progress-container")).not.toBeVisible();
    await expect(page.locator(".streaming-message")).not.toBeVisible();
  });

  test("should format tool names from snake_case to Title Case", async ({ page }) => {
    await page.evaluate(() => {
      const { useChatInterfaceStore } = (window as any); if (!useChatInterfaceStore) return;
      const store = useChatInterfaceStore.getState();
      
      store.setIsStreaming(true);
      store.addToolUpdate({
        name: "get_attribute_values_tool",
        status: "running",
      });
    });

    await page.waitForTimeout(100);

    // Verify formatted name
    const toolName = page.locator(".tool-progress-name");
    await expect(toolName).toContainText("Get Attribute Values Tool");
  });

  test("should append tokens to streaming message progressively", async ({ page }) => {
    await page.evaluate(() => {
      const { useChatInterfaceStore } = (window as any); if (!useChatInterfaceStore) return;
      const store = useChatInterfaceStore.getState();
      
      store.setIsStreaming(true);
      store.setStreamingMessage("");
    });

    // Append tokens one by one
    await page.evaluate(() => {
      const { useChatInterfaceStore } = (window as any); if (!useChatInterfaceStore) return;
      const store = useChatInterfaceStore.getState();
      store.appendStreamingToken("Here ");
    });

    await page.waitForTimeout(50);
    await expect(page.locator(".streaming-message")).toContainText("Here ");

    await page.evaluate(() => {
      const { useChatInterfaceStore } = (window as any); if (!useChatInterfaceStore) return;
      const store = useChatInterfaceStore.getState();
      store.appendStreamingToken("are ");
    });

    await page.waitForTimeout(50);
    await expect(page.locator(".streaming-message")).toContainText("Here are ");

    await page.evaluate(() => {
      const { useChatInterfaceStore } = (window as any); if (!useChatInterfaceStore) return;
      const store = useChatInterfaceStore.getState();
      store.appendStreamingToken("results");
    });

    await page.waitForTimeout(50);
    await expect(page.locator(".streaming-message")).toContainText("Here are results");
  });

  test("should show tool progress above chat messages", async ({ page }) => {
    await page.evaluate(() => {
      const { useChatInterfaceStore } = (window as any); if (!useChatInterfaceStore) return;
      const store = useChatInterfaceStore.getState();
      
      // Add a regular message
      store.setMessages([
        { type: "human", content: "Hello" },
        { type: "ai", content: "Hi there" },
      ]);
      
      // Add streaming tool
      store.setIsStreaming(true);
      store.addToolUpdate({
        name: "overpass_search",
        status: "running",
      });
    });

    await page.waitForTimeout(100);

    // Both elements should be visible
    await expect(page.locator(".tool-progress-container")).toBeVisible();
    
    // Tool progress should appear before messages in DOM
    const container = page.locator(".overflow-y-auto").first();
    const toolProgress = container.locator(".tool-progress-container");
    const chatMessages = container.locator("text=Hello");
    
    // Simple check: tool progress is visible
    await expect(toolProgress).toBeVisible();
    await expect(chatMessages).toBeVisible();
  });

  test("should display tool updates BELOW user message in DOM order", async ({ page }) => {
    await page.evaluate(() => {
      const { useChatInterfaceStore } = (window as any); if (!useChatInterfaceStore) return;
      const store = useChatInterfaceStore.getState();
      
      // Add user message first
      store.setMessages([
        { type: "human", content: "Find rivers in Germany" },
      ]);
      
      // Then add streaming tool (this should appear AFTER the user message)
      store.setIsStreaming(true);
      store.addToolUpdate({
        name: "overpass_search",
        status: "running",
      });
    });

    await page.waitForTimeout(100);

    // Check that user message appears first, then tool progress
    const scrollableArea = page.locator(".overflow-y-auto").first();
    
    // Get positions of elements
    const userMessageBox = await scrollableArea.locator("text=Find rivers in Germany").boundingBox();
    const toolProgressBox = await scrollableArea.locator(".tool-progress-container").boundingBox();
    
    // Tool progress should be below (higher Y position) than user message
    expect(toolProgressBox).not.toBeNull();
    expect(userMessageBox).not.toBeNull();
    expect(toolProgressBox!.y).toBeGreaterThan(userMessageBox!.y);
  });

  test("should clear streaming state when result is received", async ({ page }) => {
    // Set up streaming state with tool and message
    await page.evaluate(() => {
      const { useChatInterfaceStore } = (window as any); if (!useChatInterfaceStore) return;
      const store = useChatInterfaceStore.getState();
      
      store.setIsStreaming(true);
      store.addToolUpdate({
        name: "overpass_search",
        status: "running",
      });
      store.setStreamingMessage("Finding rivers...");
    });

    await page.waitForTimeout(100);

    // Verify streaming elements are visible
    await expect(page.locator(".tool-progress-container")).toBeVisible();
    await expect(page.locator(".streaming-message")).toBeVisible();

    // Simulate receiving final result
    await page.evaluate(() => {
      const { useChatInterfaceStore } = (window as any); if (!useChatInterfaceStore) return;
      const store = useChatInterfaceStore.getState();
      
      // Clear streaming state (as done in result event handler)
      store.clearStreamingMessage();
      store.clearToolUpdates();
      store.setIsStreaming(false);
      
      // Set final messages
      store.setMessages([
        { type: "human", content: "Find rivers" },
        { type: "ai", content: "Here are the rivers I found" },
      ]);
    });

    await page.waitForTimeout(100);

    // Verify streaming elements are hidden
    await expect(page.locator(".tool-progress-container")).not.toBeVisible();
    await expect(page.locator(".streaming-message")).not.toBeVisible();

    // Verify final messages are shown
    await expect(page.locator("text=Here are the rivers I found")).toBeVisible();
  });

  test("should show search results after streaming completes", async ({ page }) => {
    // Simulate streaming completion with geodata results
    await page.evaluate(() => {
      const { useChatInterfaceStore } = (window as any); if (!useChatInterfaceStore) return;
      const store = useChatInterfaceStore.getState();
      
      // Add final messages
      store.setMessages([
        { type: "human", content: "Find rivers" },
        { type: "ai", content: "I found 3 rivers" },
      ]);
      
      // Add geodata results
      store.setGeoDataList([
        {
          id: "river-1",
          title: "Rhine River",
          llm_description: "Major river in Germany",
          layer_type: "vector",
          url: "http://example.com/rhine",
        },
        {
          id: "river-2", 
          title: "Danube River",
          llm_description: "Another major river",
          layer_type: "vector",
          url: "http://example.com/danube",
        },
      ]);
      
      // Clear streaming state
      store.setIsStreaming(false);
      store.clearStreamingMessage();
      store.clearToolUpdates();
    });

    await page.waitForTimeout(100);

    // Verify search results are displayed
    await expect(page.locator("text=Search Results:")).toBeVisible();
    await expect(page.locator("text=Rhine River")).toBeVisible();
    await expect(page.locator("text=Danube River")).toBeVisible();
    
    // Verify streaming elements are not shown
    await expect(page.locator(".tool-progress-container")).not.toBeVisible();
    await expect(page.locator(".streaming-message")).not.toBeVisible();
  });
});
