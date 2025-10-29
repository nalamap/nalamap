import { Page, expect, Locator } from "@playwright/test";

/**
 * E2E Test Utilities for NaLaMap
 * 
 * Generic test utilities for E2E testing of NaLaMap features:
 * - Chat interface interactions
 * - Map layer management
 * - GeoServer integration
 * - LLM model selection
 * - Tool execution validation
 * 
 * Usage:
 * ```typescript
 * import { E2ETestUtils } from "./utils/e2e-utils";
 * 
 * test("Geocoding test", async ({ page }) => {
 *   const utils = new E2ETestUtils(page);
 *   await utils.goto();
 *   await utils.sendMessage("Find hospitals in Paris, France");
 *   await utils.waitForAIResponse();
 *   const response = await utils.getLastAIMessage();
 *   expect(response).toContain("hospital");
 * });
 * ```
 */

export interface ChatResponse {
  messages: Array<{ type: string; content: string }>;
  streaming?: boolean;
  streamResponse?: any;
  duration?: number;
}

export interface ToolProgress {
  name: string;
  status: "running" | "complete" | "error";
  element: Locator;
}

export interface ValidationOptions {
  keywords?: string[];
  minKeywordMatch?: number; // 0-1 (percentage)
  timeout?: number;
}

export interface WorkflowStepOptions {
  label?: string;
  waitForLayers?: boolean;
  screenshot?: boolean;
  timeout?: number;
}

export class E2ETestUtils {
  private page: Page;
  private backendUrl: string;
  private frontendUrl: string;

  constructor(
    page: Page,
    backendUrl: string = "http://localhost:8000",
    frontendUrl: string = "http://localhost:3000"
  ) {
    this.page = page;
    this.backendUrl = backendUrl;
    this.frontendUrl = frontendUrl;
  }

  // ============================================================================
  // NAVIGATION & SETUP
  // ============================================================================

  /**
   * Navigate to the application and wait for it to be ready
   */
  async goto(url?: string): Promise<void> {
    const targetUrl = url || this.frontendUrl;
    console.log(`🌐 Navigating to: ${targetUrl}`);
    await this.page.goto(targetUrl);

    // Wait for chat input to be ready
    await expect(
      this.page.getByPlaceholder(/Type a chat command/i)
    ).toBeVisible({ timeout: 30000 });

    console.log("✅ Application loaded and ready");
  }

  /**
   * Get the chat input field
   */
  getChatInput(): Locator {
    return this.page.getByPlaceholder(/Type a chat command/i);
  }

  // ============================================================================
  // CHAT INTERACTIONS
  // ============================================================================

  /**
   * Send a chat message and wait for streaming response
   * 
   * @param message - The message to send
   * @param label - Optional label for logging (e.g., "Q1", "Geocoding query")
   * @param waitForCompletion - Whether to wait for AI response (default: true)
   * @returns Response data including messages and timing
   */
  async sendMessage(
    message: string,
    label?: string,
    waitForCompletion: boolean = true
  ): Promise<ChatResponse> {
    const startTime = Date.now();
    const logPrefix = label ? `[${label}]` : "";

    console.log(`${logPrefix} 💬 Sending: "${message}"`);

    const input = this.getChatInput();
    await input.fill(message);
    await input.press("Enter");

    if (waitForCompletion) {
      await this.waitForAIResponse();
    }

    const duration = Date.now() - startTime;
    console.log(`${logPrefix} ⏱️  Response received in ${duration}ms`);

    return {
      messages: [],
      streaming: true,
      duration,
    };
  }

  /**
   * Wait for AI response to appear and complete
   * 
   * @param timeout - Maximum time to wait in milliseconds (default: 120s)
   */
  async waitForAIResponse(timeout: number = 120_000): Promise<void> {
    // Wait for AI message to appear
    await expect(this.page.locator(".message-ai").last()).toBeVisible({
      timeout,
    });

    // Wait for streaming to complete (no "..." indicator)
    await this.page.waitForFunction(
      () => {
        const lastMsg = document.querySelector(".message-ai:last-child");
        return lastMsg && !lastMsg.textContent?.includes("...");
      },
      { timeout }
    );

    console.log("✅ AI response complete");
  }

  /**
   * Get the last AI message content
   */
  async getLastAIMessage(): Promise<string> {
    const lastMessage = this.page.locator(".message-ai").last();
    await expect(lastMessage).toBeVisible();
    const content = await lastMessage.textContent();
    return content || "";
  }

  /**
   * Get all AI messages
   */
  async getAllAIMessages(): Promise<string[]> {
    const messages = await this.page.locator(".message-ai").all();
    const texts = await Promise.all(messages.map((msg) => msg.textContent()));
    return texts.map((text) => text || "");
  }

  // ============================================================================
  // VALIDATION HELPERS
  // ============================================================================

  /**
   * Validate response contains expected keywords
   * 
   * @param response - The response text to validate
   * @param keywords - Array of keywords to check for
   * @param minMatchPercentage - Minimum percentage of keywords that must match (0-1)
   * @returns true if validation passes
   */
  validateResponse(
    response: string,
    keywords: string[],
    minMatchPercentage: number = 0.5
  ): boolean {
    const lowerResponse = response.toLowerCase();
    const matches = keywords.filter((keyword) =>
      lowerResponse.includes(keyword.toLowerCase())
    );

    const matchPercentage = matches.length / keywords.length;
    const passed = matchPercentage >= minMatchPercentage;

    console.log(
      `🔍 Keyword validation: ${matches.length}/${keywords.length} matched (${(matchPercentage * 100).toFixed(0)}%)`
    );
    console.log(`   Matched: ${matches.join(", ")}`);

    if (!passed) {
      const missing = keywords.filter((k) => !matches.includes(k));
      console.log(`   Missing: ${missing.join(", ")}`);
    }

    return passed;
  }

  /**
   * Assert response contains expected keywords (throws if validation fails)
   */
  assertResponseContains(
    response: string,
    keywords: string[],
    minMatchPercentage: number = 0.5
  ): void {
    const passed = this.validateResponse(
      response,
      keywords,
      minMatchPercentage
    );
    if (!passed) {
      throw new Error(
        `Response validation failed: expected ${(minMatchPercentage * 100).toFixed(0)}% of keywords to match`
      );
    }
  }

  // ============================================================================
  // TOOL EXECUTION
  // ============================================================================

  /**
   * Wait for a specific tool to start executing
   * 
   * @param toolName - Name of the tool (e.g., "search_layers", "geocode")
   * @param timeout - Maximum time to wait
   */
  async waitForToolStart(
    toolName: string,
    timeout: number = 60_000
  ): Promise<void> {
    await expect(
      this.page.locator(`.tool-call`).filter({ hasText: toolName })
    ).toBeVisible({ timeout });
    console.log(`🔧 Tool started: ${toolName}`);
  }

  /**
   * Wait for a specific tool to complete
   * 
   * @param toolName - Name of the tool
   * @param timeout - Maximum time to wait
   */
  async waitForToolComplete(
    toolName: string,
    timeout: number = 120_000
  ): Promise<void> {
    const toolElement = this.page
      .locator(`.tool-call`)
      .filter({ hasText: toolName });

    await expect(toolElement).toBeVisible({ timeout: 10_000 });

    // Wait for completion indicator (✓ or similar)
    await this.page.waitForFunction(
      (name) => {
        const tools = Array.from(document.querySelectorAll(".tool-call"));
        const tool = tools.find((t) => t.textContent?.includes(name));
        return tool && tool.textContent?.includes("✓");
      },
      toolName,
      { timeout }
    );

    console.log(`✅ Tool completed: ${toolName}`);
  }

  /**
   * Wait for all currently running tools to complete
   */
  async waitForAllToolsComplete(timeout: number = 180_000): Promise<void> {
    console.log("⏳ Waiting for all tools to complete...");

    await this.page.waitForFunction(
      () => {
        const tools = document.querySelectorAll(".tool-call");
        return Array.from(tools).every((tool) =>
          tool.textContent?.includes("✓")
        );
      },
      { timeout }
    );

    console.log("✅ All tools completed");
  }

  /**
   * Get all tool execution statuses
   */
  async getToolStatuses(): Promise<ToolProgress[]> {
    const toolElements = await this.page.locator(".tool-call").all();

    return Promise.all(
      toolElements.map(async (element) => {
        const text = (await element.textContent()) || "";
        const name = text.split("\n")[0] || "Unknown";
        const status = text.includes("✓")
          ? "complete"
          : text.includes("❌")
            ? "error"
            : "running";

        return { name, status, element };
      })
    );
  }

  // ============================================================================
  // LAYER MANAGEMENT
  // ============================================================================

  /**
   * Wait for a new layer to be added to the map
   * 
   * @param expectedCount - Expected layer count after addition (optional)
   * @param timeout - Maximum time to wait
   */
  async waitForLayerAdded(
    expectedCount?: number,
    timeout: number = 60_000
  ): Promise<void> {
    if (expectedCount !== undefined) {
      await this.page.waitForFunction(
        (count) => {
          const layers = document.querySelectorAll(".layer-item");
          return layers.length >= count;
        },
        expectedCount,
        { timeout }
      );
      console.log(`✅ Layer added (total: ${expectedCount})`);
    } else {
      // Just wait for any layer to appear
      await expect(this.page.locator(".layer-item").first()).toBeVisible({
        timeout,
      });
      console.log("✅ Layer added");
    }
  }

  /**
   * Get current number of layers on the map
   */
  async getLayerCount(): Promise<number> {
    const layers = await this.page.locator(".layer-item").count();
    return layers;
  }

  /**
   * Get all layer names
   */
  async getLayerNames(): Promise<string[]> {
    const layerElements = await this.page.locator(".layer-item").all();
    return Promise.all(
      layerElements.map(async (el) => (await el.textContent()) || "")
    );
  }

  // ============================================================================
  // WORKFLOW HELPERS
  // ============================================================================

  /**
   * Execute a complete workflow step: send message, wait for response, validate
   * 
   * @param message - The message to send
   * @param expectedKeywords - Keywords to validate in response
   * @param options - Additional options for the workflow step
   */
  async executeWorkflowStep(
    message: string,
    expectedKeywords: string[],
    options: WorkflowStepOptions = {}
  ): Promise<string> {
    const {
      label = "",
      waitForLayers = false,
      screenshot = false,
      timeout = 120_000,
    } = options;

    // Send message
    await this.sendMessage(message, label, false);

    // Wait for AI response
    await this.waitForAIResponse(timeout);

    // Get response
    const response = await this.getLastAIMessage();

    // Validate keywords
    this.assertResponseContains(response, expectedKeywords, 0.3);

    // Wait for layers if requested
    if (waitForLayers) {
      await this.waitForLayerAdded(undefined, 30_000);
    }

    // Take screenshot if requested
    if (screenshot && label) {
      await this.screenshot(`${label.toLowerCase().replace(/\s+/g, "-")}`);
    }

    return response;
  }

  // ============================================================================
  // SETTINGS & CONFIGURATION
  // ============================================================================

  /**
   * Navigate to settings page
   */
  async gotoSettings(): Promise<void> {
    console.log("⚙️  Navigating to settings page");
    await this.page.goto(`${this.frontendUrl}/settings`);
    await this.page.waitForLoadState("networkidle");
    console.log("✅ Settings page loaded");
  }

  /**
   * Select an LLM provider and model
   * 
   * @param provider - Provider name (e.g., "openai", "google", "anthropic")
   * @param model - Model name (e.g., "gpt-4", "gemini-1.5-flash")
   * @returns Object containing the selected provider and model
   */
  async selectLLM(
    provider: string,
    model: string
  ): Promise<{ provider: string; model: string }> {
    console.log(`🤖 Selecting LLM: ${provider} - ${model}`);

    // Navigate to settings if not already there
    if (!this.page.url().includes("/settings")) {
      await this.gotoSettings();
    }

    // Expand Model Settings section
    const modelSettingsButton = this.page.getByRole("button", {
      name: /Model Settings/i,
    });
    await modelSettingsButton.click();

    // Select provider
    const providerSelect = this.page.locator('select[name="provider"]');
    await providerSelect.selectOption(provider);

    // Wait for models to load
    await this.page.waitForTimeout(500);

    // Select model
    const modelSelect = this.page.locator('select[name="model"]');
    await modelSelect.selectOption(model);

    console.log(`✅ Selected: ${provider} - ${model}`);

    return { provider, model };
  }

  /**
   * Add a custom GeoServer and optionally wait for preloading
   * 
   * @param url - GeoServer URL
   * @param name - Optional custom name for the GeoServer
   * @param waitForPreload - Whether to wait for layers to preload
   * @param timeout - Maximum time to wait for preload (default: 2 minutes)
   * @returns Object with status, duration, and layer count
   */
  async addGeoServer(
    url: string,
    name?: string,
    waitForPreload: boolean = true,
    timeout: number = 120_000
  ): Promise<{
    status: "complete" | "timeout" | "error";
    duration?: number;
    layersCount?: number;
  }> {
    console.log(`🗺️  Adding GeoServer: ${url}`);

    // Navigate to settings if not already there
    if (!this.page.url().includes("/settings")) {
      await this.gotoSettings();
    }

    // Find the GeoServer URL input
    const urlInput = this.page.locator('input[placeholder*="GeoServer URL"]');
    await urlInput.fill(url);

    if (name) {
      const nameInput = this.page.locator('input[placeholder*="name"]');
      await nameInput.fill(name);
    }

    // Click Add button
    const addButton = this.page.getByRole("button", { name: /Add.*Server/i });
    await addButton.click();

    if (!waitForPreload) {
      return { status: "complete" };
    }

    // Wait for preload to complete
    const startTime = Date.now();

    try {
      // Wait for preload status to change from "⏱️ Waiting" → "⏳ In Progress" → "✓ Complete"
      await this.page.waitForFunction(
        () => {
          const servers = document.querySelectorAll(".geoserver-item");
          const lastServer = servers[servers.length - 1];
          return lastServer?.textContent?.includes("✓");
        },
        { timeout }
      );

      const duration = Date.now() - startTime;

      // Extract layer count
      const serverItems = await this.page.locator(".geoserver-item").all();
      const lastServer = serverItems[serverItems.length - 1];
      const text = (await lastServer.textContent()) || "";
      const layerMatch = text.match(/(\d+)\s+layer/i);
      const layersCount = layerMatch ? parseInt(layerMatch[1]) : 0;

      console.log(
        `✅ GeoServer preloaded: ${layersCount} layers in ${duration}ms`
      );

      return { status: "complete", duration, layersCount };
    } catch (error) {
      console.log("⚠️  GeoServer preload timeout");
      return { status: "timeout" };
    }
  }

  /**
   * Get model cost information from UI
   */
  async getModelCosts(): Promise<{
    input?: number;
    output?: number;
    cache?: number;
  }> {
    const modelInfo = await this.page.locator(".model-info").textContent();
    if (!modelInfo) return {};

    const inputMatch = modelInfo.match(/Input:\s*\$?([\d.]+)/i);
    const outputMatch = modelInfo.match(/Output:\s*\$?([\d.]+)/i);
    const cacheMatch = modelInfo.match(/Cache:\s*\$?([\d.]+)/i);

    return {
      input: inputMatch ? parseFloat(inputMatch[1]) : undefined,
      output: outputMatch ? parseFloat(outputMatch[1]) : undefined,
      cache: cacheMatch ? parseFloat(cacheMatch[1]) : undefined,
    };
  }

  // ============================================================================
  // DEBUGGING & SCREENSHOTS
  // ============================================================================

  /**
   * Take a screenshot with a descriptive name
   */
  async screenshot(name: string): Promise<void> {
    const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
    await this.page.screenshot({
      path: `screenshots/${name}-${timestamp}.png`,
      fullPage: true,
    });
    console.log(`📸 Screenshot saved: ${name}-${timestamp}.png`);
  }

  /**
   * Log current page state (useful for debugging)
   */
  async logPageState(): Promise<void> {
    const url = this.page.url();
    const title = await this.page.title();
    const layerCount = await this.getLayerCount();
    const messages = await this.page.locator(".message-ai").count();

    console.log("📊 Page State:");
    console.log(`   URL: ${url}`);
    console.log(`   Title: ${title}`);
    console.log(`   Layers: ${layerCount}`);
    console.log(`   AI Messages: ${messages}`);
  }

  /**
   * Track timing for performance analysis
   */
  trackTiming(label: string): () => number {
    const startTime = Date.now();
    return () => {
      const duration = Date.now() - startTime;
      console.log(`⏱️  ${label}: ${duration}ms`);
      return duration;
    };
  }
}
