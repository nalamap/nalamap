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
  
  console.log('Page loaded, waiting for Next.js hydration...');
  
  // Wait for Next.js to hydrate by checking for __NEXT_DATA__
  await page.waitForFunction(() => {
    return !!(window as any).__NEXT_DATA__;
  }, { timeout: 30000 });
  
  console.log('Next.js hydrated!');
  
  // Wait for hydration
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(3000);
  
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
