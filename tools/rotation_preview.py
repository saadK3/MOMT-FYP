"""
Rotation Preview Tool - OPTIMIZED VERSION

Displays the satellite image at different rotation angles alongside the trajectory
plot to help identify which rotation brings them into rough alignment.

Usage:
    python tools/rotation_preview.py

Instructions:
    - View the satellite image rotated at 8 different angles (0° to 315° in 45° steps)
    - Compare each to the trajectory plot on the right
    - Note which angle looks closest to matching the trajectory orientation
    - Close the window when done
    - You'll be prompted to enter the best angle
    - The rotated image will be saved for use with the alignment tool
"""

import json
import numpy as np
import matplotlib.pyplot as plt
from PIL import Image
from pathlib import Path

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
SATELLITE_IMAGE_PATH = PROJECT_ROOT / 'assets' / 'GPS_intersection_zoomed.jpg'
BOUNDS_CONFIG_PATH = PROJECT_ROOT / 'visualization' / 'ground_plane_bounds.json'
OUTPUT_IMAGE_PATH = PROJECT_ROOT / 'assets' / 'GPS_intersection_rotated.jpg'
JSON_DIR = PROJECT_ROOT / 'json'

# Preview settings - downscale for faster display
PREVIEW_MAX_SIZE = 600  # Max dimension for preview


def load_trajectories():
    """Load vehicle trajectories from JSON files"""
    camera_ids = ['c001', 'c002', 'c003', 'c004', 'c005']
    trajectories = []

    for camera_id in camera_ids:
        json_path = JSON_DIR / f'S01_{camera_id}_tracks_data.json'
        if not json_path.exists():
            continue

        with open(json_path, 'r') as f:
            data = json.load(f)

        for track in data['tracks']:
            path = []
            for det in track['dets']:
                birdeye = det['det_birdeye']
                center_x = (birdeye[0] + birdeye[2] + birdeye[4] + birdeye[6]) / 4
                center_y = (birdeye[1] + birdeye[3] + birdeye[5] + birdeye[7]) / 4
                path.append((center_x, center_y))

            if len(path) >= 2:
                trajectories.append(path)

    return trajectories


def rotate_image_fast(pil_image, angle):
    """Rotate PIL image by given angle (degrees) - FAST using PIL"""
    # PIL's rotate is much faster than scipy
    # Negative angle because PIL rotates counter-clockwise
    rotated = pil_image.rotate(-angle, expand=True, fillcolor=(255, 255, 255), resample=Image.BICUBIC)
    return rotated


def create_rotation_preview():
    """Create a preview showing satellite image at different rotations"""

    print("\n" + "="*70)
    print("ROTATION PREVIEW TOOL (OPTIMIZED)")
    print("="*70)
    print("Loading data...")

    # Load satellite image
    satellite_img = Image.open(SATELLITE_IMAGE_PATH)

    # Downscale for faster preview
    original_size = satellite_img.size
    max_dim = max(original_size)
    if max_dim > PREVIEW_MAX_SIZE:
        scale_factor = PREVIEW_MAX_SIZE / max_dim
        new_size = (int(original_size[0] * scale_factor), int(original_size[1] * scale_factor))
        satellite_img_preview = satellite_img.resize(new_size, Image.LANCZOS)
        print(f"Downscaled image from {original_size} to {new_size} for faster preview")
    else:
        satellite_img_preview = satellite_img

    # Load bounds and trajectories
    with open(BOUNDS_CONFIG_PATH, 'r') as f:
        bounds_config = json.load(f)

    trajectories = load_trajectories()
    print(f"Loaded {len(trajectories)} trajectories")

    # Rotation angles to test
    angles = [0, 45, 90, 135, 180, 225, 270, 315]

    print("Generating rotated previews (this should be fast now)...")

    # Create figure with subplots
    fig = plt.figure(figsize=(20, 10))
    fig.suptitle('Rotation Preview - Find which angle matches trajectory orientation',
                 fontsize=16, fontweight='bold')

    # Left side: 8 rotated satellite images (4x2 grid)
    for idx, angle in enumerate(angles):
        print(f"  Rotating {angle}°...", end='\r')
        ax = plt.subplot(2, 5, idx + 1)
        rotated = rotate_image_fast(satellite_img_preview, angle)
        ax.imshow(rotated)
        ax.set_title(f'{angle}°', fontsize=14, fontweight='bold')
        ax.axis('off')

    print("  ✓ All rotations complete!     ")

    # Right side: Trajectory plot (spanning 2 rows)
    ax_traj = plt.subplot(1, 5, 5)

    cropped = bounds_config['cropped_bounds']
    for traj in trajectories:
        xs, ys = zip(*traj)
        ax_traj.plot(xs, ys, 'b-', alpha=0.3, linewidth=0.8)

    ax_traj.set_xlim(cropped['x_min'] - 5, cropped['x_max'] + 5)
    ax_traj.set_ylim(cropped['y_min'] - 5, cropped['y_max'] + 5)
    ax_traj.set_title('TRAJECTORY MAP\n(Compare orientation)', fontsize=14, fontweight='bold')
    ax_traj.set_xlabel('X (meters)')
    ax_traj.set_ylabel('Y (meters)')
    ax_traj.set_aspect('equal')
    ax_traj.grid(True, alpha=0.3)

    plt.tight_layout()

    print("\n" + "="*70)
    print("INSTRUCTIONS:")
    print("="*70)
    print("1. Look at each rotated satellite image (0° to 315°)")
    print("2. Compare the road orientation in each to the trajectory plot")
    print("3. Identify which rotation angle brings them closest to alignment")
    print("4. Note the angle (you'll enter it after closing this window)")
    print("5. Close the window when ready")
    print("="*70 + "\n")

    plt.show()

    return angles


def save_rotated_image(angle):
    """Save the satellite image rotated by the specified angle"""

    print(f"\nRotating full-resolution satellite image by {angle}°...")

    # Load original image
    satellite_img = Image.open(SATELLITE_IMAGE_PATH)

    # Rotate using fast PIL method
    rotated_img = rotate_image_fast(satellite_img, angle)

    # Save
    rotated_img.save(OUTPUT_IMAGE_PATH, quality=95)

    print(f"✓ Rotated image saved to: {OUTPUT_IMAGE_PATH}")
    print(f"  Original size: {satellite_img.size}")
    print(f"  Rotated size: {rotated_img.size}")

    return OUTPUT_IMAGE_PATH


def main():
    """Main function"""

    # Show preview
    angles = create_rotation_preview()

    # Get user input
    print("\n" + "="*70)
    while True:
        try:
            user_input = input("Enter the best rotation angle (0, 45, 90, 135, 180, 225, 270, 315) or custom angle: ").strip()

            if not user_input:
                print("No rotation selected. Exiting.")
                return

            angle = float(user_input)

            if angle < 0 or angle >= 360:
                print("⚠️  Angle should be between 0 and 359. Try again.")
                continue

            break

        except ValueError:
            print("⚠️  Invalid input. Please enter a number.")

    # Save rotated image
    output_path = save_rotated_image(angle)

    print("\n" + "="*70)
    print("✓ ROTATION COMPLETE")
    print("="*70)
    print(f"Rotated image saved to: {output_path}")
    print("\nNEXT STEPS:")
    print("1. Update reference_point_alignment.py to use the rotated image:")
    print(f"   Change line 31 to: SATELLITE_IMAGE_PATH = PROJECT_ROOT / 'assets' / 'GPS_intersection_rotated.jpg'")
    print("2. Run the alignment tool:")
    print("   python tools/reference_point_alignment.py")
    print("3. Click matching points between the rotated satellite image and trajectories")
    print("4. Press 'C' to compute alignment, then 'S' to save")
    print("="*70 + "\n")


if __name__ == '__main__':
    main()
