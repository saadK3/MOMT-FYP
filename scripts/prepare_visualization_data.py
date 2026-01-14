"""
Enhanced data preparation with smooth trajectory reconstruction
- Removes temporal overlaps
- Applies spatial smoothing
- Filters bad matches
"""

import json
import os
import sys
import numpy as np
from scipy.ndimage import uniform_filter1d

# Add parent directory to path to import cross_camera_tracking
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cross_camera_tracking.config import CAMERA_TIME_OFFSETS

# Paths
JSON_DIR = 'json'
OUTPUT_FILE = 'visualization/trajectory_data_optimized.json'
GLOBAL_MAPPING_FILE = 'output/global_id_mapping.json'

# Camera colors
CAMERA_COLORS = {
    'c001': '#FF6B6B',
    'c002': '#4ECDC4',
    'c003': '#45B7D1',
    'c004': '#FFA07A',
    'c005': '#98D8C8'
}

# Smoothing parameters
TEMPORAL_TOLERANCE = 0.3  # Detections within 0.3s are considered overlapping
MAX_SPEED = 30.0  # Maximum reasonable speed in m/s (108 km/h)
SMOOTHING_WINDOW = 5  # Moving average window size


def load_camera_json(camera_id):
    """Load JSON data for a camera"""
    json_path = os.path.join(JSON_DIR, f'S01_{camera_id}_tracks_data.json')
    with open(json_path, 'r') as f:
        return json.load(f)


def get_footprint_center(footprint):
    """Get center point of footprint"""
    x_coords = [footprint[i] for i in range(0, 8, 2)]
    y_coords = [footprint[i] for i in range(1, 8, 2)]
    return np.mean(x_coords), np.mean(y_coords)


def remove_temporal_overlaps(detections):
    """
    Remove temporal overlaps by keeping only one detection per time window
    When multiple detections exist within TEMPORAL_TOLERANCE, keep the middle one
    """
    if len(detections) <= 1:
        return detections

    filtered = []
    i = 0

    while i < len(detections):
        # Find all detections within temporal tolerance
        group = [detections[i]]
        j = i + 1

        while j < len(detections) and (detections[j]['timestamp'] - detections[i]['timestamp']) < TEMPORAL_TOLERANCE:
            group.append(detections[j])
            j += 1

        # Keep the middle detection from the group
        middle_idx = len(group) // 2
        filtered.append(group[middle_idx])

        i = j

    return filtered


def smooth_trajectory(detections, window_size=SMOOTHING_WINDOW):
    """
    Apply moving average smoothing to trajectory
    """
    if len(detections) < window_size:
        return detections

    # Extract positions
    positions = []
    for det in detections:
        x, y = get_footprint_center(det['footprint'])
        positions.append([x, y])

    positions = np.array(positions)

    # Apply moving average
    smoothed_x = uniform_filter1d(positions[:, 0], size=window_size, mode='nearest')
    smoothed_y = uniform_filter1d(positions[:, 1], size=window_size, mode='nearest')

    # Update footprints with smoothed centers
    smoothed_detections = []
    for i, det in enumerate(detections):
        # Calculate offset from original center
        orig_x, orig_y = get_footprint_center(det['footprint'])
        dx = smoothed_x[i] - orig_x
        dy = smoothed_y[i] - orig_y

        # Apply offset to all footprint points
        smoothed_footprint = []
        for j in range(0, 8, 2):
            smoothed_footprint.append(det['footprint'][j] + dx)
            smoothed_footprint.append(det['footprint'][j + 1] + dy)

        smoothed_det = det.copy()
        smoothed_det['footprint'] = smoothed_footprint
        smoothed_detections.append(smoothed_det)

    return smoothed_detections


def filter_bad_trajectories(detections):
    """
    Filter out trajectories with impossible speeds
    Returns True if trajectory is valid, False if it's a bad match
    """
    if len(detections) < 2:
        return True

    for i in range(len(detections) - 1):
        det1 = detections[i]
        det2 = detections[i + 1]

        x1, y1 = get_footprint_center(det1['footprint'])
        x2, y2 = get_footprint_center(det2['footprint'])

        distance = np.sqrt((x2 - x1)**2 + (y2 - y1)**2)
        time_diff = det2['timestamp'] - det1['timestamp']

        if time_diff > 0:
            speed = distance / time_diff

            if speed > MAX_SPEED:
                return False  # Impossible speed - bad match

    return True


def prepare_optimized_data():
    """Prepare optimized data with smooth trajectory reconstruction"""

    print("Loading data...")

    with open(GLOBAL_MAPPING_FILE, 'r') as f:
        global_mapping = json.load(f)

    all_camera_data = {}
    for camera in CAMERA_TIME_OFFSETS.keys():
        all_camera_data[camera] = load_camera_json(camera)

    print(f"Loaded {len(global_mapping)} global IDs")

    # Build trajectory data
    trajectories = {}
    all_timestamps = set()
    bad_matches = []

    for global_id, camera_tracks in global_mapping.items():
        trajectory = {
            'global_id': int(global_id),
            'cameras': list(camera_tracks.keys()),
            'detections': []
        }

        # Collect all detections
        for camera, info in camera_tracks.items():
            track_id = info['track_id']
            offset = CAMERA_TIME_OFFSETS[camera]

            camera_data = all_camera_data[camera]
            for track in camera_data['tracks']:
                if track['id'] == track_id:
                    for det in track['dets']:
                        synced_time = det['det_timestamp'] + offset
                        all_timestamps.add(round(synced_time, 1))

                        detection = {
                            'camera': camera,
                            'track_id': track_id,
                            'timestamp': synced_time,
                            'footprint': det['det_birdeye'],
                            'frame_number': int(det['det_impath']),
                            'class': det['det_kp_class_name'],
                            'color': CAMERA_COLORS[camera],
                            'keypoints': det['det_keypoints']
                        }
                        trajectory['detections'].append(detection)
                    break

        # Sort by timestamp
        trajectory['detections'].sort(key=lambda x: x['timestamp'])

        # STEP 1: Remove temporal overlaps
        trajectory['detections'] = remove_temporal_overlaps(trajectory['detections'])

        # STEP 2: Check if trajectory is valid (no impossible speeds)
        if not filter_bad_trajectories(trajectory['detections']):
            bad_matches.append(global_id)
            print(f"  ⚠️  Global ID {global_id}: Bad match detected (impossible speed)")
            continue

        # STEP 3: Apply smoothing
        if len(trajectory['detections']) >= SMOOTHING_WINDOW:
            trajectory['detections'] = smooth_trajectory(trajectory['detections'])

        trajectories[global_id] = trajectory

    print(f"\n✓ Processed {len(trajectories)} valid trajectories")
    if bad_matches:
        print(f"✗ Filtered out {len(bad_matches)} bad matches: {bad_matches[:10]}...")

    # Pre-compute frames for smooth animation
    print("\nPre-computing animation frames...")
    sorted_times = sorted(all_timestamps)
    time_min = min(sorted_times)
    time_max = max(sorted_times)

    # Create frame index (every 0.1s)
    frame_times = np.arange(time_min, time_max + 0.1, 0.1)
    frames = {}

    tolerance = 0.15
    for frame_time in frame_times:
        frame_time = round(frame_time, 1)
        frame_vehicles = []

        for global_id, trajectory in trajectories.items():
            # Find detection closest to this time
            closest_det = None
            min_diff = float('inf')

            for det in trajectory['detections']:
                diff = abs(det['timestamp'] - frame_time)
                if diff < tolerance and diff < min_diff:
                    min_diff = diff
                    closest_det = det

            if closest_det:
                frame_vehicles.append({
                    'global_id': int(global_id),
                    'footprint': closest_det['footprint'],
                    'color': closest_det['color'],
                    'camera': closest_det['camera'],
                    'track_id': closest_det['track_id'],
                    'class': closest_det['class'],
                    'frame_number': closest_det['frame_number'],
                    'keypoints': closest_det.get('keypoints', [])
                })

        if frame_vehicles:
            frames[str(frame_time)] = frame_vehicles

    # Calculate statistics
    stats = {
        'total_vehicles': len(trajectories),
        'total_frames': len(frames),
        'total_detections': sum(len(t['detections']) for t in trajectories.values()),
        'bad_matches_filtered': len(bad_matches),
        'cameras': list(CAMERA_TIME_OFFSETS.keys()),
        'vehicle_classes': list(set(
            det['class']
            for traj in trajectories.values()
            for det in traj['detections']
        ))
    }

    output_data = {
        'trajectories': trajectories,
        'frames': frames,
        'time_range': {
            'min': float(time_min),
            'max': float(time_max),
            'step': 0.1
        },
        'camera_colors': CAMERA_COLORS,
        'statistics': stats
    }

    os.makedirs('visualization', exist_ok=True)
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(output_data, f, indent=2)

    print(f"\n✓ Created optimized visualization data: {OUTPUT_FILE}")
    print(f"  Valid vehicles: {stats['total_vehicles']}")
    print(f"  Bad matches filtered: {stats['bad_matches_filtered']}")
    print(f"  Total frames: {stats['total_frames']}")
    print(f"  Time range: {time_min:.1f}s - {time_max:.1f}s")
    print(f"  Total detections: {stats['total_detections']}")
    print(f"  Vehicle classes: {', '.join(stats['vehicle_classes'])}")


if __name__ == "__main__":
    prepare_optimized_data()
