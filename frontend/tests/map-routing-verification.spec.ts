import { test, expect } from "@playwright/test";

/**
 * Quick verification tests for /map routing changes
 * These tests verify that the Next.js rewrite configuration works correctly
 * without requiring backend services.
 */

test.describe("/map Routing Verification", () => {
  test("should serve content at /map route", async ({ page }) => {
    // Navigate to /map
    await page.goto("/map");

    // URL should contain /map
    expect(page.url()).toContain("/map");

    // Page should load (may have errors due to no backend, but HTML should load)
    const bodyElement = page.locator("body");
    await expect(bodyElement).toBeVisible();
  });

  test("/map URL should persist after navigation", async ({ page }) => {
    // Navigate to /map
    await page.goto("/map");

    // Wait for page to load
    await page.waitForLoadState("domcontentloaded");

    // URL should still be /map
    expect(page.url()).toContain("/map");
  });

  test("next.config.ts rewrite should work", async ({ page }) => {
    // Navigate to /map
    await page.goto("/map");

    // Should render the root page content (rewrite working)
    // Check for Next.js HTML structure
    const html = await page.content();
    
    // Should have Next.js app structure (Next.js 15 uses different structure)
    // Check for Next.js specific elements that prove app is loaded
    expect(html).toContain("__next_f"); // Next.js RSC flight data
    expect(html).toContain("_next/static"); // Next.js static assets
    
    // Should have our app title
    expect(html).toContain("NaLaMap");
  });

  test("root path / should serve content (development mode)", async ({ page }) => {
    // In development (without nginx), / should work
    await page.goto("/");

    // Should load
    const bodyElement = page.locator("body");
    await expect(bodyElement).toBeVisible();
  });
});
