import { test, expect } from '@playwright/test';

test('check if stores are exposed', async ({ page }) => {
  // Set up console and error listeners BEFORE navigation
  const consoleMessages: string[] = [];
  page.on('console', msg => {
    consoleMessages.push(`[${msg.type()}] ${msg.text()}`);
  });

  const pageErrors: string[] = [];
  page.on('pageerror', error => {
    pageErrors.push(error.message);
  });

  await page.goto('/');
  
  console.log('Page loaded, waiting for app to be ready...');
  
  // Wait for the app to be ready by checking for stores or React hydration
  // Try multiple indicators to be more robust across environments
  await page.waitForFunction(() => {
    const hasStores = !!(window as any).useLayerStore || !!(window as any).useMapStore;
    const hasNextData = !!(window as any).__NEXT_DATA__;
    const nextRoot = document.querySelector('#__next');
    const hasReactRoot = nextRoot && nextRoot.children.length > 0;
    // Consider ready if we have stores OR Next.js data OR React root with content
    return hasStores || hasNextData || hasReactRoot;
  }, { timeout: 60000 }); // Increased timeout for CI
  
  console.log('App ready!');
  
  // Wait for network to settle
  await page.waitForLoadState('networkidle', { timeout: 30000 });
  // Give stores time to initialize
  await page.waitForTimeout(2000);
  
  // Check if the page has loaded properly
  const pageContent = await page.evaluate(() => {
    return {
      hasBody: !!document.body,
      bodyChildren: document.body?.children.length,
      bodyHTML: document.body?.innerHTML.substring(0, 500),
      hasStoresExposedAttr: document.body?.getAttribute('data-stores-exposed') === 'true',
      scriptCount: document.querySelectorAll('script').length,
      hasNextData: !!(window as any).__NEXT_DATA__,
    };
  });
  console.log('Page content check:', pageContent);
  
  // Test that console capture works
  await page.evaluate(() => console.log('[TEST] This is a test log from browser'));
  
  await page.waitForTimeout(2000);
  
  // Check console messages
  const hasStoreLog = consoleMessages.some(msg => msg.includes('Stores exposed'));
  console.log('Has store exposure log:', hasStoreLog);
  console.log('All console messages:', consoleMessages);
  
  // Check window object
  const windowCheck = await page.evaluate(() => {
    return {
      hasUseLayerStore: typeof (window as any).useLayerStore !== 'undefined',
      hasUseMapStore: typeof (window as any).useMapStore !== 'undefined',
      hasUseSettingsStore: typeof (window as any).useSettingsStore !== 'undefined',
      hasStoresExposedFlag: (window as any).__STORES_EXPOSED__ === true,
      allKeys: Object.keys(window).filter(key => 
        key.includes('Store') || key.includes('store') || key.includes('STORES')
      )
    };
  });
  console.log('Window check:', windowCheck);
  console.log('Console messages:', consoleMessages);
  console.log('Page errors:', pageErrors);
  
  expect(windowCheck.hasUseLayerStore).toBe(true);
});
