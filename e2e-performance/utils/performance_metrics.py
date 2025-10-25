"""
Performance measurement utilities for E2E tests.
"""
import time
from dataclasses import dataclass
from typing import Optional
import requests


@dataclass
class TransferMetrics:
    """Metrics for a file transfer operation."""

    filename: str
    file_size_bytes: int
    total_time_seconds: float
    time_to_first_byte_seconds: float
    transfer_rate_mbps: float
    status_code: int
    success: bool
    error_message: Optional[str] = None

    def __str__(self) -> str:
        """Format metrics as a readable string."""
        size_mb = self.file_size_bytes / (1024 * 1024)
        return (
            f"{self.filename}:\n"
            f"  Size: {size_mb:.2f} MB\n"
            f"  Total Time: {self.total_time_seconds:.3f}s\n"
            f"  TTFB: {self.time_to_first_byte_seconds:.3f}s\n"
            f"  Rate: {self.transfer_rate_mbps:.2f} MB/s\n"
            f"  Status: {self.status_code}\n"
            f"  Success: {self.success}"
        )


class PerformanceTester:
    """Utility class for testing file transfer performance."""

    def __init__(self, base_url: str):
        """
        Initialize the performance tester.

        Args:
            base_url: Base URL of the backend (e.g., http://localhost)
        """
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()

    def measure_transfer(
        self, filepath: str, endpoint: str = "/uploads"
    ) -> TransferMetrics:
        """
        Measure the performance of downloading a file.

        Args:
            filepath: Name of the file to download
            endpoint: API endpoint to download from (default: /uploads)

        Returns:
            TransferMetrics object with performance data
        """
        url = f"{self.base_url}{endpoint}/{filepath}"

        # Get file size first (HEAD request)
        try:
            head_response = self.session.head(url, timeout=10)
            file_size = int(head_response.headers.get("content-length", 0))
        except Exception as e:
            return TransferMetrics(
                filename=filepath,
                file_size_bytes=0,
                total_time_seconds=0.0,
                time_to_first_byte_seconds=0.0,
                transfer_rate_mbps=0.0,
                status_code=0,
                success=False,
                error_message=f"HEAD request failed: {str(e)}",
            )

        # Measure download performance
        start_time = time.time()
        ttfb = None
        bytes_downloaded = 0
        error_message = None
        status_code = 0

        try:
            response = self.session.get(url, stream=True, timeout=60)
            status_code = response.status_code

            if response.status_code != 200:
                return TransferMetrics(
                    filename=filepath,
                    file_size_bytes=file_size,
                    total_time_seconds=time.time() - start_time,
                    time_to_first_byte_seconds=0.0,
                    transfer_rate_mbps=0.0,
                    status_code=status_code,
                    success=False,
                    error_message=f"HTTP {status_code}",
                )

            # Stream the response and measure TTFB
            for chunk in response.iter_content(chunk_size=8192):
                if ttfb is None:
                    ttfb = time.time() - start_time
                if chunk:
                    bytes_downloaded += len(chunk)

            total_time = time.time() - start_time

        except Exception as e:
            total_time = time.time() - start_time
            error_message = str(e)
            return TransferMetrics(
                filename=filepath,
                file_size_bytes=file_size,
                total_time_seconds=total_time,
                time_to_first_byte_seconds=ttfb or 0.0,
                transfer_rate_mbps=0.0,
                status_code=status_code,
                success=False,
                error_message=error_message,
            )

        # Calculate transfer rate
        if total_time > 0:
            transfer_rate_mbps = (bytes_downloaded / (1024 * 1024)) / total_time
        else:
            transfer_rate_mbps = 0.0

        return TransferMetrics(
            filename=filepath,
            file_size_bytes=file_size,
            total_time_seconds=total_time,
            time_to_first_byte_seconds=ttfb or 0.0,
            transfer_rate_mbps=transfer_rate_mbps,
            status_code=status_code,
            success=True,
        )

    def run_multiple_tests(
        self, filepaths: list[str], endpoint: str = "/uploads", runs: int = 3
    ) -> dict[str, list[TransferMetrics]]:
        """
        Run multiple test iterations for each file.

        Args:
            filepaths: List of file names to test
            endpoint: API endpoint to download from
            runs: Number of test runs per file

        Returns:
            Dictionary mapping filenames to list of metrics
        """
        results = {}

        for filepath in filepaths:
            print(f"\nTesting {filepath}...")
            file_results = []

            for run in range(1, runs + 1):
                print(f"  Run {run}/{runs}...", end=" ", flush=True)
                metrics = self.measure_transfer(filepath, endpoint)
                file_results.append(metrics)

                if metrics.success:
                    print(
                        f"✓ {metrics.transfer_rate_mbps:.2f} MB/s "
                        f"({metrics.total_time_seconds:.3f}s)"
                    )
                else:
                    print(f"✗ Failed: {metrics.error_message}")

            results[filepath] = file_results

        return results

    def calculate_statistics(
        self, metrics_list: list[TransferMetrics]
    ) -> dict:
        """
        Calculate statistics from multiple test runs.

        Args:
            metrics_list: List of metrics from multiple runs

        Returns:
            Dictionary with average, min, max statistics
        """
        successful = [m for m in metrics_list if m.success]

        if not successful:
            return {
                "success_rate": 0.0,
                "avg_time": 0.0,
                "avg_ttfb": 0.0,
                "avg_rate": 0.0,
                "min_time": 0.0,
                "max_time": 0.0,
            }

        total_times = [m.total_time_seconds for m in successful]
        ttfbs = [m.time_to_first_byte_seconds for m in successful]
        rates = [m.transfer_rate_mbps for m in successful]

        return {
            "success_rate": len(successful) / len(metrics_list),
            "avg_time": sum(total_times) / len(total_times),
            "avg_ttfb": sum(ttfbs) / len(ttfbs),
            "avg_rate": sum(rates) / len(rates),
            "min_time": min(total_times),
            "max_time": max(total_times),
        }

    def close(self):
        """Close the session."""
        self.session.close()
