"""
JSON Reader - Loads detection data from JSON track files
"""
import json
import os
import logging
from pathlib import Path
from typing import Dict, List, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)


def load_detections_from_json(json_path: Path, camera_id: str) -> Optional[Dict[float, List[Dict]]]:
    """
    Load JSON track data and organize detections by timestamp.

    Args:
        json_path: Path to the JSON file
        camera_id: Camera identifier (for logging)

    Returns:
        Dictionary mapping timestamp -> list of detections
        {
            5.0: [
                {
                    'track_id': 3,
                    'bbox': [0.34, 0.93, 0.45, 0.99],
                    'bbox_score': 0.81,
                    'birdeye': [x1, y1, x2, y2, x3, y3, x4, y4],
                    'vehicle_class': 'Pickup / Minitruck',
                    'frame': 50
                },
                ...
            ],
            5.1: [...],
            ...
        }
    """
    if not json_path.exists():
        logger.error(f"[{camera_id}] JSON file not found: {json_path}")
        return None

    try:
        with open(json_path, 'r') as f:
            data = json.load(f)

        detections_by_timestamp = defaultdict(list)

        # Parse tracks
        for track in data.get('tracks', []):
            track_id = track['id']

            for det in track.get('dets', []):
                timestamp = det['det_timestamp']

                # Extract relevant fields (use same names as original JSON for compatibility)
                detection = {
                    'track_id': track_id,
                    'det_bbox': det['det_bbox'],
                    'det_bbox_score': det.get('det_bbox_score', 0.0),
                    'det_birdeye': det['det_birdeye'],  # Keep original name for tracking
                    'det_kp_class_name': det.get('det_kp_class_name', 'Unknown'),  # Keep original name
                    'det_timestamp': timestamp,  # Add timestamp field
                    'det_impath': det['det_impath'],  # Keep original name
                    'det_keypoints': det.get('det_keypoints', []),
                    'det_im_w': det.get('det_im_w'),
                    'det_im_h': det.get('det_im_h'),
                }

                detections_by_timestamp[timestamp].append(detection)

        logger.info(f"[{camera_id}] Loaded {len(detections_by_timestamp)} unique timestamps")
        return dict(detections_by_timestamp)

    except Exception as e:
        logger.error(f"[{camera_id}] Failed to load JSON: {e}", exc_info=True)
        return None


def load_all_cameras(json_dir: str, cameras: List[str], json_pattern: str) -> Dict[str, Dict]:
    """
    Load detection data for all cameras.

    Args:
        json_dir: Directory containing JSON files
        cameras: List of camera IDs
        json_pattern: Pattern for JSON filenames (e.g., 'S01_{camera}_tracks_data.json')

    Returns:
        Dictionary mapping camera_id -> detections_by_timestamp
    """
    all_data = {}

    for camera_id in cameras:
        json_filename = json_pattern.format(camera=camera_id)
        json_path = Path(json_dir) / json_filename

        logger.info(f"Loading {camera_id} from {json_path}...")
        detections = load_detections_from_json(json_path, camera_id)

        if detections:
            all_data[camera_id] = detections
        else:
            logger.warning(f"No data loaded for {camera_id}")

    logger.info(f"✓ Loaded {len(all_data)} cameras")
    return all_data
