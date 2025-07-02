import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from models.geodata import GeoDataObject, LayerStyle
from services.tools.styling_tools import normalize_color


def test_normalize_color_valid_and_invalid():
    # Valid colors
    assert normalize_color("red").lower() == "#ff0000"
    assert normalize_color("#ff0000").lower() == "#ff0000"
    hex_result = normalize_color("ff0000")
    assert hex_result.lower() in ["#ff0000", "ff0000"]
    # Invalid colors returned as-is
    assert normalize_color("invalidcolor") == "invalidcolor"
    assert normalize_color("") == ""
    assert normalize_color(None) is None


def test_layer_style_defaults_and_custom():
    # Default style
    style = LayerStyle()
    assert style.stroke_color in ["#3388ff", "#3388f"]
    assert style.fill_color in ["#3388ff", "#3388f"] 
    assert style.stroke_weight == 2
    assert style.fill_opacity == 0.3
    # Custom style
    custom = LayerStyle(stroke_color="#ff0000", fill_color="#00ff00", radius=10)
    assert custom.stroke_color == "#ff0000"
    assert custom.fill_color == "#00ff00"
    assert custom.radius == 10


def test_geodata_object_creation_and_styling():
    # Basic layer with default style
    layer = create_test_layer("test_layer")
    assert layer.name == "test_layer"
    assert layer.data_type == "GeoJson"
    assert layer.visible is True
    assert layer.style.stroke_color in ["#3388ff", "#3388f"]
    # Custom styling
    custom_layer = create_test_layer("custom", has_default_style=False)
    assert custom_layer.style.stroke_color == "#404040"
    assert custom_layer.style.fill_color == "#808080"
    # Multiple layers
    layers = [create_test_layer(f"layer_{i}") for i in range(3)]
    assert len(layers) == 3
    assert all(layer.style is not None for layer in layers)

# Helper function
def create_test_layer(name: str, has_default_style: bool = True) -> GeoDataObject:
    """Create a test layer for styling tests."""
    layer = GeoDataObject(
        id=f"test-{name}",
        data_source_id="test_db",
        data_type="GeoJson",
        data_origin="uploaded",
        data_source="Test Source",
        data_link="http://test.com",
        name=name,
        title=f"{name.title()} Dataset",
        description=f"Test {name} layer",
        visible=True,
    )
    
    if has_default_style:
        layer.style = LayerStyle()  # Default styling
    else:
        # Custom styling to simulate non-default
        layer.style = LayerStyle(stroke_color="#404040", fill_color="#808080")
    
    return layer
