"""
Tests for Deployment Configuration Loading and Validation.

Tests cover:
1. Config file loading (valid/invalid JSON, missing file)
2. Pydantic model validation
3. Tool name validation against available tools
4. Model provider/name availability checking
5. GeoServer URL normalization
6. Color settings validation
7. Merging config with defaults
8. Error/warning logging
"""

import json
import os
import tempfile

import pytest

from models.deployment_config import (
    ColorScale,
    ColorSettings,
    DeploymentConfig,
    DeploymentGeoServerBackend,
    DeploymentModelSettings,
    DeploymentToolConfig,
)
from services.deployment_config_loader import (
    DEPLOYMENT_CONFIG_ENV_VAR,
    clear_config_cache,
    get_preload_backends,
    get_tool_overrides,
    load_and_validate_config,
    load_config_file,
    merge_tool_metadata_with_config,
    validate_color_settings,
    validate_geoserver_backends,
    validate_model_settings,
    validate_tools,
)


@pytest.fixture(autouse=True)
def reset_config_cache():
    """Reset config cache before each test."""
    clear_config_cache()
    # Also ensure env var is cleared
    if DEPLOYMENT_CONFIG_ENV_VAR in os.environ:
        del os.environ[DEPLOYMENT_CONFIG_ENV_VAR]
    yield
    clear_config_cache()
    if DEPLOYMENT_CONFIG_ENV_VAR in os.environ:
        del os.environ[DEPLOYMENT_CONFIG_ENV_VAR]


class TestLoadConfigFile:
    """Tests for load_config_file function."""

    def test_load_valid_json(self):
        """Test loading a valid JSON config file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"config_name": "Test Config"}, f)
            temp_path = f.name

        try:
            data, error = load_config_file(temp_path)
            assert error is None
            assert data == {"config_name": "Test Config"}
        finally:
            os.unlink(temp_path)

    def test_load_invalid_json(self):
        """Test loading an invalid JSON file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("{ invalid json }")
            temp_path = f.name

        try:
            data, error = load_config_file(temp_path)
            assert data is None
            assert "Invalid JSON" in error
        finally:
            os.unlink(temp_path)

    def test_load_missing_file(self):
        """Test loading a non-existent file."""
        data, error = load_config_file("/nonexistent/path/config.json")
        assert data is None
        assert "not found" in error

    def test_load_directory_instead_of_file(self):
        """Test loading a directory path instead of a file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            data, error = load_config_file(temp_dir)
            assert data is None
            assert "not a file" in error


class TestValidateTools:
    """Tests for validate_tools function."""

    def test_valid_tools(self):
        """Test validation of valid tool names."""
        tool_configs = [
            DeploymentToolConfig(name="geoprocess", enabled=True),
            DeploymentToolConfig(name="geocode_nominatim", enabled=False),
        ]
        valid_configs, warnings = validate_tools(tool_configs)
        assert len(valid_configs) == 2
        assert len(warnings) == 0

    def test_unknown_tool(self):
        """Test validation with unknown tool name."""
        tool_configs = [
            DeploymentToolConfig(name="geoprocess", enabled=True),
            DeploymentToolConfig(name="unknown_tool", enabled=True),
        ]
        valid_configs, warnings = validate_tools(tool_configs)
        assert len(valid_configs) == 1
        assert valid_configs[0].name == "geoprocess"
        assert len(warnings) == 1
        assert "Unknown tool" in warnings[0]
        assert "unknown_tool" in warnings[0]


class TestValidateModelSettings:
    """Tests for validate_model_settings function."""

    def test_no_settings(self):
        """Test validation with no model settings."""
        settings, warnings = validate_model_settings(None)
        assert settings is None
        assert len(warnings) == 0

    def test_valid_strategy(self):
        """Test validation with valid tool selection strategy."""
        model_settings = DeploymentModelSettings(tool_selection_strategy="conservative")
        settings, warnings = validate_model_settings(model_settings)
        assert settings is not None
        assert len(warnings) == 0

    def test_invalid_strategy(self):
        """Test validation with invalid tool selection strategy."""
        model_settings = DeploymentModelSettings(tool_selection_strategy="invalid_strategy")
        settings, warnings = validate_model_settings(model_settings)
        assert settings is not None
        assert len(warnings) == 1
        assert "Invalid tool_selection_strategy" in warnings[0]


class TestValidateGeoServerBackends:
    """Tests for validate_geoserver_backends function."""

    def test_valid_backends(self):
        """Test validation of valid backends."""
        backends = [
            DeploymentGeoServerBackend(
                url="https://geoserver.example.org/geoserver/",
                name="Test Backend",
                enabled=True,
            ),
        ]
        validated, warnings = validate_geoserver_backends(backends)
        assert len(validated) == 1
        assert len(warnings) == 0

    def test_missing_protocol(self):
        """Test validation of URL without protocol."""
        backends = [
            DeploymentGeoServerBackend(
                url="geoserver.example.org/geoserver/",
                name="Test Backend",
                enabled=True,
            ),
        ]
        validated, warnings = validate_geoserver_backends(backends)
        assert len(validated) == 1
        assert len(warnings) == 1
        assert "missing protocol" in warnings[0]

    def test_empty_url(self):
        """Test validation skips backends with empty URLs."""
        backends = [
            DeploymentGeoServerBackend(url="", name="Empty", enabled=True),
        ]
        validated, warnings = validate_geoserver_backends(backends)
        assert len(validated) == 0
        assert len(warnings) == 1
        assert "empty URL" in warnings[0]


class TestValidateColorSettings:
    """Tests for validate_color_settings function."""

    def test_no_settings(self):
        """Test validation with no color settings."""
        settings, warnings = validate_color_settings(None)
        assert settings is None
        assert len(warnings) == 0

    def test_valid_color_scale(self):
        """Test validation of valid color settings."""
        scale = ColorScale(
            shade_50="#FFFFFF",
            shade_100="#F0F0F0",
            shade_200="#E0E0E0",
            shade_300="#D0D0D0",
            shade_400="#C0C0C0",
            shade_500="#B0B0B0",
            shade_600="#A0A0A0",
            shade_700="#909090",
            shade_800="#808080",
            shade_900="#707070",
            shade_950="#000000",
        )
        color_settings = ColorSettings(
            primary=scale,
            second_primary=scale,
            secondary=scale,
            tertiary=scale,
            danger=scale,
            warning=scale,
            info=scale,
            neutral=scale,
            corporate_1=scale,
            corporate_2=scale,
            corporate_3=scale,
        )
        validated, warnings = validate_color_settings(color_settings)
        assert validated is not None
        assert len(warnings) == 0


class TestLoadAndValidateConfig:
    """Tests for load_and_validate_config function."""

    def test_no_config_path(self):
        """Test when no config path is set."""
        result = load_and_validate_config()
        assert result.valid is True
        assert result.config is None
        assert len(result.errors) == 0

    def test_valid_config_file(self):
        """Test loading a valid config file."""
        config_data = {
            "config_name": "Test Deployment",
            "config_description": "A test deployment configuration",
            "geoserver_backends": [
                {
                    "url": "https://geoserver.example.org/geoserver/",
                    "name": "Test GeoServer",
                    "enabled": True,
                    "preload_on_startup": False,
                }
            ],
            "tools": [
                {"name": "geoprocess", "enabled": True},
                {"name": "geocode_nominatim", "enabled": False},
            ],
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            temp_path = f.name

        try:
            os.environ[DEPLOYMENT_CONFIG_ENV_VAR] = temp_path
            result = load_and_validate_config()

            assert result.valid is True
            assert result.config is not None
            assert result.config.config_name == "Test Deployment"
            assert len(result.config.geoserver_backends) == 1
            assert len(result.config.tools) == 2
            assert len(result.errors) == 0
        finally:
            os.unlink(temp_path)

    def test_config_with_unknown_tools(self):
        """Test config with unknown tools generates warnings."""
        config_data = {
            "tools": [
                {"name": "geoprocess", "enabled": True},
                {"name": "nonexistent_tool", "enabled": True},
            ],
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            temp_path = f.name

        try:
            os.environ[DEPLOYMENT_CONFIG_ENV_VAR] = temp_path
            result = load_and_validate_config()

            assert result.valid is True
            assert result.config is not None
            # Only valid tool should remain
            assert len(result.config.tools) == 1
            assert result.config.tools[0].name == "geoprocess"
            # Warning should be generated
            assert len(result.warnings) >= 1
            assert any("Unknown tool" in w for w in result.warnings)
        finally:
            os.unlink(temp_path)

    def test_invalid_json_config(self):
        """Test loading invalid JSON config file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("{ not valid json }")
            temp_path = f.name

        try:
            os.environ[DEPLOYMENT_CONFIG_ENV_VAR] = temp_path
            result = load_and_validate_config()

            assert result.valid is False
            assert result.config is None
            assert len(result.errors) >= 1
        finally:
            os.unlink(temp_path)


class TestMergeToolMetadataWithConfig:
    """Tests for merge_tool_metadata_with_config function."""

    def test_no_config_returns_base(self):
        """Test that no config returns base metadata unchanged."""
        base_metadata = {
            "geoprocess": {"enabled": True, "category": "geoprocessing"},
            "geocode_nominatim": {"enabled": True, "category": "geocoding"},
        }
        result = merge_tool_metadata_with_config(base_metadata)
        assert result == base_metadata

    def test_override_enabled_state(self):
        """Test that config overrides tool enabled state."""
        # Create a config file that disables geoprocess
        config_data = {
            "tools": [
                {"name": "geoprocess", "enabled": False},
            ],
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            temp_path = f.name

        try:
            os.environ[DEPLOYMENT_CONFIG_ENV_VAR] = temp_path
            # Clear cache and reload
            clear_config_cache()
            load_and_validate_config()

            base_metadata = {
                "geoprocess": {"enabled": True, "category": "geoprocessing"},
                "geocode_nominatim": {"enabled": True, "category": "geocoding"},
            }
            result = merge_tool_metadata_with_config(base_metadata)

            # geoprocess should now be disabled
            assert result["geoprocess"]["enabled"] is False
            # geocode_nominatim should remain enabled
            assert result["geocode_nominatim"]["enabled"] is True
        finally:
            os.unlink(temp_path)


class TestGetToolOverrides:
    """Tests for get_tool_overrides function."""

    def test_no_config(self):
        """Test returns empty dict when no config."""
        result = get_tool_overrides()
        assert result == {}

    def test_with_config(self):
        """Test returns tool overrides from config."""
        config_data = {
            "tools": [
                {"name": "geoprocess", "enabled": False},
                {"name": "geocode_nominatim", "enabled": True},
            ],
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            temp_path = f.name

        try:
            os.environ[DEPLOYMENT_CONFIG_ENV_VAR] = temp_path
            load_and_validate_config()
            result = get_tool_overrides()

            assert result == {
                "geoprocess": False,
                "geocode_nominatim": True,
            }
        finally:
            os.unlink(temp_path)


class TestGetPreloadBackends:
    """Tests for get_preload_backends function."""

    def test_no_config(self):
        """Test returns empty list when no config."""
        result = get_preload_backends()
        assert result == []

    def test_with_preload_backends(self):
        """Test returns backends marked for preload."""
        config_data = {
            "geoserver_backends": [
                {
                    "url": "https://geoserver1.example.org/geoserver/",
                    "name": "Backend 1",
                    "enabled": True,
                    "preload_on_startup": True,
                },
                {
                    "url": "https://geoserver2.example.org/geoserver/",
                    "name": "Backend 2",
                    "enabled": True,
                    "preload_on_startup": False,
                },
            ],
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            temp_path = f.name

        try:
            os.environ[DEPLOYMENT_CONFIG_ENV_VAR] = temp_path
            load_and_validate_config()
            result = get_preload_backends()

            assert len(result) == 1
            assert result[0].name == "Backend 1"
            assert result[0].preload_on_startup is True
        finally:
            os.unlink(temp_path)


class TestDeploymentConfigModel:
    """Tests for DeploymentConfig Pydantic model."""

    def test_minimal_config(self):
        """Test creating a minimal valid config."""
        config = DeploymentConfig()
        assert config.geoserver_backends == []
        assert config.mcp_servers == []
        assert config.tools == []
        assert config.model_settings is None

    def test_full_config(self):
        """Test creating a fully populated config."""
        config = DeploymentConfig(
            config_name="Full Test Config",
            config_description="A complete test configuration",
            config_version="1.0",
            geoserver_backends=[
                DeploymentGeoServerBackend(
                    url="https://geoserver.example.org/geoserver/",
                    name="Test Backend",
                    enabled=True,
                    preload_on_startup=True,
                    search_term="population",
                )
            ],
            model_settings=DeploymentModelSettings(
                model_provider="openai",
                model_name="gpt-4o",
                max_tokens=8000,
                enable_smart_crs=True,
            ),
            tools=[
                DeploymentToolConfig(name="geoprocess", enabled=True),
            ],
            system_prompt="Custom system prompt",
            theme="dark",
        )

        assert config.config_name == "Full Test Config"
        assert len(config.geoserver_backends) == 1
        assert config.geoserver_backends[0].preload_on_startup is True
        assert config.model_settings.model_provider == "openai"
        assert config.theme == "dark"

    def test_extra_fields_allowed(self):
        """Test that extra fields are allowed for forward compatibility."""
        config_data = {
            "config_name": "Test",
            "future_field": "some value",
            "another_future_field": {"nested": "data"},
        }
        config = DeploymentConfig.model_validate(config_data)
        assert config.config_name == "Test"
        # Extra fields should not raise an error
