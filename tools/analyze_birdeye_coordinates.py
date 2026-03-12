"""
Analyze det_birdeye coordinates to understand what they represent
and identify potential reference points for GPS alignment
"""

import json
import numpy as np
import matplotlib.pyplot as plt
from collections import defaultdict

def load_camera_data(camera_id):
    """Load JSON data for a camera"""
    with open(f'data/S01_{camera_id}_tracks_data.json', 'r') as f:
        return json.load(f)


def analyze_birdeye_structure():
    """Understand what det_birdeye coordinates represent"""

    print("="*70)
    print("UNDERSTANDING det_birdeye COORDINATES")
    print("="*70)

    # Load one camera's data
    data = load_camera_data('c001')

    # Get first detection
    first_track = data['tracks'][0]
    first_det = first_track['dets'][0]

    print(f"\nSample Detection:")
    print(f"  Camera: c001")
    print(f"  Track ID: {first_track['id']}")
    print(f"  Timestamp: {first_det['det_timestamp']}s")
    print(f"  Vehicle Class: {first_det['det_kp_class_name']}")

    # Analyze birdeye
    birdeye = first_det['det_birdeye']
    print(f"\ndet_birdeye structure (8 values = 4 points):")
    print(f"  Point 1: ({birdeye[0]:.2f}, {birdeye[1]:.2f})")
    print(f"  Point 2: ({birdeye[2]:.2f}, {birdeye[3]:.2f})")
    print(f"  Point 3: ({birdeye[4]:.2f}, {birdeye[5]:.2f})")
    print(f"  Point 4: ({birdeye[6]:.2f}, {birdeye[7]:.2f})")

    # Calculate footprint properties
    points = np.array([
        [birdeye[0], birdeye[1]],
        [birdeye[2], birdeye[3]],
        [birdeye[4], birdeye[5]],
        [birdeye[6], birdeye[7]]
    ])

    center = points.mean(axis=0)

    # Calculate distances between points
    d12 = np.linalg.norm(points[0] - points[1])
    d23 = np.linalg.norm(points[1] - points[2])
    d34 = np.linalg.norm(points[2] - points[3])
    d41 = np.linalg.norm(points[3] - points[0])

    print(f"\nFootprint Properties:")
    print(f"  Center: ({center[0]:.2f}, {center[1]:.2f})")
    print(f"  Side 1-2: {d12:.2f}m")
    print(f"  Side 2-3: {d23:.2f}m")
    print(f"  Side 3-4: {d34:.2f}m")
    print(f"  Side 4-1: {d41:.2f}m")
    print(f"\nInterpretation:")
    print(f"  → These are the 4 GROUND CONTACT POINTS of the vehicle")
    print(f"  → Projected onto a bird's-eye view plane")
    print(f"  → In a custom coordinate system (meters)")
    print(f"  → Represents the vehicle's footprint on the ground")


def find_trajectory_patterns():
    """Analyze trajectory patterns to find potential reference points"""

    print(f"\n{'='*70}")
    print("FINDING REFERENCE POINTS FROM TRAJECTORIES")
    print(f"{'='*70}\n")

    # Collect all trajectory centers from all cameras
    all_centers = []

    for camera_id in ['c001', 'c002', 'c003', 'c004', 'c005']:
        data = load_camera_data(camera_id)

        for track in data['tracks'][:10]:  # First 10 tracks per camera
            for det in track['dets']:
                birdeye = det['det_birdeye']
                center_x = (birdeye[0] + birdeye[2] + birdeye[4] + birdeye[6]) / 4
                center_y = (birdeye[1] + birdeye[3] + birdeye[5] + birdeye[7]) / 4

                all_centers.append({
                    'x': center_x,
                    'y': center_y,
                    'camera': camera_id,
                    'timestamp': det['det_timestamp']
                })

    print(f"Collected {len(all_centers)} vehicle positions\n")

    # Find coordinate bounds
    x_coords = [c['x'] for c in all_centers]
    y_coords = [c['y'] for c in all_centers]

    x_min, x_max = min(x_coords), max(x_coords)
    y_min, y_max = min(y_coords), max(y_coords)

    print(f"Coordinate Bounds:")
    print(f"  X: {x_min:.2f} to {x_max:.2f} (range: {x_max-x_min:.2f}m)")
    print(f"  Y: {y_min:.2f} to {y_max:.2f} (range: {y_max-y_min:.2f}m)")

    # Find potential reference points
    print(f"\n{'='*70}")
    print("POTENTIAL REFERENCE POINTS")
    print(f"{'='*70}\n")

    print("Strategy: Use trajectory patterns to identify landmarks")
    print("\n1. INTERSECTION CENTER (where most trajectories converge)")
    print(f"   Ground Plane: ({(x_min+x_max)/2:.2f}, {(y_min+y_max)/2:.2f})")
    print(f"   → Find the main intersection in satellite image")

    print("\n2. CORNER POINTS (extreme positions)")
    print(f"   Northwest: ({x_min:.2f}, {y_max:.2f})")
    print(f"   Northeast: ({x_max:.2f}, {y_max:.2f})")
    print(f"   Southwest: ({x_min:.2f}, {y_min:.2f})")
    print(f"   Southeast: ({x_max:.2f}, {y_min:.2f})")
    print(f"   → These mark the extent of vehicle movement")

    print("\n3. TRAJECTORY CLUSTERS (road lanes)")
    print(f"   → Analyze where vehicles cluster")
    print(f"   → These follow road centerlines")

    return all_centers


def visualize_ground_plane(centers):
    """Create visualization of ground plane to identify patterns"""

    print(f"\n{'='*70}")
    print("CREATING GROUND PLANE VISUALIZATION")
    print(f"{'='*70}\n")

    x_coords = [c['x'] for c in centers]
    y_coords = [c['y'] for c in centers]

    plt.figure(figsize=(12, 10))
    plt.scatter(x_coords, y_coords, alpha=0.3, s=10, c='blue')
    plt.xlabel('X (meters)')
    plt.ylabel('Y (meters)')
    plt.title('Ground Plane - All Vehicle Positions\n(Patterns reveal road structure)')
    plt.grid(True, alpha=0.3)
    plt.axis('equal')

    # Mark potential reference points
    x_min, x_max = min(x_coords), max(x_coords)
    y_min, y_max = min(y_coords), max(y_coords)

    # Center
    plt.plot((x_min+x_max)/2, (y_min+y_max)/2, 'r*', markersize=20,
             label='Center (Intersection?)')

    # Corners
    corners = [
        (x_min, y_max, 'NW'),
        (x_max, y_max, 'NE'),
        (x_min, y_min, 'SW'),
        (x_max, y_min, 'SE')
    ]

    for x, y, label in corners:
        plt.plot(x, y, 'go', markersize=15)
        plt.text(x, y, f'  {label}', fontsize=10, ha='left')

    plt.legend()
    plt.tight_layout()
    plt.savefig('tools/ground_plane_visualization.png', dpi=150)
    print(f"✓ Saved visualization to: tools/ground_plane_visualization.png")
    print(f"\nThis image shows:")
    print(f"  - Blue dots = vehicle positions")
    print(f"  - Patterns = roads and lanes")
    print(f"  - Red star = potential intersection center")
    print(f"  - Green dots = extent boundaries")


def main():
    analyze_birdeye_structure()
    centers = find_trajectory_patterns()
    visualize_ground_plane(centers)

    print(f"\n{'='*70}")
    print("CONCLUSION")
    print(f"{'='*70}\n")

    print("det_birdeye represents:")
    print("  ✓ 4 ground contact points of each vehicle")
    print("  ✓ In bird's-eye view (top-down projection)")
    print("  ✓ Custom coordinate system (meters)")
    print("  ✓ Already transformed from camera images")

    print("\nReference points CAN be extracted from:")
    print("  ✓ Trajectory patterns (vehicles follow roads)")
    print("  ✓ Intersection points (where paths cross)")
    print("  ✓ Turning points (sharp direction changes)")
    print("  ✓ Boundary extents (edges of movement area)")

    print("\nNext step:")
    print("  1. View ground_plane_visualization.png")
    print("  2. Identify 3-4 clear patterns (intersections, turns)")
    print("  3. Match these to satellite image features")
    print("  4. Use as reference points for alignment")
    print("="*70)


if __name__ == '__main__':
    main()
