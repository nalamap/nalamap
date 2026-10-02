"""Regression: no OIDC provider (esp. Google) is enabled unless explicitly configured."""

import importlib

import core.config as config


def _reload(monkeypatch, **env):
    for key in ("OIDC_PROVIDERS", "OIDC_GOOGLE_ISSUER", "OIDC_GOOGLE_CLIENT_ID"):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    return importlib.reload(config)


def test_no_oidc_provider_by_default(monkeypatch):
    cfg = _reload(monkeypatch)
    try:
        assert cfg.OIDC_PROVIDERS == []
        assert cfg.get_oidc_providers() == []
    finally:
        importlib.reload(config)


def test_google_not_enabled_by_leftover_google_env(monkeypatch):
    cfg = _reload(
        monkeypatch,
        OIDC_GOOGLE_ISSUER="https://accounts.google.com",
        OIDC_GOOGLE_CLIENT_ID="x",
    )
    try:
        assert cfg.get_oidc_providers() == []
    finally:
        importlib.reload(config)
