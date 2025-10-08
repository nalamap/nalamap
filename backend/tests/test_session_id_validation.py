"""Tests for session_id validation to prevent cookie injection attacks.

These tests verify that user-supplied session IDs are properly validated
before being used in cookies, addressing CodeQL security warnings.
"""

from api.settings import validate_session_id


def test_validate_session_id_accepts_uuid_hex():
    """Valid UUID hex strings should be accepted."""
    # UUID4 hex format (32 characters)
    assert validate_session_id("a1b2c3d4e5f6789012345678901234ab") is True

    # UUID format with hyphens
    assert validate_session_id("550e8400-e29b-41d4-a716-446655440000") is True


def test_validate_session_id_accepts_alphanumeric():
    """Alphanumeric strings with hyphens should be accepted."""
    assert validate_session_id("session-123") is True
    assert validate_session_id("abcdef123456") is True
    assert validate_session_id("SESSION-ID-789") is True


def test_validate_session_id_rejects_empty():
    """Empty strings should be rejected."""
    assert validate_session_id("") is False
    assert validate_session_id(None) is False  # type: ignore[arg-type]


def test_validate_session_id_rejects_too_short():
    """Session IDs shorter than 8 characters should be rejected."""
    assert validate_session_id("abc123") is False
    assert validate_session_id("1234567") is False


def test_validate_session_id_rejects_too_long():
    """Session IDs longer than 128 characters should be rejected."""
    long_id = "a" * 129
    assert validate_session_id(long_id) is False


def test_validate_session_id_rejects_special_characters():
    """Special characters that could enable cookie injection should be rejected."""
    # Semicolon (cookie separator)
    assert validate_session_id("session;malicious=value") is False

    # Equals sign (cookie assignment)
    assert validate_session_id("session=malicious") is False

    # Newline (HTTP header injection)
    assert validate_session_id("session\nSet-Cookie: evil=1") is False

    # Carriage return
    assert validate_session_id("session\rmalicious") is False

    # Comma (cookie separator in some contexts)
    assert validate_session_id("session,value") is False

    # Backslash
    assert validate_session_id("session\\path") is False

    # Forward slash
    assert validate_session_id("session/path") is False

    # Space
    assert validate_session_id("session with spaces") is False

    # Quotes
    assert validate_session_id('session"quoted') is False
    assert validate_session_id("session'quoted") is False


def test_validate_session_id_rejects_unicode():
    """Unicode characters should be rejected."""
    assert validate_session_id("session-🔒") is False
    assert validate_session_id("сессия123") is False


def test_validate_session_id_rejects_control_characters():
    """Control characters should be rejected."""
    assert validate_session_id("session\x00null") is False
    assert validate_session_id("session\ttab") is False


def test_validate_session_id_boundary_cases():
    """Test boundary cases for length validation."""
    # Exactly 8 characters (minimum)
    assert validate_session_id("abcd1234") is True

    # Exactly 128 characters (maximum)
    assert validate_session_id("a" * 128) is True

    # 7 characters (too short)
    assert validate_session_id("abc1234") is False

    # 129 characters (too long)
    assert validate_session_id("a" * 129) is False


def test_validate_session_id_realistic_attacks():
    """Test realistic cookie injection attack patterns."""
    # HTTP Response Splitting
    assert validate_session_id("session\r\nSet-Cookie: admin=true") is False

    # Cookie Attribute Injection
    assert validate_session_id("session; HttpOnly; Secure") is False

    # Path Traversal in Cookie
    assert validate_session_id("../../etc/passwd") is False

    # SQL Injection Pattern (though not directly applicable, good to block)
    assert validate_session_id("session'; DROP TABLE users--") is False

    # XSS Pattern
    assert validate_session_id("<script>alert('xss')</script>") is False
