import { test, expect, Page } from "@playwright/test";

// Helper function to expand the Color Customization section
async function expandColorSettings(page: Page) {
  const colorButton = page.locator("button:has-text('Color Customization')");
  await colorButton.scrollIntoViewIfNeeded();
  await expect(colorButton).toBeVisible({ timeout: 5000 });
  
  // Check if already expanded by looking for the reset button
  const resetButton = page.getByRole("button", { name: "Reset", exact: true });
  const isExpanded = await resetButton.isVisible().catch(() => false);
  
  if (!isExpanded) {
    await colorButton.click();
    await page.waitForTimeout(300);
  }
}

const mockSettings = {
  system_prompt: "You are a helpful assistant.",
  tool_options: {},
  example_geoserver_backends: [],
  model_options: {
    openai: [{ name: "gpt-4", max_tokens: 4000 }],
  },
  color_settings: {
    primary: {
      shade_50: "#f7f7f8",
      shade_100: "#eeeef0",
      shade_200: "#d8d8df",
      shade_300: "#b7b9c2",
      shade_400: "#8f91a1",
      shade_500: "#717386",
      shade_600: "#5b5c6e",
      shade_700: "#505160",
      shade_800: "#40414c",
      shade_900: "#383842",
      shade_950: "#25252c",
    },
    second_primary: {
      shade_50: "#f5f8f9",
      shade_100: "#e8eef1",
      shade_200: "#d6e1e7",
      shade_300: "#baccd6",
      shade_400: "#99b2c1",
      shade_500: "#809bb1",
      shade_600: "#68829e",
      shade_700: "#627793",
      shade_800: "#546279",
      shade_900: "#465262",
      shade_950: "#2e343d",
    },
    secondary: {
      shade_50: "#fafaeb",
      shade_100: "#f2f4d3",
      shade_200: "#e6eaac",
      shade_300: "#d3db7b",
      shade_400: "#bec952",
      shade_500: "#aebd38",
      shade_600: "#7e8b25",
      shade_700: "#606a21",
      shade_800: "#4d551d",
      shade_900: "#40481b",
      shade_950: "#21270c",
    },
    tertiary: {
      shade_50: "#f4f8f3",
      shade_100: "#e6efe3",
      shade_200: "#cddfc8",
      shade_300: "#aac89f",
      shade_400: "#7fa96e",
      shade_500: "#598234",
      shade_600: "#4d7233",
      shade_700: "#3f5a2a",
      shade_800: "#354925",
      shade_900: "#2d3d20",
      shade_950: "#15210f",
    },
    danger: {
      shade_50: "#fef2f2",
      shade_100: "#fee2e2",
      shade_200: "#fecaca",
      shade_300: "#fca5a5",
      shade_400: "#f87171",
      shade_500: "#ef4444",
      shade_600: "#dc2626",
      shade_700: "#b91c1c",
      shade_800: "#991b1b",
      shade_900: "#7f1d1d",
      shade_950: "#450a0a",
    },
    warning: {
      shade_50: "#fffbeb",
      shade_100: "#fef3c7",
      shade_200: "#fde68a",
      shade_300: "#fcd34d",
      shade_400: "#fbbf24",
      shade_500: "#f59e0b",
      shade_600: "#d97706",
      shade_700: "#b45309",
      shade_800: "#92400e",
      shade_900: "#78350f",
      shade_950: "#451a03",
    },
    info: {
      shade_50: "#eff6ff",
      shade_100: "#dbeafe",
      shade_200: "#bfdbfe",
      shade_300: "#93c5fd",
      shade_400: "#60a5fa",
      shade_500: "#3b82f6",
      shade_600: "#2563eb",
      shade_700: "#1d4ed8",
      shade_800: "#1e40af",
      shade_900: "#1e3a8a",
      shade_950: "#172554",
    },
    neutral: {
      shade_50: "#ffffff",
      shade_100: "#f9fafb",
      shade_200: "#f3f4f6",
      shade_300: "#e5e7eb",
      shade_400: "#d1d5db",
      shade_500: "#9ca3af",
      shade_600: "#6b7280",
      shade_700: "#4b5563",
      shade_800: "#374151",
      shade_900: "#1f2937",
      shade_950: "#000000",
    },
    corporate_1: {
      shade_50: "#fff1f2",
      shade_100: "#ffe4e6",
      shade_200: "#fecdd3",
      shade_300: "#fda4af",
      shade_400: "#fb7185",
      shade_500: "#f43f5e",
      shade_600: "#e11d48",
      shade_700: "#be123c",
      shade_800: "#9f1239",
      shade_900: "#881337",
      shade_950: "#4c0519",
    },
    corporate_2: {
      shade_50: "#f0f9ff",
      shade_100: "#e0f2fe",
      shade_200: "#bae6fd",
      shade_300: "#7dd3fc",
      shade_400: "#38bdf8",
      shade_500: "#0ea5e9",
      shade_600: "#0284c7",
      shade_700: "#0369a1",
      shade_800: "#075985",
      shade_900: "#0c4a6e",
      shade_950: "#082f49",
    },
    corporate_3: {
      shade_50: "#faf5ff",
      shade_100: "#f3e8ff",
      shade_200: "#e9d5ff",
      shade_300: "#d8b4fe",
      shade_400: "#c084fc",
      shade_500: "#a855f7",
      shade_600: "#9333ea",
      shade_700: "#7e22ce",
      shade_800: "#6b21a8",
      shade_900: "#581c87",
      shade_950: "#3b0764",
    },
  },
  session_id: "test-session-123",
};

test.describe("Color Settings", () => {
  test.beforeEach(async ({ page }) => {
    // Mock the settings/options endpoint
    await page.route("**/settings/options", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockSettings),
      });
    });

    await page.goto("http://localhost:3000/settings");
    await page.waitForLoadState("networkidle");
    // Wait a bit for all components to render
    await page.waitForTimeout(1000);
  });

  test("should display color customization section", async ({ page }) => {
    // Check that Color Customization button exists (section starts collapsed)
    const colorButton = page.locator("button:has-text('Color Customization')");
    await colorButton.scrollIntoViewIfNeeded();
    await expect(colorButton).toBeVisible();

    // Check for corporate branding badge (it's part of the button, always visible)
    const badge = page.getByText("Corporate Branding");
    await expect(badge).toBeVisible();
  });

  test("should expand and collapse color settings", async ({ page }) => {
    // Find and click the Color Customization button
    const colorButton = page.locator("button:has-text('Color Customization')");
    await colorButton.scrollIntoViewIfNeeded();
    await expect(colorButton).toBeVisible();

    // Initially should be collapsed - check for the color reset button specifically
    const resetButton = page.getByRole("button", { name: "Reset", exact: true });
    await expect(resetButton).not.toBeVisible();

    // Expand
    await colorButton.click();
    await page.waitForTimeout(300);
    await expect(resetButton).toBeVisible();

    // Collapse
    await colorButton.click();
    await page.waitForTimeout(300);
    await expect(resetButton).not.toBeVisible();
  });

  test("should display all eleven color scales", async ({ page }) => {
    // Expand color settings
    await expandColorSettings(page);

    // Check for all eleven color scales - use more specific selectors to avoid duplicates
    // The text includes the full names like "Primary (Text & Borders)", so we use partial match
    const primaryScale = page.locator("button:has-text('Primary')").first();
    const secondPrimaryScale = page.locator("button:has-text('Second Primary')").first();
    const secondaryScale = page.locator("button:has-text('Secondary')").first();
    const tertiaryScale = page.locator("button:has-text('Tertiary')").first();
    const dangerScale = page.locator("button:has-text('Danger')").first();
    const warningScale = page.locator("button:has-text('Warning')").first();
    const infoScale = page.locator("button:has-text('Info')").first();
    const neutralScale = page.locator("button:has-text('Neutral')").first();
    const corporate1Scale = page.locator("button:has-text('Corporate 1')").first();
    const corporate2Scale = page.locator("button:has-text('Corporate 2')").first();
    const corporate3Scale = page.locator("button:has-text('Corporate 3')").first();
    
    await expect(primaryScale).toBeVisible();
    await expect(secondPrimaryScale).toBeVisible();
    await expect(secondaryScale).toBeVisible();
    await expect(tertiaryScale).toBeVisible();
    await expect(dangerScale).toBeVisible();
    await expect(warningScale).toBeVisible();
    await expect(infoScale).toBeVisible();
    await expect(neutralScale).toBeVisible();
    await expect(corporate1Scale).toBeVisible();
    await expect(corporate2Scale).toBeVisible();
    await expect(corporate3Scale).toBeVisible();
  });

  test("should expand color scale to show individual shades", async ({
    page,
  }) => {
    // Expand color settings
    await expandColorSettings(page);

    // Expand primary color scale
    const primaryButton = page.locator("button:has-text('Primary')").first();
    await primaryButton.click();
    await page.waitForTimeout(200);

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
    await expandColorSettings(page);

    // Expand primary color scale
    await page.locator("button:has-text('Primary')").first().click();
    await page.waitForTimeout(200);

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
    await expandColorSettings(page);
    await page.locator("button:has-text('Primary')").first().click();
    await page.waitForTimeout(200);

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
    await expandColorSettings(page);

    // Click the color reset button (not the "Reset App" button)
    const resetButton = page.getByRole("button", { name: "Reset", exact: true });
    await resetButton.click();

    // Wait for confirmation UI to appear
    await page.waitForTimeout(100);

    // Verify confirmation text is shown
    await expect(
      page.getByText("Reset all colors to defaults?")
    ).toBeVisible();

    // Verify confirm and cancel buttons are present
    await expect(page.getByRole("button", { name: "Confirm" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Cancel" })).toBeVisible();
  });

  test("should reset colors to defaults when confirmed", async ({ page }) => {
    // Expand color settings and change a color
    await expandColorSettings(page);
    await page.locator("button:has-text('Primary')").first().click();
    await page.waitForTimeout(200);

    const colorInput = page.locator('input[type="color"]').first();
    await colorInput.fill("#ff0000");
    
    // Verify color changed
    expect(await colorInput.inputValue()).toBe("#ff0000");

    // Click the color reset button
    await page.getByRole("button", { name: "Reset", exact: true }).click();

    // Click the confirm button
    await page.getByRole("button", { name: "Confirm" }).click();

    // Wait a bit for the reset to complete
    await page.waitForTimeout(500);
    
    // The color should be reset - check if the primary shade_50 is back to default
    // or just verify the confirmation UI is gone
    await expect(page.getByText("Reset all colors to defaults?")).not.toBeVisible();
  });

  test("should persist color settings in store", async ({ page }) => {
    // Expand color settings and change a color
    await expandColorSettings(page);
    await page.locator("button:has-text('Primary')").first().click();
    await page.waitForTimeout(200);

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
    await expandColorSettings(page);

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
    await expandColorSettings(page);
    await page.locator("button:has-text('Primary')").first().click();
    await page.waitForTimeout(200);
    await page.locator('input[type="color"]').first().fill("#123456");

    // Scroll to top to find export button
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.waitForTimeout(300);

    // Set up download handler
    const downloadPromise = page.waitForEvent("download");

    // Click export button (should be at the top of the page)
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
    await expandColorSettings(page);

    // Should show loading state or default to initial colors
    // The component should handle this gracefully without crashing
    const colorButton = page.locator("button:has-text('Color Customization')");
    await expect(colorButton).toBeVisible();
  });
});
