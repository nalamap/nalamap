import { test, expect } from "@playwright/test";

/**
 * Tests for loading page behavior at root (/)
 * 
 * Architecture:
 * - Nginx serves static loading.html at /
 * - Loading page polls /health/nginx, /health/backend, /health/frontend
 * - When all services ready, auto-redirects to /map
 * - Next.js serves app on /map (internally rewrites to root)
 * 
 * NOTE: These tests require nginx to be running (production/docker environment).
 * They will be skipped in development where Next.js is accessed directly.
 * Run these tests with: docker-compose up (full stack with nginx)
 */

// Skip these tests in development (when accessing Next.js directly without nginx)
test.describe.skip("Loading Page and Redirect", () => {
  test("root path (/) serves loading page with health polling", async ({ page }) => {
    // Navigate to root
    await page.goto("/");

    // Should show loading page content
    await expect(page.locator("text=NaLaMap is starting")).toBeVisible({ timeout: 5000 });
    
    // Should have progress indicators
    await expect(page.locator("text=nginx").first()).toBeVisible();
    await expect(page.locator("text=backend").first()).toBeVisible();
    await expect(page.locator("text=frontend").first()).toBeVisible();

    // Check that loading animation elements are present
    const loadingContainer = page.locator(".flex.flex-col.items-center");
    await expect(loadingContainer).toBeVisible();
  });

  test("loading page redirects to /map when services are ready", async ({ page }) => {
    // Mock health endpoints to return ready immediately
    await page.route("**/health/nginx", (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "ok" }),
      });
    });

    await page.route("**/health/backend", (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "ok" }),
      });
    });

    await page.route("**/health/frontend", (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "ok" }),
      });
    });

    // Navigate to root
    await page.goto("/");

    // Wait for redirect to /map (should happen within 2 seconds after health checks)
    await page.waitForURL("**/map", { timeout: 5000 });
    
    // Verify we're now on /map
    expect(page.url()).toContain("/map");
  });

  test("/map serves the Next.js application", async ({ page }) => {
    // Navigate directly to /map
    await page.goto("/map");

    // Should load the main application (not loading page)
    // Look for map container
    await expect(page.locator(".leaflet-container")).toBeVisible({ timeout: 10000 });
    
    // Should not show loading page text
    await expect(page.locator("text=NaLaMap is starting")).not.toBeVisible();
  });

  test("loading page polls health endpoints at regular intervals", async ({ page }) => {
    let nginxCallCount = 0;
    let backendCallCount = 0;
    let frontendCallCount = 0;

    // Track health endpoint calls
    await page.route("**/health/nginx", (route) => {
      nginxCallCount++;
      route.fulfill({
        status: nginxCallCount < 3 ? 503 : 200, // Become ready after 3 calls
        contentType: "application/json",
        body: JSON.stringify({ status: nginxCallCount < 3 ? "starting" : "ok" }),
      });
    });

    await page.route("**/health/backend", (route) => {
      backendCallCount++;
      route.fulfill({
        status: backendCallCount < 3 ? 503 : 200,
        contentType: "application/json",
        body: JSON.stringify({ status: backendCallCount < 3 ? "starting" : "ok" }),
      });
    });

    await page.route("**/health/frontend", (route) => {
      frontendCallCount++;
      route.fulfill({
        status: frontendCallCount < 3 ? 503 : 200,
        contentType: "application/json",
        body: JSON.stringify({ status: frontendCallCount < 3 ? "starting" : "ok" }),
      });
    });

    // Navigate to root
    await page.goto("/");

    // Wait for multiple polling cycles (at least 3 seconds for 3 polls at 1s interval)
    await page.waitForTimeout(3500);

    // Verify health endpoints were called multiple times
    expect(nginxCallCount).toBeGreaterThanOrEqual(3);
    expect(backendCallCount).toBeGreaterThanOrEqual(3);
    expect(frontendCallCount).toBeGreaterThanOrEqual(3);

    // Should redirect to /map after all become ready
    await page.waitForURL("**/map", { timeout: 5000 });
  });

  test("loading page shows progress indicators for each service", async ({ page }) => {
    let nginxReady = false;
    let backendReady = false;

    // Make services become ready sequentially
    await page.route("**/health/nginx", (route) => {
      nginxReady = true;
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "ok" }),
      });
    });

    await page.route("**/health/backend", (route) => {
      setTimeout(() => { backendReady = true; }, 2000); // Ready after 2 seconds
      route.fulfill({
        status: backendReady ? 200 : 503,
        contentType: "application/json",
        body: JSON.stringify({ status: backendReady ? "ok" : "starting" }),
      });
    });

    await page.route("**/health/frontend", (route) => {
      route.fulfill({
        status: (nginxReady && backendReady) ? 200 : 503,
        contentType: "application/json",
        body: JSON.stringify({ status: (nginxReady && backendReady) ? "ok" : "starting" }),
      });
    });

    // Navigate to root
    await page.goto("/");

    // Initially should show loading state
    await expect(page.locator("text=NaLaMap is starting")).toBeVisible();
    
    // Wait for health checks to complete
    await page.waitForTimeout(3000);

    // Eventually should redirect to /map
    await page.waitForURL("**/map", { timeout: 5000 });
  });

  test("direct navigation to /map bypasses loading page", async ({ page }) => {
    // Navigate directly to /map
    await page.goto("/map");

    // Should never show loading page
    await expect(page.locator("text=NaLaMap is starting")).not.toBeVisible();
    
    // Should show map immediately (or as fast as Next.js can render)
    await expect(page.locator(".leaflet-container")).toBeVisible({ timeout: 10000 });
  });

  test("loading page shows warning after 30 seconds", async ({ page }) => {
    // Mock health endpoints to stay not ready
    await page.route("**/health/nginx", (route) => {
      route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({ status: "starting" }),
      });
    });

    await page.route("**/health/backend", (route) => {
      route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({ status: "starting" }),
      });
    });

    await page.route("**/health/frontend", (route) => {
      route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({ status: "starting" }),
      });
    });

    // Navigate to root
    await page.goto("/");

    // Wait for 30 second warning to appear
    // Note: This test is slow (30+ seconds), consider marking as @slow
    await expect(page.locator("text=Taking longer than expected")).toBeVisible({ 
      timeout: 35000 
    });
  });

  test("home button in sidebar links to /map", async ({ page }) => {
    // Navigate to /map
    await page.goto("/map");

    // Wait for sidebar to load
    await page.waitForSelector("button[title='Home']", { timeout: 5000 });

    // Click home button
    const homeButton = page.locator("button[title='Home']").first();
    await homeButton.click();

    // Should stay on /map or reload /map (not go to /)
    await page.waitForLoadState("networkidle");
    expect(page.url()).toContain("/map");
    
    // Should not show loading page
    await expect(page.locator("text=NaLaMap is starting")).not.toBeVisible();
  });

  test("rewrite configuration: /map shows root page content", async ({ page }) => {
    // Navigate to /map
    await page.goto("/map");

    // Should show the main map application (root page content)
    await expect(page.locator(".leaflet-container")).toBeVisible({ timeout: 10000 });
    
    // Should have all main app elements
    await expect(page.locator("button[title='Home']")).toBeVisible();
    await expect(page.locator("button[title='Settings']")).toBeVisible();
    
    // URL should still show /map
    expect(page.url()).toContain("/map");
  });
});

test.describe.skip("Loading Page Edge Cases", () => {
  test("loading page handles network errors gracefully", async ({ page }) => {
    // Mock health endpoints to fail
    await page.route("**/health/nginx", (route) => {
      route.abort("failed");
    });

    await page.route("**/health/backend", (route) => {
      route.abort("failed");
    });

    await page.route("**/health/frontend", (route) => {
      route.abort("failed");
    });

    // Navigate to root
    await page.goto("/");

    // Loading page should still be visible and not crash
    await expect(page.locator("text=NaLaMap is starting")).toBeVisible();
    
    // Should keep polling despite errors
    await page.waitForTimeout(3000);
    
    // Page should still be interactive
    const loadingPage = page.locator("body");
    await expect(loadingPage).toBeVisible();
  });

  test("loading page handles mixed service states", async ({ page }) => {
    // Nginx ready, backend slow, frontend waiting
    await page.route("**/health/nginx", (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "ok" }),
      });
    });

    let backendCallCount = 0;
    await page.route("**/health/backend", (route) => {
      backendCallCount++;
      route.fulfill({
        status: backendCallCount < 5 ? 503 : 200,
        contentType: "application/json",
        body: JSON.stringify({ status: backendCallCount < 5 ? "starting" : "ok" }),
      });
    });

    let frontendCallCount = 0;
    await page.route("**/health/frontend", (route) => {
      frontendCallCount++;
      route.fulfill({
        status: frontendCallCount < 5 ? 503 : 200,
        contentType: "application/json",
        body: JSON.stringify({ status: frontendCallCount < 5 ? "starting" : "ok" }),
      });
    });

    // Navigate to root
    await page.goto("/");

    // Should show loading page
    await expect(page.locator("text=NaLaMap is starting")).toBeVisible();

    // Wait for services to become ready
    await page.waitForTimeout(6000);

    // Should eventually redirect
    await page.waitForURL("**/map", { timeout: 5000 });
  });
});
