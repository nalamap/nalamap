#!/usr/bin/env python3
"""
Pre-compress test files for compression performance testing.
"""
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from services.compression.gzip_utils import compress_directory  # noqa: E402


def main():
    """Compress all test files > 1MB."""
    # Get uploads directory
    uploads_dir = Path(__file__).parent.parent.parent / "uploads"

    if not uploads_dir.exists():
        print(f"❌ Uploads directory not found: {uploads_dir}")
        return

    print(f"Compressing files in {uploads_dir}...\n")

    compressed_files = compress_directory(uploads_dir, min_size_mb=1.0)

    print(f"\n✅ Compressed {len(compressed_files)} files")

    # Show compression results
    if compressed_files:
        print("\nCompression Results:")
        print("-" * 70)
        for compressed_path in compressed_files:
            original_path = compressed_path.with_suffix("")
            if original_path.exists():
                original_size = original_path.stat().st_size / 1024 / 1024
                compressed_size = compressed_path.stat().st_size / 1024 / 1024
                ratio = (1 - compressed_size / original_size) * 100
                print(
                    f"{original_path.name}: {original_size:.2f} MB -> "
                    f"{compressed_size:.2f} MB ({ratio:.1f}% reduction)"
                )


if __name__ == "__main__":
    main()
