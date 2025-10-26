"""
E2E integration tests to verify file streaming works through the full stack.

Tests nginx -> backend -> file serving with actual data verification.
"""

import os
import sys
from pathlib import Path

import pytest
import requests

# Add utils to path
sys.path.insert(0, str(Path(__file__).parent.parent / "utils"))
from performance_metrics import PerformanceTester  # noqa: E402


# Configuration
BASE_URL = os.environ.get("E2E_BASE_URL", "http://localhost")
TEST_DATA_DIR = Path(__file__).parent.parent / "test_data"


@pytest.fixture(scope="module")
def test_file():
    """Get a medium-sized test file for integration testing."""
    test_file = TEST_DATA_DIR / "006_polygons_100_1mb.geojson"
    if not test_file.exists():
        pytest.skip("Test file not found. Run generate_test_files.py first.")
    return test_file.name


class TestFullStackIntegration:
    """Test full stack integration with nginx."""

    def test_nginx_health(self):
        """Verify nginx is running and healthy."""
        response = requests.get(f"{BASE_URL}/health/nginx", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "nginx"

    def test_backend_health_through_nginx(self):
        """Verify backend is accessible through nginx."""
        response = requests.get(f"{BASE_URL}/api/health", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_legacy_uploads_endpoint(self, test_file):
        """Test legacy /uploads/ endpoint through nginx."""
        url = f"{BASE_URL}/uploads/{test_file}"
        response = requests.get(url, timeout=30)

        assert response.status_code == 200
        assert "application" in response.headers["content-type"].lower()

        # Verify it's valid JSON
        data = response.json()
        assert "type" in data
        assert data["type"] == "FeatureCollection"
        assert "features" in data
        assert len(data["features"]) > 0

    def test_streaming_endpoint_through_nginx(self, test_file):
        """Test streaming endpoint /api/stream/ through nginx."""
        url = f"{BASE_URL}/api/stream/{test_file}"
        response = requests.get(url, timeout=30)

        assert response.status_code == 200
        assert "application" in response.headers["content-type"].lower()

        # Check for streaming/compression headers
        assert "accept-ranges" in response.headers
        assert response.headers["accept-ranges"] == "bytes"

        # Verify it's valid JSON
        data = response.json()
        assert "type" in data
        assert data["type"] == "FeatureCollection"
        assert "features" in data
        assert len(data["features"]) > 0

    def test_streaming_with_gzip_through_nginx(self):
        """Test streaming with gzip compression through nginx."""
        # Use a large file that should be compressed
        large_file = "007_polygons_500_5mb.geojson"
        url = f"{BASE_URL}/api/stream/{large_file}"

        response = requests.get(url, headers={"Accept-Encoding": "gzip"}, timeout=30)

        assert response.status_code == 200

        # Verify data integrity
        data = response.json()
        assert "type" in data
        assert data["type"] == "FeatureCollection"
        assert "features" in data
        assert len(data["features"]) > 0

        print(
            f"\nCompressed transfer: "
            f"{len(response.content) / 1024 / 1024:.2f} MB received"
        )

    def test_range_request_through_nginx(self, test_file):
        """Test range requests through nginx."""
        url = f"{BASE_URL}/api/stream/{test_file}"

        # First get file size
        head_response = requests.head(url, timeout=10)
        assert head_response.status_code == 200
        file_size = int(head_response.headers["content-length"])
        assert file_size > 1024  # Ensure file is large enough for range test

        # Request first 1024 bytes
        range_header = {"Range": "bytes=0-1023"}
        response = requests.get(url, headers=range_header, timeout=10)

        # Should return partial content
        assert response.status_code == 206
        assert len(response.content) == 1024
        assert "content-range" in response.headers

    def test_data_integrity_across_endpoints(self, test_file):
        """Verify same data from both endpoints."""
        legacy_url = f"{BASE_URL}/uploads/{test_file}"
        streaming_url = f"{BASE_URL}/api/stream/{test_file}"

        # Get data from both endpoints
        legacy_data = requests.get(legacy_url, timeout=30).json()
        streaming_data = requests.get(streaming_url, timeout=30).json()

        # Verify both return same structure
        assert legacy_data["type"] == streaming_data["type"]
        assert len(legacy_data["features"]) == len(streaming_data["features"])

        # Verify first feature matches
        if len(legacy_data["features"]) > 0:
            assert (
                legacy_data["features"][0]["type"]
                == streaming_data["features"][0]["type"]
            )


class TestPerformanceThroughNginx:
    """Performance tests through nginx."""

    def test_compare_endpoints_performance(self, test_file):
        """Compare performance: legacy vs streaming through nginx."""
        tester = PerformanceTester(BASE_URL)

        # Test legacy endpoint
        print("\n=== Testing Legacy /uploads/ ===")
        legacy_results = tester.run_multiple_tests(
            [test_file], endpoint="/uploads", runs=3
        )

        # Test streaming endpoint
        print("\n=== Testing Streaming /api/stream/ ===")
        streaming_results = tester.run_multiple_tests(
            [test_file], endpoint="/api/stream", runs=3
        )

        # Compare
        legacy_stats = tester.calculate_statistics(legacy_results[test_file])
        streaming_stats = tester.calculate_statistics(streaming_results[test_file])

        print(f"\n=== Results for {test_file} ===")
        print(f"Legacy:    {legacy_stats['avg_rate']:.1f} MB/s")
        print(f"Streaming: {streaming_stats['avg_rate']:.1f} MB/s")

        improvement = (
            (streaming_stats["avg_rate"] - legacy_stats["avg_rate"])
            / legacy_stats["avg_rate"]
        ) * 100
        print(f"Improvement: {improvement:+.1f}%")

        # Assert both work
        assert legacy_stats["success_rate"] == 1.0
        assert streaming_stats["success_rate"] == 1.0

        tester.close()
