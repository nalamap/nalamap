#!/usr/bin/env python3
"""
Generate test GeoJSON files of various sizes for performance testing.
"""
import json
import os
from pathlib import Path
from typing import Dict, List


def generate_point(lon: float, lat: float) -> Dict:
    """Generate a GeoJSON point feature."""
    return {
        "type": "Feature",
        "properties": {"id": f"point_{lon}_{lat}"},
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
    }


def generate_polygon_ring(
    center_lon: float, center_lat: float, radius: float, points: int
) -> List[List[float]]:
    """Generate a polygon ring with specified number of points."""
    import math

    ring = []
    for i in range(points):
        angle = (2 * math.pi * i) / points
        lon = center_lon + radius * math.cos(angle)
        lat = center_lat + radius * math.sin(angle)
        ring.append([lon, lat])
    # Close the ring
    ring.append(ring[0])
    return ring


def generate_polygon(
    center_lon: float, center_lat: float, radius: float, points: int
) -> Dict:
    """Generate a GeoJSON polygon feature."""
    return {
        "type": "Feature",
        "properties": {"id": f"polygon_{center_lon}_{center_lat}"},
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                generate_polygon_ring(center_lon, center_lat, radius, points)
            ],
        },
    }


def generate_multipolygon(num_polygons: int, points_per_polygon: int) -> Dict:
    """Generate a GeoJSON multipolygon feature with many polygons."""
    polygons = []
    for i in range(num_polygons):
        lon = -180 + (360 * i / num_polygons)
        lat = -80 + (160 * i / num_polygons) % 160 - 80
        polygons.append(
            [generate_polygon_ring(lon, lat, 0.1, points_per_polygon)]
        )

    return {
        "type": "Feature",
        "properties": {"id": f"multipolygon_{num_polygons}_polygons"},
        "geometry": {"type": "MultiPolygon", "coordinates": polygons},
    }


def create_feature_collection(features: List[Dict]) -> Dict:
    """Create a GeoJSON FeatureCollection."""
    return {"type": "FeatureCollection", "features": features}


def save_geojson(data: Dict, filepath: Path):
    """Save GeoJSON data to file."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w") as f:
        json.dump(data, f, separators=(",", ":"))

    size = os.path.getsize(filepath)
    size_kb = size / 1024
    size_mb = size / (1024 * 1024)
    if size_mb >= 1:
        print(f"Generated {filepath.name}: {size_mb:.2f} MB")
    else:
        print(f"Generated {filepath.name}: {size_kb:.2f} KB")


def main():
    """Generate test files of various sizes."""
    test_data_dir = Path(__file__).parent.parent / "test_data"

    print("Generating test GeoJSON files...\n")

    # 1KB - Single point (minimal)
    single_point = create_feature_collection([generate_point(-122.4, 37.8)])
    save_geojson(single_point, test_data_dir / "001_single_point_1kb.geojson")

    # ~10KB - Small point cloud (100 points)
    points_10kb = [
        generate_point(-122.4 + i * 0.01, 37.8 + j * 0.01)
        for i in range(10)
        for j in range(10)
    ]
    save_geojson(
        create_feature_collection(points_10kb),
        test_data_dir / "002_points_100_10kb.geojson",
    )

    # ~50KB - Medium point cloud (500 points)
    points_50kb = [
        generate_point(-122.4 + i * 0.01, 37.8 + j * 0.01)
        for i in range(25)
        for j in range(20)
    ]
    save_geojson(
        create_feature_collection(points_50kb),
        test_data_dir / "003_points_500_50kb.geojson",
    )

    # ~100KB - Large point cloud (1000 points)
    points_100kb = [
        generate_point(-122.4 + i * 0.01, 37.8 + j * 0.01)
        for i in range(50)
        for j in range(20)
    ]
    save_geojson(
        create_feature_collection(points_100kb),
        test_data_dir / "004_points_1000_100kb.geojson",
    )

    # ~500KB - Simple polygons (50 polygons with 100 points each)
    polygons_500kb = [
        generate_polygon(-122.4 + i * 0.1, 37.8 + j * 0.1, 0.05, 100)
        for i in range(10)
        for j in range(5)
    ]
    save_geojson(
        create_feature_collection(polygons_500kb),
        test_data_dir / "005_polygons_50_500kb.geojson",
    )

    # ~1MB - Complex polygons (100 polygons with 200 points each)
    polygons_1mb = [
        generate_polygon(-122.4 + i * 0.1, 37.8 + j * 0.1, 0.05, 200)
        for i in range(10)
        for j in range(10)
    ]
    save_geojson(
        create_feature_collection(polygons_1mb),
        test_data_dir / "006_polygons_100_1mb.geojson",
    )

    # ~5MB - Very complex polygons (500 polygons with 200 points each)
    polygons_5mb = [
        generate_polygon(-122.4 + i * 0.05, 37.8 + j * 0.05, 0.02, 200)
        for i in range(25)
        for j in range(20)
    ]
    save_geojson(
        create_feature_collection(polygons_5mb),
        test_data_dir / "007_polygons_500_5mb.geojson",
    )

    # ~10MB - Highly complex polygons (1000 polygons with 200 points each)
    polygons_10mb = [
        generate_polygon(-122.4 + i * 0.05, 37.8 + j * 0.05, 0.02, 200)
        for i in range(50)
        for j in range(20)
    ]
    save_geojson(
        create_feature_collection(polygons_10mb),
        test_data_dir / "008_polygons_1000_10mb.geojson",
    )

    # ~25MB - Extremely complex MultiPolygon
    multipolygon_25mb = create_feature_collection(
        [generate_multipolygon(2500, 200)]
    )
    save_geojson(
        multipolygon_25mb, test_data_dir / "009_multipolygon_2500_25mb.geojson"
    )

    # ~50MB - Massive MultiPolygon
    multipolygon_50mb = create_feature_collection(
        [generate_multipolygon(5000, 200)]
    )
    save_geojson(
        multipolygon_50mb, test_data_dir / "010_multipolygon_5000_50mb.geojson"
    )

    print("\n✓ Test file generation complete!")
    print(f"Files saved to: {test_data_dir}")


if __name__ == "__main__":
    main()
