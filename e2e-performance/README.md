# E2E Performance Tests

> **Performance testing for the full nalamap stack**
> 
> Tests file transfer performance for GeoJSON files ranging from 1KB to 50MB+.

## Structure

- `test_data/` - Generated test GeoJSON files of various sizes
- `utils/` - Performance measurement utilities
- `tests/` - Performance test suites
- `docker-compose.e2e.yml` - Full stack setup for E2E testing
- `results/` - Performance test results (gitignored)

## Running Tests

```bash
# Generate test data
python3 utils/generate_test_files.py

# Run E2E tests with full stack
docker compose -f docker-compose.e2e.yml up --build
python3 -m pytest tests/ -v

# Or run specific test
python3 -m pytest tests/test_file_transfer_performance.py -v
```

## Test Categories

1. **Baseline Performance**: Current StaticFiles + nginx buffering
2. **Streaming Performance**: Custom streaming endpoint + nginx optimization
3. **Compression Performance**: Pre-compressed .gz variants

## Metrics Tracked

- Total transfer time
- Time to first byte (TTFB)
- Transfer rate (MB/s)
- Memory usage (backend process)
- CPU usage during transfer
