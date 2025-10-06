import { expect, test } from '@playwright/test'

/**
 * Test suite for GeoServer backend immediate addition and progress tracking
 * 
 * Tests verify:
 * 1. Backend appears immediately when added (no waiting for embedding)
 * 2. Progress states display correctly (waiting -> processing -> completed)
 * 3. User can navigate away during embedding and return
 * 4. Multiple backends can be added and process simultaneously
 */

test.describe('GeoServer Backend Immediate Addition', () => {
    test.beforeEach(async ({ page }) => {
        // Navigate to settings page
        await page.goto('/settings')
        await page.waitForLoadState('networkidle')
    })

    test('backend appears immediately when added', async ({ page }) => {
        // Fill in backend details
        const testBackendUrl = 'https://test-geoserver.example.com/geoserver'
        const testBackendName = 'Test Backend'
        
        await page.fill('input[placeholder*="GeoServer URL"]', testBackendUrl)
        await page.fill('input[placeholder*="Backend Name"]', testBackendName)
        
        // Click add button
        await page.click('button:has-text("Add Backend")')
        
        // Backend should appear immediately in the list (within 2 seconds)
        await expect(page.locator(`text=${testBackendName}`)).toBeVisible({ timeout: 2000 })
        await expect(page.locator(`text=${testBackendUrl}`)).toBeVisible()
        
        // Should show a status indicator
        const backendItem = page.locator(`li:has-text("${testBackendName}")`)
        await expect(backendItem).toBeVisible()
        
        // Form inputs should be cleared
        await expect(page.locator('input[placeholder*="GeoServer URL"]')).toHaveValue('')
        await expect(page.locator('input[placeholder*="Backend Name"]')).toHaveValue('')
    })

    test('progress states display correctly', async ({ page }) => {
        const testBackendUrl = 'https://test-geoserver.example.com/geoserver'
        const testBackendName = 'Progress Test Backend'
        
        // Add backend
        await page.fill('input[placeholder*="GeoServer URL"]', testBackendUrl)
        await page.fill('input[placeholder*="Backend Name"]', testBackendName)
        await page.click('button:has-text("Add Backend")')
        
        // Wait for backend to appear
        await expect(page.locator(`text=${testBackendName}`)).toBeVisible({ timeout: 2000 })
        
        const backendItem = page.locator(`li:has-text("${testBackendName}")`)
        
        // Should show "Waiting to start" state initially (or processing if it starts fast)
        await expect(
            backendItem.locator('text=/Waiting to start|Embedding in progress/')
        ).toBeVisible({ timeout: 5000 })
        
        // Wait for processing state (if not already there)
        // Note: In a real test, we'd mock the backend to control timing
        await page.waitForTimeout(2000)
        
        // Eventually should show progress or completion
        // (Exact state depends on backend speed and test environment)
        await expect(
            backendItem.locator('text=/Embedding|layers/')
        ).toBeVisible({ timeout: 10000 })
    })

    test('user can navigate away during embedding', async ({ page }) => {
        const testBackendUrl = 'https://test-geoserver.example.com/geoserver'
        const testBackendName = 'Navigate Test Backend'
        
        // Add backend
        await page.fill('input[placeholder*="GeoServer URL"]', testBackendUrl)
        await page.fill('input[placeholder*="Backend Name"]', testBackendName)
        await page.click('button:has-text("Add Backend")')
        
        // Wait for backend to appear
        await expect(page.locator(`text=${testBackendName}`)).toBeVisible({ timeout: 2000 })
        
        // Navigate to chat page immediately
        await page.goto('/')
        await page.waitForLoadState('networkidle')
        
        // Verify we're on the chat page
        await expect(page.locator('input[placeholder*="message"]')).toBeVisible()
        
        // Navigate back to settings
        await page.goto('/settings')
        await page.waitForLoadState('networkidle')
        
        // Backend should still be there
        await expect(page.locator(`text=${testBackendName}`)).toBeVisible()
        
        // Progress status should still be updating
        const backendItem = page.locator(`li:has-text("${testBackendName}")`)
        await expect(
            backendItem.locator('text=/Embedding|Waiting|complete/')
        ).toBeVisible({ timeout: 5000 })
    })

    test('multiple backends can be added simultaneously', async ({ page }) => {
        const backends = [
            { url: 'https://backend1.example.com/geoserver', name: 'Backend One' },
            { url: 'https://backend2.example.com/geoserver', name: 'Backend Two' },
            { url: 'https://backend3.example.com/geoserver', name: 'Backend Three' },
        ]
        
        // Add all backends quickly
        for (const backend of backends) {
            await page.fill('input[placeholder*="GeoServer URL"]', backend.url)
            await page.fill('input[placeholder*="Backend Name"]', backend.name)
            await page.click('button:has-text("Add Backend")')
            
            // Wait for it to appear before adding next
            await expect(page.locator(`text=${backend.name}`)).toBeVisible({ timeout: 2000 })
        }
        
        // All backends should be visible
        for (const backend of backends) {
            await expect(page.locator(`text=${backend.name}`)).toBeVisible()
        }
        
        // Each should have its own progress indicator
        for (const backend of backends) {
            const backendItem = page.locator(`li:has-text("${backend.name}")`)
            await expect(
                backendItem.locator('text=/Embedding|Waiting|layers/')
            ).toBeVisible({ timeout: 5000 })
        }
    })

    test('error state displays correctly', async ({ page }) => {
        // Add backend with invalid URL to trigger error
        const testBackendUrl = 'https://invalid-nonexistent-backend.example.com/geoserver'
        const testBackendName = 'Error Test Backend'
        
        await page.fill('input[placeholder*="GeoServer URL"]', testBackendUrl)
        await page.fill('input[placeholder*="Backend Name"]', testBackendName)
        await page.click('button:has-text("Add Backend")')
        
        // Backend should appear immediately
        await expect(page.locator(`text=${testBackendName}`)).toBeVisible({ timeout: 2000 })
        
        // Should eventually show error state
        const backendItem = page.locator(`li:has-text("${testBackendName}")`)
        
        // Wait for error message to appear (may take a few seconds for connection timeout)
        await expect(
            backendItem.locator('text=/Error|✗/')
        ).toBeVisible({ timeout: 30000 })
    })

    test('progress percentage updates correctly', async ({ page }) => {
        const testBackendUrl = 'https://test-geoserver.example.com/geoserver'
        const testBackendName = 'Percentage Test Backend'
        
        // Add backend
        await page.fill('input[placeholder*="GeoServer URL"]', testBackendUrl)
        await page.fill('input[placeholder*="Backend Name"]', testBackendName)
        await page.click('button:has-text("Add Backend")')
        
        // Wait for backend to appear
        await expect(page.locator(`text=${testBackendName}`)).toBeVisible({ timeout: 2000 })
        
        const backendItem = page.locator(`li:has-text("${testBackendName}")`)
        
        // Should see percentage indicator once processing starts
        await expect(
            backendItem.locator('text=/%/')
        ).toBeVisible({ timeout: 10000 })
        
        // Get initial percentage
        const percentageText = await backendItem.locator('text=/%/').textContent()
        const initialPercentage = parseInt(percentageText?.match(/(\d+)%/)?.[1] || '0')
        
        // Wait a bit and check again - percentage should increase or be 100%
        await page.waitForTimeout(5000)
        
        const updatedPercentageText = await backendItem.locator('text=/%/').textContent()
        const updatedPercentage = parseInt(updatedPercentageText?.match(/(\d+)%/)?.[1] || '0')
        
        // Percentage should have increased or reached 100%
        expect(updatedPercentage).toBeGreaterThanOrEqual(initialPercentage)
    })

    test('completed backend shows checkmark', async ({ page }) => {
        const testBackendUrl = 'https://fast-backend.example.com/geoserver'
        const testBackendName = 'Fast Completion Backend'
        
        // Add backend
        await page.fill('input[placeholder*="GeoServer URL"]', testBackendUrl)
        await page.fill('input[placeholder*="Backend Name"]', testBackendName)
        await page.click('button:has-text("Add Backend")')
        
        // Wait for backend to appear
        await expect(page.locator(`text=${testBackendName}`)).toBeVisible({ timeout: 2000 })
        
        const backendItem = page.locator(`li:has-text("${testBackendName}")`)
        
        // Eventually should show completion (with generous timeout for real backend)
        await expect(
            backendItem.locator('text=/✓ Embedding complete/')
        ).toBeVisible({ timeout: 60000 })
        
        // Progress bar should be green and at 100%
        const progressBar = backendItem.locator('div.bg-green-500')
        await expect(progressBar).toBeVisible()
    })
})

test.describe('GeoServer Backend State Persistence', () => {
    test('backend state persists across page reloads', async ({ page }) => {
        const testBackendUrl = 'https://persist-test.example.com/geoserver'
        const testBackendName = 'Persistence Test Backend'
        
        // Add backend
        await page.goto('/settings')
        await page.fill('input[placeholder*="GeoServer URL"]', testBackendUrl)
        await page.fill('input[placeholder*="Backend Name"]', testBackendName)
        await page.click('button:has-text("Add Backend")')
        
        // Wait for backend to appear
        await expect(page.locator(`text=${testBackendName}`)).toBeVisible({ timeout: 2000 })
        
        // Reload page
        await page.reload()
        await page.waitForLoadState('networkidle')
        
        // Backend should still be there
        await expect(page.locator(`text=${testBackendName}`)).toBeVisible()
        
        // Progress should continue from where it was
        const backendItem = page.locator(`li:has-text("${testBackendName}")`)
        await expect(
            backendItem.locator('text=/Embedding|Waiting|complete/')
        ).toBeVisible({ timeout: 5000 })
    })
})
