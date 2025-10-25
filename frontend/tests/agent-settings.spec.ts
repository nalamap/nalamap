import { test, expect } from "@playwright/test";

const mockSettings = {
  system_prompt: "You are a helpful geospatial assistant.",
  tool_options: {
    search: {
      default_prompt: "Search prompt",
      settings: {},
    },
  },
  example_geoserver_backends: [],
  model_options: {
    MockProvider: [{ name: "mock-model", max_tokens: 999 }],
  },
  color_settings: {
    primary: { shade_50: "#FFFFFF", shade_900: "#000000", shade_950: "#000000" },
    second_primary: { shade_50: "#FFFFFF", shade_900: "#000000", shade_950: "#000000" },
    secondary: { shade_50: "#FFFFFF", shade_900: "#000000", shade_950: "#000000" },
    tertiary: { shade_50: "#FFFFFF", shade_900: "#000000", shade_950: "#000000" },
    danger: { shade_50: "#FFFFFF", shade_900: "#000000", shade_950: "#000000" },
    warning: { shade_50: "#FFFFFF", shade_900: "#000000", shade_950: "#000000" },
    info: { shade_50: "#FFFFFF", shade_900: "#000000", shade_950: "#000000" },
    neutral: { shade_50: "#FFFFFF", shade_900: "#000000", shade_950: "#000000" },
    corporate_1: { shade_50: "#FFFFFF", shade_900: "#000000", shade_950: "#000000" },
    corporate_2: { shade_50: "#FFFFFF", shade_900: "#000000", shade_950: "#000000" },
    corporate_3: { shade_50: "#FFFFFF", shade_900: "#000000", shade_950: "#000000" },
  },
  session_id: "test-session-123",
};

test.describe("Agent Settings Component", () => {
  test("renders Agent Settings section", async ({ page }) => {
    // Mock the settings endpoint
    await page.route("**/settings/options", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockSettings),
      });
    });

    await page.goto("/settings");
    await page.waitForLoadState("networkidle");

    // Wait for Settings heading to be visible
    await expect(
      page.getByRole("heading", { level: 1, name: "Settings" }),
    ).toBeVisible();

    // Find the Agent Settings button
    const agentSettingsButton = page.locator("button:has-text('Agent Settings')");
    await agentSettingsButton.scrollIntoViewIfNeeded();
    await expect(agentSettingsButton).toBeVisible();
  });

  test("expands and shows system prompt textarea", async ({ page }) => {
    await page.route("**/settings/options", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockSettings),
      });
    });

    await page.goto("/settings");
    await page.waitForLoadState("networkidle");

    // Find and click the Agent Settings collapsible button
    const agentSettingsButton = page.locator("button:has-text('Agent Settings')");
    await agentSettingsButton.scrollIntoViewIfNeeded();
    await agentSettingsButton.click();

    // Wait for expansion
    await page.waitForTimeout(500);

    // Check system prompt textarea is visible
    const systemPromptTextarea = page.locator('textarea[placeholder*="system prompt"]');
    await expect(systemPromptTextarea).toBeVisible();
    await expect(systemPromptTextarea).toHaveValue("You are a helpful geospatial assistant.");
  });

  test("enables dynamic tool selection toggle", async ({ page }) => {
    await page.route("**/settings/options", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockSettings),
      });
    });

    await page.goto("/settings");
    await page.waitForLoadState("networkidle");

    // Expand Agent Settings
    const agentSettingsButton = page.locator("button:has-text('Agent Settings')");
    await agentSettingsButton.scrollIntoViewIfNeeded();
    await agentSettingsButton.click();
    await page.waitForTimeout(500);

    // Find the enable dynamic tools checkbox
    const dynamicToolsCheckbox = page.locator("#enable-dynamic-tools");
    await expect(dynamicToolsCheckbox).toBeVisible();
    await expect(dynamicToolsCheckbox).not.toBeChecked();

    // Toggle on
    await dynamicToolsCheckbox.click();
    await expect(dynamicToolsCheckbox).toBeChecked();

    // Wait for dynamic settings to appear
    await page.waitForTimeout(300);

    // Check that strategy selector is visible
    const strategySelect = page.locator('select').filter({ hasText: /Conservative|Semantic|Minimal|All Tools/ });
    await expect(strategySelect).toBeVisible();
  });

  test("shows tool selection strategy dropdown when enabled", async ({ page }) => {
    await page.route("**/settings/options", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockSettings),
      });
    });

    await page.goto("/settings");
    await page.waitForLoadState("networkidle");

    // Expand Agent Settings
    const agentSettingsButton = page.locator("button:has-text('Agent Settings')");
    await agentSettingsButton.scrollIntoViewIfNeeded();
    await agentSettingsButton.click();
    await page.waitForTimeout(500);

    // Enable dynamic tools
    const dynamicToolsCheckbox = page.locator("#enable-dynamic-tools");
    await dynamicToolsCheckbox.click();
    await page.waitForTimeout(500);

    // Check strategy select is visible
    const strategySelect = page.locator("label:has-text('Tool Selection Strategy')").locator("..").locator("select");
    await expect(strategySelect).toBeVisible();
    
    // Check default value is "conservative"
    await expect(strategySelect).toHaveValue("conservative");

    // Test changing strategy
    await strategySelect.selectOption("semantic");
    await expect(strategySelect).toHaveValue("semantic");

    await strategySelect.selectOption("minimal");
    await expect(strategySelect).toHaveValue("minimal");

    await strategySelect.selectOption("all");
    await expect(strategySelect).toHaveValue("all");
  });

  test("adjusts tool similarity threshold slider", async ({ page }) => {
    await page.route("**/settings/options", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockSettings),
      });
    });

    await page.goto("/settings");
    await page.waitForLoadState("networkidle");

    // Expand Agent Settings
    const agentSettingsButton = page.locator("button:has-text('Agent Settings')");
    await agentSettingsButton.scrollIntoViewIfNeeded();
    await agentSettingsButton.click();
    await page.waitForTimeout(500);

    // Enable dynamic tools
    const dynamicToolsCheckbox = page.locator("#enable-dynamic-tools");
    await dynamicToolsCheckbox.click();
    await page.waitForTimeout(500);

    // Find the threshold slider
    const thresholdSlider = page.locator('input[type="range"]');
    await expect(thresholdSlider).toBeVisible();

    // Check default value (0.3)
    await expect(thresholdSlider).toHaveValue("0.3");

    // Adjust slider
    await thresholdSlider.fill("0.5");
    await expect(thresholdSlider).toHaveValue("0.5");

    // Verify label updates
    const thresholdLabel = page.locator("label:has-text('Tool Similarity Threshold')");
    await expect(thresholdLabel).toContainText("0.50");
  });

  test("sets max tools per query input", async ({ page }) => {
    await page.route("**/settings/options", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockSettings),
      });
    });

    await page.goto("/settings");
    await page.waitForLoadState("networkidle");

    // Expand Agent Settings
    const agentSettingsButton = page.locator("button:has-text('Agent Settings')");
    await agentSettingsButton.scrollIntoViewIfNeeded();
    await agentSettingsButton.click();
    await page.waitForTimeout(500);

    // Enable dynamic tools
    const dynamicToolsCheckbox = page.locator("#enable-dynamic-tools");
    await dynamicToolsCheckbox.click();
    await page.waitForTimeout(500);

    // Find max tools input
    const maxToolsInput = page.locator('input[type="number"]');
    await expect(maxToolsInput).toBeVisible();

    // Default value is empty (null = unlimited)
    await expect(maxToolsInput).toHaveValue("");

    // Change value
    await maxToolsInput.fill("15");
    await expect(maxToolsInput).toHaveValue("15");
  });

  test("hides dynamic tool settings when toggle is off", async ({ page }) => {
    await page.route("**/settings/options", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockSettings),
      });
    });

    await page.goto("/settings");
    await page.waitForLoadState("networkidle");

    // Expand Agent Settings
    const agentSettingsButton = page.locator("button:has-text('Agent Settings')");
    await agentSettingsButton.scrollIntoViewIfNeeded();
    await agentSettingsButton.click();
    await page.waitForTimeout(500);

    // Enable dynamic tools first
    const dynamicToolsCheckbox = page.locator("#enable-dynamic-tools");
    await dynamicToolsCheckbox.click();
    await page.waitForTimeout(500);

    // Verify settings are visible
    const strategyLabel = page.locator("label:has-text('Tool Selection Strategy')");
    await expect(strategyLabel).toBeVisible();

    // Disable dynamic tools
    await dynamicToolsCheckbox.click();
    await page.waitForTimeout(500);

    // Verify settings are hidden
    await expect(strategyLabel).not.toBeVisible();
  });

  test("shows information banner when dynamic tools enabled", async ({ page }) => {
    await page.route("**/settings/options", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockSettings),
      });
    });

    await page.goto("/settings");
    await page.waitForLoadState("networkidle");

    // Expand Agent Settings
    const agentSettingsButton = page.locator("button:has-text('Agent Settings')");
    await agentSettingsButton.scrollIntoViewIfNeeded();
    await agentSettingsButton.click();
    await page.waitForTimeout(500);

    // Enable dynamic tools
    const dynamicToolsCheckbox = page.locator("#enable-dynamic-tools");
    await dynamicToolsCheckbox.click();
    await page.waitForTimeout(500);

    // Check for information banner
    const infoBanner = page.locator("text=Dynamic Tool Selection Benefits:");
    await expect(infoBanner).toBeVisible();
  });

  test("displays all strategy descriptions", async ({ page }) => {
    await page.route("**/settings/options", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockSettings),
      });
    });

    await page.goto("/settings");
    await page.waitForLoadState("networkidle");

    // Expand Agent Settings
    const agentSettingsButton = page.locator("button:has-text('Agent Settings')");
    await agentSettingsButton.scrollIntoViewIfNeeded();
    await agentSettingsButton.click();
    await page.waitForTimeout(500);

    // Enable dynamic tools
    const dynamicToolsCheckbox = page.locator("#enable-dynamic-tools");
    await dynamicToolsCheckbox.click();
    await page.waitForTimeout(500);

    // Get the strategy select
    const strategySelect = page.locator("label:has-text('Tool Selection Strategy')").locator("..").locator("select");

    // Test each strategy and verify its description appears
    const strategies = [
      { value: "conservative", text: "Balanced selection with common tools" },
      { value: "semantic", text: "Select tools based on query similarity" },
      { value: "minimal", text: "Only most relevant tools for the query" },
      { value: "all", text: "Provide all available tools" },
    ];

    for (const strategy of strategies) {
      await strategySelect.selectOption(strategy.value);
      const description = page.locator(`text=${strategy.text}`);
      await expect(description).toBeVisible();
    }
  });

  test("allows editing system prompt", async ({ page }) => {
    await page.route("**/settings/options", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockSettings),
      });
    });

    await page.goto("/settings");
    await page.waitForLoadState("networkidle");

    // Find and click the Agent Settings collapsible button
    const agentSettingsButton = page.locator("button:has-text('Agent Settings')");
    await agentSettingsButton.click();

    // Wait for expansion
    await page.waitForTimeout(500);

    // Edit system prompt
    const systemPromptTextarea = page.locator('textarea[placeholder*="system prompt"]');
    await systemPromptTextarea.fill("New custom prompt");
    await expect(systemPromptTextarea).toHaveValue("New custom prompt");
  });

  test("displays conversation summarization checkbox", async ({ page }) => {
    await page.route("**/settings/options", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockSettings),
      });
    });

    await page.goto("/settings");
    await page.waitForLoadState("networkidle");

    // Expand Agent Settings
    const agentSettingsButton = page.locator("button:has-text('Agent Settings')");
    await agentSettingsButton.scrollIntoViewIfNeeded();
    await agentSettingsButton.click();
    await page.waitForTimeout(500);

    // Find the conversation summarization checkbox
    const summarizationCheckbox = page.locator("#enable-summarization");
    await expect(summarizationCheckbox).toBeVisible();
    
    // Check label text
    const label = page.locator("label[for='enable-summarization']");
    await expect(label).toContainText("Enable Conversation Summarization");
  });

  test("enables conversation summarization toggle", async ({ page }) => {
    await page.route("**/settings/options", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockSettings),
      });
    });

    await page.goto("/settings");
    await page.waitForLoadState("networkidle");

    // Expand Agent Settings
    const agentSettingsButton = page.locator("button:has-text('Agent Settings')");
    await agentSettingsButton.scrollIntoViewIfNeeded();
    await agentSettingsButton.click();
    await page.waitForTimeout(500);

    // Find and check the conversation summarization checkbox
    const summarizationCheckbox = page.locator("#enable-summarization");
    await expect(summarizationCheckbox).not.toBeChecked();
    
    // Enable it
    await summarizationCheckbox.click();
    await page.waitForTimeout(300);
    
    // Verify it's checked
    await expect(summarizationCheckbox).toBeChecked();
  });

  test("disables conversation summarization toggle", async ({ page }) => {
    await page.route("**/settings/options", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockSettings),
      });
    });

    await page.goto("/settings");
    await page.waitForLoadState("networkidle");

    // Expand Agent Settings
    const agentSettingsButton = page.locator("button:has-text('Agent Settings')");
    await agentSettingsButton.scrollIntoViewIfNeeded();
    await agentSettingsButton.click();
    await page.waitForTimeout(500);

    // Enable then disable
    const summarizationCheckbox = page.locator("#enable-summarization");
    await summarizationCheckbox.click();
    await page.waitForTimeout(300);
    await expect(summarizationCheckbox).toBeChecked();
    
    await summarizationCheckbox.click();
    await page.waitForTimeout(300);
    await expect(summarizationCheckbox).not.toBeChecked();
  });

  test("shows conversation summarization description and benefits", async ({ page }) => {
    await page.route("**/settings/options", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockSettings),
      });
    });

    await page.goto("/settings");
    await page.waitForLoadState("networkidle");

    // Expand Agent Settings
    const agentSettingsButton = page.locator("button:has-text('Agent Settings')");
    await agentSettingsButton.scrollIntoViewIfNeeded();
    await agentSettingsButton.click();
    await page.waitForTimeout(500);

    // Check description text
    const description = page.locator("text=Automatically condense older messages");
    await expect(description).toBeVisible();
    
    // Check benefits section
    const benefits = page.locator("text=Benefits:");
    await expect(benefits).toBeVisible();
    
    // Check specific benefits mentioned
    const infiniteConversation = page.locator("text=infinite conversation length");
    await expect(infiniteConversation).toBeVisible();
    
    const tokenReduction = page.locator("text=reduces token costs by 50-80%");
    await expect(tokenReduction).toBeVisible();
  });

  test("conversation summarization and dynamic tools can be enabled independently", async ({ page }) => {
    await page.route("**/settings/options", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockSettings),
      });
    });

    await page.goto("/settings");
    await page.waitForLoadState("networkidle");

    // Expand Agent Settings
    const agentSettingsButton = page.locator("button:has-text('Agent Settings')");
    await agentSettingsButton.scrollIntoViewIfNeeded();
    await agentSettingsButton.click();
    await page.waitForTimeout(500);

    const dynamicToolsCheckbox = page.locator("#enable-dynamic-tools");
    const summarizationCheckbox = page.locator("#enable-summarization");

    // Both should be unchecked initially
    await expect(dynamicToolsCheckbox).not.toBeChecked();
    await expect(summarizationCheckbox).not.toBeChecked();

    // Enable summarization only
    await summarizationCheckbox.click();
    await page.waitForTimeout(300);
    await expect(summarizationCheckbox).toBeChecked();
    await expect(dynamicToolsCheckbox).not.toBeChecked();

    // Enable dynamic tools as well
    await dynamicToolsCheckbox.click();
    await page.waitForTimeout(300);
    await expect(dynamicToolsCheckbox).toBeChecked();
    await expect(summarizationCheckbox).toBeChecked();

    // Disable summarization, keep dynamic tools
    await summarizationCheckbox.click();
    await page.waitForTimeout(300);
    await expect(summarizationCheckbox).not.toBeChecked();
    await expect(dynamicToolsCheckbox).toBeChecked();
  });
});
