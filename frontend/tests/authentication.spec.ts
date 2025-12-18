import { test, expect } from '@playwright/test';

test.describe('Authentication flow', () => {
  test('Sign up flow redirects to map after successful signup', async ({ page }) => {
    await page.route('**/api/auth/oidc/providers', route =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) })
    );
    // Mock signup and me endpoints
    await page.route('**/api/auth/signup', route =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ user: { id: '1', email: 'alice@example.com', display_name: 'Alice' } }),
      })
    );
    await page.route('**/api/auth/me', route =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ id: '1', email: 'alice@example.com', display_name: 'Alice' }),
      })
    );

    await page.goto('/signup');
    await page.fill('input[name="email"]', 'alice@example.com');
    await page.fill('input[name="displayName"]', 'Alice');
    await page.fill('input[name="password"]', 'password123');
    await page.click('button[type="submit"]');
    await page.waitForURL('**/map');
    expect(page.url()).toContain('/map');
  });

  test('Login flow redirects to map after successful login', async ({ page }) => {
    await page.route('**/api/auth/oidc/providers', route =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) })
    );
    // Mock login and me endpoints
    await page.route('**/api/auth/login', route =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ user: { id: '2', email: 'bob@example.com', display_name: 'Bob' } }),
      })
    );
    await page.route('**/api/auth/me', route =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ id: '2', email: 'bob@example.com', display_name: 'Bob' }),
      })
    );

    await page.goto('/login');
    await page.fill('input[name="email"]', 'bob@example.com');
    await page.fill('input[name="password"]', 'password456');
    await page.click('button[type="submit"]');
    await page.waitForURL('**/map');
    expect(page.url()).toContain('/map');
  });
});
