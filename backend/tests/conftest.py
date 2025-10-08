import sys
from pathlib import Path

# Add the backend root directory to Python path first
backend_root = Path(__file__).parent.parent
sys.path.insert(0, str(backend_root))

"""
Pytest configuration and fixtures for styling tools tests.
"""

import pytest

from models.geodata import DataOrigin, DataType, GeoDataObject, LayerStyle


@pytest.fixture
def sample_river_layer():
    """Create a sample river layer for testing."""
    return GeoDataObject(
        id="river-test-1",
        data_source_id="test_db",
        data_type=DataType.GEOJSON,
        data_origin=DataOrigin.UPLOAD,
        data_source="Test Source",
        data_link="http://test.com",
        name="Rivers of Africa",
        title="Major Rivers Dataset",
        description="This dataset contains major rivers and waterways across Africa",
        style=LayerStyle(
            stroke_color="#3388f",
            stroke_weight=2,
            fill_color="#3388f",
            fill_opacity=0.3,
        ),
        visible=True,
    )


@pytest.fixture
def sample_building_layer():
    """Create a sample building layer for testing."""
    return GeoDataObject(
        id="building-test-1",
        data_source_id="test_db",
        data_type=DataType.GEOJSON,
        data_origin=DataOrigin.UPLOAD,
        data_source="Test Source",
        data_link="http://test.com",
        name="Urban Buildings",
        title="City Buildings Dataset",
        description="Buildings and urban structures in major cities",
        style=LayerStyle(
            stroke_color="#3388f",
            stroke_weight=1,
            fill_color="#3388f",
            fill_opacity=0.3,
        ),
        visible=True,
    )


@pytest.fixture
def sample_park_layer():
    """Create a sample park layer for testing."""
    return GeoDataObject(
        id="park-test-1",
        data_source_id="test_db",
        data_type=DataType.GEOJSON,
        data_origin=DataOrigin.UPLOAD,
        data_source="Test Source",
        data_link="http://test.com",
        name="National Parks",
        title="Protected Areas",
        description="National parks and protected green spaces with forests and wildlife",
        style=LayerStyle(
            stroke_color="#3388f",
            stroke_weight=1,
            fill_color="#3388f",
            fill_opacity=0.3,
        ),
        visible=True,
    )


@pytest.fixture
def basic_state():
    """Create a basic state for testing."""
    return {"geodata_layers": [], "messages": []}


@pytest.fixture
def state_with_river_layer(basic_state, sample_river_layer):
    """Create a state with a river layer."""
    basic_state["geodata_layers"] = [sample_river_layer]
    return basic_state


@pytest.fixture
def state_with_multiple_layers(basic_state, sample_river_layer, sample_building_layer):
    """Create a state with multiple layers."""
    basic_state["geodata_layers"] = [sample_river_layer, sample_building_layer]
    return basic_state


@pytest.fixture
def sample_road_layer():
    """Create a sample road layer for testing."""
    return GeoDataObject(
        id="road-test-1",
        data_source_id="test_db",
        data_type=DataType.GEOJSON,
        data_origin=DataOrigin.UPLOAD,
        data_source="Test Source",
        data_link="http://test.com",
        name="Transportation Network",
        title="Major Roads Dataset",
        description="Primary and secondary roads for transportation planning",
        style=LayerStyle(
            stroke_color="#3388f",
            stroke_weight=2,
            fill_color="#3388f",
            fill_opacity=0.3,
        ),
        visible=True,
    )


@pytest.fixture
def sample_boundary_layer():
    """Create a sample administrative boundary layer for testing."""
    return GeoDataObject(
        id="boundary-test-1",
        data_source_id="test_db",
        data_type=DataType.GEOJSON,
        data_origin=DataOrigin.UPLOAD,
        data_source="Test Source",
        data_link="http://test.com",
        name="Administrative Boundaries",
        title="District Boundaries",
        description="Official administrative boundaries for regional planning",
        style=LayerStyle(
            stroke_color="#3388f",
            stroke_weight=1,
            fill_color="#3388f",
            fill_opacity=0.1,
        ),
        visible=True,
    )


@pytest.fixture
def sample_mining_layer():
    """Create a sample mining/industrial layer for testing."""
    return GeoDataObject(
        id="mining-test-1",
        data_source_id="test_db",
        data_type=DataType.GEOJSON,
        data_origin=DataOrigin.UPLOAD,
        data_source="Test Source",
        data_link="http://test.com",
        name="Mining Operations",
        title="Active Mining Sites",
        description="Mining concessions and active extraction operations",
        style=LayerStyle(
            stroke_color="#3388f",
            stroke_weight=2,
            fill_color="#3388f",
            fill_opacity=0.3,
        ),
        visible=True,
    )


@pytest.fixture
def layer_with_custom_style():
    """Create a layer that already has custom styling."""
    return GeoDataObject(
        id="custom-styled-test",
        data_source_id="test_db",
        data_type=DataType.GEOJSON,
        data_origin=DataOrigin.UPLOAD,
        data_source="Test Source",
        data_link="http://test.com",
        name="Custom Styled Layer",
        title="Pre-styled Dataset",
        description="Layer with existing custom styling",
        style=LayerStyle(
            stroke_color="purple",
            stroke_weight=5,
            fill_color="orange",
            fill_opacity=0.7,
            stroke_opacity=0.9,
            radius=15,
        ),
        visible=True,
    )


@pytest.fixture
def layer_without_style():
    """Create a layer without any styling."""
    layer_dict = {
        "id": "no-style-test",
        "data_source_id": "test_db",
        "data_type": DataType.GEOJSON,
        "data_origin": DataOrigin.UPLOAD,
        "data_source": "Test Source",
        "data_link": "http://test.com",
        "name": "No Style Layer",
        "description": "Layer without initial styling",
        "visible": True,
        # No style field
    }
    return GeoDataObject(**layer_dict)


@pytest.fixture
def state_with_mixed_layers(
    basic_state,
    sample_river_layer,
    sample_building_layer,
    sample_park_layer,
    layer_with_custom_style,
):
    """Create a state with layers in different styling states."""
    basic_state["geodata_layers"] = [
        sample_river_layer,  # Default styling
        sample_building_layer,  # Default styling
        sample_park_layer,  # Default styling
        layer_with_custom_style,  # Already custom styled
    ]
    return basic_state


@pytest.fixture
def realistic_layer_collection():
    """Create a collection of realistic layers for testing."""
    layers = []

    # Water features
    layers.append(
        GeoDataObject(
            id="african-rivers",
            data_source_id="realistic_db",
            data_type=DataType.GEOJSON,
            data_origin=DataOrigin.UPLOAD,
            data_source="Realistic Source",
            data_link="http://realistic.com",
            name="African Major Rivers 2024",
            description=(
                "Updated dataset of major rivers across Africa including "
                "the Nile, Congo, Niger, and Zambezi"
            ),
            style=LayerStyle(
                stroke_color="#3388f",
                stroke_weight=2,
                fill_color="#3388f",
                fill_opacity=0.3,
            ),
            visible=True,
        )
    )

    # Built environment
    layers.append(
        GeoDataObject(
            id="lagos-buildings",
            data_source_id="realistic_db",
            data_type=DataType.GEOJSON,
            data_origin=DataOrigin.UPLOAD,
            data_source="Realistic Source",
            data_link="http://realistic.com",
            name="Urban Buildings - Lagos Metropolitan",
            description="Comprehensive building footprints for Lagos metropolitan area",
            style=LayerStyle(
                stroke_color="#3388f",
                stroke_weight=1,
                fill_color="#3388f",
                fill_opacity=0.3,
            ),
            visible=True,
        )
    )

    # Natural areas
    layers.append(
        GeoDataObject(
            id="protected-areas",
            data_source_id="realistic_db",
            data_type=DataType.GEOJSON,
            data_origin=DataOrigin.UPLOAD,
            data_source="Realistic Source",
            data_link="http://realistic.com",
            name="Protected Areas and National Parks",
            description="National parks, game reserves, and protected areas across East Africa",
            style=LayerStyle(
                stroke_color="#3388f",
                stroke_weight=1,
                fill_color="#3388ff",
                fill_opacity=0.3,
            ),
            visible=True,
        )
    )

    return layers
