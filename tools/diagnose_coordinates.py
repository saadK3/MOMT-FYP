"""
Coordinate System Diagnostic Tool

Analyzes the ground plane coordinate system and provides information
to help understand the transformation needed for satellite image alignment.
"""

import json
import numpy as np
from pathlib import Path
from PIL import Image

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
BOUNDS_CONFIG_PATH = PROJECT_ROOT / 'visualization' / 'ground_plane_bounds.json'
SATELLITE_IMAGE_PATH = PROJECT_ROOT / 'assets' / 'GPS_intersection.jpg'
JSON_DIR = PROJECT_ROOT / 'json'


def analyze_coordinate_system():
    """Analyze the ground plane coordinate system"""

    print("=" * 70)
    print("COORDINATE SYSTEM DIAGNOSTIC")
    print("=" * 70)

    # Load bounds
    with open(BOUNDS_CONFIG_PATH, 'r') as f:
        bounds = json.load(f)

    cropped = bounds['cropped_bounds']

    print("\n📍 GROUND PLANE BOUNDS (Cropped Area)")
    print("-" * 70)
    print(f"X Range: {cropped['x_min']:.2f} to {cropped['x_max']:.2f}")
    print(f"Y Range: {cropped['y_min']:.2f} to {cropped['y_max']:.2f}")
    print(f"Width:   {cropped['width']:.2f} meters")
    print(f"Height:  {cropped['height']:.2f} meters")
    print(f"Center:  X={((cropped['x_min'] + cropped['x_max'])/2):.2f}, "
          f"Y={((cropped['y_min'] + cropped['y_max'])/2):.2f}")

    # Analyze coordinate system type
    print("\n🔍 COORDINATE SYSTEM ANALYSIS")
    print("-" * 70)

    x_magnitude = abs(cropped['x_min'])
    y_magnitude = abs(cropped['y_min'])

    if x_magnitude > 1000000 and y_magnitude > 1000000:
        print("✓ Detected: PROJECTED COORDINATE SYSTEM")
        print("  Likely EPSG:3857 (Web Mercator) or similar")
        print("  These are NOT simple meters from origin!")
        print("  These are map projection coordinates")
    else:
        print("✓ Detected: LOCAL COORDINATE SYSTEM")
        print("  Coordinates appear to be in meters from a local origin")

    # Load satellite image
    if SATELLITE_IMAGE_PATH.exists():
        img = Image.open(SATELLITE_IMAGE_PATH)
        img_width, img_height = img.size

        print("\n🖼️  SATELLITE IMAGE")
        print("-" * 70)
        print(f"Dimensions: {img_width} × {img_height} pixels")
        print(f"Aspect Ratio: {img_width/img_height:.3f}")

        # Compare aspect ratios
        ground_aspect = cropped['width'] / cropped['height']
        image_aspect = img_width / img_height

        print(f"\nGround Plane Aspect Ratio: {ground_aspect:.3f}")
        print(f"Image Aspect Ratio:        {image_aspect:.3f}")

        if abs(ground_aspect - image_aspect) > 0.1:
            print("\n⚠️  WARNING: Aspect ratios don't match!")
            print("   The satellite image may not cover the exact same area")
            print("   as the ground plane bounds.")

    # Sample some trajectory points
    print("\n📊 SAMPLE TRAJECTORY POINTS")
    print("-" * 70)

    camera_ids = ['c001', 'c002', 'c003', 'c004', 'c005']
    sample_points = []

    for camera_id in camera_ids[:2]:  # Just check first 2 cameras
        json_path = JSON_DIR / f'S01_{camera_id}_tracks_data.json'
        if not json_path.exists():
            continue

        with open(json_path, 'r') as f:
            data = json.load(f)

        if data['tracks']:
            track = data['tracks'][0]
            if track['dets']:
                det = track['dets'][0]
                birdeye = det['det_birdeye']
                center_x = (birdeye[0] + birdeye[2] + birdeye[4] + birdeye[6]) / 4
                center_y = (birdeye[1] + birdeye[3] + birdeye[5] + birdeye[7]) / 4
                sample_points.append((center_x, center_y, camera_id))

    for x, y, cam in sample_points[:3]:
        print(f"  {cam}: ({x:.2f}, {y:.2f})")

    # Recommendations
    print("\n💡 RECOMMENDATIONS")
    print("-" * 70)
    print("To properly align the satellite image with trajectories:")
    print()
    print("1. USE THE REFERENCE POINT ALIGNMENT TOOL:")
    print("   python tools/reference_point_alignment.py")
    print()
    print("2. Click at least 4 matching points between:")
    print("   - Satellite image (left panel)")
    print("   - Trajectory map (right panel)")
    print()
    print("3. Good reference points to use:")
    print("   • Road intersection corners")
    print("   • Lane marking intersections")
    print("   • Building corners near roads")
    print("   • Crosswalk edges")
    print()
    print("4. The tool will compute the transformation matrix that handles:")
    print("   ✓ Scale differences")
    print("   ✓ Rotation")
    print("   ✓ Translation/offset")
    print("   ✓ Perspective distortion")
    print()
    print("=" * 70)


if __name__ == '__main__':
    analyze_coordinate_system()
