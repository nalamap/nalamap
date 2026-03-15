"""Geocoding services package.

This package directory shadows the legacy geocoding.py module.  All public
symbols from that module are re-exported here so that existing imports such as

    from services.tools.geocoding import geocode_using_nominatim_to_geostate

continue to work unchanged.
"""

import importlib.util
import os
import sys

# ---------------------------------------------------------------------------
# Re-export legacy geocoding.py
# ---------------------------------------------------------------------------
# The package directory takes precedence over geocoding.py in Python's import
# system.  We load the original file explicitly, giving it the correct
# __package__ so that its relative imports (from .constants import …) resolve
# against services.tools rather than this sub-package.

_legacy_path = os.path.join(os.path.dirname(__file__), "..", "geocoding.py")
_legacy_name = "services.tools._geocoding_legacy"

if _legacy_name not in sys.modules:
    _spec = importlib.util.spec_from_file_location(
        _legacy_name,
        _legacy_path,
        submodule_search_locations=[],
    )
    _legacy_mod = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
    # Relative imports in geocoding.py are relative to services.tools
    _legacy_mod.__package__ = "services.tools"
    sys.modules[_legacy_name] = _legacy_mod
    _spec.loader.exec_module(_legacy_mod)  # type: ignore[union-attr]
else:
    _legacy_mod = sys.modules[_legacy_name]

# Inject all names from the legacy module into this package namespace,
# including private names (some tests import them directly).
# Skip only dunder attributes to avoid overwriting package internals.
for _name in dir(_legacy_mod):
    if not (_name.startswith("__") and _name.endswith("__")):
        globals()[_name] = getattr(_legacy_mod, _name)

del _legacy_path, _legacy_name, _spec, _legacy_mod, _name

# ---------------------------------------------------------------------------
# New package exports
# ---------------------------------------------------------------------------
from .tag_resolver import SemanticTagResolver, TagCandidate, TagResolution  # noqa: E402
from .tag_vector_store import TagVectorStore  # noqa: E402
from .taginfo_fetcher import TagInfoEntry, TagInfoFetchError, fetch_popular_tags  # noqa: E402

__all__ = [
    # new exports
    "TagInfoEntry",
    "TagInfoFetchError",
    "fetch_popular_tags",
    "TagVectorStore",
    "SemanticTagResolver",
    "TagCandidate",
    "TagResolution",
]
