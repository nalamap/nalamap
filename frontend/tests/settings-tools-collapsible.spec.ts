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

    // Find the Tools Configuration button
    const toolsButton = page.locator("button:has-text('Tools Configuration')");
    await expect(toolsButton).toBeVisible();

    // Section starts collapsed by default - wait and verify content is not visible
    await page.waitForTimeout(300);
    const addToolButton = page.getByRole("button", { name: "Add Tool" });
    await expect(addToolButton).not.toBeVisible();

    // Click to expand
    await toolsButton.click();
    await page.waitForTimeout(300);

    // After clicking, content should be visible
    await expect(addToolButton).toBeVisible({ timeout: 3000 });

    // Click again to collapse
    await toolsButton.click();
    await page.waitForTimeout(300);

    // Content should be hidden again
    await expect(addToolButton).not.toBeVisible();
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

    // Expand the Tools Configuration section first
    const toolsButton = page.locator("button:has-text('Tools Configuration')");
    await expect(toolsButton).toBeVisible();
    await toolsButton.click();
    await page.waitForTimeout(300);

    // Add a tool first
    const toolSelect = page.locator("select").filter({ hasText: "search" }).or(page.locator("select").first());
    await toolSelect.selectOption("search");
    await page.getByRole("button", { name: "Add Tool" }).click();

    // Tool should appear in the list
    const toolItem = page.locator("li:has-text('search')");
    await expect(toolItem).toBeVisible({ timeout: 3000 });

    // Initially, the prompt textarea should be hidden
    const promptTextarea = toolItem.locator("textarea");
    await expect(promptTextarea).not.toBeVisible();

    // Find and click "Show Prompt" button
    const showPromptButton = toolItem.getByRole("button", { name: "Show Prompt" });
    await expect(showPromptButton).toBeVisible();
    await showPromptButton.click();

    // Prompt textarea should now be visible
    await expect(promptTextarea).toBeVisible({ timeout: 2000 });

    // Button text should change to "Hide Prompt"
    const hidePromptButton = toolItem.getByRole("button", { name: "Hide Prompt" });
    await expect(hidePromptButton).toBeVisible();
    await hidePromptButton.click();

    // Prompt textarea should be hidden again
    await expect(promptTextarea).not.toBeVisible();
  });
});
