"""Regression: no OIDC provider (esp. Google) is enabled unless explicitly configured."""

import importlib

import pytest

import core.config as config


@pytest.fixture
def reload_config():
    """Reload core.config under a controlled env; restore real config afterwards."""

    def _reload(monkeypatch, **env):
        # Isolate from developer .env / .env.local files read at import time.
        monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: False)
        for key in ("OIDC_PROVIDERS", "OIDC_GOOGLE_ISSUER", "OIDC_GOOGLE_CLIENT_ID"):
            monkeypatch.delenv(key, raising=False)
        for key, value in env.items():
            monkeypatch.setenv(key, value)
        return importlib.reload(config)

    yield _reload
    # Fixture teardown runs after monkeypatch has been undone (it is requested
    # first, so it is torn down last): reload with the real environment.
    importlib.reload(config)


def test_no_oidc_provider_by_default(reload_config, monkeypatch):
    cfg = reload_config(monkeypatch)
    assert cfg.OIDC_PROVIDERS == []
    assert cfg.get_oidc_providers() == []


def test_google_not_enabled_by_leftover_google_env(reload_config, monkeypatch):
    cfg = reload_config(
        monkeypatch,
        OIDC_GOOGLE_ISSUER="https://accounts.google.com",
        OIDC_GOOGLE_CLIENT_ID="x",
    )
    assert cfg.get_oidc_providers() == []
