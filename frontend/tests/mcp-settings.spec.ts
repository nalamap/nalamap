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
  example_mcp_servers: [],
  model_options: {
    MockProvider: [{ name: "mock-model", max_tokens: 999 }],
  },
  session_id: "test-session-123",
};

const mockSettingsWithExampleMCP = {
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

  test("displays example MCP servers when provided", async ({ page }) => {
    // Override with settings that have example servers
    await page.route("**/settings/options", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockSettingsWithExampleMCP),
      });
    });

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

  test("hides example MCP servers section when none provided", async ({ page }) => {
    await page.goto("/settings");
    await page.waitForLoadState("networkidle");

    // Expand MCP Servers section
    const mcpButton = page.locator("button:has-text('MCP Servers')");
    await mcpButton.scrollIntoViewIfNeeded();
    await mcpButton.click();

    // Wait for section to expand
    await page.waitForTimeout(500);

    // Example servers section should not be visible
    await expect(page.locator("text=Example MCP Servers")).not.toBeVisible();
    
    // Custom server section should still be visible
    await expect(page.locator("text=Add Custom MCP Server")).toBeVisible();
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
    // Override with settings that have example servers
    await page.route("**/settings/options", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockSettingsWithExampleMCP),
      });
    });

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
    // Override with settings that have example servers
    await page.route("**/settings/options", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockSettingsWithExampleMCP),
      });
    });

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

  test("can add API key to custom MCP server", async ({ page }) => {
    await page.goto("/settings");
    await page.waitForLoadState("networkidle");

    // Expand MCP Servers section
    const mcpButton = page.locator("button:has-text('MCP Servers')");
    await mcpButton.scrollIntoViewIfNeeded();
    await mcpButton.click();
    await page.waitForTimeout(500);

    // Fill in custom MCP server form with API key
    const urlInput = page.locator('input[placeholder*="MCP Server URL"]');
    await urlInput.scrollIntoViewIfNeeded();
    await urlInput.fill("http://localhost:9000/mcp");

    const nameInput = page.locator('input[placeholder*="Name (optional)"]').last();
    await nameInput.fill("Authenticated Server");

    const apiKeyInput = page.locator('input[placeholder*="API Key"]');
    await apiKeyInput.fill("test-api-key-12345");

    // Click Add button
    const addButton = page.locator("button:has-text('Add MCP Server')");
    await addButton.click();

    // Verify server appears with API key indicator
    await expect(page.locator("text=Authenticated Server")).toBeVisible();
    await expect(page.locator("text=🔑 API Key configured")).toBeVisible();
  });

  test("can add custom headers to MCP server", async ({ page }) => {
    await page.goto("/settings");
    await page.waitForLoadState("networkidle");

    // Expand MCP Servers section
    const mcpButton = page.locator("button:has-text('MCP Servers')");
    await mcpButton.scrollIntoViewIfNeeded();
    await mcpButton.click();
    await page.waitForTimeout(500);

    // Fill in URL
    const urlInput = page.locator('input[placeholder*="MCP Server URL"]');
    await urlInput.scrollIntoViewIfNeeded();
    await urlInput.fill("http://localhost:9000/mcp");

    const nameInput = page.locator('input[placeholder*="Name (optional)"]').last();
    await nameInput.fill("Server with Headers");

    // Add first custom header
    const headerKeyInput = page.locator('input[placeholder*="Header name"]');
    const headerValueInput = page.locator('input[placeholder*="Header value"]');
    const addHeaderButton = page.locator('button[aria-label="Add header"]');

    await headerKeyInput.fill("X-API-Key");
    await headerValueInput.fill("my-api-key");
    await addHeaderButton.click();

    // Verify header appears in the list
    await expect(page.locator("text=X-API-Key: my-api-key")).toBeVisible();

    // Add second header
    await headerKeyInput.fill("X-Custom-Header");
    await headerValueInput.fill("custom-value");
    await addHeaderButton.click();

    // Verify second header appears
    await expect(page.locator("text=X-Custom-Header: custom-value")).toBeVisible();

    // Click Add MCP Server button
    const addButton = page.locator("button:has-text('Add MCP Server')");
    await addButton.click();

    // Verify server appears with headers indicator
    await expect(page.locator("text=Server with Headers")).toBeVisible();
    await expect(page.locator("text=📋 2 custom header(s)")).toBeVisible();
  });

  test("can remove custom headers before adding server", async ({ page }) => {
    await page.goto("/settings");
    await page.waitForLoadState("networkidle");

    // Expand MCP Servers section
    const mcpButton = page.locator("button:has-text('MCP Servers')");
    await mcpButton.scrollIntoViewIfNeeded();
    await mcpButton.click();
    await page.waitForTimeout(500);

    // Fill in URL
    const urlInput = page.locator('input[placeholder*="MCP Server URL"]');
    await urlInput.scrollIntoViewIfNeeded();
    await urlInput.fill("http://localhost:9000/mcp");

    // Add a custom header
    const headerKeyInput = page.locator('input[placeholder*="Header name"]');
    const headerValueInput = page.locator('input[placeholder*="Header value"]');
    const addHeaderButton = page.locator('button[aria-label="Add header"]');

    await headerKeyInput.fill("X-Test-Header");
    await headerValueInput.fill("test-value");
    await addHeaderButton.click();

    // Verify header appears
    await expect(page.locator("text=X-Test-Header: test-value")).toBeVisible();

    // Remove the header
    const removeHeaderButton = page.locator('button[aria-label="Remove header X-Test-Header"]');
    await removeHeaderButton.click();

    // Verify header is removed
    await expect(page.locator("text=X-Test-Header: test-value")).not.toBeVisible();
  });

  test("Add Header button is disabled when fields are empty", async ({ page }) => {
    await page.goto("/settings");
    await page.waitForLoadState("networkidle");

    // Expand MCP Servers section
    const mcpButton = page.locator("button:has-text('MCP Servers')");
    await mcpButton.scrollIntoViewIfNeeded();
    await mcpButton.click();
    await page.waitForTimeout(500);

    const addHeaderButton = page.locator('button[aria-label="Add header"]');
    
    // Should be disabled when both fields are empty
    await expect(addHeaderButton).toBeDisabled();

    // Fill only key
    const headerKeyInput = page.locator('input[placeholder*="Header name"]');
    await headerKeyInput.fill("X-Test");
    
    // Should still be disabled with only key
    await expect(addHeaderButton).toBeDisabled();

    // Clear key and fill only value
    await headerKeyInput.clear();
    const headerValueInput = page.locator('input[placeholder*="Header value"]');
    await headerValueInput.fill("test-value");
    
    // Should still be disabled with only value
    await expect(addHeaderButton).toBeDisabled();

    // Fill both
    await headerKeyInput.fill("X-Test");
    
    // Should be enabled now
    await expect(addHeaderButton).toBeEnabled();
  });

  test("form clears after adding MCP server with authentication", async ({ page }) => {
    await page.goto("/settings");
    await page.waitForLoadState("networkidle");

    // Expand MCP Servers section
    const mcpButton = page.locator("button:has-text('MCP Servers')");
    await mcpButton.scrollIntoViewIfNeeded();
    await mcpButton.click();
    await page.waitForTimeout(500);

    // Fill in all fields
    const urlInput = page.locator('input[placeholder*="MCP Server URL"]');
    await urlInput.fill("http://localhost:9000/mcp");

    const nameInput = page.locator('input[placeholder*="Name (optional)"]').last();
    await nameInput.fill("Test Server");

    const descInput = page.locator('textarea[placeholder*="Description"]').last();
    await descInput.fill("Test description");

    const apiKeyInput = page.locator('input[placeholder*="API Key"]');
    await apiKeyInput.fill("test-key");

    // Add a header
    const headerKeyInput = page.locator('input[placeholder*="Header name"]');
    const headerValueInput = page.locator('input[placeholder*="Header value"]');
    const addHeaderButton = page.locator('button[aria-label="Add header"]');
    
    await headerKeyInput.fill("X-Test");
    await headerValueInput.fill("value");
    await addHeaderButton.click();

    // Add the server
    const addButton = page.locator("button:has-text('Add MCP Server')");
    await addButton.click();

    // Wait a bit for state to update
    await page.waitForTimeout(300);

    // Verify all form fields are cleared
    await expect(urlInput).toHaveValue("");
    await expect(nameInput).toHaveValue("");
    await expect(descInput).toHaveValue("");
    await expect(apiKeyInput).toHaveValue("");
    await expect(headerKeyInput).toHaveValue("");
    await expect(headerValueInput).toHaveValue("");
    
    // Verify header list is empty
    await expect(page.locator("text=X-Test: value")).not.toBeVisible();
  });

  test("displays custom headers section with helpful text", async ({ page }) => {
    await page.goto("/settings");
    await page.waitForLoadState("networkidle");

    // Expand MCP Servers section
    const mcpButton = page.locator("button:has-text('MCP Servers')");
    await mcpButton.scrollIntoViewIfNeeded();
    await mcpButton.click();
    await page.waitForTimeout(500);

    // Verify custom headers section exists
    await expect(page.locator("text=Custom Headers (optional)")).toBeVisible();
    await expect(
      page.locator("text=Add custom HTTP headers for advanced authentication")
    ).toBeVisible();
  });
});
