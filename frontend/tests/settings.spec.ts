import { test, expect } from "@playwright/test";

const mockSettings = {
  system_prompt: "You are a helpful assistant.",
  tool_options: {
    search: {
      default_prompt: "Search prompt",
      settings: {},
    },
  },
  search_portals: ["https://portal.example"],
  model_options: {
    MockProvider: [{ name: "mock-model", max_tokens: 999 }],
  },
};

test.describe("Settings page", () => {
  test("initializes settings from backend options", async ({ page }) => {
    await page.route("**/settings/options", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockSettings),
      });
    });

    await page.goto("/settings");

    await expect(
      page.getByRole("heading", { level: 1, name: "Settings" }),
    ).toBeVisible();

    const providerSelect = page.locator("main select").first();
    await expect(providerSelect).toContainText("MockProvider");
    await expect(providerSelect).toHaveValue("MockProvider");

    const modelSelect = page.locator("main select").nth(1);
    await expect(modelSelect).toContainText("mock-model");
    await expect(modelSelect).toHaveValue("mock-model");

    const maxTokensInput = page.locator('main input[type="number"]').first();
    await expect(maxTokensInput).toHaveValue("999");
  });
});
