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

test.describe("Chat interface", () => {
  test("sends a message and renders agent response", async ({ page }) => {
    await page.route("**/settings/options", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockSettings),
      });
    });

    const mockResponse = {
      messages: [
        { type: "human", content: "Hello agent!" },
        { type: "ai", content: "Mock agent response" },
      ],
      geodata_results: [],
      geodata_layers: [],
    };

    await page.route("**/chat", async (route) => {
      const request = route.request();
      const payload = JSON.parse(request.postData() || "{}");
      expect(payload.query).toBe("Hello agent!");

      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockResponse),
      });
    });

    await page.goto("/");

    const chatInput = page.getByPlaceholder("Type a chat command...");
    await chatInput.fill("Hello agent!");

    await Promise.all([
      page.waitForResponse("**/chat"),
      chatInput.press("Enter"),
    ]);

    await expect(page.getByText("Hello agent!").first()).toBeVisible();
    await expect(page.getByText("Mock agent response")).toBeVisible();
  });
});
