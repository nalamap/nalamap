import types

from services.tools.geoserver.custom_geoserver import _sanitize_crs_list, _sanitize_properties


def test_sanitize_crs_list_basic():
    """Test that _sanitize_crs_list filters to common CRS codes only."""

    class FakeCrs:
        def __init__(self, code, proj4=None):
            self.code = code
            self.proj4 = proj4

    crs_items = [
        FakeCrs("EPSG:4326"),
        "EPSG:3857",
        FakeCrs("EPSG:32610"),  # UTM zone - not in common list
        FakeCrs(None, proj4="+proj=longlat +datum=WGS84"),  # No code - filtered out
    ]
    out = _sanitize_crs_list(crs_items)
    # Only common CRS codes should be returned
    assert "EPSG:4326" in out
    assert "EPSG:3857" in out
    # UTM and proj4-only entries should be filtered out
    assert not any("32610" in x for x in out)
    assert not any("+proj=longlat" in x for x in out)
    # Should have exactly 2 items (the common ones)
    assert len(out) == 2


def test_sanitize_properties_nested():
    nested = {
        "a": {"b": {"c": 1}},
        "set": {1, 2, 3},
        "obj": types.SimpleNamespace(x=5),
    }
    sanitized = _sanitize_properties(nested)
    assert isinstance(sanitized["a"], dict)
    assert sanitized["a"]["b"]["c"] == 1
    assert sorted(sanitized["set"]) == [1, 2, 3]
    assert sanitized["obj"].startswith("namespace(")
