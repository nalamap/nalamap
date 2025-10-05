import { test, expect } from '@playwright/test';

/**
 * Minimal test case to isolate Next.js hydration issue.
 * This test simply checks if:
 * 1. The page loads
 * 2. Next.js hydrates (client-side JS executes)
 * 3. A simple useEffect hook runs
 */
test('minimal hydration check', async ({ page }) => {
  console.log('Starting minimal hydration test...');
  
  // Capture console messages
  const consoleMessages: string[] = [];
  page.on('console', msg => {
    const text = msg.text();
    consoleMessages.push(`[${msg.type()}] ${text}`);
    console.log(`Browser console [${msg.type()}]:`, text);
  });

  // Capture errors
  const pageErrors: string[] = [];
  page.on('pageerror', error => {
    const errorMsg = error.message;
    pageErrors.push(errorMsg);
    console.error('Browser error:', errorMsg);
  });

  // Navigate to the page
  console.log('Navigating to /...');
  await page.goto('/', { waitUntil: 'domcontentloaded' });
  
  console.log('Page loaded, waiting for network idle...');
  await page.waitForLoadState('networkidle', { timeout: 15000 });
  
  // Check basic page structure
  const pageStructure = await page.evaluate(() => {
    return {
      hasBody: !!document.body,
      hasHtml: !!document.documentElement,
      bodyChildrenCount: document.body?.children.length || 0,
      scriptCount: document.querySelectorAll('script').length,
      // Check for Next.js specific elements
      hasNextScript: !!document.querySelector('script[src*="_next"]'),
      // Check if __NEXT_DATA__ exists (set by Next.js during hydration)
      hasNextData: typeof (window as any).__NEXT_DATA__ !== 'undefined',
      nextDataKeys: (window as any).__NEXT_DATA__ ? Object.keys((window as any).__NEXT_DATA__) : [],
    };
  });
  
  console.log('Page structure:', JSON.stringify(pageStructure, null, 2));
  
  // Inject a simple hydration test marker
  await page.evaluate(() => {
    console.log('[TEST] Injected test script executed');
    (window as any).__TEST_SCRIPT_RAN__ = true;
  });
  
  // Wait a bit for any deferred scripts
  await page.waitForTimeout(2000);
  
  // Check if our injected script ran
  const testScriptRan = await page.evaluate(() => {
    return (window as any).__TEST_SCRIPT_RAN__ === true;
  });
  
  console.log('Test script ran:', testScriptRan);
  
  // Check if stores were exposed (should happen if hydration works)
  const storesCheck = await page.evaluate(() => {
    return {
      hasUseLayerStore: typeof (window as any).useLayerStore !== 'undefined',
      hasStoresExposedFlag: (window as any).__STORES_EXPOSED__ === true,
      hasDataStoresExposedAttr: document.body?.getAttribute('data-stores-exposed') === 'true',
    };
  });
  
  console.log('Stores check:', storesCheck);
  console.log('All console messages:', consoleMessages);
  console.log('Page errors:', pageErrors);
  
  // Log results (don't assert yet)
  console.log('\n=== Test Results ===');
  console.log(`Has Body: ${pageStructure.hasBody ? '✅' : '❌'}`);
  console.log(`Script Count: ${pageStructure.scriptCount}`);
  console.log(`Test Script Ran: ${testScriptRan ? '✅' : '❌'}`);
  console.log(`Next.js Hydrated (__NEXT_DATA__): ${pageStructure.hasNextData ? '✅' : '❌'}`);
  console.log(`Stores Exposed (flag): ${storesCheck.hasStoresExposedFlag ? '✅' : '❌'}`);
  console.log(`Stores Exposed (DOM attr): ${storesCheck.hasDataStoresExposedAttr ? '✅' : '❌'}`);
  console.log(`Has useLayerStore: ${storesCheck.hasUseLayerStore ? '✅' : '❌'}`);
  console.log(`Console Messages: ${consoleMessages.length}`);
  console.log(`Page Errors: ${pageErrors.length}`);
  
  // Only fail if critical issues exist
  expect(pageStructure.hasBody).toBe(true);
  expect(testScriptRan).toBe(true);
  expect(pageErrors.length).toBe(0);
  
  // The key test - are stores accessible?
  expect(storesCheck.hasUseLayerStore).toBe(true);
});
