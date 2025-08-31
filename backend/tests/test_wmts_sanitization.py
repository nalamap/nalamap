from services.tools.geoserver.custom_geoserver import parse_wmts_capabilities


class _MockLayer:
    def __init__(self, lid):
        self.id = lid
        self.title = lid
        self.abstract = ""
        self.boundingBoxWGS84 = (-1, -1, 1, 1)
        self.resourceURLs = [
            {
                "template": (
                    "https://example.com/wmts/rest/workspace:layer/{style}/"
                    "{TileMatrixSet}/{TileMatrix}/{TileRow}/{TileCol}?format="
                    "application/json;type=utfgrid"
                )
            }
        ]
        self.tilematrixsetlinks = {}

class _MockProvider:
    name = "Mock WMTS Org"

class _MockWMTS:
    def __init__(self):
        self.contents = {"workspace:layer": _MockLayer("workspace:layer")}
        self.provider = _MockProvider()


def test_wmts_template_sanitized():
    wmts = _MockWMTS()
    layers = parse_wmts_capabilities(wmts, "http://example.com/gwc/service/wmts")
    assert len(layers) == 1
    link = layers[0].data_link
    assert "{style}" not in link
    assert "application/json;type=utfgrid" not in link
    assert "image/png" in link
