import { test, expect } from "@playwright/test";
import { E2ETestUtils } from "./utils/e2e-utils";

/**
 * E2E Test: AI-Based Layer Styling
 * 
 * Tests the AI styling feature with generic GeoJSON data.
 * Validates that the AI can apply appropriate styles to map layers.
 */

const TEST_TIMEOUT = 180_000; // 3 minutes

test.describe("AI Styling E2E Tests", () => {
  test.setTimeout(TEST_TIMEOUT);

  test("Style a layer with AI assistance", async ({ page }) => {
    const utils = new E2ETestUtils(page);
    
    await utils.goto();

    // First, add a layer (using a public GeoServer or upload)
    await utils.sendMessage(
      "Add a layer showing parks in Berlin",
      "Add Layer"
    );

    await utils.waitForAIResponse();
    await utils.waitForLayerAdded();

    // Now request AI to style it
    await utils.sendMessage(
      "Style this park layer in green with transparency",
      "Style Request"
    );

    await utils.waitForAIResponse();

    const response = await utils.getLastAIMessage();
    
    // Should mention styling or color
    const keywords = ["style", "color", "green", "transparent"];
    const hasKeywords = utils.validateResponse(response, keywords, 0.25);
    expect(hasKeywords).toBe(true);

    await utils.screenshot("ai-styling-parks");
  });

  test("Compare styling of different layer types", async ({ page }) => {
    const utils = new E2ETestUtils(page);
    
    await utils.goto();

    // Add multiple layers with different types of data
    await utils.executeWorkflowStep(
      "Show roads in Amsterdam",
      ["road", "amsterdam"],
      { label: "Add Roads", waitForLayers: true }
    );

    await utils.executeWorkflowStep(
      "Style the roads in dark gray",
      ["style", "gray"],
      { label: "Style Roads" }
    );

    // Add water features
    await utils.executeWorkflowStep(
      "Show water bodies in Amsterdam",
      ["water", "amsterdam"],
      { label: "Add Water", waitForLayers: true }
    );

    await utils.executeWorkflowStep(
      "Style water in blue",
      ["style", "blue"],
      { label: "Style Water" }
    );

    // Verify multiple layers exist
    const layerCount = await utils.getLayerCount();
    expect(layerCount).toBeGreaterThanOrEqual(2);

    await utils.screenshot("ai-styling-comparison");
  });

  test("Request AI to auto-style based on data attributes", async ({ page }) => {
    const utils = new E2ETestUtils(page);
    
    await utils.goto();

    // Add a layer with attributes
    await utils.sendMessage(
      "Add a layer with population data for European cities",
      "Population Layer"
    );

    await utils.waitForAIResponse();
    await utils.waitForLayerAdded();

    // Request AI to create graduated styling
    await utils.sendMessage(
      "Create a color gradient for this layer based on population - red for high, yellow for medium, green for low",
      "Graduated Style"
    );

    await utils.waitForAIResponse();

    const response = await utils.getLastAIMessage();
    
    // Should discuss graduated styling or color scheme
    expect(response.toLowerCase()).toMatch(/color|gradient|style/);

    await utils.screenshot("ai-styling-graduated");
  });
});
