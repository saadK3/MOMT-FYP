"""
Investigate the actual projection used in det_birdeye coordinates

Since standard UTM doesn't match, let's try:
1. Web Mercator (EPSG:3857) - common for web maps
2. Custom local projection
3. Check if there's a simple offset from UTM
"""

import json
import math

# Camera GPS coordinates
CAMERA_GPS = {
    'c001': {'lat': 42.5254829, 'lon': -90.7233451},
    'c002': {'lat': 42.5258119, 'lon': -90.7238137},
    'c003': {'lat': 42.5257186, 'lon': -90.7232303},
    'c004': {'lat': 42.5255629, 'lon': -90.7239331},
    'c005': {'lat': 42.5258378, 'lon': -90.7235177}
}


def web_mercator(lat, lon):
    """Convert lat/lon to Web Mercator (EPSG:3857)"""
    # Earth radius
    R = 6378137.0

    # Convert to radians
    lat_rad = math.radians(lat)
    lon_rad = math.radians(lon)

    # Web Mercator formulas
    x = R * lon_rad
    y = R * math.log(math.tan(math.pi/4 + lat_rad/2))

    return x, y


def analyze_coordinate_system():
    """Analyze what coordinate system is actually used"""

    print("="*70)
    print("COORDINATE SYSTEM INVESTIGATION")
    print("="*70)

    # Load sample data from one camera
    with open('data/S01_c001_tracks_data.json', 'r') as f:
        data = json.load(f)

    # Get first detection
    first_det = data['tracks'][0]['dets'][0]
    birdeye = first_det['det_birdeye']

    print(f"\nSample det_birdeye values:")
    print(f"  Point 1: ({birdeye[0]:.2f}, {birdeye[1]:.2f})")
    print(f"  Point 2: ({birdeye[2]:.2f}, {birdeye[3]:.2f})")
    print(f"  Point 3: ({birdeye[4]:.2f}, {birdeye[5]:.2f})")
    print(f"  Point 4: ({birdeye[6]:.2f}, {birdeye[7]:.2f})")

    # Calculate center
    center_x = (birdeye[0] + birdeye[2] + birdeye[4] + birdeye[6]) / 4
    center_y = (birdeye[1] + birdeye[3] + birdeye[5] + birdeye[7]) / 4

    print(f"\nCenter: ({center_x:.2f}, {center_y:.2f})")

    print(f"\n{'='*70}")
    print("Testing Web Mercator (EPSG:3857)")
    print(f"{'='*70}\n")

    for camera_id, gps in CAMERA_GPS.items():
        merc_x, merc_y = web_mercator(gps['lat'], gps['lon'])
        print(f"{camera_id}:")
        print(f"  GPS: {gps['lat']:.7f}°N, {gps['lon']:.7f}°W")
        print(f"  Web Mercator: ({merc_x:.2f}, {merc_y:.2f})")

    print(f"\n{'='*70}")
    print("PATTERN ANALYSIS")
    print(f"{'='*70}\n")

    # Check if there's a simple offset pattern
    print("Checking for offset patterns...")

    # Try camera c001
    gps = CAMERA_GPS['c001']
    merc_x, merc_y = web_mercator(gps['lat'], gps['lon'])

    offset_x = center_x - merc_x
    offset_y = center_y - merc_y

    print(f"\nIf det_birdeye = Web Mercator + offset:")
    print(f"  Offset X: {offset_x:.2f}")
    print(f"  Offset Y: {offset_y:.2f}")

    # Check the magnitude of coordinates
    print(f"\n{'='*70}")
    print("COORDINATE MAGNITUDE ANALYSIS")
    print(f"{'='*70}\n")

    print(f"det_birdeye X range: ~4,252,xxx (millions)")
    print(f"det_birdeye Y range: ~-9,072,xxx (negative millions)")
    print(f"\nThis suggests:")
    print(f"  - NOT standard UTM (would be 100,000s)")
    print(f"  - NOT Web Mercator (would be -10M to +10M for X, similar for Y)")
    print(f"  - Possibly a CUSTOM projection or transformed coordinates")

    print(f"\n{'='*70}")
    print("RECOMMENDATION")
    print(f"{'='*70}\n")

    print("The det_birdeye coordinates appear to use a CUSTOM coordinate system.")
    print("\nPossible sources:")
    print("  1. Custom homography matrix specific to this dataset")
    print("  2. Local coordinate system with arbitrary origin")
    print("  3. Transformed from a specific projection we haven't tested")
    print("\nNEXT STEPS:")
    print("  Option A: Find the original homography matrix or projection info")
    print("  Option B: Use RELATIVE coordinates (treat as arbitrary grid)")
    print("  Option C: Manually align image using visual reference points")
    print("\nFor Option B (RECOMMENDED):")
    print("  - Treat det_birdeye as arbitrary X,Y grid")
    print("  - Manually capture satellite image")
    print("  - Align using 2-3 visual reference points")
    print("  - Calculate simple affine transform (rotation + scale + offset)")
    print("="*70)


if __name__ == '__main__':
    analyze_coordinate_system()
