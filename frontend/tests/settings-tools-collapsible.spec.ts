import { test, expect } from "@playwright/test";

const mockSettings = {
  system_prompt: "You are a helpful assistant.",
  tool_options: {
    search: {
      default_prompt: "Search prompt",
      settings: {},
    },
    map_layers: {
      default_prompt: "Map layers prompt",
      settings: {},
    },
  },
  example_geoserver_backends: [],
  model_options: {
    openai: [{ name: "gpt-4", max_tokens: 4000 }],
  },
  session_id: "test-session-123",
};

test.describe("Settings page - Tools Configuration", () => {
  test("tools section can be collapsed and expanded", async ({ page }) => {
    await page.route("**/settings/options", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockSettings),
      });
    });

    await page.goto("/settings");
    await page.waitForLoadState("networkidle");

    // Find the Tools Configuration section
    const toolsSection = page.locator("section:has(h2:text('Tools Configuration'))");
    await expect(toolsSection).toBeVisible();

    // Initially, the section should be expanded (content visible)
    const addToolButton = toolsSection.getByRole("button", { name: "Add Tool" });
    await expect(addToolButton).toBeVisible();

    // Find and click the collapse/expand button
    const toggleButton = toolsSection.locator("button:has-text('Hide')");
    await expect(toggleButton).toBeVisible();
    await toggleButton.click();

    // After clicking, content should be hidden
    await expect(addToolButton).not.toBeVisible();

    // Button text should change to "Show"
    await expect(toolsSection.locator("button:has-text('Show')")).toBeVisible();

    // Click again to expand
    await page.locator("button:has-text('Show')").click();

    // Content should be visible again
    await expect(addToolButton).toBeVisible();
  });

  test("individual tool prompts can be shown and hidden", async ({ page }) => {
    await page.route("**/settings/options", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockSettings),
      });
    });

    await page.goto("/settings");
    await page.waitForLoadState("networkidle");

    const toolsSection = page.locator("section:has(h2:text('Tools Configuration'))");

    // Add a tool first
    const toolSelect = toolsSection.locator("select");
    await toolSelect.selectOption("search");
    await toolsSection.getByRole("button", { name: "Add Tool" }).click();

    // Tool should appear in the list
    const toolItem = toolsSection.locator("li:has-text('search')");
    await expect(toolItem).toBeVisible();

    // Initially, the prompt textarea should be hidden
    const promptTextarea = toolItem.locator("textarea");
    await expect(promptTextarea).not.toBeVisible();

    // Find and click "Show Prompt" button
    const showPromptButton = toolItem.getByRole("button", { name: "Show Prompt" });
    await expect(showPromptButton).toBeVisible();
    await showPromptButton.click();

    // Prompt textarea should now be visible
    await expect(promptTextarea).toBeVisible();

    // Button text should change to "Hide Prompt"
    const hidePromptButton = toolItem.getByRole("button", { name: "Hide Prompt" });
    await expect(hidePromptButton).toBeVisible();
    await hidePromptButton.click();

    // Prompt textarea should be hidden again
    await expect(promptTextarea).not.toBeVisible();
  });
});
