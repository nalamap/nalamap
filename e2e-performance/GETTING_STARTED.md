# E2E Performance Testing - Getting Started

## 📋 Overview

This directory contains comprehensive end-to-end (E2E) performance tests for testing file transfer performance across the full nalamap stack (nginx → backend → file serving) with GeoJSON files ranging from 1KB to 50MB+.

## ✅ Setup Complete

The following components have been created:

### 1. Test Infrastructure
- ✅ `utils/generate_test_files.py` - Generates test GeoJSON files of various sizes
- ✅ `utils/performance_metrics.py` - Performance measurement utilities
- ✅ `tests/test_file_transfer_performance.py` - Comprehensive test suite
- ✅ `docker-compose.e2e.yml` - Full stack configuration for E2E testing
- ✅ `pytest.ini` - Test configuration
- ✅ `requirements.txt` - Python dependencies

### 2. Test Data Generated
10 test files have been generated and copied to `backend/uploads/`:

| File | Size | Description |
|------|------|-------------|
| `001_single_point_1kb.geojson` | 0.15 KB | Single point (minimal) |
| `002_points_100_10kb.geojson` | 13.58 KB | 100 points |
| `003_points_500_50kb.geojson` | 67.74 KB | 500 points |
| `004_points_1000_100kb.geojson` | 135.47 KB | 1000 points |
| `005_polygons_50_500kb.geojson` | 200.24 KB | 50 polygons |
| `006_polygons_100_1mb.geojson` | 791.92 KB | 100 polygons |
| `007_polygons_500_5mb.geojson` | 3.85 MB | 500 polygons |
| `008_polygons_1000_10mb.geojson` | 7.71 MB | 1000 polygons |
| `009_multipolygon_2500_25mb.geojson` | 19.21 MB | MultiPolygon 2500 |
| `010_multipolygon_5000_50mb.geojson` | 38.42 MB | MultiPolygon 5000 |

## 🚀 Running the Tests

### Option 1: Using Existing Development Stack

If your development stack is already running (via `dev.docker-compose.yml`):

```bash
cd e2e-performance

# Run all baseline performance tests
python3 -m pytest tests/ -v

# Run specific test categories
python3 -m pytest tests/test_file_transfer_performance.py::TestBaselinePerformance::test_small_files_1kb_to_100kb -v
python3 -m pytest tests/test_file_transfer_performance.py::TestBaselinePerformance::test_medium_files_500kb_to_1mb -v
python3 -m pytest tests/test_file_transfer_performance.py::TestBaselinePerformance::test_large_files_5mb_to_10mb -v
python3 -m pytest tests/test_file_transfer_performance.py::TestBaselinePerformance::test_xlarge_files_25mb_to_50mb -v

# Save comprehensive baseline results
python3 -m pytest tests/test_file_transfer_performance.py::TestBaselinePerformance::test_save_baseline_results -v
```

### Option 2: Using E2E Test Stack

If you want to run tests with a dedicated E2E stack:

```bash
cd e2e-performance

# Start the E2E stack
docker-compose -f docker-compose.e2e.yml up --build -d

# Wait for services to be ready
sleep 10

# Run the tests
python3 -m pytest tests/ -v

# View logs if needed
docker-compose -f docker-compose.e2e.yml logs -f

# Stop the stack when done
docker-compose -f docker-compose.e2e.yml down
```

### Quick Start Script

Alternatively, use the provided quick start script:

```bash
cd e2e-performance
./quickstart.sh
```

## 📊 Test Results

After running the comprehensive baseline test, results will be saved to:
- `results/baseline_results.txt` - Detailed baseline performance metrics

The results include:
- Success rate for each file size
- Average transfer time
- Average time to first byte (TTFB)
- Average transfer rate (MB/s)
- Min/max transfer times

Example output:
```
006_polygons_100_1mb.geojson (0.79 MB)
--------------------------------------------------------------------------------
Success Rate: 100.0%
Average Time: 0.234s
Average TTFB: 0.045s
Average Rate: 3.38 MB/s
Min Time: 0.218s
Max Time: 0.251s
```

## 🎯 Test Categories

### 1. Baseline Performance Tests
Tests current implementation (StaticFiles + nginx proxy_buffering):
- ✅ Small files (1KB-100KB): < 1 second expected
- ✅ Medium files (500KB-1MB): < 5 seconds expected
- ✅ Large files (5MB-10MB): < 30 seconds expected
- ✅ Extra large files (25MB-50MB): < 60 seconds expected

### 2. Optimized Performance Tests (TODO)
After implementing streaming and compression optimizations:
- Custom streaming endpoint tests
- Nginx streaming configuration tests
- Gzip compression tests
- Performance comparison vs baseline

## 🔧 Test Metrics

Each test measures:
- **Total Transfer Time**: End-to-end download time
- **Time to First Byte (TTFB)**: Time until first byte received
- **Transfer Rate**: MB/s throughput
- **Success Rate**: Percentage of successful transfers
- **HTTP Status Code**: Response codes

## 📈 Performance Assertions

Tests validate:
- ✅ Success rate ≥ 80% overall
- ✅ Small files complete in < 1 second
- ✅ Medium files complete in < 5 seconds
- ✅ Large files complete in < 30 seconds
- ✅ Extra large files complete in < 60 seconds

## 🐛 Troubleshooting

### Tests failing?
1. **Check if backend is running**: `curl http://localhost:8000/health`
2. **Check if nginx is running**: `curl http://localhost/api/health`
3. **Check test files exist**: `ls -lh ../uploads/*.geojson`
4. **Check Docker logs**: `docker-compose -f dev.docker-compose.yml logs`

### Need to regenerate test data?
```bash
cd e2e-performance
python3 utils/generate_test_files.py
cp test_data/*.geojson ../uploads/
```

### Want to test against different URL?
```bash
export E2E_BASE_URL=http://your-server.com
python3 -m pytest tests/ -v
```

## 📝 Next Steps

After establishing baseline performance:

1. **Implement streaming endpoint** (Task 4)
   - Replace FastAPI StaticFiles with custom StreamingResponse
   - Add `/api/uploads/{filename}` endpoint with chunked transfer

2. **Optimize nginx configuration** (Task 5)
   - Disable `proxy_buffering` for uploads endpoint
   - Enable `chunked_transfer_encoding`

3. **Add gzip compression** (Task 6)
   - Pre-compress large files (.geojson.gz)
   - Serve compressed variants with gzip_static

4. **Compare optimized vs baseline** (Task 7)
   - Run identical tests with optimizations
   - Generate comparison report
   - Document performance improvements

## 📚 Related Documentation

- [Large Dataset Transfer Analysis](../docs/large-dataset-transfer-analysis.md)
- [Azure Blob Storage Security](../docs/azure-blob-storage-security.md)
- [Runtime Environment](../docs/runtime-environment.md)
