"""
Data loading utilities for camera tracking data
Handles JSON file loading and timestamp-based detection extraction with camera synchronization
"""

import json
import os
from .config import JSON_DIR, JSON_PATTERN, CAMERAS, CAMERA_TIME_OFFSETS, TIMESTAMP_TOLERANCE


def load_camera_data(camera_id):
    """
    Load tracking data for one camera

    Args:
        camera_id: Camera identifier (e.g., 'c001')

    Returns:
        dict: Parsed JSON data with tracks
    """
    json_filename = JSON_PATTERN.format(camera=camera_id)
    json_path = os.path.join(JSON_DIR, json_filename)

    if not os.path.exists(json_path):
        raise FileNotFoundError(f"JSON file not found: {json_path}")

    with open(json_path, 'r') as f:
        data = json.load(f)

    return data


def load_all_cameras():
    """
    Load tracking data for all cameras

    Returns:
        dict: Dictionary mapping camera_id -> camera_data
    """
    all_data = {}

    for camera_id in CAMERAS:
        print(f"Loading {camera_id}...")
        all_data[camera_id] = load_camera_data(camera_id)

    print(f"✓ Loaded {len(all_data)} cameras")
    return all_data


def get_synchronized_timestamp(camera_id, original_timestamp):
    """
    Convert camera-specific timestamp to synchronized global timestamp

    Args:
        camera_id: Camera identifier
        original_timestamp: Original timestamp from JSON

    Returns:
        float: Synchronized timestamp
    """
    offset = CAMERA_TIME_OFFSETS.get(camera_id, 0.0)
    return original_timestamp + offset


def get_detections_at_timestamp(camera_data, camera_id, target_timestamp, tolerance=None):
    """
    Extract all detections at a specific synchronized timestamp from one camera

    Args:
        camera_data: Parsed JSON data for one camera
        camera_id: Camera identifier
        target_timestamp: Target synchronized timestamp
        tolerance: Time tolerance in seconds (default: from config)

    Returns:
        list: List of detection dictionaries
    """
    if tolerance is None:
        tolerance = TIMESTAMP_TOLERANCE

    detections = []

    for track in camera_data['tracks']:
        for det in track['dets']:
            # Get synchronized timestamp
            synced_timestamp = get_synchronized_timestamp(camera_id, det['det_timestamp'])

            # Check if within tolerance
            if abs(synced_timestamp - target_timestamp) < tolerance:
                detections.append({
                    'camera': camera_id,
                    'track_id': track['id'],
                    'footprint': det['det_birdeye'],
                    'class': det['det_kp_class_name'],
                    'timestamp': synced_timestamp,  # Store synchronized timestamp
                    'original_timestamp': det['det_timestamp'],
                    'frame': int(det['det_impath'])
                })

    return detections


def get_all_detections_at_timestamp(all_camera_data, target_timestamp, tolerance=None):
    """
    Extract all detections at a specific synchronized timestamp from ALL cameras

    Args:
        all_camera_data: Dictionary of all camera data
        target_timestamp: Target synchronized timestamp
        tolerance: Time tolerance in seconds

    Returns:
        list: List of all detections across all cameras
    """
    all_detections = []

    for camera_id, camera_data in all_camera_data.items():
        detections = get_detections_at_timestamp(camera_data, camera_id, target_timestamp, tolerance)
        all_detections.extend(detections)

    return all_detections


def get_timestamp_range(all_camera_data):
    """
    Determine min/max synchronized timestamps across all cameras

    Args:
        all_camera_data: Dictionary of all camera data

    Returns:
        tuple: (min_timestamp, max_timestamp)
    """
    min_timestamp = float('inf')
    max_timestamp = float('-inf')

    for camera_id, camera_data in all_camera_data.items():
        for track in camera_data['tracks']:
            for det in track['dets']:
                synced_timestamp = get_synchronized_timestamp(camera_id, det['det_timestamp'])
                min_timestamp = min(min_timestamp, synced_timestamp)
                max_timestamp = max(max_timestamp, synced_timestamp)

    return (min_timestamp, max_timestamp)
