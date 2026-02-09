"""Tests for authentication reset bug - 500 error after reset button.

This test file replicates the user-reported bug where:
1. User is logged in via authentication
2. User clicks reset button in frontend
3. Page reloads with valid cookie but gets 500 error from /auth/me
4. User cannot log in again, gets 500 error on /auth/login

Root cause: Missing validation in /auth/me endpoint for null user_id,
and improper UUID validation that causes database errors instead of 401.
"""

import pytest
from fastapi.testclient import TestClient
from jose import jwt
from datetime import datetime, timedelta

from main import app
from core.config import SECRET_KEY
from db.session import AsyncSessionLocal, get_session


# Check if database is configured
DATABASE_CONFIGURED = AsyncSessionLocal is not None


# Stub session dependency so token validation tests never touch the DB.
async def _stub_session():
    """Yield a no-op session; token checks must reject before DB access."""
    yield None


class TestAuthMeEndpointNoDB:
    """Tests for /auth/me endpoint that don't require database.

    These tests verify token validation BEFORE the database is touched.
    We override the DB session dependency so a missing database can never
    mask a token-level failure as 500.
    """

    @pytest.fixture
    def client(self):
        """Create a test client with the DB dependency overridden."""
        app.dependency_overrides[get_session] = _stub_session
        yield TestClient(app, raise_server_exceptions=False)
        app.dependency_overrides.pop(get_session, None)

    @pytest.mark.unit
    def test_auth_me_without_cookie_returns_401(self, client):
        """Test that /auth/me returns 401 when no cookie is present."""
        response = client.get("/api/auth/me")
        assert response.status_code == 401
        assert response.json()["detail"] == "Not authenticated"

    @pytest.mark.unit
    def test_auth_me_with_invalid_jwt_returns_401(self, client):
        """Test that /auth/me returns 401 for invalid JWT tokens."""
        client.cookies.set("access_token", "invalid.jwt.token")
        response = client.get("/api/auth/me")
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid token"

    @pytest.mark.unit
    def test_auth_me_with_expired_token_returns_401(self, client):
        """Test that /auth/me returns 401 for expired tokens."""
        expired_payload = {
            "sub": "12345678-1234-1234-1234-123456789012",
            "exp": datetime.utcnow() - timedelta(hours=1),
        }
        expired_token = jwt.encode(expired_payload, SECRET_KEY, algorithm="HS256")

        client.cookies.set("access_token", expired_token)
        response = client.get("/api/auth/me")
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid token"


@pytest.mark.skipif(not DATABASE_CONFIGURED, reason="Database not configured")
class TestAuthMeEndpointWithDB:
    """Tests for /auth/me endpoint that require database."""

    @pytest.fixture
    def client(self):
        """Create a test client."""
        return TestClient(app, raise_server_exceptions=False)

    @pytest.mark.unit
    def test_auth_me_with_token_missing_sub_returns_401(self, client):
        """Test that /auth/me returns 401 when token lacks 'sub' claim.

        This is a key bug fix test - tokens without 'sub' claim previously
        caused 500 errors because user_id=None was passed to the database query.
        """
        payload_without_sub = {"exp": datetime.utcnow() + timedelta(hours=1)}
        token_without_sub = jwt.encode(payload_without_sub, SECRET_KEY, algorithm="HS256")

        client.cookies.set("access_token", token_without_sub)
        response = client.get("/api/auth/me")
        # Should return 401, not 500
        assert response.status_code == 401
        assert "Invalid token" in response.json()["detail"]

    @pytest.mark.unit
    def test_auth_me_with_empty_sub_returns_401(self, client):
        """Test that /auth/me returns 401 when 'sub' claim is empty string."""
        payload_with_empty_sub = {"sub": "", "exp": datetime.utcnow() + timedelta(hours=1)}
        token = jwt.encode(payload_with_empty_sub, SECRET_KEY, algorithm="HS256")

        client.cookies.set("access_token", token)
        response = client.get("/api/auth/me")
        assert response.status_code == 401
        assert "Invalid token" in response.json()["detail"]

    @pytest.mark.unit
    def test_auth_me_with_invalid_uuid_returns_401(self, client):
        """Test that /auth/me returns 401 when 'sub' is not a valid UUID.

        This prevents database errors when the user_id cannot be parsed as UUID.
        """
        payload_with_invalid_uuid = {
            "sub": "not-a-valid-uuid",
            "exp": datetime.utcnow() + timedelta(hours=1),
        }
        token = jwt.encode(payload_with_invalid_uuid, SECRET_KEY, algorithm="HS256")

        client.cookies.set("access_token", token)
        response = client.get("/api/auth/me")
        assert response.status_code == 401
        assert "Invalid token" in response.json()["detail"]

    @pytest.mark.unit
    def test_auth_me_with_valid_uuid_but_nonexistent_user_returns_404(self, client):
        """Test that /auth/me returns 404 for valid token with nonexistent user."""
        payload = {
            "sub": "12345678-1234-1234-1234-123456789012",  # Valid UUID but no user
            "exp": datetime.utcnow() + timedelta(hours=1),
        }
        token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")

        client.cookies.set("access_token", token)
        response = client.get("/api/auth/me")
        # User doesn't exist, should return 404
        assert response.status_code == 404


@pytest.mark.skipif(not DATABASE_CONFIGURED, reason="Database not configured")
class TestAuthLoginEndpoint:
    """Tests for /auth/login endpoint to ensure it doesn't 500."""

    @pytest.fixture
    def client(self):
        """Create a test client."""
        return TestClient(app, raise_server_exceptions=False)

    @pytest.mark.unit
    def test_auth_login_with_missing_fields_returns_422(self, client):
        """Test that /auth/login returns 422 for missing required fields."""
        response = client.post("/api/auth/login", json={})
        assert response.status_code == 422

    @pytest.mark.unit
    def test_auth_login_with_empty_credentials_returns_401(self, client):
        """Test that /auth/login returns 401 for empty credentials."""
        response = client.post("/api/auth/login", json={"email": "", "password": ""})
        # Should return 401, not 500
        assert response.status_code == 401


@pytest.mark.skipif(not DATABASE_CONFIGURED, reason="Database not configured")
class TestResetScenario:
    """Integration-style tests simulating the reset button scenario."""

    @pytest.fixture
    def client(self):
        """Create a test client."""
        return TestClient(app, raise_server_exceptions=False)

    @pytest.mark.unit
    def test_auth_after_frontend_reset_simulation(self, client):
        """Simulate what happens when frontend reset button is clicked.

        The frontend reset button:
        1. Clears localStorage
        2. Reloads the page (cookie still present)
        3. Frontend calls /auth/me to check if user is logged in

        If the token is somehow corrupted or missing sub claim,
        we should get 401, not 500.
        """
        problematic_payloads = [
            {"exp": datetime.utcnow() + timedelta(hours=1)},  # No sub
            {"sub": None, "exp": datetime.utcnow() + timedelta(hours=1)},  # Null sub
            {"sub": "", "exp": datetime.utcnow() + timedelta(hours=1)},  # Empty sub
        ]

        for payload in problematic_payloads:
            token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
            client.cookies.set("access_token", token)
            response = client.get("/api/auth/me")

            assert response.status_code == 401, (
                f"Expected 401 for payload {payload}, got {response.status_code}: "
                f"{response.json()}"
            )
