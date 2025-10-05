"""
Tests for Azure Blob Storage compression functionality.

These tests verify that GeoJSON files are properly compressed before
uploading to Azure Blob Storage, and that the Content-Encoding header
is set correctly so browsers can automatically decompress.
"""

import gzip
import pytest
from unittest.mock import patch, MagicMock
from io import BytesIO

from services.storage.file_management import (
    store_file,
    store_file_stream,
    _should_compress_for_azure,
    _compress_for_azure,
)


class TestAzureCompressionHelpers:
    """Test helper functions for Azure compression."""

    def test_should_compress_for_azure_geojson_large(self):
        """GeoJSON files larger than 1MB should be compressed."""
        size = 2 * 1024 * 1024  # 2MB
        assert _should_compress_for_azure("test.geojson", size) is True

    def test_should_compress_for_azure_geojson_small(self):
        """GeoJSON files smaller than 1MB should not be compressed."""
        size = 500 * 1024  # 500KB
        assert _should_compress_for_azure("test.geojson", size) is False

    def test_should_compress_for_azure_non_geojson(self):
        """Non-GeoJSON files should not be compressed."""
        size = 2 * 1024 * 1024  # 2MB
        assert _should_compress_for_azure("test.json", size) is False
        assert _should_compress_for_azure("test.txt", size) is False
        assert _should_compress_for_azure("test.csv", size) is False

    def test_should_compress_case_insensitive(self):
        """Should handle .GeoJSON and .GEOJSON extensions."""
        size = 2 * 1024 * 1024
        assert _should_compress_for_azure("test.GeoJSON", size) is True
        assert _should_compress_for_azure("test.GEOJSON", size) is True

    def test_compress_for_azure(self):
        """Test compression produces valid gzip data."""
        # Create test GeoJSON content
        test_content = b'{"type":"FeatureCollection","features":[]}' * 1000
        compressed = _compress_for_azure(test_content)

        # Verify it's smaller
        assert len(compressed) < len(test_content)

        # Verify it can be decompressed
        decompressed = gzip.decompress(compressed)
        assert decompressed == test_content


class TestStoreFileWithCompression:
    """Test store_file() with Azure compression."""

    @pytest.fixture
    def mock_azure_env(self, monkeypatch):
        """Set up Azure environment."""
        monkeypatch.setenv("USE_AZURE_STORAGE", "true")
        monkeypatch.setenv(
            "AZURE_CONN_STRING", "DefaultEndpointsProtocol=https;AccountName=test;AccountKey=test=="
        )
        monkeypatch.setenv("AZURE_CONTAINER", "uploads")

    @patch("services.storage.file_management.USE_AZURE", True)
    @patch("azure.storage.blob.BlobServiceClient")
    def test_store_file_compresses_large_geojson(self, mock_blob_client):
        """Large GeoJSON files should be compressed."""
        # Create large GeoJSON content (>1MB)
        test_geojson = (
            b'{"type":"FeatureCollection","features":[' + b'{"type":"Feature"},' * 100000 + b"]}"
        )
        original_size = len(test_geojson)
        assert original_size > 1024 * 1024  # Ensure > 1MB

        # Mock Azure SDK
        mock_container = MagicMock()
        mock_blob_client.from_connection_string.return_value.get_container_client.return_value = (
            mock_container
        )
        mock_upload = mock_container.upload_blob

        # Call store_file
        url, unique_name = store_file("test.geojson", test_geojson)

        # Verify upload was called
        assert mock_upload.called

        # Get the uploaded data
        call_args = mock_upload.call_args
        uploaded_data = call_args.kwargs.get("data")
        content_settings = call_args.kwargs.get("content_settings")

        # Verify compression
        assert len(uploaded_data) < original_size
        assert content_settings is not None
        assert content_settings.content_encoding == "gzip"
        assert content_settings.content_type == "application/geo+json"

        # Verify it can be decompressed
        decompressed = gzip.decompress(uploaded_data)
        assert decompressed == test_geojson

    @patch("services.storage.file_management.USE_AZURE", True)
    @patch("azure.storage.blob.BlobServiceClient")
    def test_store_file_skips_compression_small_geojson(self, mock_blob_client):
        """Small GeoJSON files should not be compressed."""
        # Create small GeoJSON content (<1MB)
        test_geojson = b'{"type":"FeatureCollection","features":[]}'
        assert len(test_geojson) < 1024 * 1024

        # Mock Azure SDK
        mock_container = MagicMock()
        mock_blob_client.from_connection_string.return_value.get_container_client.return_value = (
            mock_container
        )
        mock_upload = mock_container.upload_blob

        # Call store_file
        url, unique_name = store_file("test.geojson", test_geojson)

        # Verify upload was called WITHOUT content_settings
        assert mock_upload.called
        call_args = mock_upload.call_args
        assert call_args.kwargs.get("content_settings") is None

    @patch("services.storage.file_management.USE_AZURE", True)
    @patch("azure.storage.blob.BlobServiceClient")
    def test_store_file_skips_compression_non_geojson(self, mock_blob_client):
        """Non-GeoJSON files should not be compressed."""
        # Create large non-GeoJSON content
        test_content = b"x" * (2 * 1024 * 1024)  # 2MB of data

        # Mock Azure SDK
        mock_container = MagicMock()
        mock_blob_client.from_connection_string.return_value.get_container_client.return_value = (
            mock_container
        )

        # Call store_file
        url, unique_name = store_file("test.txt", test_content)

        # Verify upload was called WITHOUT compression
        call_args = mock_container.upload_blob.call_args
        assert call_args.kwargs.get("content_settings") is None


class TestStoreFileStreamWithCompression:
    """Test store_file_stream() with Azure compression."""

    @patch("services.storage.file_management.USE_AZURE", True)
    @patch("azure.storage.blob.BlobServiceClient")
    @patch("core.config.MAX_FILE_SIZE", 100 * 1024 * 1024)  # 100MB
    def test_store_file_stream_compresses_large_geojson(self, mock_blob_client):
        """Large GeoJSON streams should be compressed."""
        # Create large GeoJSON content (>1MB)
        test_geojson = (
            b'{"type":"FeatureCollection","features":[' + b'{"type":"Feature"},' * 100000 + b"]}"
        )
        original_size = len(test_geojson)
        assert original_size > 1024 * 1024

        stream = BytesIO(test_geojson)

        # Mock Azure SDK
        mock_blob_container = MagicMock()
        mock_blob_client_instance = MagicMock()
        mock_blob_client.from_connection_string.return_value.get_container_client.return_value = (
            mock_blob_container
        )
        mock_blob_container.get_blob_client.return_value = mock_blob_client_instance

        # Call store_file_stream
        url, unique_name = store_file_stream("test.geojson", stream)

        # Verify blob upload was called
        assert mock_blob_client_instance.upload_blob.called

        # Get the uploaded data
        call_args = mock_blob_client_instance.upload_blob.call_args
        uploaded_data = call_args.kwargs.get("data")
        content_settings = call_args.kwargs.get("content_settings")

        # Verify compression
        assert len(uploaded_data) < original_size
        assert content_settings is not None
        assert content_settings.content_encoding == "gzip"
        assert content_settings.content_type == "application/geo+json"

        # Verify it can be decompressed
        decompressed = gzip.decompress(uploaded_data)
        assert decompressed == test_geojson

    @patch("services.storage.file_management.USE_AZURE", True)
    @patch("azure.storage.blob.BlobServiceClient")
    @patch("core.config.MAX_FILE_SIZE", 100 * 1024 * 1024)
    def test_store_file_stream_skips_compression_small_geojson(self, mock_blob_client):
        """Small GeoJSON streams should not be compressed."""
        # Create small GeoJSON content (<1MB)
        test_geojson = b'{"type":"FeatureCollection","features":[]}'
        stream = BytesIO(test_geojson)

        # Mock Azure SDK
        mock_blob_container = MagicMock()
        mock_blob_client_instance = MagicMock()
        mock_blob_client.from_connection_string.return_value.get_container_client.return_value = (
            mock_blob_container
        )
        mock_blob_container.get_blob_client.return_value = mock_blob_client_instance

        # Call store_file_stream
        url, unique_name = store_file_stream("test.geojson", stream)

        # Verify upload was called WITHOUT content_settings
        call_args = mock_blob_client_instance.upload_blob.call_args
        uploaded_data = call_args.kwargs.get("data")
        content_settings = call_args.kwargs.get("content_settings")

        # Should upload original content without compression
        assert content_settings is None
        assert uploaded_data == test_geojson


class TestCompressionRatio:
    """Test actual compression ratios for realistic data."""

    def test_realistic_geojson_compression(self):
        """Test compression on realistic GeoJSON data."""
        # Simulate a realistic GeoJSON with many features
        features = []
        for i in range(1000):
            features.append(
                f'{{"type":"Feature","properties":{{"id":{i},"name":"Feature {i}"}},'
                f'"geometry":{{"type":"Point","coordinates":[{i * 0.001}, {i * 0.001}]}}}}'
            )

        geojson = f'{{"type":"FeatureCollection","features":[{",".join(features)}]}}'
        original = geojson.encode("utf-8")
        compressed = _compress_for_azure(original)

        # GeoJSON should compress very well (typically 80-90%)
        compression_ratio = (1 - len(compressed) / len(original)) * 100
        assert compression_ratio > 80, f"Compression ratio {compression_ratio:.1f}% is below 80%"
        assert (
            compression_ratio < 95
        ), f"Compression ratio {compression_ratio:.1f}% seems unrealistic"

        # Verify decompression works
        decompressed = gzip.decompress(compressed)
        assert decompressed == original

    def test_compression_preserves_unicode(self):
        """Test that compression preserves Unicode characters."""
        # GeoJSON with special characters
        geojson = b'{"type":"Feature","properties":{"name":"M\xc3\xbcnchen \xe2\x9c\x93"}}'
        compressed = _compress_for_azure(geojson)
        decompressed = gzip.decompress(compressed)

        assert decompressed == geojson
        assert "München" in decompressed.decode("utf-8")
