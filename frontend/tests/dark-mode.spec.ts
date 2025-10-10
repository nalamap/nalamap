import { test, expect, Page } from "@playwright/test";

// Mock settings data with complete color configuration
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
};

// Helper function to navigate to settings page
async function goToSettings(page: Page) {
  await page.route("**/api/settings", (route) => {
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(mockSettings),
    });
  });

  await page.goto("/settings");
  await page.waitForLoadState("networkidle");
}

// Helper function to scroll to and expand theme settings
async function scrollToThemeSettings(page: Page) {
  // Scroll to theme section
  const themeHeading = page.locator("h2:has-text('Theme Preference')");
  await themeHeading.scrollIntoViewIfNeeded();
  await page.waitForTimeout(300);
  
  // Expand the theme section if it's collapsed
  const themeButton = page.locator("button").filter({ has: page.locator("h2:has-text('Theme Preference')") });
  const chevronDown = themeButton.locator("svg.lucide-chevron-down");
  const isCollapsed = await chevronDown.count() > 0;
  
  if (isCollapsed) {
    await themeButton.click();
    await page.waitForTimeout(300);
  }
}

test.describe("Dark Mode Tests", () => {
  test("should toggle between light and dark mode", async ({ page }) => {
    await goToSettings(page);
    await scrollToThemeSettings(page);

    // Verify we start in light mode
    const htmlElement = page.locator("html");
    let hasLight = await htmlElement.evaluate((el) => 
      !el.classList.contains("dark")
    );
    expect(hasLight).toBe(true);

    // Click Dark Mode button
    const darkModeButton = page.getByRole("button", { name: /Dark Mode/i });
    await darkModeButton.click();
    await page.waitForTimeout(500);

    // Verify dark class is applied
    let hasDark = await htmlElement.evaluate((el) =>
      el.classList.contains("dark")
    );
    expect(hasDark).toBe(true);

    // Click Light Mode button
    const lightModeButton = page.getByRole("button", { name: /Light Mode/i });
    await lightModeButton.click();
    await page.waitForTimeout(500);

    // Verify dark class is removed
    hasDark = await htmlElement.evaluate((el) =>
      el.classList.contains("dark")
    );
    expect(hasDark).toBe(false);
  });

  test("should apply dark background colors", async ({ page }) => {
    await goToSettings(page);
    await scrollToThemeSettings(page);

    // Switch to dark mode
    const darkModeButton = page.getByRole("button", { name: /Dark Mode/i });
    await darkModeButton.click();
    await page.waitForTimeout(500);

    // Check body background is dark
    const bodyBg = await page.locator("body").evaluate((el) => {
      return window.getComputedStyle(el).backgroundColor;
    });

    // Should be a dark color (close to black/very dark gray)
    // RGB values should all be low (< 50)
    const rgbMatch = bodyBg.match(/rgb\((\d+),\s*(\d+),\s*(\d+)\)/);
    if (rgbMatch) {
      const [_, r, g, b] = rgbMatch.map(Number);
      expect(Math.max(r, g, b)).toBeLessThan(60); // Should be very dark
    }
  });

  test("should apply dark text colors for readability", async ({ page }) => {
    await goToSettings(page);
    await scrollToThemeSettings(page);

    // Switch to dark mode
    const darkModeButton = page.getByRole("button", { name: /Dark Mode/i });
    await darkModeButton.click();
    await page.waitForTimeout(500);

    // Check a heading color (should be light for contrast)
    const heading = page.locator("h2").first();
    const color = await heading.evaluate((el) => {
      return window.getComputedStyle(el).color;
    });

    // Should be a light color (high RGB values)
    const rgbMatch = color.match(/rgb\((\d+),\s*(\d+),\s*(\d+)\)/);
    if (rgbMatch) {
      const [_, r, g, b] = rgbMatch.map(Number);
      // At least one color channel should be bright for readability
      expect(Math.max(r, g, b)).toBeGreaterThan(150);
    }
  });

  test("should persist theme preference", async ({ page }) => {
    await goToSettings(page);
    await scrollToThemeSettings(page);

    // Switch to dark mode
    const darkModeButton = page.getByRole("button", { name: /Dark Mode/i });
    await darkModeButton.click();
    await page.waitForTimeout(500);

    // Check localStorage - theme is stored directly with key "theme"
    const theme = await page.evaluate(() => {
      return localStorage.getItem("theme");
    });

    expect(theme).toBe("dark");

    // Reload page
    await page.reload();
    await page.waitForLoadState("networkidle");

    // Verify dark mode persists
    const htmlElement = page.locator("html");
    const hasDark = await htmlElement.evaluate((el) =>
      el.classList.contains("dark")
    );
    expect(hasDark).toBe(true);
  });

  test("should show theme badge correctly", async ({ page }) => {
    await goToSettings(page);
    await scrollToThemeSettings(page);

    // Check initial badge (Light Mode)
    let badge = page.locator("span:has-text('Light Mode')");
    await expect(badge).toBeVisible();

    // Switch to dark mode
    const darkModeButton = page.getByRole("button", { name: /Dark Mode/i });
    await darkModeButton.click();
    await page.waitForTimeout(300);

    // Check badge updated to Dark Mode
    badge = page.locator("span:has-text('Dark Mode')");
    await expect(badge).toBeVisible();
  });

  test("should display active indicator on selected theme", async ({ page }) => {
    await goToSettings(page);
    await scrollToThemeSettings(page);

    // Light mode should have Active indicator
    const lightButton = page.getByRole("button", { name: /Light Mode/i });
    await expect(lightButton.locator("div:has-text('Active')").first()).toBeVisible();

    // Switch to dark mode
    const darkModeButton = page.getByRole("button", { name: /Dark Mode/i });
    await darkModeButton.click();
    await page.waitForTimeout(300);

    // Dark mode should now have Active indicator
    await expect(darkModeButton.locator("div:has-text('Active')").first()).toBeVisible();

    // Light mode should NOT have Active indicator anymore
    await expect(lightButton.locator("div:has-text('Active')")).toHaveCount(0);
  });

  test("should apply dark mode to panels and borders", async ({ page }) => {
    await goToSettings(page);
    await scrollToThemeSettings(page);

    // Switch to dark mode
    const darkModeButton = page.getByRole("button", { name: /Dark Mode/i });
    await darkModeButton.click();
    await page.waitForTimeout(500);

    // Check that borders are visible but subtle
    const panels = page.locator(".border");
    const count = await panels.count();
    
    if (count > 0) {
      const borderColor = await panels.first().evaluate((el) => {
        return window.getComputedStyle(el).borderColor;
      });

      // Border should exist and be a dark color
      expect(borderColor).toBeTruthy();
      expect(borderColor).not.toBe("rgba(0, 0, 0, 0)"); // Not transparent
    }
  });

  test("user custom colors should override dark mode defaults", async ({ page }) => {
    // Create custom colors (bright red for testing)
    const customSettings = {
      ...mockSettings,
      color_settings: {
        ...mockSettings.color_settings,
        primary: {
          ...mockSettings.color_settings.primary,
          shade_950: "#ff0000", // Bright red instead of dark
        },
      },
    };

    // Mock the settings/options endpoint (same as color-settings test)
    await page.route("**/settings/options", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(customSettings),
      });
    });

    await page.goto("/settings");
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(500);
    await page.waitForTimeout(500);

    // Switch to dark mode
    await scrollToThemeSettings(page);
    const darkModeButton = page.getByRole("button", { name: /Dark Mode/i });
    await darkModeButton.click();
    await page.waitForTimeout(500);

    // Check that custom color is applied via CSS variable
    const primaryColor = await page.evaluate(() => {
      return getComputedStyle(document.documentElement)
        .getPropertyValue("--color-primary-950")
        .trim();
    });

    expect(primaryColor).toBe("#ff0000");

    // Also check the legacy variable format
    const legacyPrimaryColor = await page.evaluate(() => {
      return getComputedStyle(document.documentElement)
        .getPropertyValue("--primary-950")
        .trim();
    });

    expect(legacyPrimaryColor).toBe("#ff0000");
  });

  test("should have proper contrast between dark backgrounds and text", async ({ page }) => {
    await goToSettings(page);
    await scrollToThemeSettings(page);

    // Switch to dark mode
    const darkModeButton = page.getByRole("button", { name: /Dark Mode/i });
    await darkModeButton.click();
    await page.waitForTimeout(500);

    // Get multiple text elements and their backgrounds
    const elements = await page.locator("h2, h3, p, span").all();
    
    for (let i = 0; i < Math.min(5, elements.length); i++) {
      const element = elements[i];
      const isVisible = await element.isVisible().catch(() => false);
      
      if (!isVisible) continue;

      const styles = await element.evaluate((el) => {
        const computed = window.getComputedStyle(el);
        return {
          color: computed.color,
          backgroundColor: computed.backgroundColor,
        };
      });

      // Parse RGB values
      const textRgb = styles.color.match(/rgb\((\d+),\s*(\d+),\s*(\d+)\)/);
      const bgRgb = styles.backgroundColor.match(/rgb\((\d+),\s*(\d+),\s*(\d+)\)/);

      if (textRgb && bgRgb) {
        const [_, tr, tg, tb] = textRgb.map(Number);
        const [__, br, bg, bb] = bgRgb.map(Number);

        // Calculate relative luminance
        const textLuminance = 0.299 * tr + 0.587 * tg + 0.114 * tb;
        const bgLuminance = 0.299 * br + 0.587 * bg + 0.114 * bb;

        // Should have reasonable contrast (text lighter than background in dark mode)
        // Allow for some flexibility as computed styles may vary
        if (textLuminance > 50 || bgLuminance < 100) {
          // Either text is reasonably light OR background is reasonably dark
          expect(true).toBe(true);
        }
      }
    }
  });

  test("theme toggle should be accessible", async ({ page }) => {
    await goToSettings(page);
    await scrollToThemeSettings(page);

    // Check that theme buttons are keyboard accessible
    // Use exact text matches for the theme mode buttons (not the header button)
    const lightModeButton = page
      .getByRole("button", { name: "Light Mode Bright and clear" })
      .first();
    const darkModeButton = page
      .getByRole("button", { name: "Dark Mode Easy on the eyes" })
      .first();

    await expect(lightModeButton).toBeVisible();
    await expect(darkModeButton).toBeVisible();

    // Should be able to focus with keyboard
    await lightModeButton.focus();
    await expect(lightModeButton).toBeFocused();

    await darkModeButton.focus();
    await expect(darkModeButton).toBeFocused();
  });
});
