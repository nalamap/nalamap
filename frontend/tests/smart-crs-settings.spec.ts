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
  model_settings: {
    model_provider: "openai",
    model_name: "gpt-4",
    max_tokens: 4000,
    use_summarization: false,
    enable_smart_crs: true,
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

test.describe("Smart CRS Settings", () => {
  test("renders Smart CRS toggle in Agent Settings", async ({ page }) => {
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

    // Find and click the Agent Settings collapsible button
    const agentSettingsButton = page.locator("button:has-text('Agent Settings')");
    await agentSettingsButton.scrollIntoViewIfNeeded();
    await agentSettingsButton.click();

    // Wait for expansion
    await page.waitForTimeout(500);

    // Check Smart CRS checkbox is visible
    const smartCrsCheckbox = page.locator('input#enable-smart-crs');
    await smartCrsCheckbox.scrollIntoViewIfNeeded();
    await expect(smartCrsCheckbox).toBeVisible();
  });

  test("Smart CRS toggle is checked by default", async ({ page }) => {
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

    // Check Smart CRS checkbox is checked by default
    const smartCrsCheckbox = page.locator('input#enable-smart-crs');
    await smartCrsCheckbox.scrollIntoViewIfNeeded();
    await expect(smartCrsCheckbox).toBeChecked();
  });

  test("can toggle Smart CRS setting off and on", async ({ page }) => {
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

    // Find Smart CRS checkbox
    const smartCrsCheckbox = page.locator('input#enable-smart-crs');
    await smartCrsCheckbox.scrollIntoViewIfNeeded();

    // Initially checked
    await expect(smartCrsCheckbox).toBeChecked();

    // Uncheck it
    await smartCrsCheckbox.click();
    await expect(smartCrsCheckbox).not.toBeChecked();

    // Check it again
    await smartCrsCheckbox.click();
    await expect(smartCrsCheckbox).toBeChecked();
  });

  test("displays Smart CRS description text", async ({ page }) => {
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

    // Look for description text
    const descriptionText = page.locator('text=Automatically select optimal coordinate reference systems');
    await descriptionText.scrollIntoViewIfNeeded();
    await expect(descriptionText).toBeVisible();
  });

  test("displays Smart CRS info panel with technical details", async ({ page }) => {
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

    // Look for info panel with technical details
    const infoPanelText = page.locator('text=3-tier hierarchy: UTM zones for local areas');
    await infoPanelText.scrollIntoViewIfNeeded();
    await expect(infoPanelText).toBeVisible();
  });

  test("respects disabled state from backend", async ({ page }) => {
    const settingsWithDisabledCrs = {
      ...mockSettings,
      model_settings: {
        ...mockSettings.model_settings,
        enable_smart_crs: false,
      },
    };

    await page.route("**/settings/options", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(settingsWithDisabledCrs),
      });
    });

    await page.goto("/settings");
    await page.waitForLoadState("networkidle");

    // Expand Agent Settings
    const agentSettingsButton = page.locator("button:has-text('Agent Settings')");
    await agentSettingsButton.scrollIntoViewIfNeeded();
    await agentSettingsButton.click();
    await page.waitForTimeout(500);

    // Check Smart CRS checkbox is NOT checked when disabled in settings
    const smartCrsCheckbox = page.locator('input#enable-smart-crs');
    await smartCrsCheckbox.scrollIntoViewIfNeeded();
    await expect(smartCrsCheckbox).not.toBeChecked();
  });
});
