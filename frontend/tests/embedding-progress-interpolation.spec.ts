import { test, expect, Page } from '@playwright/test';

// Helper function to expand the GeoServer Backends section
async function expandGeoServerSection(page: Page) {
  const geoserverButton = page.locator("button:has-text('GeoServer Backends')");
  await expect(geoserverButton).toBeVisible({ timeout: 5000 });
  await geoserverButton.click();
  await page.waitForTimeout(300);
}

const mockSettings = {
  system_prompt: "Test system prompt",
  tool_options: {},
  example_geoserver_backends: [],
  model_providers: ["openai", "anthropic"],
  model_options: {},
  session_id: "test-session-id",
};

test.describe('Embedding Progress Interpolation', () => {
  test.beforeEach(async ({ page }) => {
    // Mock the settings/options endpoint for initialization
    await page.route("**/settings/options", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockSettings),
      });
    });

    // Mock the settings/state endpoint to return empty backends initially
    await page.route("**/settings/state", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          geoserver_backends: [],
          model_settings: {
            provider: 'openai',
            model: 'gpt-4-turbo',
          },
        }),
      });
    });

    // Navigate to settings page
    await page.goto('/settings');
    await page.waitForLoadState('networkidle');
    
    // Expand GeoServer Backends section
    await expandGeoServerSection(page);
  });

  // Note: This test was replaced by "should handle real updates smoothly without resets" below
  // which provides better E2E coverage by simulating realistic backend behavior.
  // The interpolation logic is thoroughly tested by unit tests in embedding-progress-logic.test.ts

  test('should handle real updates smoothly without resets', async ({ page }) => {
    let updateCount = 0;
    const updates = [
      { encoded: 0, total: 100 },
      { encoded: 15, total: 100 },  // After 5 seconds: 3/sec * 5 = 15
      { encoded: 30, total: 100 },  // After 10 seconds: 3/sec * 5 = 15 more
      { encoded: 45, total: 100 },  // After 15 seconds
      { encoded: 60, total: 100 },  // After 20 seconds
    ];

    await page.route('**/settings/geoserver/embedding-status*', async (route) => {
      const update = updates[Math.min(updateCount, updates.length - 1)];
      updateCount++;

      const url = new URL(route.request().url());
      const backendUrls = url.searchParams.get('backend_urls')?.split(',') || [];
      const backends: Record<string, any> = {};
      
      for (const backendUrl of backendUrls) {
        backends[backendUrl] = {
          total: update.total,
          encoded: update.encoded,
          percentage: (update.encoded / update.total) * 100,
          state: 'processing',
          in_progress: true,
          complete: false,
          error: null,
        };
      }

      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ backends }),
      });
    });

    await page.route('**/settings/geoserver/preload', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          total_layers: 100,
          session_id: 'test-session',
        }),
      });
    });

    // Add backend
    const testBackendUrl = 'test-geoserver.com';
    await page.getByPlaceholder('GeoServer URL').fill(testBackendUrl);
    await page.getByRole('button', { name: /Add Backend/i }).click();
    
    const normalizedUrl = `https://${testBackendUrl}`;
    await expect(page.locator(`text=${normalizedUrl}`)).toBeVisible({ timeout: 5000 });

    // Monitor for resets over a period of time
    const progressReadings: { time: number; value: number }[] = [];
    const startTime = Date.now();
    const monitorDuration = 15000; // 15 seconds to capture multiple updates

    while (Date.now() - startTime < monitorDuration && progressReadings.length < 30) {
      const progressText = await page.locator('text=/\\d+ \\/ \\d+ layers/').textContent();
      if (progressText) {
        const match = progressText.match(/(\d+(?:\.\d+)?)\s*\/\s*(\d+)/);
        if (match) {
          progressReadings.push({
            time: Date.now() - startTime,
            value: parseFloat(match[1]),
          });
        }
      }
      await page.waitForTimeout(500);
    }

    // Verify we got readings
    expect(progressReadings.length).toBeGreaterThan(5);

    // Check for resets (backward jumps > 2 layers, allowing for minor variations)
    for (let i = 1; i < progressReadings.length; i++) {
      const prev = progressReadings[i - 1];
      const curr = progressReadings[i];
      const jump = curr.value - prev.value;
      
      // If there's a backward jump of more than 2 layers, that's a reset
      expect(jump).toBeGreaterThanOrEqual(-2);
    }
    
    // Verify progress is generally increasing
    const firstReading = progressReadings[0];
    const lastReading = progressReadings[progressReadings.length - 1];
    expect(lastReading.value).toBeGreaterThan(firstReading.value);
  });
});
