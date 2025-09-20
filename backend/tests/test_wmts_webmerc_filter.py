import os
from types import SimpleNamespace

from services.tools.geoserver.custom_geoserver import parse_wmts_capabilities


class _MockProvider:
    name = "Mock WMTS Org"


class _MockLayer:
    def __init__(self, lid: str, matrix_sets, with_resource_url=False):
        self.id = lid
        self.title = lid
        self.abstract = ""
        self.boundingBoxWGS84 = (-1, -1, 1, 1)
        self.tilematrixsetlinks = {
            ms: SimpleNamespace(
                template=(
                    f"http://mock/{ms}/{{TileMatrix}}/{{TileRow}}/{{TileCol}}"
                )
            )
            for ms in matrix_sets
        }
        # Optionally include a resourceURLs entry
        if with_resource_url:
            if with_resource_url:
                self.resourceURLs = [
                    {
                        "template": (
                            f"http://mock/rest/{lid}/default/{{TileMatrixSet}}/"
                            f"{{TileMatrix}}/{{TileRow}}/{{TileCol}}?format=image/png"
                        )
                    }
                ]
            else:
                self.resourceURLs = []
            self.resourceURLs = []


class _MockWMTS:
    def __init__(self, layers):
        self.contents = {lyr.id: lyr for lyr in layers}
        self.provider = _MockProvider()


def _run(parse_env_value: str, matrix_sets):
    os.environ["NALAMAP_FILTER_NON_WEBMERCATOR_WMTS"] = parse_env_value
    # Reload module not necessary since parse reads env at runtime inside function
    wmts = _MockWMTS([_MockLayer("workspace:layer", matrix_sets)])
    layers = parse_wmts_capabilities(wmts, "http://example.com/geoserver/gwc/service/wmts")
    return layers


def test_filter_excludes_non_webmercator():
    layers = _run("true", ["CUSTOM_CRS", "EPSG:1234"])
    assert (
        len(layers) == 0
    ), "Expected no layers when only non-WebMercator sets present and filter active"


def test_filter_includes_webmercator():
    layers = _run("true", ["EPSG:3857", "CUSTOM_CRS"])
    assert len(layers) == 1
    lyr = layers[0]
    props = getattr(lyr, "properties", {}) or {}
    assert isinstance(props, dict)
    assert props.get("has_webmercator") is True
    assert (
        "tilematrixset=EPSG:3857" in lyr.data_link
        or "tilematrixset=EPSG%3A3857" in lyr.data_link
    )


def test_filter_disabled_shows_all():
    layers = _run("false", ["NO_MERC", "EPSG:1234"])
    assert len(layers) == 1, "Expected layer to be returned when filter disabled"
    lyr = layers[0]
    props = getattr(lyr, "properties", {}) or {}
    assert isinstance(props, dict)
    assert props.get("has_webmercator") is False


def test_prefers_explicit_3857_over_alias():
    layers = _run("true", ["GoogleMapsCompatible", "EPSG:3857"])  # both acceptable
    assert len(layers) == 1
    link = layers[0].data_link
    # Ensure chosen preferred matrix set is EPSG:3857
    assert "tilematrixset=EPSG:3857" in link


def test_uses_alias_when_no_3857():
    layers = _run("true", ["GoogleMapsCompatible"])  # alias only
    assert len(layers) == 1
    link = layers[0].data_link
    assert "tilematrixset=GoogleMapsCompatible" in link
