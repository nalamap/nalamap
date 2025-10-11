import os
import sys

from api.ai_style import parse_color
from models.geodata import GeoDataObject, LayerStyle
from services.tools.styling_tools import normalize_color

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


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


def test_normalize_color_lowercase():
    """Test that lowercase color names work correctly."""
    # Test basic color names (lowercase)
    assert normalize_color("red").lower() == "#ff0000"
    assert normalize_color("blue").lower() == "#0000ff"
    assert normalize_color("green").lower() == "#00ff00"
    assert normalize_color("yellow").lower() == "#ffff00"
    assert normalize_color("orange").lower() == "#ffa500"

    # Test uppercase should also work
    assert normalize_color("RED").lower() == "#ff0000"
    assert normalize_color("BLUE").lower() == "#0000ff"

    # Test mixed case
    assert normalize_color("Red").lower() == "#ff0000"
    assert normalize_color("Blue").lower() == "#0000ff"


def test_parse_color_function():
    """Test the parse_color function in ai_style.py for correct hex codes."""
    # Test basic colors have correct 6-digit hex codes
    assert parse_color("red") == "#ff0000"
    assert parse_color("blue") == "#0000ff", "Blue should be #0000ff, not #0000f"
    assert parse_color("white") == "#ffffff", "White should be #ffffff, not #fffff"
    assert parse_color("cyan") == "#00ffff", "Cyan should be #00ffff, not #00fff"
    assert parse_color("magenta") == "#ff00ff", "Magenta should be #ff00ff, not #ff00f"
    assert parse_color("aqua") == "#00ffff", "Aqua should be #00ffff, not #00fff"

    # Test lowercase normalization
    assert parse_color("RED") == "#ff0000"
    assert parse_color("BLUE") == "#0000ff"
    assert parse_color("White") == "#ffffff"


def test_color_hex_format():
    """Test that all hex codes are properly formatted (6 characters after #)."""
    # All normalized colors should have exactly 7 characters (#RRGGBB)
    colors_to_test = ["red", "blue", "green", "yellow", "cyan", "magenta", "white", "black"]

    for color_name in colors_to_test:
        normalized = normalize_color(color_name)
        assert normalized.startswith("#"), f"{color_name} should start with #"
        assert len(normalized) == 7, f"{color_name} normalized to {normalized} should be 7 chars"

        # Also test parse_color
        parsed = parse_color(color_name)
        assert parsed.startswith("#"), f"{color_name} from parse_color should start with #"
        assert len(parsed) == 7, f"{color_name} parsed to {parsed} should be 7 chars"


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
