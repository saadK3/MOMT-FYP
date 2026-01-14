"""
Analyze ground plane coordinate system for GPS alignment
"""
import json
import numpy as np

# Load trajectory data
with open('visualization/trajectory_data_optimized.json', 'r') as f:
    data = json.load(f)

trajectories = data['trajectories']

# Extract all footprint coordinates
all_x = []
all_y = []

for traj_id, traj in trajectories.items():
    for det in traj['detections']:
        fp = det['footprint']
        # Footprint has 8 values: [x1, y1, x2, y2, x3, y3, x4, y4]
        all_x.extend([fp[0], fp[2], fp[4], fp[6]])
        all_y.extend([fp[1], fp[3], fp[5], fp[7]])

# Calculate statistics
min_x, max_x = min(all_x), max(all_x)
min_y, max_y = min(all_y), max(all_y)
center_x = np.mean(all_x)
center_y = np.mean(all_y)
width = max_x - min_x
height = max_y - min_y

print("="*70)
print("GROUND PLANE COORDINATE ANALYSIS")
print("="*70)
print(f"\nCoordinate Bounds:")
print(f"  X: {min_x:.2f} to {max_x:.2f} meters")
print(f"  Y: {min_y:.2f} to {max_y:.2f} meters")
print(f"\nDimensions:")
print(f"  Width:  {width:.2f} meters")
print(f"  Height: {height:.2f} meters")
print(f"\nCenter Point:")
print(f"  X: {center_x:.2f} meters")
print(f"  Y: {center_y:.2f} meters")
print(f"\nTotal Points Analyzed: {len(all_x):,}")

# Sample coordinates
print(f"\nSample Footprint (first detection):")
first_traj = list(trajectories.values())[0]
first_det = first_traj['detections'][0]
fp = first_det['footprint']
print(f"  Camera: {first_det['camera']}")
print(f"  Point 1: ({fp[0]:.2f}, {fp[1]:.2f})")
print(f"  Point 2: ({fp[2]:.2f}, {fp[3]:.2f})")
print(f"  Point 3: ({fp[4]:.2f}, {fp[5]:.2f})")
print(f"  Point 4: ({fp[6]:.2f}, {fp[7]:.2f})")

# Check coordinate system type
print(f"\nCoordinate System Analysis:")
if abs(min_x) > 1000 or abs(min_y) > 1000:
    print(f"  ✓ Projected coordinate system detected (large values)")
    print(f"  ✓ Likely UTM or similar projection")
    print(f"  ✓ Units are in meters")
else:
    print(f"  ✓ Local coordinate system (small values)")
    print(f"  ✓ Origin-based system")

# Camera GPS coordinates (from config)
camera_gps = {
    'c001': {'lat': 42.5254829, 'lon': -90.7233451},
    'c002': {'lat': 42.5258119, 'lon': -90.7238137},
    'c003': {'lat': 42.5257186, 'lon': -90.7232303},
    'c004': {'lat': 42.5255629, 'lon': -90.7239331},
    'c005': {'lat': 42.5258378, 'lon': -90.7235177}
}

# Calculate approximate center GPS
avg_lat = np.mean([c['lat'] for c in camera_gps.values()])
avg_lon = np.mean([c['lon'] for c in camera_gps.values()])

print(f"\nCamera GPS Center (approximate):")
print(f"  Latitude:  {avg_lat:.7f}")
print(f"  Longitude: {avg_lon:.7f}")

print(f"\n" + "="*70)
print("NEXT STEPS FOR GPS ALIGNMENT:")
print("="*70)
print(f"1. Go to Google Earth and navigate to: {avg_lat:.7f}, {avg_lon:.7f}")
print(f"2. Zoom to show an area approximately {width*1.2:.0f}m x {height*1.2:.0f}m")
print(f"3. Switch to top-down view (View → Reset → Tilt)")
print(f"4. Mark 4 corners of the area and note GPS coordinates")
print(f"5. Save high-resolution image (File → Save → Save Image)")
print("="*70)
