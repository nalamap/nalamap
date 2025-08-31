import types
from services.tools.geoserver.custom_geoserver import _sanitize_crs_list, _sanitize_properties


def test_sanitize_crs_list_basic():
    class FakeCrs:
        def __init__(self, code, proj4=None):
            self.code = code
            self.proj4 = proj4
    crs_items = [
        FakeCrs("EPSG:4326"),
        "EPSG:3857",
        FakeCrs(None, proj4="+proj=longlat +datum=WGS84"),
    ]
    out = _sanitize_crs_list(crs_items)
    assert "EPSG:4326" in out
    assert "EPSG:3857" in out
    # Fallback to proj4 str conversion
    assert any("+proj=longlat" in x for x in out)


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
