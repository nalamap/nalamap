import { test, expect } from "@playwright/test";

const mockSettingsWithMCP = {
  system_prompt: "You are a helpful assistant.",
  tool_options: {
    search: {
      default_prompt: "Search prompt",
      settings: {},
    },
  },
  example_geoserver_backends: [],
  example_mcp_servers: [
    {
      url: "http://localhost:8001/mcp",
      name: "Local Test MCP Server",
      description: "A local MCP server for testing",
    },
  ],
  model_options: {
    MockProvider: [{ name: "mock-model", max_tokens: 999 }],
  },
  session_id: "test-session-123",
};

test.describe("MCP Server Settings", () => {
  test.beforeEach(async ({ page }) => {
    // Mock settings endpoint
    await page.route("**/settings/options", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockSettingsWithMCP),
      });
    });
  });

  test("displays MCP Servers section", async ({ page }) => {
    await page.goto("/settings");
    await page.waitForLoadState("networkidle");

    // Find and expand MCP Servers section
    const mcpButton = page.locator("button:has-text('MCP Servers')");
    await mcpButton.scrollIntoViewIfNeeded();
    await expect(mcpButton).toBeVisible();
  });

  test("can expand and collapse MCP Servers section", async ({ page }) => {
    await page.goto("/settings");
    await page.waitForLoadState("networkidle");

    const mcpButton = page.locator("button:has-text('MCP Servers')");
    await mcpButton.scrollIntoViewIfNeeded();
    await mcpButton.click();

    // Should show content after expanding
    await expect(
      page.locator("text=Add Custom MCP Server")
    ).toBeVisible({ timeout: 2000 });

    // Collapse again
    await mcpButton.click();
    await page.waitForTimeout(300);

    // Content should be hidden
    await expect(page.locator("text=Add Custom MCP Server")).not.toBeVisible();
  });

  test("displays example MCP servers", async ({ page }) => {
    await page.goto("/settings");
    await page.waitForLoadState("networkidle");

    // Expand MCP Servers section
    const mcpButton = page.locator("button:has-text('MCP Servers')");
    await mcpButton.scrollIntoViewIfNeeded();
    await mcpButton.click();

    // Wait for section to expand
    await page.waitForTimeout(500);

    // Check for example servers section
    await expect(page.locator("text=Example MCP Servers")).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "Local Test MCP Server" })
    ).toBeVisible();

    // Check dropdown has the example server
    const dropdown = page.locator("select").filter({ hasText: "Select an example MCP server" });
    await expect(dropdown).toBeVisible();
    await expect(dropdown).toContainText("Local Test MCP Server");
  });

  test("can add custom MCP server", async ({ page }) => {
    await page.goto("/settings");
    await page.waitForLoadState("networkidle");

    // Expand MCP Servers section
    const mcpButton = page.locator("button:has-text('MCP Servers')");
    await mcpButton.scrollIntoViewIfNeeded();
    await mcpButton.click();
    await page.waitForTimeout(500);

    // Fill in custom MCP server form
    const urlInput = page.locator(
      'input[placeholder*="MCP Server URL"]'
    );
    await urlInput.scrollIntoViewIfNeeded();
    await urlInput.fill("http://localhost:9000/mcp");

    const nameInput = page.locator('input[placeholder*="Name (optional)"]').last();
    await nameInput.fill("Custom Test Server");

    const descInput = page.locator('textarea[placeholder*="Description"]').last();
    await descInput.fill("My custom MCP server");

    // Click Add button
    const addButton = page.locator("button:has-text('Add MCP Server')");
    await addButton.click();

    // Verify server appears in configured list
    await expect(
      page.locator("text=Configured MCP Servers")
    ).toBeVisible();
    await expect(page.locator("text=Custom Test Server")).toBeVisible();
    await expect(page.locator("text=http://localhost:9000/mcp")).toBeVisible();
  });

  test("can add example MCP server from dropdown", async ({ page }) => {
    await page.goto("/settings");
    await page.waitForLoadState("networkidle");

    // Expand MCP Servers section
    const mcpButton = page.locator("button:has-text('MCP Servers')");
    await mcpButton.scrollIntoViewIfNeeded();
    await mcpButton.click();
    await page.waitForTimeout(500);

    // Select example server from dropdown
    const dropdown = page.locator("select").filter({ hasText: "Select an example MCP server" });
    await dropdown.selectOption("http://localhost:8001/mcp");

    // Click Add Example Server button
    const addButton = page.locator("button:has-text('Add Example Server')");
    await addButton.click();

    // Verify server appears in configured list
    await expect(
      page.locator("text=Configured MCP Servers")
    ).toBeVisible();
    await expect(
      page.locator("li").filter({ hasText: "Local Test MCP Server" })
    ).toBeVisible();
    await expect(
      page.locator("li").filter({ hasText: "Local Test MCP Server" }).locator("text=http://localhost:8001/mcp")
    ).toBeVisible();
  });

  test("can toggle MCP server enabled/disabled", async ({ page }) => {
    await page.goto("/settings");
    await page.waitForLoadState("networkidle");

    // Expand and add a server first
    const mcpButton = page.locator("button:has-text('MCP Servers')");
    await mcpButton.scrollIntoViewIfNeeded();
    await mcpButton.click();
    await page.waitForTimeout(500);

    const urlInput = page.locator('input[placeholder*="MCP Server URL"]');
    await urlInput.fill("http://localhost:9000/mcp");

    const addButton = page.locator("button:has-text('Add MCP Server')");
    await addButton.click();

    // Find the checkbox for the server
    const checkbox = page
      .locator("li")
      .filter({ hasText: "http://localhost:9000/mcp" })
      .locator('input[type="checkbox"]');

    // Should be checked by default
    await expect(checkbox).toBeChecked();

    // Uncheck it
    await checkbox.uncheck();
    await expect(checkbox).not.toBeChecked();

    // Check it again
    await checkbox.check();
    await expect(checkbox).toBeChecked();
  });

  test("can remove MCP server", async ({ page }) => {
    await page.goto("/settings");
    await page.waitForLoadState("networkidle");

    // Expand and add a server first
    const mcpButton = page.locator("button:has-text('MCP Servers')");
    await mcpButton.scrollIntoViewIfNeeded();
    await mcpButton.click();
    await page.waitForTimeout(500);

    const urlInput = page.locator('input[placeholder*="MCP Server URL"]');
    await urlInput.fill("http://localhost:9000/mcp");

    const nameInput = page.locator('input[placeholder*="Name (optional)"]').last();
    await nameInput.fill("Test Server");

    const addButton = page.locator("button:has-text('Add MCP Server')");
    await addButton.click();

    // Verify server was added
    await expect(page.locator("text=Test Server")).toBeVisible();

    // Click remove button
    const removeButton = page
      .locator("li")
      .filter({ hasText: "Test Server" })
      .locator("button:has-text('Remove')");
    await removeButton.click();

    // Verify server was removed
    await expect(page.locator("text=Test Server")).not.toBeVisible();
    await expect(
      page.locator("text=No MCP servers configured")
    ).toBeVisible();
  });

  test("shows empty state when no MCP servers configured", async ({ page }) => {
    await page.goto("/settings");
    await page.waitForLoadState("networkidle");

    // Expand MCP Servers section
    const mcpButton = page.locator("button:has-text('MCP Servers')");
    await mcpButton.scrollIntoViewIfNeeded();
    await mcpButton.click();
    await page.waitForTimeout(500);

    // Should show empty state message
    await expect(
      page.locator("text=No MCP servers configured")
    ).toBeVisible();
  });

  test("Add MCP Server button is disabled when URL is empty", async ({ page }) => {
    await page.goto("/settings");
    await page.waitForLoadState("networkidle");

    // Expand MCP Servers section
    const mcpButton = page.locator("button:has-text('MCP Servers')");
    await mcpButton.scrollIntoViewIfNeeded();
    await mcpButton.click();
    await page.waitForTimeout(500);

    const addButton = page.locator("button:has-text('Add MCP Server')");

    // Should be disabled when URL is empty
    await expect(addButton).toBeDisabled();

    // Fill in URL
    const urlInput = page.locator('input[placeholder*="MCP Server URL"]');
    await urlInput.fill("http://localhost:9000/mcp");

    // Should be enabled now
    await expect(addButton).toBeEnabled();
  });

  test("Add Example Server button is disabled when nothing selected", async ({
    page,
  }) => {
    await page.goto("/settings");
    await page.waitForLoadState("networkidle");

    // Expand MCP Servers section
    const mcpButton = page.locator("button:has-text('MCP Servers')");
    await mcpButton.scrollIntoViewIfNeeded();
    await mcpButton.click();
    await page.waitForTimeout(500);

    const addButton = page.locator("button:has-text('Add Example Server')");

    // Should be disabled when nothing selected
    await expect(addButton).toBeDisabled();

    // Select an example
    const dropdown = page.locator("select").filter({ hasText: "Select an example MCP server" });
    await dropdown.selectOption("http://localhost:8001/mcp");

    // Should be enabled now
    await expect(addButton).toBeEnabled();
  });
});
