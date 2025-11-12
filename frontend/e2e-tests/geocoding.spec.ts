import { test, expect } from "@playwright/test";
import { E2ETestUtils } from "./utils/e2e-utils";

/**
 * E2E Test: Geocoding Functionality
 * 
 * Tests the geocoding feature with public location data.
 * Uses the running stack (nginx → backend → frontend).
 */

const TEST_TIMEOUT = 180_000; // 3 minutes

test.describe("Geocoding E2E Tests", () => {
  test.setTimeout(TEST_TIMEOUT);

  test("Find hospitals in Paris", async ({ page }) => {
    const utils = new E2ETestUtils(page);
    
    // Navigate to app
    await utils.goto();

    // Send geocoding query
    await utils.sendMessage(
      "Find hospitals in Paris, France",
      "Geocoding Test"
    );

    // Wait for AI response
    await utils.waitForAIResponse();

    // Get response and validate
    const response = await utils.getLastAIMessage();
    
    // Should contain location-related keywords
    const keywords = ["hospital", "paris", "france", "location"];
    const hasKeywords = utils.validateResponse(response, keywords, 0.3);
    expect(hasKeywords).toBe(true);

    // Wait for tools to complete
    await utils.waitForAllToolsComplete();

    // Take screenshot
    await utils.screenshot("geocoding-hospitals-paris");

    console.log("✅ Geocoding test completed successfully");
  });

  test("Find restaurants in Tokyo", async ({ page }) => {
    const utils = new E2ETestUtils(page);
    
    await utils.goto();

    // Send geocoding query for a different location
    await utils.sendMessage(
      "Show me restaurants in Tokyo, Japan",
      "Tokyo Restaurants"
    );

    await utils.waitForAIResponse();

    const response = await utils.getLastAIMessage();
    
    // Validate response contains expected content
    expect(response.toLowerCase()).toContain("restaurant");
    expect(response.toLowerCase()).toMatch(/tokyo|japan/);

    await utils.screenshot("geocoding-restaurants-tokyo");
  });

  test("Geocode multiple locations in workflow", async ({ page }) => {
    const utils = new E2ETestUtils(page);
    
    await utils.goto();

    // Step 1: Find a landmark
    await utils.executeWorkflowStep(
      "Find the Eiffel Tower",
      ["eiffel", "tower", "paris"],
      { label: "Step 1", waitForLayers: true }
    );

    // Step 2: Find nearby amenities
    await utils.executeWorkflowStep(
      "Show me cafes near the Eiffel Tower",
      ["cafe", "restaurant", "near"],
      { label: "Step 2", waitForLayers: true }
    );

    // Verify multiple layers were added
    const layerCount = await utils.getLayerCount();
    expect(layerCount).toBeGreaterThan(0);

    console.log(`✅ Added ${layerCount} layers`);

    await utils.screenshot("geocoding-workflow-complete");
  });
});
