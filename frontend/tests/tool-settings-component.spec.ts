import { test, expect, Page } from "@playwright/test";

// Helper function to expand the Tools Configuration section
async function expandToolsConfiguration(page: Page) {
  const toolsButton = page.locator("button:has-text('Tools Configuration')");
  await expect(toolsButton).toBeVisible({ timeout: 5000 });
  await toolsButton.click();
  await page.waitForTimeout(300);
}

const mockSettings = {
  system_prompt: "You are a helpful AI assistant.",
  tool_options: {
    search: {
      default_prompt: "Search for information",
      settings: {},
    },
    map_layers: {
      default_prompt: "Find map layers",
      settings: {},
    },
    attribute_tools: {
      default_prompt: "Query attributes",
      settings: {},
    },
  },
  tools: ["search", "map_layers"],
  example_geoserver_backends: [],
  model_options: {
    openai: [{ name: "gpt-4o-mini", max_tokens: 4000 }],
  },
  session_id: "test-session-123",
};

test.describe("Tool Settings Component", () => {
  test.beforeEach(async ({ page }) => {
    await page.route("**/settings/options", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockSettings),
      });
    });

    await page.goto("/settings");
    await page.waitForLoadState("networkidle");
  });

  test("should display tools configuration button", async ({ page }) => {
    const toolsButton = page.locator("button:has-text('Tools Configuration')");
    await expect(toolsButton).toBeVisible();
  });

  test("should expand and collapse tools configuration", async ({ page }) => {
    const toolsButton = page.locator("button:has-text('Tools Configuration')");
    await expect(toolsButton).toBeVisible();

    // Initially collapsed - Add Tool button should not be visible
    const addToolButton = page.getByRole("button", { name: "Add Tool" });
    await expect(addToolButton).not.toBeVisible();

    // Expand
    await toolsButton.click();
    await page.waitForTimeout(300);
    await expect(addToolButton).toBeVisible();

    // Collapse
    await toolsButton.click();
    await page.waitForTimeout(300);
    await expect(addToolButton).not.toBeVisible();
  });

  test("should display enabled tools", async ({ page }) => {
    await expandToolsConfiguration(page);

    // Should show enabled tools
    await expect(page.locator("li:has-text('search')")).toBeVisible();
    await expect(page.locator("li:has-text('map_layers')")).toBeVisible();
  });

  test("should allow enabling and disabling tools", async ({ page }) => {
    await expandToolsConfiguration(page);

    const searchTool = page.locator("li:has-text('search')");
    const checkbox = searchTool.locator('input[type="checkbox"]');

    // Should be enabled initially
    await expect(checkbox).toBeChecked();

    // Disable the tool
    await checkbox.uncheck();
    await expect(checkbox).not.toBeChecked();

    // Re-enable the tool
    await checkbox.check();
    await expect(checkbox).toBeChecked();
  });

  test("should allow adding a new tool", async ({ page }) => {
    await expandToolsConfiguration(page);

    const toolSelect = page.locator("select").first();
    await expect(toolSelect).toBeVisible();

    // Select attribute_tools (not currently enabled)
    await toolSelect.selectOption("attribute_tools");

    // Click Add Tool
    await page.getByRole("button", { name: "Add Tool" }).click();

    // Tool should appear in the list
    await expect(page.locator("li:has-text('attribute_tools')")).toBeVisible({
      timeout: 3000,
    });
  });

  test("should allow removing a tool", async ({ page }) => {
    await expandToolsConfiguration(page);

    const searchTool = page.locator("li:has-text('search')");
    await expect(searchTool).toBeVisible();

    // Click remove button
    const removeButton = searchTool.getByRole("button", { name: "Remove" });
    await removeButton.click();

    // Tool should be removed from the list
    await expect(searchTool).not.toBeVisible();
  });

  test("should show and hide tool prompts", async ({ page }) => {
    await expandToolsConfiguration(page);

    const searchTool = page.locator("li:has-text('search')");
    const promptTextarea = searchTool.locator("textarea");

    // Initially hidden
    await expect(promptTextarea).not.toBeVisible();

    // Show prompt
    const showPromptButton = searchTool.getByRole("button", { name: "Show Prompt" });
    await showPromptButton.click();
    await expect(promptTextarea).toBeVisible();

    // Verify prompt text
    await expect(promptTextarea).toHaveValue("Search for information");

    // Hide prompt
    const hidePromptButton = searchTool.getByRole("button", { name: "Hide Prompt" });
    await hidePromptButton.click();
    await expect(promptTextarea).not.toBeVisible();
  });

  test("should allow editing tool prompts", async ({ page }) => {
    await expandToolsConfiguration(page);

    const searchTool = page.locator("li:has-text('search')");

    // Show prompt
    const showPromptButton = searchTool.getByRole("button", { name: "Show Prompt" });
    await showPromptButton.click();

    const promptTextarea = searchTool.locator("textarea");
    await expect(promptTextarea).toBeVisible();

    // Edit the prompt
    await promptTextarea.fill("Custom search prompt");
    await expect(promptTextarea).toHaveValue("Custom search prompt");
  });

  test("should persist tool changes in store", async ({ page }) => {
    await expandToolsConfiguration(page);

    const toolSelect = page.locator("select").first();
    await toolSelect.selectOption("attribute_tools");
    await page.getByRole("button", { name: "Add Tool" }).click();

    // Check that changes are persisted in the store
    const storeValue = await page.evaluate(() => {
      // @ts-ignore - accessing window store for testing
      const tools = window.useSettingsStore?.getState().tools;
      // tools is an array of objects, extract the names
      return tools.map((t: any) => t.name);
    });

    expect(storeValue).toContain("attribute_tools");
  });

  test("should display available tools in dropdown", async ({ page }) => {
    await expandToolsConfiguration(page);

    const toolSelect = page.locator("select").first();
    await expect(toolSelect).toBeVisible();

    // Check that all available tools are in the dropdown
    await expect(toolSelect).toContainText("search");
    await expect(toolSelect).toContainText("map_layers");
    await expect(toolSelect).toContainText("attribute_tools");
  });

  test("should not add duplicate tools", async ({ page }) => {
    await expandToolsConfiguration(page);

    // search is already enabled
    const initialSearchTools = await page.locator("li:has-text('search')").count();
    expect(initialSearchTools).toBe(1);

    // Try to add search again
    const toolSelect = page.locator("select").first();
    await toolSelect.selectOption("search");
    await page.getByRole("button", { name: "Add Tool" }).click();

    // Should still only have one search tool
    const finalSearchTools = await page.locator("li:has-text('search')").count();
    expect(finalSearchTools).toBe(1);
  });

  test("should handle empty tool options gracefully", async ({ page }) => {
    // Mock settings with no tool options
    await page.route("**/settings/options", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          ...mockSettings,
          tool_options: {},
          tools: [],
        }),
      });
    });

    await page.reload();
    await page.waitForLoadState("networkidle");

    await expandToolsConfiguration(page);

    // Component should still render without errors
    const toolsButton = page.locator("button:has-text('Tools Configuration')");
    await expect(toolsButton).toBeVisible();
  });
});
