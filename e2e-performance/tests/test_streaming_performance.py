"""
Optimized performance tests for streaming file transfer.

Tests the streaming endpoint (/api/stream/) with:
- Custom StreamingResponse
- 1MB chunk size
- Range request support
"""
import os
import sys
from pathlib import Path

import pytest

# Add utils to path
sys.path.insert(0, str(Path(__file__).parent.parent / "utils"))
from performance_metrics import PerformanceTester  # noqa: E402


# Configuration
BASE_URL = os.environ.get("E2E_BASE_URL", "http://localhost")
TEST_DATA_DIR = Path(__file__).parent.parent / "test_data"
RESULTS_DIR = Path(__file__).parent.parent / "results"


@pytest.fixture(scope="module")
def tester():
    """Create a performance tester instance."""
    t = PerformanceTester(BASE_URL)
    yield t
    t.close()


@pytest.fixture(scope="module")
def test_files():
    """Get list of test files."""
    if not TEST_DATA_DIR.exists():
        pytest.skip(
            "Test data directory not found. Run generate_test_files.py first."
        )

    files = sorted(TEST_DATA_DIR.glob("*.geojson"))
    if not files:
        pytest.skip("No test files found. Run generate_test_files.py first.")

    # Return just the filenames
    return [f.name for f in files]


class TestStreamingPerformance:
    """Test streaming endpoint performance."""

    def test_small_files_streaming(self, tester, test_files):
        """Test streaming performance for small files (1KB-100KB)."""
        small_files = [
            f
            for f in test_files
            if "1kb" in f or "10kb" in f or "50kb" in f or "100kb" in f
        ]

        if not small_files:
            pytest.skip("No small test files found")

        results = tester.run_multiple_tests(
            small_files, endpoint="/api/stream", runs=3
        )

        for filename, metrics_list in results.items():
            stats = tester.calculate_statistics(metrics_list)
            assert stats["success_rate"] == 1.0, f"{filename} had failures"
            avg_time = stats["avg_time"]
            assert avg_time < 1.0, f"{filename} took too long: {avg_time:.3f}s"

            print(f"\n{filename} stats:")
            print(f"  Avg time: {stats['avg_time']:.3f}s")
            print(f"  Avg TTFB: {stats['avg_ttfb']:.3f}s")
            print(f"  Avg rate: {stats['avg_rate']:.2f} MB/s")

    def test_medium_files_streaming(self, tester, test_files):
        """Test streaming performance for medium files (500KB-1MB)."""
        medium_files = [f for f in test_files if "500kb" in f or "1mb" in f]

        if not medium_files:
            pytest.skip("No medium test files found")

        results = tester.run_multiple_tests(
            medium_files, endpoint="/api/stream", runs=3
        )

        for filename, metrics_list in results.items():
            stats = tester.calculate_statistics(metrics_list)
            assert stats["success_rate"] == 1.0, f"{filename} had failures"
            avg_time = stats["avg_time"]
            assert avg_time < 5.0, f"{filename} took too long: {avg_time:.3f}s"

            print(f"\n{filename} stats:")
            print(f"  Avg time: {stats['avg_time']:.3f}s")
            print(f"  Avg TTFB: {stats['avg_ttfb']:.3f}s")
            print(f"  Avg rate: {stats['avg_rate']:.2f} MB/s")

    def test_large_files_streaming(self, tester, test_files):
        """Test streaming performance for large files (5MB-10MB)."""
        large_files = [f for f in test_files if "5mb" in f or "10mb" in f]

        if not large_files:
            pytest.skip("No large test files found")

        results = tester.run_multiple_tests(
            large_files, endpoint="/api/stream", runs=3
        )

        for filename, metrics_list in results.items():
            stats = tester.calculate_statistics(metrics_list)
            assert stats["success_rate"] == 1.0, f"{filename} had failures"
            avg_time = stats["avg_time"]
            assert avg_time < 30.0, f"{filename} took too long: {avg_time:.3f}s"

            print(f"\n{filename} stats:")
            print(f"  Avg time: {stats['avg_time']:.3f}s")
            print(f"  Avg TTFB: {stats['avg_ttfb']:.3f}s")
            print(f"  Avg rate: {stats['avg_rate']:.2f} MB/s")

    @pytest.mark.slow
    def test_xlarge_files_streaming(self, tester, test_files):
        """Test streaming performance for extra large files (25MB-50MB+)."""
        xlarge_files = [f for f in test_files if "25mb" in f or "50mb" in f]

        if not xlarge_files:
            pytest.skip("No extra large test files found")

        results = tester.run_multiple_tests(
            xlarge_files, endpoint="/api/stream", runs=2
        )

        for filename, metrics_list in results.items():
            stats = tester.calculate_statistics(metrics_list)
            success_rate = stats["success_rate"]
            assert success_rate >= 0.5, f"{filename} had too many failures"

            if stats["success_rate"] > 0:
                avg_time = stats["avg_time"]
                assert avg_time < 60.0, f"{filename} too long: {avg_time:.3f}s"

                print(f"\n{filename} stats:")
                print(f"  Avg time: {stats['avg_time']:.3f}s")
                print(f"  Avg TTFB: {stats['avg_ttfb']:.3f}s")
                print(f"  Avg rate: {stats['avg_rate']:.2f} MB/s")

    @pytest.mark.slow
    def test_save_streaming_results(self, tester, test_files):
        """Run comprehensive streaming tests and save results."""
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)

        print("\n\n=== Running Comprehensive Streaming Tests ===\n")

        all_results = tester.run_multiple_tests(
            test_files, endpoint="/api/stream", runs=3
        )

        # Write results to file
        results_file = RESULTS_DIR / "streaming_results.txt"
        with open(results_file, "w") as f:
            f.write("STREAMING PERFORMANCE RESULTS\n")
            f.write("=" * 80 + "\n")
            f.write(f"Base URL: {BASE_URL}\n")
            f.write(
                "Configuration: Custom StreamingResponse "
                "+ 1MB chunks + range support\n\n"
            )

            for filename, metrics_list in all_results.items():
                stats = tester.calculate_statistics(metrics_list)
                file_size_mb = metrics_list[0].file_size_bytes / (1024 * 1024)

                f.write(f"\n{filename} ({file_size_mb:.2f} MB)\n")
                f.write("-" * 80 + "\n")
                f.write(f"Success Rate: {stats['success_rate'] * 100:.1f}%\n")
                f.write(f"Average Time: {stats['avg_time']:.3f}s\n")
                f.write(f"Average TTFB: {stats['avg_ttfb']:.3f}s\n")
                f.write(f"Average Rate: {stats['avg_rate']:.2f} MB/s\n")
                f.write(f"Min Time: {stats['min_time']:.3f}s\n")
                f.write(f"Max Time: {stats['max_time']:.3f}s\n")

        print(f"\n✓ Results saved to: {results_file}")

        # Assert at least 80% success rate overall
        total_success = sum(
            len([m for m in metrics if m.success])
            for metrics in all_results.values()
        )
        total_tests = sum(len(metrics) for metrics in all_results.values())
        overall_success_rate = (
            total_success / total_tests if total_tests > 0 else 0
        )

        success_pct = overall_success_rate * 100
        assert overall_success_rate >= 0.8, (
            f"Overall success rate too low: {success_pct:.1f}%"
        )
