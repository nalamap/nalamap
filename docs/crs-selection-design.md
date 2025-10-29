# Intelligent CRS Selection for Geoprocessing

## Overview

NaLaMap implements automatic, deterministic CRS selection for geoprocessing operations to ensure geometric accuracy across the globe. This document describes the design, operation mapping, API changes, and testing strategy.

## Problem Statement

Using a single global projection (EPSG:3857 Web Mercator) for all geoprocessing operations causes:
- Large area errors at high latitudes
- Distance inaccuracies in many regions
- Topology artifacts (slivers/gaps) in overlays
- No support above ~85° latitude

## Solution Summary

A rule-based selector chooses an appropriate CRS based on bounding box extent and operation type. Selection is deterministic, whitelist-based, and validated with pyproj.

### Three-tier selection hierarchy
1. Local (<6° extent): UTM zones via `zone = floor((lon+180)/6)+1` (conformal)
2. Regional: Continental Albers (equal-area) or Lambert Conformal Conic (conformal)
3. Polar (>80° lat): Stereographic (conformal) or LAEA (equal-area)

## Operation → Projection mapping
- area, dissolve(preserve_area=True): equal-area (Albers/LAEA)
- overlay, clip, simplify: conformal (LCC/UTM/Stereographic)
- buffer, sjoin_nearest: UTM when local, otherwise equal-area or equidistant where appropriate

## API additions
- `auto_optimize_crs=True` (default behavior stays backward-compatible if False)
- `projection_priority` optional override
- `override_crs` to force a specific CRS
- `projection_metadata` to include metadata about the chosen CRS in responses

## Testing
- Unit tests for CRS selection rules and validation
- Integration tests for operation accuracy and metadata
- Edge cases: antimeridian crossing, polar regions, global extents

## Deployment & Rollout
- Feature gated by `auto_optimize_crs` flag
- Logging of selection reasoning for audits
- Fallback chain: optimal → regional → EPSG:3857

## Notes
- The design prefers reproducibility and auditability over ML-based selection.
- Future work: dynamic PROJ strings, caching, and user preferences.
