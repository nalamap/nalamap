import { test, expect } from '@playwright/test';

test.describe('Scale Control - Map Instance Investigation', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('http://localhost:3000');
    await page.waitForSelector('.leaflet-container', { state: 'visible' });
    
    // Wait for scale control to be visible
    await page.waitForSelector('.leaflet-control-scale', { state: 'visible' });
    
    // Wait a bit for map to fully initialize
    await page.waitForTimeout(1000);
  });

  test('should investigate map instance availability', async ({ page }) => {
    // Try multiple ways to access the map instance
    const mapInfo = await page.evaluate(() => {
      const container = document.querySelector('.leaflet-container') as HTMLElement;
      if (!container) return { error: 'No container found' };

      // Method 1: _leaflet_id property
      const leafletId = (container as any)._leaflet_id;
      
      // Method 2: window.L global
      const L = (window as any).L;
      const hasLeaflet = !!L;
      
      // Method 3: Try to get from react-leaflet
      const reactLeaflet = (window as any).__REACT_LEAFLET__;
      
      // Method 4: Get all Leaflet map instances
      let mapInstance = null;
      if (L && leafletId !== undefined) {
        // Access internal Leaflet map registry
        const maps = (L as any).Map?._instances || {};
        mapInstance = maps[leafletId];
      }
      
      return {
        hasContainer: true,
        leafletId,
        hasLeaflet,
        hasReactLeaflet: !!reactLeaflet,
        hasMapInstance: !!mapInstance,
        mapCenter: mapInstance ? mapInstance.getCenter() : null,
        mapZoom: mapInstance ? mapInstance.getZoom() : null,
      };
    });

    console.log('Map Info:', JSON.stringify(mapInfo, null, 2));
    
    expect(mapInfo.hasContainer).toBe(true);
    expect(mapInfo.hasLeaflet).toBe(true);
  });

  test('should check scale control update mechanism', async ({ page }) => {
    // Get initial scale text
    const initialScale = await page.locator('.leaflet-control-scale-line').first().textContent();
    console.log('Initial scale:', initialScale);

    // Zoom in using the zoom button
    await page.click('a.leaflet-control-zoom-in');
    await page.waitForTimeout(500);

    // Get new scale text
    const afterZoomScale = await page.locator('.leaflet-control-scale-line').first().textContent();
    console.log('After zoom scale:', afterZoomScale);

    // Check if scale actually changed
    expect(afterZoomScale).not.toBe(initialScale);
  });

  test('should manually trigger scale update', async ({ page }) => {
    // Get the map and scale control
    const result = await page.evaluate(() => {
      const container = document.querySelector('.leaflet-container') as HTMLElement;
      const scaleControl = document.querySelector('.leaflet-control-scale') as HTMLElement;
      
      if (!container || !scaleControl) {
        return { error: 'Missing elements' };
      }

      const L = (window as any).L;
      const leafletId = (container as any)._leaflet_id;
      
      // Try to get map instance
      let map = null;
      if (L && leafletId !== undefined) {
        const maps = (L as any).Map?._instances || {};
        map = maps[leafletId];
      }
      
      if (!map) {
        return { error: 'Could not find map instance' };
      }

      // Get initial state
      const initialZoom = map.getZoom();
      const initialCenter = map.getCenter();
      const initialScale = scaleControl.querySelector('.leaflet-control-scale-line')?.textContent;

      // Manually zoom
      map.setZoom(5);
      
      // Force scale update if possible
      const scaleControlInstance = (scaleControl as any)._leaflet_control;
      if (scaleControlInstance && typeof scaleControlInstance.update === 'function') {
        scaleControlInstance.update();
      }
      
      const afterZoom = map.getZoom();
      const afterScale = scaleControl.querySelector('.leaflet-control-scale-line')?.textContent;

      return {
        initialZoom,
        initialCenter: `${initialCenter.lat.toFixed(2)}, ${initialCenter.lng.toFixed(2)}`,
        initialScale,
        afterZoom,
        afterScale,
        hasScaleControlInstance: !!scaleControlInstance,
        hasUpdateMethod: !!(scaleControlInstance && typeof scaleControlInstance.update === 'function'),
      };
    });

    console.log('Manual update result:', JSON.stringify(result, null, 2));
    
    if ('error' in result) {
      throw new Error(result.error);
    }

    expect(result.afterZoom).toBe(5);
    expect(result.afterScale).not.toBe(result.initialScale);
  });

  test('should check if scale control is bound to map events', async ({ page }) => {
    const eventInfo = await page.evaluate(() => {
      const container = document.querySelector('.leaflet-container') as HTMLElement;
      const L = (window as any).L;
      const leafletId = (container as any)._leaflet_id;
      
      let map = null;
      if (L && leafletId !== undefined) {
        const maps = (L as any).Map?._instances || {};
        map = maps[leafletId];
      }
      
      if (!map) {
        return { error: 'No map instance' };
      }

      // Check what events are registered on the map
      const events = (map as any)._events || {};
      const moveEvents = events.move || [];
      const zoomEvents = events.zoom || [];
      const zoomendEvents = events.zoomend || [];
      const moveendEvents = events.moveend || [];

      return {
        hasMoveEvents: moveEvents.length > 0,
        hasZoomEvents: zoomEvents.length > 0,
        hasZoomendEvents: zoomendEvents.length > 0,
        hasMoveendEvents: moveendEvents.length > 0,
        moveEventsCount: moveEvents.length,
        zoomEventsCount: zoomEvents.length,
        zoomendEventsCount: zoomendEvents.length,
        moveendEventsCount: moveendEvents.length,
      };
    });

    console.log('Event info:', JSON.stringify(eventInfo, null, 2));
    
    if ('error' in eventInfo) {
      throw new Error(eventInfo.error);
    }

    // Scale control should register move or zoomend events
    expect(eventInfo.hasMoveEvents || eventInfo.hasZoomendEvents || eventInfo.hasMoveendEvents).toBe(true);
  });
});
