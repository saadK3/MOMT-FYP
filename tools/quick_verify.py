"""
Quick visual verification - Shows one multi-camera match
Run this for a fast sanity check
"""

import json
import cv2
import numpy as np
import matplotlib.pyplot as plt
from cross_camera_tracking.data_loader import load_all_cameras
from cross_camera_tracking.config import VIDEO_DIR, FOOTPRINT_INDICES
import os


def quick_verify():
    """Quick verification of one multi-camera match"""

    # Load results
    with open('output/test_sample_results.json', 'r') as f:
        results = json.load(f)

    # Find first multi-camera match
    multi_camera_match = None
    for global_id, cameras in results.items():
        if len(cameras) >= 2:
            multi_camera_match = (global_id, cameras)
            break

    if not multi_camera_match:
        print("❌ No multi-camera matches found!")
        return

    global_id, cameras = multi_camera_match

    print(f"\\n{'='*70}")
    print(f"VISUAL VERIFICATION - Global ID {global_id}")
    print(f"{'='*70}")
    print(f"This vehicle was detected in {len(cameras)} cameras:")
    for cam, info in cameras.items():
        print(f"  - {cam}: Track {info['track_id']}")
    print(f"{'='*70}\\n")

    # Load camera data
    print("Loading camera data...")
    all_camera_data = load_all_cameras()

    # Use frame 10
    frame_num = 10

    # Create visualization
    num_cams = len(cameras)
    fig, axes = plt.subplots(1, num_cams, figsize=(8 * num_cams, 6))
    if num_cams == 1:
        axes = [axes]

    for idx, (camera, info) in enumerate(cameras.items()):
        track_id = info['track_id']

        # Load frame
        video_path = os.path.join(VIDEO_DIR, f'S01_{camera}.mp4')
        cap = cv2.VideoCapture(video_path)
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
        ret, frame = cap.read()
        cap.release()

        if not ret:
            print(f"⚠️  Could not load frame from {camera}")
            continue

        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Find and draw footprint
        camera_data = all_camera_data[camera]
        for track in camera_data['tracks']:
            if track['id'] == track_id:
                for det in track['dets']:
                    if int(det['det_impath']) == frame_num:
                        keypoints = det['det_keypoints']
                        img_h, img_w = frame_rgb.shape[:2]

                        # Get footprint points
                        footprint = []
                        for kp_idx in FOOTPRINT_INDICES:
                            x = keypoints[kp_idx * 2] * img_w
                            y = keypoints[kp_idx * 2 + 1] * img_h
                            footprint.append([x, y])

                        # Draw
                        pts = np.array([
                            footprint[0], footprint[1],
                            footprint[3], footprint[2]
                        ], dtype=np.int32)

                        cv2.polylines(frame_rgb, [pts], True, (0, 255, 0), 4)

                        # Label
                        center = np.array(footprint).mean(axis=0).astype(int)
                        cv2.putText(frame_rgb, f'Global ID {global_id}',
                                   tuple(center - [0, 30]),
                                   cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 0), 3)
                        cv2.putText(frame_rgb, f'{camera}-T{track_id}',
                                   tuple(center + [0, 30]),
                                   cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)

        axes[idx].imshow(frame_rgb)
        axes[idx].set_title(f'{camera} - Track {track_id}', fontsize=14, fontweight='bold')
        axes[idx].axis('off')

    plt.suptitle(f'SAME VEHICLE (Global ID {global_id}) - Seen in {num_cams} Cameras',
                 fontsize=16, fontweight='bold', y=0.98)
    plt.tight_layout()

    output_path = 'output/visualizations/quick_verification.png'
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"\\n✓ Saved: {output_path}")
    plt.show()

    print(f"\\n{'='*70}")
    print("✅ VERIFICATION:")
    print(f"   If the vehicle looks the SAME in both/all images,")
    print(f"   then the algorithm is working correctly!")
    print(f"{'='*70}\\n")


if __name__ == "__main__":
    quick_verify()
