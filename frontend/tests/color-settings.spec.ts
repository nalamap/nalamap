import { test, expect } from "@playwright/test";

test.describe("Color Settings", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("http://localhost:3000/settings");
    await page.waitForLoadState("networkidle");
  });

  test("should display color customization section", async ({ page }) => {
    // Check that Color Customization section exists
    const colorSection = page.getByText("Color Customization");
    await expect(colorSection).toBeVisible();

    // Check for corporate branding badge
    const badge = page.getByText("Corporate Branding");
    await expect(badge).toBeVisible();
  });

  test("should expand and collapse color settings", async ({ page }) => {
    // Find and click the Color Customization button
    const colorButton = page.locator("button:has-text('Color Customization')");
    await expect(colorButton).toBeVisible();

    // Initially should be collapsed
    const resetButton = page.getByRole("button", { name: /reset/i });
    await expect(resetButton).not.toBeVisible();

    // Expand
    await colorButton.click();
    await expect(resetButton).toBeVisible();

    // Collapse
    await colorButton.click();
    await expect(resetButton).not.toBeVisible();
  });

  test("should display all four color scales", async ({ page }) => {
    // Expand color settings
    await page.locator("button:has-text('Color Customization')").click();

    // Check for all four color scales
    await expect(page.getByText("Primary")).toBeVisible();
    await expect(page.getByText("Second Primary")).toBeVisible();
    await expect(page.getByText("Secondary")).toBeVisible();
    await expect(page.getByText("Tertiary")).toBeVisible();
  });

  test("should expand color scale to show individual shades", async ({
    page,
  }) => {
    // Expand color settings
    await page.locator("button:has-text('Color Customization')").click();

    // Expand primary color scale
    const primaryButton = page.locator("button:has-text('Primary')").first();
    await primaryButton.click();

    // Check that color inputs are visible
    const colorInputs = page.locator('input[type="color"]');
    await expect(colorInputs.first()).toBeVisible();

    // Check for shade labels
    await expect(page.getByText("50 - Lightest")).toBeVisible();
    await expect(page.getByText("500 - Base")).toBeVisible();
    await expect(page.getByText("950 - Darkest")).toBeVisible();
  });

  test("should allow changing individual color values", async ({ page }) => {
    // Expand color settings
    await page.locator("button:has-text('Color Customization')").click();

    // Expand primary color scale
    await page.locator("button:has-text('Primary')").first().click();

    // Find first color input
    const colorInput = page.locator('input[type="color"]').first();
    const originalValue = await colorInput.inputValue();

    // Change color value
    await colorInput.fill("#ff0000");

    // Verify color changed
    const newValue = await colorInput.inputValue();
    expect(newValue).toBe("#ff0000");
    expect(newValue).not.toBe(originalValue);
  });

  test("should apply color changes immediately to UI", async ({ page }) => {
    // Get the original background color of the main content area
    const mainContent = page.locator("main");
    const originalBgColor = await mainContent.evaluate((el) =>
      window.getComputedStyle(el).backgroundColor,
    );

    // Expand color settings and change primary-50 (used for backgrounds)
    await page.locator("button:has-text('Color Customization')").click();
    await page.locator("button:has-text('Primary')").first().click();

    // Change the lightest shade
    const firstColorInput = page.locator('input[type="color"]').first();
    await firstColorInput.fill("#ffeeee");

    // Wait a bit for CSS variable injection
    await page.waitForTimeout(100);

    // Check that background color changed
    const newBgColor = await mainContent.evaluate((el) =>
      window.getComputedStyle(el).backgroundColor,
    );

    // Background should have changed
    expect(newBgColor).not.toBe(originalBgColor);
  });

  test("should show reset confirmation dialog", async ({ page }) => {
    // Expand color settings
    await page.locator("button:has-text('Color Customization')").click();

    // Set up dialog handler
    let dialogShown = false;
    page.on("dialog", async (dialog) => {
      dialogShown = true;
      expect(dialog.message()).toContain("reset all colors to defaults");
      await dialog.dismiss();
    });

    // Click reset button
    const resetButton = page.getByRole("button", { name: /reset/i });
    await resetButton.click();

    // Wait a bit for dialog
    await page.waitForTimeout(100);

    // Verify dialog was shown
    expect(dialogShown).toBe(true);
  });

  test("should reset colors to defaults when confirmed", async ({ page }) => {
    // Expand color settings and change a color
    await page.locator("button:has-text('Color Customization')").click();
    await page.locator("button:has-text('Primary')").first().click();

    const colorInput = page.locator('input[type="color"]').first();
    await colorInput.fill("#ff0000");

    // Set up dialog handler to accept
    page.on("dialog", async (dialog) => {
      await dialog.accept();
    });

    // Click reset button
    await page.getByRole("button", { name: /reset/i }).click();

    // Wait for reset to complete
    await page.waitForTimeout(200);

    // Color should be back to default
    const resetValue = await colorInput.inputValue();
    expect(resetValue).toBe("#f7f7f8"); // Default primary-50 from globals.css
  });

  test("should persist color settings in store", async ({ page }) => {
    // Expand color settings and change a color
    await page.locator("button:has-text('Color Customization')").click();
    await page.locator("button:has-text('Primary')").first().click();

    const colorInput = page.locator('input[type="color"]').first();
    await colorInput.fill("#aabbcc");

    // Check that color is persisted in the store
    const storeValue = await page.evaluate(() => {
      // @ts-ignore - accessing window store for testing
      return window.useSettingsStore?.getState().color_settings?.primary
        ?.shade_50;
    });

    expect(storeValue).toBe("#aabbcc");
  });

  test("should show tips for color selection", async ({ page }) => {
    // Expand color settings
    await page.locator("button:has-text('Color Customization')").click();

    // Check for tips section
    await expect(
      page.getByText("Tips for Color Selection"),
    ).toBeVisible();
    await expect(
      page.getByText(/Use lighter shades.*for backgrounds/),
    ).toBeVisible();
    await expect(
      page.getByText(/sufficient contrast for accessibility/),
    ).toBeVisible();
  });

  test("should export settings with custom colors", async ({ page }) => {
    // Change a color
    await page.locator("button:has-text('Color Customization')").click();
    await page.locator("button:has-text('Primary')").first().click();
    await page.locator('input[type="color"]').first().fill("#123456");

    // Set up download handler
    const downloadPromise = page.waitForEvent("download");

    // Click export button
    await page.getByRole("button", { name: /export settings/i }).click();

    // Wait for download
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toBe("settings.json");

    // Read downloaded file
    const path = await download.path();
    const fs = require("fs");
    const content = fs.readFileSync(path, "utf-8");
    const settings = JSON.parse(content);

    // Verify color settings are included
    expect(settings.color_settings).toBeDefined();
    expect(settings.color_settings.primary.shade_50).toBe("#123456");
  });

  test("should handle missing color settings gracefully", async ({ page }) => {
    // Clear color settings in store
    await page.evaluate(() => {
      // @ts-ignore
      window.useSettingsStore?.setState({ color_settings: undefined });
    });

    // Navigate to ensure component re-renders
    await page.reload();
    await page.waitForLoadState("networkidle");

    // Expand color settings section
    await page.locator("button:has-text('Color Customization')").click();

    // Should show loading state
    await expect(page.getByText("Loading color settings...")).toBeVisible();
  });
});
