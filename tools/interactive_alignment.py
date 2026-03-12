"""
Interactive Satellite Image Alignment Tool

Run this script to align your satellite image with ground plane trajectories.
Adjust sliders until trajectories match roads, then save the configuration.
"""

import json
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider, Button
from PIL import Image
from scipy.ndimage import rotate as scipy_rotate

# Load configuration
print("Loading configuration...")
with open('C:\\Users\\admin\\Desktop\\FYP-final\\visualization\\ground_plane_bounds.json', 'r') as f:
    bounds_config = json.load(f)

# Load satellite image
print("Loading satellite image...")
satellite_img = np.array(Image.open('C:\\Users\\admin\\Desktop\\FYP-final\\assets\\GPS_intersection.jpg'))

# Load vehicle trajectories (grouped by track)
print("Loading vehicle trajectories...")
camera_ids = ['c001', 'c002', 'c003', 'c004', 'c005']
all_trajectories = []

for camera_id in camera_ids:
    with open(f'C:\\Users\\admin\\Desktop\\FYP-final\\json\\S01_{camera_id}_tracks_data.json', 'r') as f:
        data = json.load(f)
        for track in data['tracks']:
            trajectory = []
            for det in track['dets']:
                birdeye = det['det_birdeye']
                center_x = (birdeye[0] + birdeye[2] + birdeye[4] + birdeye[6]) / 4
                center_y = (birdeye[1] + birdeye[3] + birdeye[5] + birdeye[7]) / 4
                trajectory.append({
                    'x': center_x,
                    'y': center_y,
                    'timestamp': det['det_timestamp']
                })

            if len(trajectory) > 0:  # Only add non-empty trajectories
                all_trajectories.append({
                    'camera': camera_id,
                    'track_id': track['id'],
                    'path': trajectory
                })

print(f"Loaded {len(all_trajectories):,} vehicle trajectories")

# Filter trajectories to cropped bounds
# Calculate bounds from all points
all_x = [p['x'] for traj in all_trajectories for p in traj['path']]
all_y = [p['y'] for traj in all_trajectories for p in traj['path']]
x_5th, x_95th = np.percentile(all_x, [5, 95])
y_5th, y_95th = np.percentile(all_y, [5, 95])

# Filter trajectories that have at least one point in bounds
filtered_trajectories = []
for traj in all_trajectories:
    filtered_path = [
        p for p in traj['path']
        if x_5th <= p['x'] <= x_95th and y_5th <= p['y'] <= y_95th
    ]
    if len(filtered_path) >= 2:  # Need at least 2 points to draw a line
        filtered_trajectories.append({
            **traj,
            'path': filtered_path
        })

print(f"Filtered to {len(filtered_trajectories):,} trajectories in bounds")

# Initial parameters
cropped = bounds_config['cropped_bounds']
initial_params = {
    'x_offset': cropped['x_min'],
    'y_offset': cropped['y_min'],
    'scale': 1.0,
    'rotation': 0,
    'opacity': 0.6
}

# Create figure and axis
fig, ax = plt.subplots(figsize=(14, 10))
plt.subplots_adjust(left=0.1, bottom=0.35)

# Initial image display
rotated_img = satellite_img
img_width_m = cropped['width']
img_height_m = cropped['height']
extent = [initial_params['x_offset'],
          initial_params['x_offset'] + img_width_m,
          initial_params['y_offset'],
          initial_params['y_offset'] + img_height_m]

img_display = ax.imshow(rotated_img, extent=extent,
                        alpha=initial_params['opacity'], zorder=0)

# Draw trajectory lines instead of scatter points
trajectory_lines = []
for traj in filtered_trajectories:
    x_path = [p['x'] for p in traj['path']]
    y_path = [p['y'] for p in traj['path']]
    line, = ax.plot(x_path, y_path, alpha=0.5, linewidth=1.2,
                    color='red', zorder=1)
    trajectory_lines.append(line)

# Add legend with single entry
ax.plot([], [], alpha=0.5, linewidth=1.2, color='red',
        label=f'{len(filtered_trajectories)} Vehicle Paths')

ax.set_xlim(cropped['x_min'] - 10, cropped['x_max'] + 10)
ax.set_ylim(cropped['y_min'] - 10, cropped['y_max'] + 10)
ax.set_xlabel('X (meters)', fontsize=11)
ax.set_ylabel('Y (meters)', fontsize=11)
ax.set_title('Align satellite image with trajectories\nAdjust sliders until red lines follow roads',
             fontsize=13, fontweight='bold')
ax.grid(True, alpha=0.3)
ax.legend(loc='upper right')
ax.set_aspect('equal')

# Create sliders
ax_x = plt.axes([0.15, 0.25, 0.7, 0.02])
ax_y = plt.axes([0.15, 0.20, 0.7, 0.02])
ax_scale = plt.axes([0.15, 0.15, 0.7, 0.02])
ax_rotation = plt.axes([0.15, 0.10, 0.7, 0.02])
ax_opacity = plt.axes([0.15, 0.05, 0.7, 0.02])

slider_x = Slider(ax_x, 'X Offset (m)',
                  initial_params['x_offset'] - 50,
                  initial_params['x_offset'] + 50,
                  valinit=initial_params['x_offset'], valstep=1.0)

slider_y = Slider(ax_y, 'Y Offset (m)',
                  initial_params['y_offset'] - 50,
                  initial_params['y_offset'] + 50,
                  valinit=initial_params['y_offset'], valstep=1.0)

slider_scale = Slider(ax_scale, 'Scale', 0.5, 2.0,
                      valinit=initial_params['scale'], valstep=0.01)

slider_rotation = Slider(ax_rotation, 'Rotation (°)', -45, 45,
                         valinit=initial_params['rotation'], valstep=1)

slider_opacity = Slider(ax_opacity, 'Opacity', 0.0, 1.0,
                        valinit=initial_params['opacity'], valstep=0.05)

# Update function
def update(val):
    x_off = slider_x.val
    y_off = slider_y.val
    scale = slider_scale.val
    rotation = slider_rotation.val
    opacity = slider_opacity.val

    # Rotate image if needed
    if rotation != 0:
        rotated = scipy_rotate(satellite_img, rotation, reshape=False, order=1)
    else:
        rotated = satellite_img

    # Update image
    width = cropped['width'] * scale
    height = cropped['height'] * scale
    extent = [x_off, x_off + width, y_off, y_off + height]

    img_display.set_data(rotated)
    img_display.set_extent(extent)
    img_display.set_alpha(opacity)

    fig.canvas.draw_idle()

# Connect sliders
slider_x.on_changed(update)
slider_y.on_changed(update)
slider_scale.on_changed(update)
slider_rotation.on_changed(update)
slider_opacity.on_changed(update)

# Save button
ax_save = plt.axes([0.8, 0.01, 0.15, 0.03])
btn_save = Button(ax_save, 'Save Config', color='lightgreen')

def save_config(event):
    alignment_config = {
        **bounds_config,
        'alignment': {
            'x_offset': float(slider_x.val),
            'y_offset': float(slider_y.val),
            'scale': float(slider_scale.val),
            'rotation': float(slider_rotation.val),
            'opacity': float(slider_opacity.val),
            'image_path': 'assets/GPS_intersection.png'
        }
    }

    with open('../visualization/alignment_config.json', 'w') as f:
        json.dump(alignment_config, f, indent=2)

    print("\n" + "="*60)
    print("✓ SAVED ALIGNMENT CONFIGURATION")
    print("="*60)
    print(f"X Offset:  {slider_x.val:.2f} m")
    print(f"Y Offset:  {slider_y.val:.2f} m")
    print(f"Scale:     {slider_scale.val:.3f}")
    print(f"Rotation:  {slider_rotation.val:.1f}°")
    print(f"Opacity:   {slider_opacity.val:.2f}")
    print(f"\nSaved to: visualization/alignment_config.json")
    print("="*60)

btn_save.on_clicked(save_config)

# Instructions
print("\n" + "="*60)
print("INTERACTIVE ALIGNMENT TOOL")
print("="*60)
print("Instructions:")
print("  1. Adjust sliders until red dots align with roads")
print("  2. Use X/Y Offset to move image")
print("  3. Use Scale to zoom image")
print("  4. Use Rotation to rotate image")
print("  5. Use Opacity to see through image")
print("  6. Click 'Save Config' when satisfied")
print("="*60 + "\n")

plt.show()
