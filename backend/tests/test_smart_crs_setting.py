"""Tests for enable_smart_crs setting in ModelSettings."""

import pytest
from models.settings_model import ModelSettings


@pytest.mark.unit
def test_model_settings_enable_smart_crs_default_true():
    """Test that enable_smart_crs defaults to True in ModelSettings."""
    settings = ModelSettings(
        model_provider="openai",
        model_name="gpt-4",
        max_tokens=4000,
    )
    assert settings.enable_smart_crs is True


@pytest.mark.unit
def test_model_settings_enable_smart_crs_can_be_disabled():
    """Test that enable_smart_crs can be set to False."""
    settings = ModelSettings(
        model_provider="openai",
        model_name="gpt-4",
        max_tokens=4000,
        enable_smart_crs=False,
    )
    assert settings.enable_smart_crs is False


@pytest.mark.unit
def test_model_settings_enable_smart_crs_serialization():
    """Test that enable_smart_crs is properly serialized."""
    settings = ModelSettings(
        model_provider="openai",
        model_name="gpt-4",
        max_tokens=4000,
        enable_smart_crs=True,
    )
    data = settings.model_dump()
    assert "enable_smart_crs" in data
    assert data["enable_smart_crs"] is True


@pytest.mark.unit
def test_model_settings_enable_smart_crs_from_dict():
    """Test that enable_smart_crs can be loaded from dict."""
    data = {
        "model_provider": "openai",
        "model_name": "gpt-4",
        "max_tokens": 4000,
        "enable_smart_crs": False,
    }
    settings = ModelSettings(**data)
    assert settings.enable_smart_crs is False
