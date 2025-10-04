# Quick Test Guide

## Setup

The test suite is ready to run with Playwright. The test fixtures mock backend API responses for realistic testing.

## Running Tests

```bash
# Run all Leaflet map tests
npx playwright test tests/leaflet-map.spec.ts

# Run specific test suite
npx playwright test tests/leaflet-map.spec.ts --grep "Geocoding"
npx playwright test tests/leaflet-map.spec.ts --grep "Overpass"
npx playwright test tests/leaflet-map.spec.ts --grep "OGC Services"

# Run with UI (interactive mode)
npx playwright test tests/leaflet-map.spec.ts --ui

# Debug specific test
npx playwright test tests/leaflet-map.spec.ts --grep "Brazil hospitals" --debug

# Run tests in headed mode (see browser)
npx playwright test tests/leaflet-map.spec.ts --headed

# Generate HTML report
npx playwright test tests/leaflet-map.spec.ts --reporter=html
npx playwright show-report
```

## Test Structure

```
frontend/tests/
├── leaflet-map.spec.ts           # Main test suite
├── fixtures/
│   ├── geocoding-fixtures.ts     # Germany, Brazil geocoding data
│   ├── overpass-fixtures.ts      # Hospital, restaurant Overpass data
│   └── ogc-services-fixtures.ts  # WMS, WFS, WMTS, WCS mock data
└── BUG_ANALYSIS_AND_IMPROVEMENTS.md  # Detailed analysis & fixes
```

## Test Coverage

### ✅ Geocoding Tests
- Germany boundary rendering
- Brazil boundary rendering
- Single feature normalization
- Geometry normalization

### ✅ Overpass Tests
- Brazil hospitals display
- **Bug reproduction test**: Visibility toggle issue
- Feature collection rendering

### ✅ OGC Service Tests
- WMS tile layer rendering
- WFS vector feature rendering
- WMTS tile layer rendering
- WCS coverage rendering

### ✅ GeoJSON Normalization Tests
- Single Feature response
- Bare Geometry response  
- GeometryCollection response

### ✅ Layer Management Tests
- Multiple layer handling
- Layer removal
- Visibility toggling

## Bug Reproduction

The test suite includes a specific test to reproduce the layer visibility bug:

```bash
npx playwright test tests/leaflet-map.spec.ts --grep "BUG REPRODUCTION"
```

This test will:
1. Add Brazil hospitals layer
2. Check initial visibility (may fail - bug)
3. Toggle visibility off
4. Toggle visibility on
5. Verify layer appears after toggle (passes - confirms bug)

Console output will show:
```
BUG DETECTED: Layer only renders after visibility toggle!
```

## Continuous Integration

Add to your CI pipeline:

```yaml
# .github/workflows/test.yml
- name: Install dependencies
  run: npm ci

- name: Install Playwright browsers
  run: npx playwright install --with-deps

- name: Run Leaflet tests
  run: npx playwright test tests/leaflet-map.spec.ts

- name: Upload test results
  if: always()
  uses: actions/upload-artifact@v3
  with:
    name: playwright-report
    path: playwright-report/
```

## Known Issues

1. **Layer visibility bug**: Layers (especially Overpass results) may not render until toggled off/on. See BUG_ANALYSIS_AND_IMPROVEMENTS.md for details.

2. **Timing sensitivity**: Some tests use `waitForTimeout` for async operations. If tests are flaky, increase timeouts.

3. **API mocking**: Tests mock upload endpoints. Real backend integration tests would require different setup.

## Troubleshooting

### Tests fail with "Cannot find store"
- Ensure the app initializes Zustand stores properly
- Check that the page loads correctly at `/`

### Tests timeout
- Increase timeout in individual tests
- Check that dev server is running (configured in playwright.config.ts)

### Cannot see what's happening
- Run with `--headed` flag to see browser
- Run with `--debug` flag to step through tests
- Add `await page.pause()` in test to stop execution

## Next Steps

1. **Fix the bug**: Follow recommendations in BUG_ANALYSIS_AND_IMPROVEMENTS.md
2. **Run tests again**: Verify fixes resolve the issue
3. **Add more tests**: Cover edge cases, error handling, performance
4. **Integrate CI**: Automate test runs on PR/commit

## Performance Testing

To measure performance improvements after applying fixes:

```bash
# Before fixes
npx playwright test tests/leaflet-map.spec.ts --grep "Brazil hospitals" --trace on

# Apply fixes from BUG_ANALYSIS_AND_IMPROVEMENTS.md

# After fixes
npx playwright test tests/leaflet-map.spec.ts --grep "Brazil hospitals" --trace on

# Compare traces
npx playwright show-trace trace.zip
```

Look for:
- Reduced time to first render
- Fewer React re-renders
- Lower memory usage
- Smoother animations

## Questions?

See BUG_ANALYSIS_AND_IMPROVEMENTS.md for:
- Detailed bug explanation
- Code fixes with before/after examples
- Performance optimization recommendations
- Code simplification suggestions
