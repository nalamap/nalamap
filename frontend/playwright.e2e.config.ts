import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright configuration for E2E tests
 * 
 * These tests validate real user workflows with actual backend services.
 * Tests use public data only (no confidential partner information).
 */
export default defineConfig({
  testDir: './e2e-tests',
  fullyParallel: false, // Run E2E tests sequentially
  retries: process.env.CI ? 1 : 0, // Retry once in CI
  timeout: 180_000, // 3 minutes for real backend calls
  
  use: {
    baseURL: 'http://localhost:3000',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  
  // For E2E tests, we expect a running backend
  // In CI, tests should be skipped or run against a deployed environment
  webServer: process.env.CI ? undefined : {
    command: 'npm run dev',
    url: 'http://localhost:3000',
    reuseExistingServer: true,
    timeout: 120 * 1000,
  },
  
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});
