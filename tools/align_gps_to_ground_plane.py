"""
GPS-to-Ground-Plane Alignment Tool with Camera Location Markers

Shows camera positions as reference points for easier alignment.
"""

import json
import cv2
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MPLPolygon
from matplotlib.widgets import Slider, Button
from scipy.ndimage import rotate
import os


# Configuration
VIDEO_DIR = 'videos'
JSON_DIR = 'json'
GPS_IMAGE_PATH = 'GPS_intersection.png'
FOOTPRINT_INDICES = [12, 13, 14, 15]

CAMERA_OFFSETS = {
    'c001': 0.0,
    'c002': 1.640,
    'c003': 2.049,
    'c004': 2.177,
    'c005': 2.235
}

CAMERA_COLORS = {
    'c001': '#FF6B6B',
    'c002': '#4ECDC4',
    'c003': '#45B7D1',
    'c004': '#FFA07A',
    'c005': '#98D8C8'
}

# Camera GPS coordinates (lat, lon)
CAMERA_LOCATIONS = {
    'c001': {'lat': 42.5254829, 'lon': -90.7233451},
    'c002': {'lat': 42.5258119, 'lon': -90.7238137},
    'c003': {'lat': 42.5257186, 'lon': -90.7232303},
    'c004': {'lat': 42.5255629, 'lon': -90.7239331},
    'c005': {'lat': 42.5258378, 'lon': -90.7235177}
}


def latlon_to_meters(lat, lon, ref_lat, ref_lon):
    """Convert lat/lon to meters relative to reference point"""
    # Approximate conversion (works for small areas)
    lat_m_per_deg = 111320  # meters per degree latitude
    lon_m_per_deg = 111320 * np.cos(np.radians(ref_lat))  # varies with latitude

    x = (lon - ref_lon) * lon_m_per_deg
    y = (lat - ref_lat) * lat_m_per_deg

    return x, y


def get_camera_positions_meters():
    """Convert camera lat/lon to relative meters"""
    # Use c001 as reference point
    ref_lat = CAMERA_LOCATIONS['c001']['lat']
    ref_lon = CAMERA_LOCATIONS['c001']['lon']

    positions = {}
    for camera, coords in CAMERA_LOCATIONS.items():
        x, y = latlon_to_meters(coords['lat'], coords['lon'], ref_lat, ref_lon)
        positions[camera] = {'x': x, 'y': y}

    return positions


def load_camera_json(camera_id):
    """Load JSON data for a camera"""
    json_path = os.path.join(JSON_DIR, f'S01_{camera_id}_tracks_data.json')
    with open(json_path, 'r') as f:
        return json.load(f)


def get_synchronized_frames(target_time=10.0):
    """Extract frames from all 5 cameras at synchronized real-world time"""
    frames = {}

    for camera, offset in CAMERA_OFFSETS.items():
        video_time = target_time - offset
        if video_time < 0:
            continue

        frame_number = int(video_time * 10)
        video_path = os.path.join(VIDEO_DIR, f'S01_{camera}.mp4')
        cap = cv2.VideoCapture(video_path)
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
        ret, frame = cap.read()
        cap.release()

        if ret:
            frames[camera] = (cv2.cvtColor(frame, cv2.COLOR_BGR2RGB), video_time)
            print(f"✓ {camera}: frame {frame_number} at video time {video_time:.2f}s")

    return frames


def get_footprints_at_time(target_time=10.0, tolerance=0.1):
    """Get highest confidence footprint per camera at synchronized time"""
    all_footprints = []

    for camera, offset in CAMERA_OFFSETS.items():
        camera_data = load_camera_json(camera)

        for track in camera_data['tracks']:
            for det in track['dets']:
                synced_time = det['det_timestamp'] + offset

                if abs(synced_time - target_time) < tolerance:
                    all_footprints.append({
                        'camera': camera,
                        'footprint': det['det_birdeye'],
                        'class': det['det_kp_class_name'],
                        'timestamp': synced_time,
                        'track_id': track['id'],
                        'keypoints': det['det_keypoints'],
                        'bbox_score': det.get('det_bbox_score', 0.0)
                    })

    # Select highest confidence per camera
    best_per_camera = {}
    for fp in all_footprints:
        camera = fp['camera']
        if camera not in best_per_camera or fp['bbox_score'] > best_per_camera[camera]['bbox_score']:
            best_per_camera[camera] = fp

    result = list(best_per_camera.values())
    print(f"Selected {len(result)} highest confidence detections")
    return result


def create_alignment_tool(target_time=10.0):
    """Create interactive GPS alignment tool with camera markers"""
    print(f"\n{'='*70}")
    print(f"GPS-to-Ground-Plane Alignment Tool with Camera Markers")
    print(f"{'='*70}")
    print(f"Target synchronized time: {target_time}s\n")

    frames = get_synchronized_frames(target_time)
    footprints = get_footprints_at_time(target_time)
    camera_positions = get_camera_positions_meters()

    print("\nCamera positions (relative to c001):")
    for cam, pos in camera_positions.items():
        print(f"  {cam}: x={pos['x']:6.2f}m, y={pos['y']:6.2f}m")

    if not os.path.exists(GPS_IMAGE_PATH):
        print(f"ERROR: GPS image not found at {GPS_IMAGE_PATH}")
        return

    gps_img = plt.imread(GPS_IMAGE_PATH)

    fig = plt.figure(figsize=(20, 14))
    fig.suptitle(f'GPS Alignment with Camera Markers (t={target_time}s)',
                 fontsize=16, fontweight='bold')

    # Plot camera frames
    for idx, camera in enumerate(sorted(frames.keys())):
        frame, video_time = frames[camera]
        frame_copy = frame.copy()

        color_hex = CAMERA_COLORS[camera]
        color_rgb = tuple(int(color_hex[i:i+2], 16) for i in (1, 3, 5))

        camera_footprints = [fp for fp in footprints if fp['camera'] == camera]

        for fp in camera_footprints:
            keypoints = fp['keypoints']
            img_h, img_w = frame_copy.shape[:2]

            footprint_pts = []
            for kp_idx in FOOTPRINT_INDICES:
                x = int(keypoints[kp_idx * 2] * img_w)
                y = int(keypoints[kp_idx * 2 + 1] * img_h)
                footprint_pts.append([x, y])

            pts = np.array([
                footprint_pts[0], footprint_pts[1],
                footprint_pts[3], footprint_pts[2]
            ], dtype=np.int32)

            cv2.polylines(frame_copy, [pts], True, color_rgb, 4)

            center = np.array(footprint_pts).mean(axis=0).astype(int)
            label = f'T{fp["track_id"]}'

            (text_w, text_h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)
            cv2.rectangle(frame_copy,
                         (center[0] - text_w//2 - 5, center[1] - text_h - 5),
                         (center[0] + text_w//2 + 5, center[1] + 5),
                         (0, 0, 0), -1)

            cv2.putText(frame_copy, label,
                       (center[0] - text_w//2, center[1]),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

        ax = plt.subplot(3, 5, idx + 1)
        ax.imshow(frame_copy)
        conf_text = f" (conf={camera_footprints[0]['bbox_score']:.2f})" if camera_footprints else ""
        ax.set_title(f'{camera}{conf_text}\nVideo: {video_time:.2f}s',
                    fontsize=10, fontweight='bold', color=color_hex)
        ax.axis('off')

    # Ground plane plot
    ax_ground = plt.subplot(3, 1, (2, 3))

    camera_colors_mpl = {}
    for cam, hex_color in CAMERA_COLORS.items():
        rgb = tuple(int(hex_color[i:i+2], 16) / 255.0 for i in (1, 3, 5))
        camera_colors_mpl[cam] = rgb

    # Plot footprints
    for fp in footprints:
        birdeye = fp['footprint']
        points = np.array([
            [birdeye[0], birdeye[1]],
            [birdeye[2], birdeye[3]],
            [birdeye[4], birdeye[5]],
            [birdeye[6], birdeye[7]]
        ])

        color = camera_colors_mpl[fp['camera']]
        polygon = MPLPolygon(points, fill=True, facecolor=color,
                            edgecolor='black', linewidth=3, alpha=0.7)
        ax_ground.add_patch(polygon)

        center = points.mean(axis=0)
        label = f"{fp['camera']}\nT{fp['track_id']}"
        ax_ground.text(center[0], center[1], label,
                      fontsize=10, ha='center', va='center',
                      color='white', fontweight='bold',
                      bbox=dict(boxstyle='round,pad=0.4',
                               facecolor='black', alpha=0.8, edgecolor='none'))

    # Plot camera positions as stars
    for camera, pos in camera_positions.items():
        color = camera_colors_mpl[camera]
        ax_ground.plot(pos['x'], pos['y'], marker='*', markersize=25,
                      color=color, markeredgecolor='black', markeredgewidth=2,
                      label=f'{camera} camera', zorder=100)
        ax_ground.text(pos['x'], pos['y'] - 3, camera,
                      fontsize=11, ha='center', va='top',
                      fontweight='bold', color='black',
                      bbox=dict(boxstyle='round,pad=0.3',
                               facecolor='yellow', alpha=0.9, edgecolor='black', linewidth=2))

    # Calculate bounds
    all_x, all_y = [], []
    for fp in footprints:
        birdeye = fp['footprint']
        all_x.extend([birdeye[0], birdeye[2], birdeye[4], birdeye[6]])
        all_y.extend([birdeye[1], birdeye[3], birdeye[5], birdeye[7]])

    # Include camera positions in bounds
    for pos in camera_positions.values():
        all_x.append(pos['x'])
        all_y.append(pos['y'])

    if all_x and all_y:
        x_min, x_max = min(all_x), max(all_x)
        y_min, y_max = min(all_y), max(all_y)
        x_range, y_range = x_max - x_min, y_max - y_min

        padding = 0.3
        x_min -= x_range * padding
        x_max += x_range * padding
        y_min -= y_range * padding
        y_max += y_range * padding
    else:
        x_min, x_max, y_min, y_max = -50, 50, -50, 50

    gps_overlay = ax_ground.imshow(gps_img, alpha=0.5, extent=[x_min, x_max, y_min, y_max],
                                   origin='upper', zorder=0)

    ax_ground.set_xlim(x_min, x_max)
    ax_ground.set_ylim(y_min, y_max)
    ax_ground.set_xlabel('X (meters)', fontsize=12, fontweight='bold')
    ax_ground.set_ylabel('Y (meters)', fontsize=12, fontweight='bold')
    ax_ground.set_title('Ground Plane + GPS Overlay\n⭐ = Camera Positions (align these with GPS!)',
                       fontsize=14, fontweight='bold')
    ax_ground.grid(True, alpha=0.3)
    ax_ground.set_aspect('equal')
    ax_ground.legend(loc='upper right', fontsize=9)

    # Sliders
    plt.subplots_adjust(bottom=0.15)

    ax_rotation = plt.axes([0.15, 0.08, 0.7, 0.02])
    slider_rotation = Slider(ax_rotation, 'Rotation (°)', 0, 360, valinit=0, valstep=1)

    ax_opacity = plt.axes([0.15, 0.05, 0.7, 0.02])
    slider_opacity = Slider(ax_opacity, 'Opacity', 0, 1, valinit=0.5, valstep=0.05)

    ax_scale = plt.axes([0.15, 0.02, 0.7, 0.02])
    slider_scale = Slider(ax_scale, 'Scale', 0.5, 2.0, valinit=1.0, valstep=0.05)

    original_gps = gps_img.copy()

    def update(val):
        rotated_gps = rotate(original_gps, slider_rotation.val, reshape=False, order=1)
        gps_overlay.set_data(rotated_gps)
        gps_overlay.set_alpha(slider_opacity.val)

        x_center = (x_min + x_max) / 2
        y_center = (y_min + y_max) / 2
        scale = slider_scale.val
        x_range_scaled = (x_max - x_min) * scale / 2
        y_range_scaled = (y_max - y_min) * scale / 2

        gps_overlay.set_extent([
            x_center - x_range_scaled, x_center + x_range_scaled,
            y_center - y_range_scaled, y_center + y_range_scaled
        ])
        fig.canvas.draw_idle()

    slider_rotation.on_changed(update)
    slider_opacity.on_changed(update)
    slider_scale.on_changed(update)

    # Save button
    ax_save = plt.axes([0.88, 0.08, 0.1, 0.04])
    btn_save = Button(ax_save, 'Save Settings')

    def save_settings(event):
        settings = {
            'rotation': slider_rotation.val,
            'opacity': slider_opacity.val,
            'scale': slider_scale.val,
            'target_time': target_time
        }
        with open('gps_alignment_settings.json', 'w') as f:
            json.dump(settings, f, indent=2)
        print(f"\n✓ Saved: Rotation={settings['rotation']}°, Opacity={settings['opacity']}, Scale={settings['scale']}")

    btn_save.on_clicked(save_settings)

    print(f"\n{'='*70}")
    print("ALIGNMENT INSTRUCTIONS:")
    print("  1. Look for camera markers (⭐) on ground plane")
    print("  2. Rotate GPS until camera positions match star locations")
    print("  3. Adjust scale to match distances")
    print("  4. Use opacity to see both layers")
    print("  5. Save when camera stars align with GPS camera positions!")
    print(f"{'='*70}\n")

    plt.show()


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Align GPS with camera markers')
    parser.add_argument('--time', type=float, default=10.0,
                       help='Synchronized time (default: 10.0s)')
    args = parser.parse_args()
    create_alignment_tool(target_time=args.time)


if __name__ == "__main__":
    main()
