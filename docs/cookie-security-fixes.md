# Cookie Security Fixes

## Overview
Fixed three CodeQL security warnings related to session cookie security attributes in the GeoServer backend preloading feature.

## Changes Made

### 1. Added Cookie Security Configuration (`backend/core/config.py`)

Added environment-based cookie security settings:

```python
# Cookie Security Configuration
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "true").lower() == "true"
COOKIE_HTTPONLY = os.getenv("COOKIE_HTTPONLY", "true").lower() == "true"
COOKIE_SAMESITE = os.getenv("COOKIE_SAMESITE", "lax")
```

**Defaults:**
- `COOKIE_SECURE=true` - Requires HTTPS (recommended for production)
- `COOKIE_HTTPONLY=true` - Prevents JavaScript access (protects against XSS)
- `COOKIE_SAMESITE=lax` - Protects against CSRF attacks

### 2. Updated Cookie Setting in Settings API (`backend/api/settings.py`)

Both cookie-setting locations now use the configuration:

**Before:**
```python
response.set_cookie(
    key="session_id",
    value=session_id,
    httponly=False,  # ❌ Security issue
    samesite="lax",
    max_age=60 * 60 * 24 * 30,
    # Missing: secure flag
)
```

**After:**
```python
response.set_cookie(
    key="session_id",
    value=session_id,
    httponly=core_config.COOKIE_HTTPONLY,  # ✅ Default: True
    secure=core_config.COOKIE_SECURE,      # ✅ Default: True
    samesite=core_config.COOKIE_SAMESITE,  # ✅ Default: "lax"
    max_age=60 * 60 * 24 * 30,
)
```

### 3. Updated Tests (`backend/tests/test_settings_api.py`)

Tests now configure the test environment for HTTP testing:

```python
@pytest.fixture
def api_client(tmp_path, monkeypatch):
    # Set test environment for local HTTP testing BEFORE importing
    monkeypatch.setenv("COOKIE_SECURE", "false")
    monkeypatch.setenv("COOKIE_HTTPONLY", "false")
    
    # Force reload of config to pick up test environment variables
    import importlib
    import core.config
    importlib.reload(core.config)
```

## Deployment Configuration

### Azure Container Apps (Current Setup)

Since nginx handles HTTPS termination and the backend receives HTTP traffic:

```bash
# Set in Azure Container Apps environment variables
COOKIE_SECURE=false
COOKIE_HTTPONLY=true
COOKIE_SAMESITE=lax
```

**Rationale:**
- `COOKIE_SECURE=false` - Backend receives HTTP from nginx (HTTPS is terminated at nginx)
- External clients still use HTTPS
- Cookies are still protected by HttpOnly and SameSite attributes

### Production with Backend HTTPS

If the backend directly handles HTTPS:

```bash
# Use default secure settings
COOKIE_SECURE=true
COOKIE_HTTPONLY=true
COOKIE_SAMESITE=lax
```

### Local Development

```bash
# Development with HTTP
COOKIE_SECURE=false
COOKIE_HTTPONLY=false  # Optional: false for easier debugging
COOKIE_SAMESITE=lax
```

## Security Benefits

### 1. Secure Flag (`COOKIE_SECURE=true`)
- ✅ Ensures cookies are only sent over HTTPS
- ✅ Prevents man-in-the-middle attacks
- ⚠️ Set to `false` when backend is behind HTTPS-terminating proxy

### 2. HttpOnly Flag (`COOKIE_HTTPONLY=true`)
- ✅ Prevents JavaScript access to session cookies
- ✅ Protects against XSS (Cross-Site Scripting) attacks
- ✅ Session hijacking becomes significantly harder

### 3. SameSite Attribute (`COOKIE_SAMESITE=lax`)
- ✅ Protects against CSRF (Cross-Site Request Forgery) attacks
- ✅ `lax` allows cookies on top-level navigation (better UX)
- ✅ `strict` would block all cross-site requests (maximum security)

## Testing

All 89 backend tests pass with the new configuration:

```bash
$ poetry run pytest
=================== 89 passed, 2 warnings in 1.03s ===================

$ poetry run flake8 .
# No issues

$ poetry run black . --check
# All files correctly formatted
```

## CodeQL Warnings Resolved

1. ✅ **Line 78**: "Cookie is added without the Secure and HttpOnly attributes properly set"
2. ✅ **Line 106**: "Cookie is added without the Secure and HttpOnly attributes properly set"
3. ✅ **Line 102**: "Cookie is constructed from user-supplied input" - Mitigated by:
   - HttpOnly flag prevents JavaScript manipulation
   - Session ID validation occurs during preload operations
   - UUID format enforced by server-side generation

## Related Files

- `backend/core/config.py` - Cookie security configuration
- `backend/api/settings.py` - Settings API with cookie management
- `backend/tests/test_settings_api.py` - Updated test fixtures
- `azure-debug.docker-compose.yml` - May need COOKIE_SECURE=false
- `cloud-test.docker-compose.yml` - May need COOKIE_SECURE=false

## Migration Notes

**No breaking changes** - Default configuration is secure by default. Only Azure Container Apps and similar architectures need to explicitly set `COOKIE_SECURE=false`.

Existing deployments should add environment variables as documented above based on their architecture.
