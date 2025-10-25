"""Tests for GeoServer connection error handling and classification."""

import ssl
import socket
from unittest.mock import Mock

import pytest

from services.tools.geoserver.custom_geoserver import (
    GeoServerConnectionError,
    classify_connection_error,
)


class TestErrorClassification:
    """Test error classification for various connection error types."""

    def test_classify_ssl_certificate_verify_failed(self):
        """Test SSL certificate verification failure classification."""
        error = ssl.SSLError("[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed")
        error_type, message, technical = classify_connection_error(error)

        assert error_type == "ssl_certificate"
        assert "SSL certificate verification failed" in message
        assert "Allow Insecure" in message
        assert "CERTIFICATE_VERIFY_FAILED" in technical

    def test_classify_ssl_certificate_expired(self):
        """Test expired SSL certificate classification."""
        error = ssl.SSLError("certificate has expired")
        error_type, message, technical = classify_connection_error(error)

        assert error_type == "ssl_certificate"
        assert "certificate has expired" in message.lower()
        assert "Allow Insecure" in message

    def test_classify_ssl_generic_error(self):
        """Test generic SSL/TLS error classification."""
        error = ssl.SSLError("SSL handshake failed")
        error_type, message, technical = classify_connection_error(error)

        assert error_type == "ssl_certificate"
        assert "SSL/TLS connection error" in message

    def test_classify_dns_resolution_error(self):
        """Test DNS resolution failure classification."""
        error = socket.gaierror("[Errno 8] nodename nor servname provided, or not known")
        error_type, message, technical = classify_connection_error(error)

        assert error_type == "dns"
        assert "Domain name resolution failed" in message
        assert "nodename" in technical.lower()

    def test_classify_connection_refused(self):
        """Test connection refused error classification."""
        error = ConnectionRefusedError("Connection refused")
        error_type, message, technical = classify_connection_error(error)

        assert error_type == "connection"
        assert "Connection refused" in message
        assert "down, firewalled" in message

    def test_classify_connection_reset(self):
        """Test connection reset error classification."""
        error = ConnectionResetError("Connection reset by peer")
        error_type, message, technical = classify_connection_error(error)

        assert error_type == "connection"
        assert "Connection refused" in message  # Generic connection message

    def test_classify_network_unreachable(self):
        """Test network unreachable error classification."""
        error = OSError("[Errno 51] Network is unreachable")
        error_type, message, technical = classify_connection_error(error)

        assert error_type == "connection"
        assert "Network unreachable" in message

    def test_classify_timeout_error(self):
        """Test timeout error classification."""
        error = TimeoutError("Connection timed out")
        error_type, message, technical = classify_connection_error(error)

        assert error_type == "timeout"
        assert "Connection timeout" in message
        assert "took too long" in message

    def test_classify_http_401_error(self):
        """Test HTTP 401 authentication error classification."""
        error = Mock()
        error.response = Mock()
        error.response.status_code = 401
        error.__str__ = Mock(return_value="401 Client Error: Unauthorized")

        error_type, message, technical = classify_connection_error(error)

        assert error_type == "auth"
        assert "Authentication required" in message
        assert "username and password" in message
        assert "HTTP 401" in technical

    def test_classify_http_403_error(self):
        """Test HTTP 403 forbidden error classification."""
        error = Mock()
        error.response = Mock()
        error.response.status_code = 403
        error.__str__ = Mock(return_value="403 Client Error: Forbidden")

        error_type, message, technical = classify_connection_error(error)

        assert error_type == "auth"
        assert "Access forbidden" in message
        assert "HTTP 403" in technical

    def test_classify_http_404_error(self):
        """Test HTTP 404 not found error classification."""
        error = Mock()
        error.response = Mock()
        error.response.status_code = 404
        error.__str__ = Mock(return_value="404 Client Error: Not Found")

        error_type, message, technical = classify_connection_error(error)

        assert error_type == "http"
        assert "not found" in message.lower()
        assert "URL may be incorrect" in message

    def test_classify_http_500_error(self):
        """Test HTTP 500 server error classification."""
        error = Mock()
        error.response = Mock()
        error.response.status_code = 500
        error.__str__ = Mock(return_value="500 Server Error: Internal Server Error")

        error_type, message, technical = classify_connection_error(error)

        assert error_type == "http"
        assert "Server error" in message
        assert "500" in message

    def test_classify_unknown_error(self):
        """Test unknown error classification."""
        error = ValueError("Some unexpected error")
        error_type, message, technical = classify_connection_error(error)

        assert error_type == "unknown"
        assert "unexpected error" in message.lower()
        assert "Some unexpected error" in technical


class TestGeoServerConnectionError:
    """Test GeoServerConnectionError exception class."""

    def test_exception_attributes(self):
        """Test exception has all required attributes."""
        exc = GeoServerConnectionError(
            error_type="ssl_certificate",
            message="SSL certificate expired",
            technical_details="[SSL: CERTIFICATE_VERIFY_FAILED]",
        )

        assert exc.error_type == "ssl_certificate"
        assert exc.message == "SSL certificate expired"
        assert exc.technical_details == "[SSL: CERTIFICATE_VERIFY_FAILED]"
        assert str(exc) == "SSL certificate expired"

    def test_exception_can_be_raised(self):
        """Test exception can be raised and caught."""
        with pytest.raises(GeoServerConnectionError) as exc_info:
            raise GeoServerConnectionError(
                error_type="dns",
                message="Domain not found",
                technical_details="[Errno 8] nodename not known",
            )

        assert exc_info.value.error_type == "dns"
        assert exc_info.value.message == "Domain not found"


@pytest.mark.integration
class TestGeoServerConnectionWithMocks:
    """Integration tests for GeoServer connection with mocked services."""

    def test_ssl_error_propagates_with_details(self):
        """Test that SSL errors are caught and detailed information is preserved."""
        # This would be a more complex integration test that actually calls
        # fetch_all_service_capabilities_with_status with a mocked backend
        # that raises SSL errors
        pass  # TODO: Implement when we have proper test fixtures

    def test_allow_insecure_bypasses_ssl_verification(self):
        """Test that allow_insecure=True bypasses SSL certificate verification."""
        # This would test the actual SSL bypass logic with a test server
        pass  # TODO: Implement with test server setup
