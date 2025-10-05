import { promises as fs } from 'fs';
import { test, expect } from '@playwright/test';

const mockSettings = {
  system_prompt: 'Assist helpfully.',
  tool_options: {
    search: {
      default_prompt: 'Search prompt',
      settings: {},
    },
  },
  search_portals: ['https://portal.example'],
  model_options: {
    Provider: [
      { name: 'model-a', max_tokens: 512 },
    ],
  },
  session_id: 'session-initial',
};

test.describe('GeoServer backend preload', () => {
  test.beforeEach(async ({ page }) => {
    await page.route('**/settings/options', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockSettings),
      });
    });
  });

  test('shows an error when the backend cannot be prefetched', async ({ page }) => {
    await page.route('**/settings/geoserver/preload', async (route) => {
      await route.fulfill({
        status: 503,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'GeoServer unreachable' }),
      });
    });

    await page.goto('/settings');

    await page.getByPlaceholder('GeoServer URL').fill('https://example.com/geoserver');
    await page.getByRole('button', { name: 'Add Backend' }).click();

    await expect(page.getByText('GeoServer unreachable')).toBeVisible();
    await expect(page.getByText('Prefetched')).toHaveCount(0);
  });

  test('displays a success message and resets inputs after prefetching', async ({ page }) => {
    await page.route('**/settings/geoserver/preload', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          session_id: 'session-next',
          total_layers: 3,
        }),
      });
    });

    await page.goto('/settings');

    await page.getByPlaceholder('GeoServer URL').fill('https://demo.geo');
    await page.getByPlaceholder('Name (optional)', { exact: true }).fill('Demo Geo');
    await page.getByPlaceholder('Description (optional)').fill('Demo description');
    await page.getByRole('button', { name: 'Add Backend' }).click();

    await expect(page.getByText('Prefetched 3 layers successfully.')).toBeVisible();
    await expect(page.getByText('GeoServer unreachable')).toHaveCount(0);

    await expect(page.getByPlaceholder('GeoServer URL')).toHaveValue('');
    await expect(page.getByPlaceholder('Name (optional)', { exact: true })).toHaveValue('');
    await expect(page.getByPlaceholder('Description (optional)')).toHaveValue('');

    await expect(page.getByRole('listitem').filter({ hasText: 'Demo Geo' })).toBeVisible();
  });

  test('exports the current settings snapshot including prefetched backends', async ({ page }) => {
    await page.route('**/settings/geoserver/preload', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          session_id: 'session-next',
          total_layers: 2,
        }),
      });
    });

    await page.goto('/settings');

    await page.getByPlaceholder('GeoServer URL').fill('https://exports.example/geoserver');
    await page.getByRole('button', { name: 'Add Backend' }).click();
    await expect(page.getByText('Prefetched 2 layers successfully.')).toBeVisible();

    const downloadPromise = page.waitForEvent('download');
    await page.getByRole('button', { name: 'Export Settings' }).click();
    const download = await downloadPromise;
    const downloadPath = await download.path();
    expect(downloadPath).toBeTruthy();

    if (!downloadPath) {
      throw new Error('Download path missing');
    }

    const exported = JSON.parse(await fs.readFile(downloadPath, 'utf-8'));
    expect(exported.session_id).toBe('session-next');
    expect(exported.geoserver_backends).toEqual([
      expect.objectContaining({
        url: 'https://exports.example/geoserver',
        enabled: true,
      }),
    ]);
  });

  test('imports settings, prefetches configured backends, and ignores file session id', async ({ page }) => {
    const importSnapshot = {
      ...mockSettings,
      geoserver_backends: [
        {
          url: 'https://imports.example/one',
          name: 'Geo One',
          description: 'First backend',
          username: 'alice',
          password: 'secret',
          enabled: true,
        },
        {
          url: 'https://imports.example/two',
          name: 'Geo Two',
          description: 'Second backend',
          username: '',
          password: '',
          enabled: false,
        },
      ],
      session_id: 'import-session',
    };

    const seenRequests: any[] = [];
    await page.route('**/settings/geoserver/preload', async (route, request) => {
      const payload = request.postDataJSON();
      seenRequests.push(payload);
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          session_id: `session-refreshed-${seenRequests.length}`,
          total_layers: 4,
        }),
      });
    });

    await page.goto('/settings');

    await page.setInputFiles('input[type="file"]', {
      name: 'settings.json',
      mimeType: 'application/json',
      buffer: Buffer.from(JSON.stringify(importSnapshot)),
    });

    await expect(page.getByText('Prefetched 2 imported backends successfully.')).toBeVisible();

    // Look for GeoServer backend entries specifically
    await expect(page.getByRole('listitem').filter({ hasText: 'Geo One' })).toBeVisible();
    await expect(page.getByRole('listitem').filter({ hasText: 'Geo Two' })).toBeVisible();
    
    const geoOneItem = page.getByRole('listitem').filter({ hasText: 'Geo One' });
    const geoTwoItem = page.getByRole('listitem').filter({ hasText: 'Geo Two' });
    
    await expect(geoOneItem.getByRole('checkbox')).toBeChecked();
    await expect(geoTwoItem.getByRole('checkbox')).not.toBeChecked();

    expect(seenRequests).toHaveLength(2);
    expect(seenRequests[0].session_id).toBe('session-initial');
    expect(seenRequests[1].session_id).toBe('session-refreshed-1');
  });
});
