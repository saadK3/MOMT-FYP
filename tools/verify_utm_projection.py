"""
Verify UTM Projection for Ground Plane Coordinates

This script checks if the det_birdeye coordinates use standard UTM projection
by converting known camera GPS positions to UTM and comparing with nearby detections.
"""

import json
import math

# Camera GPS coordinates (from align_gps_to_ground_plane.py)
CAMERA_GPS = {
    'c001': {'lat': 42.5254829, 'lon': -90.7233451},
    'c002': {'lat': 42.5258119, 'lon': -90.7238137},
    'c003': {'lat': 42.5257186, 'lon': -90.7232303},
    'c004': {'lat': 42.5255629, 'lon': -90.7239331},
    'c005': {'lat': 42.5258378, 'lon': -90.7235177}
}


def latlon_to_utm(lat, lon, zone=15, northern=True):
    """
    Convert latitude/longitude to UTM coordinates

    Simplified conversion (accurate enough for verification)
    For production, use pyproj library

    Args:
        lat: Latitude in degrees
        lon: Longitude in degrees
        zone: UTM zone number (default 15 for Iowa)
        northern: True for Northern hemisphere

    Returns:
        (easting, northing) in meters
    """
    # Convert to radians
    lat_rad = math.radians(lat)
    lon_rad = math.radians(lon)

    # UTM zone central meridian
    lon0 = math.radians((zone - 1) * 6 - 180 + 3)

    # WGS84 ellipsoid parameters
    a = 6378137.0  # Semi-major axis
    e = 0.081819191  # Eccentricity
    e2 = e * e

    # Calculate N (radius of curvature)
    N = a / math.sqrt(1 - e2 * math.sin(lat_rad)**2)

    # Calculate T and C
    T = math.tan(lat_rad)**2
    C = (e2 / (1 - e2)) * math.cos(lat_rad)**2
    A = (lon_rad - lon0) * math.cos(lat_rad)

    # Calculate M (meridional arc)
    M = a * ((1 - e2/4 - 3*e2*e2/64 - 5*e2*e2*e2/256) * lat_rad
             - (3*e2/8 + 3*e2*e2/32 + 45*e2*e2*e2/1024) * math.sin(2*lat_rad)
             + (15*e2*e2/256 + 45*e2*e2*e2/1024) * math.sin(4*lat_rad)
             - (35*e2*e2*e2/3072) * math.sin(6*lat_rad))

    # UTM coordinates
    k0 = 0.9996  # Scale factor

    easting = k0 * N * (A + (1-T+C)*A**3/6 + (5-18*T+T**2+72*C-58*(e2/(1-e2)))*A**5/120) + 500000

    northing = k0 * (M + N*math.tan(lat_rad) * (A**2/2 + (5-T+9*C+4*C**2)*A**4/24
                     + (61-58*T+T**2+600*C-330*(e2/(1-e2)))*A**6/720))

    if not northern:
        northing += 10000000

    return easting, northing


def get_camera_detections(camera_id, max_detections=5):
    """Get first few detections from a camera"""
    json_path = f'data/S01_{camera_id}_tracks_data.json'

    with open(json_path, 'r') as f:
        data = json.load(f)

    detections = []
    for track in data['tracks'][:3]:  # First 3 tracks
        for det in track['dets'][:2]:  # First 2 detections per track
            birdeye = det['det_birdeye']
            # Calculate center of footprint
            center_x = (birdeye[0] + birdeye[2] + birdeye[4] + birdeye[6]) / 4
            center_y = (birdeye[1] + birdeye[3] + birdeye[5] + birdeye[7]) / 4

            detections.append({
                'timestamp': det['det_timestamp'],
                'x': center_x,
                'y': center_y,
                'track_id': track['id']
            })

            if len(detections) >= max_detections:
                break
        if len(detections) >= max_detections:
            break

    return detections


def main():
    print("="*70)
    print("UTM PROJECTION VERIFICATION")
    print("="*70)

    # Test multiple UTM zones
    zones_to_test = [15, 16]  # Iowa is on border of zones 15 and 16

    for zone in zones_to_test:
        print(f"\n{'='*70}")
        print(f"Testing UTM Zone {zone}N")
        print(f"{'='*70}\n")

        for camera_id, gps in CAMERA_GPS.items():
            # Convert camera GPS to UTM
            utm_x, utm_y = latlon_to_utm(gps['lat'], gps['lon'], zone=zone)

            print(f"\n{camera_id}:")
            print(f"  GPS: {gps['lat']:.7f}°N, {gps['lon']:.7f}°W")
            print(f"  UTM Zone {zone}N: ({utm_x:.2f}, {utm_y:.2f})")

            # Get some detections from this camera
            try:
                detections = get_camera_detections(camera_id, max_detections=3)

                if detections:
                    print(f"  Sample det_birdeye centers:")
                    for det in detections:
                        print(f"    Track {det['track_id']}: ({det['x']:.2f}, {det['y']:.2f})")

                        # Calculate distance from camera position to detection
                        dist = math.sqrt((utm_x - det['x'])**2 + (utm_y - det['y'])**2)
                        print(f"      Distance from camera: {dist:.2f}m")

            except Exception as e:
                print(f"  Error loading detections: {e}")

    print(f"\n{'='*70}")
    print("ANALYSIS")
    print(f"{'='*70}\n")
    print("Expected behavior:")
    print("  - If UTM zone is CORRECT:")
    print("    → Camera-to-detection distance should be 10-100m (reasonable)")
    print("    → UTM coordinates should be in similar range as det_birdeye")
    print("  - If UTM zone is WRONG:")
    print("    → Distance will be hundreds of kilometers")
    print("    → Coordinates will be completely different")
    print("\nNext steps:")
    print("  1. Check which zone gives reasonable distances")
    print("  2. If neither works, det_birdeye may use custom projection")
    print("  3. If one works, we can proceed with GPS alignment!")
    print("="*70)


if __name__ == '__main__':
    main()
