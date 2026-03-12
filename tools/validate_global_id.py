"""
Validation visualization for specific Global ID
Creates comprehensive side-by-side comparison with all camera views and ground plane
"""

import json
import cv2
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MPLPolygon
import os
import argparse


# Configuration
VIDEO_DIR = 'videos'
JSON_DIR = 'json'
OUTPUT_DIR = 'output/visualizations'
FOOTPRINT_INDICES = [12, 13, 14, 15]


def load_global_mapping(mapping_file='output/global_id_mapping.json'):
    """Load global ID mapping"""
    with open(mapping_file, 'r') as f:
        return json.load(f)


def load_camera_json(camera_id):
    """Load JSON data for a camera"""
    json_path = os.path.join(JSON_DIR, f'S01_{camera_id}_tracks_data.json')
    with open(json_path, 'r') as f:
        return json.load(f)


def find_best_frame(track_dets):
    """Find the middle/best frame from a track's detections"""
    if not track_dets:
        return None
    # Use middle detection
    mid_idx = len(track_dets) // 2
    return track_dets[mid_idx]


def extract_frame_with_footprint(camera_id, frame_number, track_id, camera_data):
    """Extract video frame and overlay footprint"""

    # Load video
    video_path = os.path.join(VIDEO_DIR, f'S01_{camera_id}.mp4')
    cap = cv2.VideoCapture(video_path)
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
    ret, frame = cap.read()
    cap.release()

    if not ret:
        print(f"Warning: Could not load frame {frame_number} from {camera_id}")
        return None, None

    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    # Find detection and draw footprint
    for track in camera_data['tracks']:
        if track['id'] == track_id:
            for det in track['dets']:
                if int(det['det_impath']) == frame_number:
                    # Extract footprint
                    keypoints = det['det_keypoints']
                    img_h, img_w = frame_rgb.shape[:2]

                    footprint = []
                    for kp_idx in FOOTPRINT_INDICES:
                        x = keypoints[kp_idx * 2] * img_w
                        y = keypoints[kp_idx * 2 + 1] * img_h
                        footprint.append([x, y])

                    # Draw footprint
                    pts = np.array([
                        footprint[0], footprint[1],
                        footprint[3], footprint[2]
                    ], dtype=np.int32)

                    cv2.polylines(frame_rgb, [pts], True, (0, 255, 0), 4)

                    # Add label
                    center = np.array(footprint).mean(axis=0).astype(int)
                    label = f'{camera_id}-T{track_id}'
                    cv2.putText(frame_rgb, label, tuple(center - [0, 30]),
                               cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 0), 3)

                    return frame_rgb, det

    return frame_rgb, None


def create_validation_visualization(global_id, mapping_file='output/global_id_mapping.json'):
    """
    Create comprehensive validation visualization for a Global ID

    Args:
        global_id: Global ID to visualize
        mapping_file: Path to global_id_mapping.json
    """

    print(f"\n{'='*70}")
    print(f"Creating Validation Visualization for Global ID {global_id}")
    print(f"{'='*70}\n")

    # Load mapping
    mapping = load_global_mapping(mapping_file)

    if str(global_id) not in mapping:
        print(f"Error: Global ID {global_id} not found in mapping")
        return

    camera_tracks = mapping[str(global_id)]
    num_cameras = len(camera_tracks)

    print(f"Global ID {global_id} appears in {num_cameras} cameras:")
    for cam, info in camera_tracks.items():
        print(f"  - {cam}: Track {info['track_id']}")

    # Create figure
    fig = plt.figure(figsize=(20, 12))
    gs = fig.add_gridspec(3, 3, hspace=0.3, wspace=0.3)

    # Collect data for each camera
    camera_frames = []
    ground_plane_data = []

    for idx, (camera_id, info) in enumerate(sorted(camera_tracks.items())):
        track_id = info['track_id']

        print(f"\nProcessing {camera_id} - Track {track_id}...")

        # Load camera data
        camera_data = load_camera_json(camera_id)

        # Find track
        track = None
        for t in camera_data['tracks']:
            if t['id'] == track_id:
                track = t
                break

        if not track:
            print(f"  Warning: Track {track_id} not found")
            continue

        # Find best frame
        best_det = find_best_frame(track['dets'])
        if not best_det:
            continue

        frame_number = int(best_det['det_impath'])

        # Extract frame with footprint
        frame_rgb, det = extract_frame_with_footprint(
            camera_id, frame_number, track_id, camera_data
        )

        if frame_rgb is not None:
            camera_frames.append({
                'camera': camera_id,
                'track_id': track_id,
                'frame': frame_rgb,
                'frame_number': frame_number,
                'timestamp': best_det['det_timestamp']
            })

        # Collect ground plane data
        for det in track['dets']:
            birdeye = det['det_birdeye']
            ground_plane_data.append({
                'camera': camera_id,
                'timestamp': det['det_timestamp'],
                'footprint': birdeye
            })

    # Plot camera frames
    positions = [(0, 0), (0, 1), (0, 2), (1, 0), (1, 1)]

    for idx, cam_data in enumerate(camera_frames[:5]):
        row, col = positions[idx]
        ax = fig.add_subplot(gs[row, col])

        ax.imshow(cam_data['frame'])
        ax.set_title(f"{cam_data['camera']} - Track {cam_data['track_id']}\n"
                    f"Frame {cam_data['frame_number']} | t={cam_data['timestamp']:.1f}s",
                    fontsize=12, fontweight='bold')
        ax.axis('off')

    # Plot ground plane trajectory
    ax_ground = fig.add_subplot(gs[1:, 2])

    # Extract and plot trajectory
    timestamps = [d['timestamp'] for d in ground_plane_data]
    sort_idx = np.argsort(timestamps)

    for i in sort_idx:
        d = ground_plane_data[i]
        birdeye = d['footprint']

        # Extract center point
        x_coords = [birdeye[j] for j in range(0, 8, 2)]
        y_coords = [birdeye[j] for j in range(1, 8, 2)]
        center_x = np.mean(x_coords)
        center_y = np.mean(y_coords)

        # Plot point
        ax_ground.plot(center_x, center_y, 'o', markersize=8,
                      color='red', alpha=0.6)

        # Draw footprint polygon
        points = np.array([
            [birdeye[0], birdeye[1]],
            [birdeye[2], birdeye[3]],
            [birdeye[4], birdeye[5]],
            [birdeye[6], birdeye[7]]
        ])
        polygon = MPLPolygon(points, fill=False, edgecolor='blue',
                            linewidth=1, alpha=0.3)
        ax_ground.add_patch(polygon)

    # Draw trajectory line
    centers_x = []
    centers_y = []
    for i in sort_idx:
        d = ground_plane_data[i]
        birdeye = d['footprint']
        x_coords = [birdeye[j] for j in range(0, 8, 2)]
        y_coords = [birdeye[j] for j in range(1, 8, 2)]
        centers_x.append(np.mean(x_coords))
        centers_y.append(np.mean(y_coords))

    ax_ground.plot(centers_x, centers_y, 'r-', linewidth=2, alpha=0.7,
                  label='Vehicle Path')
    ax_ground.plot(centers_x[0], centers_y[0], 'go', markersize=15,
                  label='Start')
    ax_ground.plot(centers_x[-1], centers_y[-1], 'rs', markersize=15,
                  label='End')

    ax_ground.set_xlabel('X (Ground Plane)', fontsize=12, fontweight='bold')
    ax_ground.set_ylabel('Y (Ground Plane)', fontsize=12, fontweight='bold')
    ax_ground.set_title(f'Ground Plane Trajectory\nGlobal ID {global_id}',
                       fontsize=14, fontweight='bold')
    ax_ground.grid(True, alpha=0.3)
    ax_ground.legend(loc='best')
    ax_ground.axis('equal')

    # Add main title
    fig.suptitle(f'Cross-Camera Tracking Validation - Global ID {global_id}\n'
                f'Vehicle tracked across {num_cameras} cameras',
                fontsize=16, fontweight='bold')

    # Save
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(OUTPUT_DIR, f'global_id_{global_id}_validation.png')
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"\n✓ Saved validation visualization to: {output_path}")

    plt.show()

    print(f"\n{'='*70}")
    print(f"VALIDATION COMPLETE")
    print(f"{'='*70}")
    print(f"Check the image to verify:")
    print(f"  1. Same vehicle type/color in all frames")
    print(f"  2. Footprints on correct vehicle")
    print(f"  3. Ground plane trajectory makes sense")
    print(f"  4. Temporal progression is logical")
    print(f"{'='*70}\n")


def main():
    parser = argparse.ArgumentParser(description='Validate Global ID tracking')
    parser.add_argument('--global_id', type=int, default=10,
                       help='Global ID to visualize (default: 10)')
    parser.add_argument('--mapping', type=str,
                       default='output/global_id_mapping.json',
                       help='Path to global ID mapping file')

    args = parser.parse_args()

    create_validation_visualization(args.global_id, args.mapping)


if __name__ == "__main__":
    main()
