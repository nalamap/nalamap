"""Tests for color settings functionality in settings API."""

import importlib
import sys
from pathlib import Path

import pytest  # noqa: F401 - used for fixtures
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Ensure backend package is importable
BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))


@pytest.fixture
def api_client(tmp_path, monkeypatch):
    # Set test environment for local HTTP testing BEFORE importing
    monkeypatch.setenv("COOKIE_SECURE", "false")
    monkeypatch.setenv("COOKIE_HTTPONLY", "false")
    monkeypatch.setenv("NALAMAP_GEOSERVER_VECTOR_DB", str(tmp_path / "vectors.db"))

    # Force reload of config to pick up test environment variables
    import core.config
    importlib.reload(core.config)

    # Now import the router
    from api.settings import router as settings_router

    app = FastAPI()
    app.include_router(settings_router)
    return TestClient(app)


def test_get_settings_options_includes_color_settings(api_client):
    """Test that /settings/options returns default color settings."""
    response = api_client.get("/settings/options")
    assert response.status_code == 200

    data = response.json()
    assert "color_settings" in data

    color_settings = data["color_settings"]
    assert "primary" in color_settings
    assert "second_primary" in color_settings
    assert "secondary" in color_settings
    assert "tertiary" in color_settings

    # Check that each color scale has all required shades
    for scale_name in ["primary", "second_primary", "secondary", "tertiary"]:
        scale = color_settings[scale_name]
        for shade in [
            "shade_50",
            "shade_100",
            "shade_200",
            "shade_300",
            "shade_400",
            "shade_500",
            "shade_600",
            "shade_700",
            "shade_800",
            "shade_900",
            "shade_950",
        ]:
            assert shade in scale
            # Validate hex color format
            assert scale[shade].startswith("#")
            assert len(scale[shade]) == 7  # #RRGGBB format


def test_color_scale_model_validation():
    """Test that ColorScale model validates hex colors correctly."""
    from api.settings import ColorScale

    # Valid color scale
    valid_scale = ColorScale(
        shade_50="#f7f7f8",
        shade_100="#eeeef0",
        shade_200="#d8d8df",
        shade_300="#b7b9c2",
        shade_400="#8f91a1",
        shade_500="#717386",
        shade_600="#5b5c6e",
        shade_700="#505160",
        shade_800="#40414c",
        shade_900="#383842",
        shade_950="#25252c",
    )
    assert valid_scale.shade_50 == "#f7f7f8"
    assert valid_scale.shade_950 == "#25252c"


def test_color_settings_model_validation():
    """Test that ColorSettings model contains all required scales."""
    from api.settings import ColorScale, ColorSettings

    primary = ColorScale(
        shade_50="#f7f7f8",
        shade_100="#eeeef0",
        shade_200="#d8d8df",
        shade_300="#b7b9c2",
        shade_400="#8f91a1",
        shade_500="#717386",
        shade_600="#5b5c6e",
        shade_700="#505160",
        shade_800="#40414c",
        shade_900="#383842",
        shade_950="#25252c",
    )

    color_settings = ColorSettings(
        primary=primary,
        second_primary=primary,  # Using same for brevity
        secondary=primary,
        tertiary=primary,
    )

    assert color_settings.primary == primary
    assert color_settings.second_primary == primary
    assert color_settings.secondary == primary
    assert color_settings.tertiary == primary


def test_default_color_settings_match_globals_css(api_client):
    """Test that default colors from API match the values in globals.css."""
    response = api_client.get("/settings/options")
    assert response.status_code == 200

    color_settings = response.json()["color_settings"]

    # Verify primary colors match globals.css defaults
    primary = color_settings["primary"]
    assert primary["shade_50"] == "#f7f7f8"
    assert primary["shade_700"] == "#505160"  # --first-primary
    assert primary["shade_950"] == "#25252c"

    # Verify second primary colors
    second_primary = color_settings["second_primary"]
    assert second_primary["shade_600"] == "#68829e"  # --second-primary

    # Verify secondary colors
    secondary = color_settings["secondary"]
    assert secondary["shade_500"] == "#aebd38"  # --secondary

    # Verify tertiary colors
    tertiary = color_settings["tertiary"]
    assert tertiary["shade_600"] == "#598234"  # --tertiary


def test_session_id_set_with_color_settings(api_client):
    """Test that session_id is set alongside color settings."""
    response = api_client.get("/settings/options")
    assert response.status_code == 200

    data = response.json()
    assert "session_id" in data
    assert "color_settings" in data

    # Check that session_id cookie is set
    assert "session_id" in response.cookies
