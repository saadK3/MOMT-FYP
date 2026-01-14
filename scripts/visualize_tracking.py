"""
Visual verification script for cross-camera tracking results
Shows matched vehicles on ground plane and in video frames
"""

import json
import cv2
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
from cross_camera_tracking.data_loader import load_all_cameras, get_all_detections_at_frame
from cross_camera_tracking.config import VIDEO_DIR, FOOTPRINT_INDICES
import os


def visualize_ground_plane_matches(results_file, all_camera_data, frame_number):
    """
    Visualize matched vehicles on ground plane for a specific frame

    Args:
        results_file: Path to global_id_mapping.json
        all_camera_data: Loaded camera data
        frame_number: Frame to visualize
    """
    # Load results
    with open(results_file, 'r') as f:
        global_mapping = json.load(f)

    # Get all detections at this frame
    detections = get_all_detections_at_frame(all_camera_data, frame_number)

    # Create reverse mapping: (camera, track_id) -> global_id
    reverse_map = {}
    for global_id, cameras in global_mapping.items():
        for camera, info in cameras.items():
            reverse_map[(camera, info['track_id'])] = int(global_id)

    # Assign global IDs to detections
    for det in detections:
        key = (det['camera'], det['track_id'])
        det['global_id'] = reverse_map.get(key, None)

    # Plot
    fig, ax = plt.subplots(1, 1, figsize=(16, 16))

    # Color map for global IDs
    colors = plt.cm.tab20(np.linspace(0, 1, 20))

    for det in detections:
        if det['global_id'] is None:
            continue

        birdeye = det['footprint']
        points = np.array([
            [birdeye[0], birdeye[1]],
            [birdeye[2], birdeye[3]],
            [birdeye[4], birdeye[5]],
            [birdeye[6], birdeye[7]]
        ])

        # Get color based on global ID
        color = colors[det['global_id'] % 20]

        # Draw polygon
        polygon = Polygon(points, fill=True, facecolor=color,
                         edgecolor='black', linewidth=2, alpha=0.7)
        ax.add_patch(polygon)

        # Draw center point
        center = points.mean(axis=0)
        ax.plot(center[0], center[1], 'o', color='black', markersize=8)

        # Add label
        label = f"G{det['global_id']}\\n{det['camera']}-T{det['track_id']}"
        ax.text(center[0], center[1], label,
                fontsize=9, color='white', fontweight='bold',
                ha='center', va='center',
                bbox=dict(boxstyle='round,pad=0.3', facecolor='black', alpha=0.8))

    ax.set_xlabel('X (Ground Plane)', fontsize=14, fontweight='bold')
    ax.set_ylabel('Y (Ground Plane)', fontsize=14, fontweight='bold')
    ax.set_title(f'Ground Plane View - Frame {frame_number}\\nSame color = Same Global ID',
                 fontsize=16, fontweight='bold')
    ax.grid(True, alpha=0.3)
    ax.axis('equal')

    plt.tight_layout()
    output_path = f'output/visualizations/ground_plane_frame_{frame_number}.png'
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"✓ Saved: {output_path}")
    plt.show()


def main():
    """Main visualization function"""

    print("Loading camera data...")
    all_camera_data = load_all_cameras()

    results_file = 'output/test_sample_results.json'

    # Visualize frame 10 ground plane
    print("\\n1. Visualizing ground plane at frame 10...")
    visualize_ground_plane_matches(results_file, all_camera_data, frame_number=10)

    print("\\n✅ Visualization complete!")
    print("Check output/visualizations/ folder for images")


if __name__ == "__main__":
    main()
