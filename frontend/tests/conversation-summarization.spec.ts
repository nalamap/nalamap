import { test, expect } from "@playwright/test";

const mockSettings = {
  system_prompt: "Test prompt",
  tool_options: {},
  example_geoserver_backends: [],
  model_options: {
    openai: [{ name: "gpt-4", max_tokens: 4096 }],
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

test.describe("Conversation Summarization Integration", () => {
  test("conversation summarization setting is visible in Agent Settings", async ({ page }) => {
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

    // Verify conversation summarization checkbox exists
    const summarizationCheckbox = page.locator("#enable-summarization");
    await expect(summarizationCheckbox).toBeVisible();

    // Verify label
    const label = page.locator("label[for='enable-summarization']");
    await expect(label).toContainText("Enable Conversation Summarization");
  });

  test("conversation summarization can be toggled on and off", async ({ page }) => {
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

    const summarizationCheckbox = page.locator("#enable-summarization");
    
    // Initially unchecked
    await expect(summarizationCheckbox).not.toBeChecked();

    // Enable it
    await summarizationCheckbox.click();
    await page.waitForTimeout(300);
    await expect(summarizationCheckbox).toBeChecked();

    // Disable it
    await summarizationCheckbox.click();
    await page.waitForTimeout(300);
    await expect(summarizationCheckbox).not.toBeChecked();
  });

  test("conversation summarization appears below dynamic tools settings", async ({ page }) => {
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

    // Get bounding boxes to verify order
    const dynamicToolsLabel = page.locator("label[for='enable-dynamic-tools']");
    const summarizationLabel = page.locator("label[for='enable-summarization']");

    await expect(dynamicToolsLabel).toBeVisible();
    await expect(summarizationLabel).toBeVisible();

    const dynamicToolsBox = await dynamicToolsLabel.boundingBox();
    const summarizationBox = await summarizationLabel.boundingBox();

    // Verify summarization appears below (higher Y coordinate)
    expect(dynamicToolsBox).not.toBeNull();
    expect(summarizationBox).not.toBeNull();
    expect(summarizationBox!.y).toBeGreaterThan(dynamicToolsBox!.y);
  });
});
