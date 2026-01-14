# NaLaMap E2E Tests

> **End-to-end tests for real user workflows with live backend**

These tests validate complete user journeys through the NaLaMap application using a running stack (nginx → backend → frontend).

---

## 📋 Overview

**Purpose**: Test real-world user scenarios with actual backend services

**Test Types**:
- Geocoding (finding locations, landmarks, POIs)
- AI-based styling (automatic layer styling)
- GeoServer integration
- Multi-step workflows

**Key Differences from Unit Tests**:
- ✅ Tests against real backend (not mocked)
- ✅ Validates complete user journeys
- ✅ Uses public data only (no confidential information)
- ✅ Can run against local or remote deployments

---

## 🗂️ Directory Structure

```
e2e-tests/
├── README.md                    # This file
├── utils/
│   └── e2e-utils.ts             # Test utility class
├── geocoding.spec.ts            # Geocoding tests
├── styling.spec.ts              # AI styling tests
└── [future tests]               # GeoServer, geoprocessing, etc.
```

---

## 🚀 Running Tests

### Prerequisites

**Option 1: Local Stack (via nginx)**
```bash
# Start Docker services
cd ../
docker-compose up -d

# Wait for services to be ready
curl http://localhost/health/nginx
curl http://localhost/health/backend
```

**Option 2: Remote Server**
```bash
# Set environment variables
export FRONTEND_URL=https://your-deployment.com
export BACKEND_URL=https://your-deployment.com
```

### Run Tests

```bash
# All E2E tests
npm run test:e2e

# Specific test file
npx playwright test e2e-tests/geocoding.spec.ts

# With UI (headed mode)
npx playwright test e2e-tests/geocoding.spec.ts --headed

# Single test
npx playwright test e2e-tests/geocoding.spec.ts -g "Find hospitals"
```

---

## 🛠️ E2ETestUtils Class

The `E2ETestUtils` class provides reusable methods for common test tasks.

### Basic Usage

```typescript
import { E2ETestUtils } from "./utils/e2e-utils";

test("My test", async ({ page }) => {
  const utils = new E2ETestUtils(page);
  
  // Navigate to app
  await utils.goto();
  
  // Send chat message
  await utils.sendMessage("Find parks in Paris");
  
  // Wait for response
  await utils.waitForAIResponse();
  
  // Validate response
  const response = await utils.getLastAIMessage();
  expect(response).toContain("park");
  
  // Wait for layers
  await utils.waitForLayerAdded();
});
```

### Available Methods

**Navigation**:
- `goto(url?)` - Navigate to app
- `gotoSettings()` - Go to settings page

**Chat Interactions**:
- `sendMessage(message, label?, waitForCompletion?)` - Send chat message
- `waitForAIResponse(timeout?)` - Wait for AI response
- `getLastAIMessage()` - Get last AI message text
- `getAllAIMessages()` - Get all AI messages

**Validation**:
- `validateResponse(response, keywords, minMatch?)` - Check for keywords
- `assertResponseContains(response, keywords, minMatch?)` - Assert keywords (throws)

**Tool Execution**:
- `waitForToolStart(toolName, timeout?)` - Wait for tool to start
- `waitForToolComplete(toolName, timeout?)` - Wait for tool to complete
- `waitForAllToolsComplete(timeout?)` - Wait for all tools
- `getToolStatuses()` - Get all tool statuses

**Layer Management**:
- `waitForLayerAdded(expectedCount?, timeout?)` - Wait for layer
- `getLayerCount()` - Get current layer count
- `getLayerNames()` - Get all layer names

**Workflow Helpers**:
- `executeWorkflowStep(message, keywords, options)` - Complete workflow step
- `selectLLM(provider, model)` - Select LLM in settings
- `addGeoServer(url, name?, waitForPreload?, timeout?)` - Add GeoServer

**Debugging**:
- `screenshot(name)` - Take screenshot
- `logPageState()` - Log current state
- `trackTiming(label)` - Track execution time

---

## ✍️ Writing Tests

### Test Structure

```typescript
import { test, expect } from "@playwright/test";
import { E2ETestUtils } from "./utils/e2e-utils";

const TEST_TIMEOUT = 180_000; // 3 minutes

test.describe("My Feature E2E Tests", () => {
  test.setTimeout(TEST_TIMEOUT);

  test("Test scenario", async ({ page }) => {
    const utils = new E2ETestUtils(page);
    
    // Test logic here
  });
});
```

### Best Practices

1. **Use Public Data Only**
   - ✅ "Find hospitals in Paris"
   - ✅ "Show restaurants in Tokyo"
   - ❌ No partner names (IUCN, WWF, etc.)
   - ❌ No confidential endpoints

2. **Use Meaningful Labels**
   ```typescript
   await utils.sendMessage("Find parks", "Query 1");
   await utils.executeWorkflowStep(
     "Style in green",
     ["style", "green"],
     { label: "Styling Step" }
   );
   ```

3. **Validate Responses**
   ```typescript
   const response = await utils.getLastAIMessage();
   utils.assertResponseContains(response, ["park", "green"], 0.5);
   ```

4. **Wait for Tools and Layers**
   ```typescript
   await utils.waitForAllToolsComplete();
   await utils.waitForLayerAdded();
   ```

5. **Take Screenshots for Debugging**
   ```typescript
   await utils.screenshot("feature-test-complete");
   ```

---

## 🧪 Test Examples

### Example 1: Simple Geocoding

```typescript
test("Geocode a location", async ({ page }) => {
  const utils = new E2ETestUtils(page);
  await utils.goto();
  
  await utils.sendMessage("Find the Eiffel Tower");
  await utils.waitForAIResponse();
  
  const response = await utils.getLastAIMessage();
  expect(response).toContain("Eiffel");
});
```

### Example 2: Multi-Step Workflow

```typescript
test("Complete workflow", async ({ page }) => {
  const utils = new E2ETestUtils(page);
  await utils.goto();
  
  // Step 1
  await utils.executeWorkflowStep(
    "Find parks in Berlin",
    ["park", "berlin"],
    { label: "Step 1", waitForLayers: true }
  );
  
  // Step 2
  await utils.executeWorkflowStep(
    "Style them in green",
    ["style", "green"],
    { label: "Step 2", screenshot: true }
  );
  
  expect(await utils.getLayerCount()).toBeGreaterThan(0);
});
```

### Example 3: LLM Selection

```typescript
test("Change LLM model", async ({ page }) => {
  const utils = new E2ETestUtils(page);
  await utils.goto();
  
  // Go to settings and select different model
  await utils.selectLLM("openai", "gpt-4");
  
  // Return to app
  await utils.goto();
  
  // Test with new model
  await utils.sendMessage("Find museums in Rome");
  await utils.waitForAIResponse();
});
```

---

## 🔍 Debugging Tests

### Failed Tests

When a test fails:

1. **Check Screenshots**: Look in `screenshots/` directory
2. **Check Logs**: Review console output for errors
3. **Run in Headed Mode**: See the browser
   ```bash
   npx playwright test e2e-tests/geocoding.spec.ts --headed
   ```
4. **Use Debug Mode**:
   ```bash
   npx playwright test e2e-tests/geocoding.spec.ts --debug
   ```

### Common Issues

**Backend Not Running**:
```bash
# Check services
docker-compose ps

# Check health
curl http://localhost/health/backend
```

**Timeouts**:
- Increase `TEST_TIMEOUT` for slow networks
- Check if backend is responding
- Verify nginx routing is working

**No AI Response**:
- Check LLM API keys in `.env`
- Verify backend can reach LLM provider
- Check browser console for errors

---

## 🚦 CI/CD Integration

### GitHub Actions

Tests can run in CI with a remote deployment:

```yaml
- name: Run E2E Tests
  env:
    FRONTEND_URL: https://staging.nalamap.com
    BACKEND_URL: https://staging.nalamap.com
  run: |
    cd frontend
    npm run test:e2e
```

### Local Testing Against Staging

```bash
export FRONTEND_URL=https://staging.nalamap.com
export BACKEND_URL=https://staging.nalamap.com
npm run test:e2e
```

---

## 📚 Related Documentation

- **Performance Tests**: See `../e2e-performance/` for file transfer performance tests
- **Unit Tests**: See `tests/` for component/unit tests
- **Test Utilities**: See `tests/utils/` for shared test fixtures

---

## 🤝 Contributing

When adding new E2E tests:

1. **Use Public Data**: No confidential partner information
2. **Document Test Purpose**: Add clear description at top of file
3. **Follow Naming Convention**: `feature-name.spec.ts`
4. **Add to README**: Update this file with test description
5. **Test Locally**: Ensure tests pass before committing

---

**Last Updated**: October 2025
