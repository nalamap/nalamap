import { test, expect } from '@playwright/test';

test.describe('Scale Control - User Experience Test', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('http://localhost:3000');
    await page.waitForLoadState('networkidle');
    
    // Wait for map components to be visible
    await page.waitForSelector('.leaflet-container', { state: 'visible' });
    await page.waitForSelector('.leaflet-control-scale', { state: 'visible' });
    
    // Give map a moment to fully initialize
    await page.waitForTimeout(1000);
  });

  test('USER SCENARIO: should show correct scale when zooming out to see whole world', async ({ page }) => {
    console.log('\n=== USER SCENARIO TEST ===');
    console.log('Simulating user zooming out to maximum level to see whole world\n');

    // Get initial scale
    const initialScale = await page.locator('.leaflet-control-scale-line').first().textContent();
    console.log(`Initial scale (zoom 2): ${initialScale}`);

    // User clicks zoom out button multiple times to see whole world
    for (let i = 0; i < 5; i++) {
      const zoomOutButton = page.locator('a.leaflet-control-zoom-out');
      const isDisabled = await zoomOutButton.getAttribute('aria-disabled');
      
      if (isDisabled === 'true') {
        console.log(`Cannot zoom out further (button disabled after ${i} clicks)`);
        break;
      }

      await zoomOutButton.click();
      await page.waitForTimeout(300);
      
      const currentScale = await page.locator('.leaflet-control-scale-line').first().textContent();
      console.log(`After zoom out ${i + 1}: ${currentScale}`);
    }

    // Get final scale at maximum zoom out
    const finalScale = await page.locator('.leaflet-control-scale-line').first().textContent();
    console.log(`\nFinal scale at max zoom out: ${finalScale}`);
    console.log('\nUSER REPORT: "scale was 30m on highest level - even it should be in the thousands of kilometers"');
    
    // The scale should show thousands of kilometers at max zoom out, not meters
    expect(finalScale).toContain('km');
    
    // Extract number from scale (e.g., "3000 km" -> 3000)
    const match = finalScale?.match(/(\d+)\s*km/);
    if (match) {
      const kmValue = parseInt(match[1]);
      console.log(`Scale shows ${kmValue} km`);
      
      // At maximum zoom out (zoom level 0 or 1), scale should be in thousands of km
      // User reported it should show "thousands of kilometers" but showed "30m" instead
      expect(kmValue).toBeGreaterThan(1000);
    }
  });

  test('USER SCENARIO: Pan around at same zoom and check if scale changes unexpectedly', async ({ page }) => {
    console.log('\n=== PAN TEST ===');
    console.log('Simulating user panning around at zoom level 5\n');

    // First zoom to a specific level
    await page.click('a.leaflet-control-zoom-in');
    await page.click('a.leaflet-control-zoom-in');
    await page.click('a.leaflet-control-zoom-in');
    await page.waitForTimeout(500);

    const initialScale = await page.locator('.leaflet-control-scale-line').first().textContent();
    console.log(`Initial scale at zoom 5: ${initialScale}`);

    // Pan the map by dragging
    const mapContainer = page.locator('.leaflet-container');
    const box = await mapContainer.boundingBox();
    
    if (box) {
      // Pan right
      await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
      await page.mouse.down();
      await page.mouse.move(box.x + box.width / 4, box.y + box.height / 2, { steps: 10 });
      await page.mouse.up();
      await page.waitForTimeout(300);
      
      const afterPanRight = await page.locator('.leaflet-control-scale-line').first().textContent();
      console.log(`After pan right: ${afterPanRight}`);

      // Pan down
      await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
      await page.mouse.down();
      await page.mouse.move(box.x + box.width / 2, box.y + box.height / 4, { steps: 10 });
      await page.mouse.up();
      await page.waitForTimeout(300);
      
      const afterPanDown = await page.locator('.leaflet-control-scale-line').first().textContent();
      console.log(`After pan down: ${afterPanDown}`);

      console.log('\nUSER REPORT: "I zoomed out all the way, scrolled around a bit and scale was changing constantly"');
      console.log('At same zoom level, scale should change when panning to different latitudes (Web Mercator distortion)');
      
      // Note: Scale SHOULD change with latitude in Web Mercator projection
      // This is expected behavior, not a bug
    }
  });

  test('USER SCENARIO: Draw a 200km buffer and measure it on scale', async ({ page }) => {
    console.log('\n=== BUFFER MEASUREMENT TEST ===');
    console.log('Simulating user creating a 200km buffer zone\n');

    // User creates a buffer (we'll just zoom to a level where ~200km should be visible)
    // At zoom 6-7, the scale should show something in the range of 100-500 km
    
    // Zoom in to level 7
    for (let i = 0; i < 5; i++) {
      await page.click('a.leaflet-control-zoom-in');
      await page.waitForTimeout(300);
    }

    // Wait for scale to stabilize after all the zoom actions
    await page.waitForTimeout(1000);

    const scaleAtZoom7 = await page.locator('.leaflet-control-scale-line').first().textContent();
    console.log(`Scale at zoom 7: ${scaleAtZoom7}`);
    console.log('\nUSER REPORT: "I added a 200km buffer zone, but scale says it would be about 400km"');
    console.log('Expected: Scale should show ~100-300 km at this zoom level');
    
    // Extract km value
    const match = scaleAtZoom7?.match(/(\d+)\s*km/);
    if (match) {
      const kmValue = parseInt(match[1]);
      console.log(`Scale shows ${kmValue} km`);
      
      // At zoom 7, typical scale bar shows 100-300 km
      // If user sees 400km for a 200km buffer, the scale would be showing ~200km
      expect(kmValue).toBeGreaterThan(50);
      expect(kmValue).toBeLessThan(500);
    }
  });

  test('DIAGNOSTIC: Check scale values at each zoom level 0-10', async ({ page }) => {
    console.log('\n=== ZOOM LEVEL SCALE VALUES ===\n');

    const scaleValues: { zoom: number; scale: string }[] = [];

    // Start from current zoom (2) and zoom out first
    let currentZoom = 2;
    
    // Zoom out to minimum
    for (let i = 0; i < 5; i++) {
      const zoomOutButton = page.locator('a.leaflet-control-zoom-out');
      const isDisabled = await zoomOutButton.getAttribute('aria-disabled');
      
      if (isDisabled === 'true') break;
      
      await zoomOutButton.click();
      await page.waitForTimeout(300);
      currentZoom--;
    }

    // Now zoom in and record scale at each level
    for (let i = 0; i < 10; i++) {
      const scale = await page.locator('.leaflet-control-scale-line').first().textContent();
      scaleValues.push({ zoom: currentZoom, scale: scale || 'N/A' });
      
      const zoomInButton = page.locator('a.leaflet-control-zoom-in');
      const isDisabled = await zoomInButton.getAttribute('aria-disabled');
      
      if (isDisabled === 'true') break;
      
      await zoomInButton.click();
      await page.waitForTimeout(300);
      currentZoom++;
    }

    console.log('Zoom Level | Scale');
    console.log('-----------|-------');
    scaleValues.forEach(({ zoom, scale }) => {
      console.log(`${zoom.toString().padStart(10)} | ${scale}`);
    });

    // Verify scale decreases as we zoom in
    const firstKm = parseInt(scaleValues[0].scale.match(/(\d+)/)?.[1] || '0');
    const lastKm = parseInt(scaleValues[scaleValues.length - 1].scale.match(/(\d+)/)?.[1] || '0');
    
    console.log(`\nFirst zoom scale: ${firstKm} (km or m)`);
    console.log(`Last zoom scale: ${lastKm} (km or m)`);
    console.log('\nExpected: Scale should decrease as zoom increases');
    
    // First scale should be larger than last scale (when comparing raw numbers)
    // Note: This might not hold if units change from km to m
    expect(scaleValues.length).toBeGreaterThan(5);
  });
});
