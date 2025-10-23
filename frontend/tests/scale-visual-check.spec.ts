import { test, expect } from "@playwright/test";

const mockSettings = {
  system_prompt: "You are a helpful assistant.",
  tool_options: {
    search: {
      default_prompt: "Search prompt",
      settings: {},
      enabled: true,
    },
  },
  example_geoserver_backends: [],
  model_options: {
    MockProvider: [{ name: "mock-model", max_tokens: 999 }],
  },
  session_id: "test-session",
};

test.describe("Scale Control Visual Check", () => {
  test.beforeEach(async ({ page }) => {
    await page.route("**/settings/options", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockSettings),
      });
    });

    await page.goto("/");
    await page.waitForLoadState("networkidle");
  });

  test("should have exactly one scale control with correct structure", async ({ page }) => {
    await page.waitForSelector(".leaflet-container", { timeout: 10000 });
    
    // Check how many scale controls exist
    const scaleControls = page.locator(".leaflet-control-scale");
    const controlCount = await scaleControls.count();
    
    console.log(`Number of scale controls: ${controlCount}`);
    expect(controlCount).toBe(1);

    // Check how many scale lines exist (should be 2: metric and imperial)
    const scaleLines = page.locator(".leaflet-control-scale-line");
    const lineCount = await scaleLines.count();
    
    console.log(`Number of scale lines: ${lineCount}`);
    expect(lineCount).toBe(2);

    // Get details of both lines
    const metricLine = scaleLines.nth(0);
    const imperialLine = scaleLines.nth(1);

    const metricInfo = await metricLine.evaluate((el) => ({
      text: el.textContent,
      width: (el as HTMLElement).style.width,
      offsetWidth: (el as HTMLElement).offsetWidth,
      class: el.className,
    }));

    const imperialInfo = await imperialLine.evaluate((el) => ({
      text: el.textContent,
      width: (el as HTMLElement).style.width,
      offsetWidth: (el as HTMLElement).offsetWidth,
      class: el.className,
    }));

    console.log("Metric line:", JSON.stringify(metricInfo, null, 2));
    console.log("Imperial line:", JSON.stringify(imperialInfo, null, 2));

    // Both should have reasonable widths
    expect(metricInfo.offsetWidth).toBeGreaterThan(30);
    expect(metricInfo.offsetWidth).toBeLessThan(120);
    expect(imperialInfo.offsetWidth).toBeGreaterThan(30);
    expect(imperialInfo.offsetWidth).toBeLessThan(120);
  });

  test("should check for any CSS transforms or scaling", async ({ page }) => {
    await page.waitForSelector(".leaflet-container", { timeout: 10000 });
    
    const scaleControl = page.locator(".leaflet-control-scale");
    
    const computedStyles = await scaleControl.evaluate((el) => {
      const styles = window.getComputedStyle(el);
      return {
        transform: styles.transform,
        scale: styles.scale,
        zoom: styles.zoom,
        fontSize: styles.fontSize,
        width: styles.width,
      };
    });

    console.log("Scale control computed styles:", JSON.stringify(computedStyles, null, 2));

    // Check if there's any unexpected transform
    expect(computedStyles.transform).toBe("none");
  });
});
