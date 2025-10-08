"""Tests for color settings functionality in settings API."""

import pytest
from fastapi.testclient import TestClient

from api.settings import ColorScale, ColorSettings


def test_get_settings_options_includes_color_settings(client: TestClient):
    """Test that /settings/options returns default color settings."""
    response = client.get("/settings/options")
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


def test_default_color_settings_match_globals_css(client: TestClient):
    """Test that default colors from API match the values in globals.css."""
    response = client.get("/settings/options")
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


def test_session_id_set_with_color_settings(client: TestClient):
    """Test that session_id is set alongside color settings."""
    response = client.get("/settings/options")
    assert response.status_code == 200

    data = response.json()
    assert "session_id" in data
    assert "color_settings" in data

    # Check that session_id cookie is set
    assert "session_id" in response.cookies
