"""Tests for GeoServer URL normalization to prevent 503 errors."""

from api.settings import normalize_geoserver_url


def test_normalize_url_adds_https_when_missing():
    """Test that https:// is added when protocol is missing."""
    url = "example.com/geoserver"
    result = normalize_geoserver_url(url)
    assert result == "https://example.com/geoserver"


def test_normalize_url_preserves_http():
    """Test that existing http:// protocol is preserved."""
    url = "http://example.com/geoserver"
    result = normalize_geoserver_url(url)
    assert result == "http://example.com/geoserver"


def test_normalize_url_preserves_https():
    """Test that existing https:// protocol is preserved."""
    url = "https://example.com/geoserver"
    result = normalize_geoserver_url(url)
    assert result == "https://example.com/geoserver"


def test_normalize_url_handles_whitespace():
    """Test that leading/trailing whitespace is removed."""
    url = "  example.com/geoserver  "
    result = normalize_geoserver_url(url)
    assert result == "https://example.com/geoserver"


def test_normalize_url_with_port():
    """Test URL with port number."""
    url = "example.com:8080/geoserver"
    result = normalize_geoserver_url(url)
    assert result == "https://example.com:8080/geoserver"


def test_normalize_url_with_subdomain():
    """Test URL with subdomain."""
    url = "geoserver.example.com/wms"
    result = normalize_geoserver_url(url)
    assert result == "https://geoserver.example.com/wms"


def test_normalize_url_with_path_and_query():
    """Test URL with complex path and query parameters."""
    url = "example.com/geoserver/wms?service=WMS&version=1.3.0"
    result = normalize_geoserver_url(url)
    assert result == "https://example.com/geoserver/wms?service=WMS&version=1.3.0"


def test_normalize_url_real_geonode_example():
    """Test with real GeoNode demo URL that caused the 503 error."""
    url = "development.demo.geonode.org/geoserver/"
    result = normalize_geoserver_url(url)
    assert result == "https://development.demo.geonode.org/geoserver/"


def test_normalize_url_case_insensitive_protocol():
    """Test that protocol detection is case-insensitive."""
    # These should be preserved as-is
    assert normalize_geoserver_url("HTTP://example.com") == "HTTP://example.com"
    assert normalize_geoserver_url("HTTPS://example.com") == "HTTPS://example.com"
    assert normalize_geoserver_url("HtTpS://example.com") == "HtTpS://example.com"
