import { test, expect, Page } from "@playwright/test";

// Helper function to expand the Model Settings section
async function expandModelSettings(page: Page) {
  const modelButton = page.locator("button:has-text('Model Settings')");
  await expect(modelButton).toBeVisible({ timeout: 5000 });
  await modelButton.click();
  await page.waitForTimeout(300);
}

const mockSettings = {
  system_prompt: "You are a helpful AI assistant.",
  tool_options: {},
  example_geoserver_backends: [],
  model_options: {
    openai: [
      { name: "gpt-4", max_tokens: 4000 },
      { name: "gpt-3.5-turbo", max_tokens: 2000 },
    ],
    anthropic: [
      { name: "claude-3-opus", max_tokens: 3000 },
      { name: "claude-3-sonnet", max_tokens: 2500 },
    ],
  },
  model_settings: {
    model_provider: "openai",
    model_name: "gpt-4",
    max_tokens: 4000,
    system_prompt: "You are a helpful AI assistant.",
  },
  session_id: "test-session-123",
};

test.describe("Model Settings Component", () => {
  test.beforeEach(async ({ page }) => {
    await page.route("**/settings/options", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockSettings),
      });
    });

    await page.goto("/settings");
    await page.waitForLoadState("networkidle");
  });

  test("should display model settings button", async ({ page }) => {
    const modelButton = page.locator("button:has-text('Model Settings')");
    await expect(modelButton).toBeVisible();
  });

  test("should expand and collapse model settings", async ({ page }) => {
    const modelButton = page.locator("button:has-text('Model Settings')");
    await expect(modelButton).toBeVisible();

    // Initially collapsed - provider select should not be visible
    const providerSelect = page.locator("select").first();
    await expect(providerSelect).not.toBeVisible();

    // Expand
    await modelButton.click();
    await page.waitForTimeout(300);
    await expect(providerSelect).toBeVisible();

    // Collapse
    await modelButton.click();
    await page.waitForTimeout(300);
    await expect(providerSelect).not.toBeVisible();
  });

  test("should display all model providers", async ({ page }) => {
    await expandModelSettings(page);

    const providerSelect = page.locator("select").first();
    await expect(providerSelect).toBeVisible();

    // Check that providers are in the dropdown
    await expect(providerSelect).toContainText("Openai");
    await expect(providerSelect).toContainText("Anthropic");
  });

  test("should display models for selected provider", async ({ page }) => {
    await expandModelSettings(page);

    const modelSelect = page.locator("select").nth(1);
    await expect(modelSelect).toBeVisible();

    // Should show openai models initially
    await expect(modelSelect).toContainText("gpt-4");
    await expect(modelSelect).toContainText("gpt-3.5-turbo");
  });

  test("should change available models when provider changes", async ({ page }) => {
    await expandModelSettings(page);

    const providerSelect = page.locator("select").first();
    const modelSelect = page.locator("select").nth(1);

    // Initially showing openai models
    await expect(modelSelect).toContainText("gpt-4");

    // Switch to anthropic
    await providerSelect.selectOption("anthropic");
    await page.waitForTimeout(300);

    // Should now show anthropic models
    await expect(modelSelect).toContainText("claude-3-opus");
    await expect(modelSelect).toContainText("claude-3-sonnet");
  });

  test("should display max tokens input", async ({ page }) => {
    await expandModelSettings(page);

    const maxTokensInput = page.locator('input[type="number"]').first();
    await expect(maxTokensInput).toBeVisible();
    await expect(maxTokensInput).toHaveValue("4000");
  });

  test("should allow changing max tokens", async ({ page }) => {
    await expandModelSettings(page);

    // Wait for model to be selected
    await page.waitForTimeout(500);

    const maxTokensInput = page.locator('input[type="number"]').first();
    
    // Test setting a valid value within the model's limit (4000)
    await maxTokensInput.fill("3000");
    await expect(maxTokensInput).toHaveValue("3000");
    
    // Test that validation clamps to max when exceeding limit
    await maxTokensInput.fill("5000");
    await page.waitForTimeout(200);
    // Should be clamped to the model's max_tokens (4000)
    await expect(maxTokensInput).toHaveValue("4000");
  });

  test("should display system prompt textarea", async ({ page }) => {
    await expandModelSettings(page);

    const systemPromptTextarea = page.locator("textarea").first();
    await expect(systemPromptTextarea).toBeVisible();
    await expect(systemPromptTextarea).toHaveValue("You are a helpful AI assistant.");
  });

  test("should allow editing system prompt", async ({ page }) => {
    await expandModelSettings(page);

    const systemPromptTextarea = page.locator("textarea").first();
    await systemPromptTextarea.fill("You are a specialized geospatial assistant.");

    await expect(systemPromptTextarea).toHaveValue(
      "You are a specialized geospatial assistant.",
    );
  });

  test("should persist model settings changes in store", async ({ page }) => {
    await expandModelSettings(page);

    const providerSelect = page.locator("select").first();
    await providerSelect.selectOption("anthropic");

    // Check that changes are persisted in the store
    const storeValue = await page.evaluate(() => {
      // @ts-ignore - accessing window store for testing
      return window.useSettingsStore?.getState().model_settings?.model_provider;
    });

    expect(storeValue).toBe("anthropic");
  });

  test("should update max tokens when model changes", async ({ page }) => {
    await expandModelSettings(page);

    const providerSelect = page.locator("select").first();
    const maxTokensInput = page.locator('input[type="number"]').first();

    // Initially gpt-4 with 4000 tokens
    await expect(maxTokensInput).toHaveValue("4000");

    // Switch provider to anthropic (this triggers max_tokens update)
    await providerSelect.selectOption("anthropic");
    await page.waitForTimeout(300);

    // Max tokens should update to the new provider's first model's max_tokens
    await expect(maxTokensInput).toHaveValue("3000");
  });

  test("should handle empty model options gracefully", async ({ page }) => {
    // Mock settings with no model options
    await page.route("**/settings/options", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          ...mockSettings,
          model_options: {},
          model_settings: {
            model_provider: "",
            model_name: "",
            max_tokens: 0,
            system_prompt: "",
          },
        }),
      });
    });

    await page.reload();
    await page.waitForLoadState("networkidle");

    await expandModelSettings(page);

    // Component should still render without errors
    const providerSelect = page.locator("select").first();
    await expect(providerSelect).toBeVisible();
  });
});
