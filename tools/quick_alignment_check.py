"""
Quick alignment check for GPS_intersection.png
Automatically loads the image and shows vehicle positions
"""

import json
import cv2
import numpy as np
from pathlib import Path
import matplotlib.pyplot as plt
from matplotlib.patches import Circle

# Paths
JSON_DIR = Path('json')
IMAGE_PATH = Path('GPS_intersection.png')

def load_sample_positions(max_samples=50):
    """Load sample vehicle positions from tracking data"""

    positions = []
    json_files = list(JSON_DIR.glob('S01_c*_tracks_data.json'))

    print(f"Loading sample positions from {len(json_files)} cameras...")

    for json_file in json_files[:2]:  # First 2 cameras for quick check
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Sample positions from first few tracks
        for track in data['tracks'][:5]:  # First 5 tracks per camera
            for det in track['dets'][::10]:  # Every 10th detection
                birdeye = det['det_birdeye']
                # Use centroid of footprint
                x = (birdeye[0] + birdeye[2] + birdeye[4] + birdeye[6]) / 4
                y = (birdeye[1] + birdeye[3] + birdeye[5] + birdeye[7]) / 4
                positions.append((x, y))

                if len(positions) >= max_samples:
                    break

            if len(positions) >= max_samples:
                break

        if len(positions) >= max_samples:
            break

    return np.array(positions)

def simple_transform(x, y, img_width, img_height, coord_bounds):
    """Simple transformation: normalize coordinates to image size"""

    # Normalize to 0-1 range
    x_norm = (x - coord_bounds['min_x']) / (coord_bounds['max_x'] - coord_bounds['min_x'])
    y_norm = (y - coord_bounds['min_y']) / (coord_bounds['max_y'] - coord_bounds['min_y'])

    # Scale to image size with some padding
    padding = 0.1
    x_pixel = (x_norm * (1 - 2*padding) + padding) * img_width
    y_pixel = (1 - (y_norm * (1 - 2*padding) + padding)) * img_height  # Flip Y

    return x_pixel, y_pixel

def main():
    """Main function"""

    print("\n" + "="*70)
    print("  GPS INTERSECTION IMAGE ALIGNMENT CHECK")
    print("="*70 + "\n")

    # Check if image exists
    if not IMAGE_PATH.exists():
        print(f"ERROR: Image not found at {IMAGE_PATH}")
        print("Please make sure GPS_intersection.png is in the project root directory.")
        return

    # Load image
    print(f"Loading image: {IMAGE_PATH}")
    image = cv2.imread(str(IMAGE_PATH))
    if image is None:
        print(f"ERROR: Could not load image from {IMAGE_PATH}")
        return

    image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    img_height, img_width = image.shape[:2]
    print(f"Image size: {img_width} x {img_height} pixels")

    # Load sample positions
    print("\nLoading vehicle positions...")
    positions = load_sample_positions(50)
    print(f"Loaded {len(positions)} sample positions")

    # Calculate coordinate bounds
    coord_bounds = {
        'min_x': positions[:, 0].min(),
        'max_x': positions[:, 0].max(),
        'min_y': positions[:, 1].min(),
        'max_y': positions[:, 1].max()
    }

    print(f"\nCoordinate range:")
    print(f"  X: [{coord_bounds['min_x']:.1f}, {coord_bounds['max_x']:.1f}]")
    print(f"  Y: [{coord_bounds['min_y']:.1f}, {coord_bounds['max_y']:.1f}]")

    # Create visualization
    print("\nCreating visualization...")
    fig, ax = plt.subplots(figsize=(14, 10))

    # Show image
    ax.imshow(image)

    # Transform and plot positions
    for x, y in positions:
        px, py = simple_transform(x, y, img_width, img_height, coord_bounds)

        # Only plot if within image bounds
        if 0 <= px < img_width and 0 <= py < img_height:
            circle = Circle((px, py), radius=8, color='red', alpha=0.7, linewidth=2, fill=False)
            ax.add_patch(circle)

    ax.set_xlim(0, img_width)
    ax.set_ylim(img_height, 0)
    ax.set_title('GPS Intersection Image with Vehicle Positions Overlay\n' +
                 'RED CIRCLES = Vehicle positions from tracking data\n' +
                 'Do the circles align with roads/intersection?',
                 fontsize=12, fontweight='bold')
    ax.axis('off')

    plt.tight_layout()

    print("\n" + "="*70)
    print("INSTRUCTIONS:")
    print("="*70)
    print("1. Look at the visualization window that just opened")
    print("2. Check if RED CIRCLES align with roads in the intersection")
    print("3. If they align well: Your image is good to use!")
    print("4. If they don't align: We'll need to adjust the transformation")
    print("\nClose the window when done reviewing.")
    print("="*70 + "\n")

    plt.show()

    # Ask user about alignment
    print("\nDid the vehicle positions align with the roads? (y/n): ", end='')
    response = input().strip().lower()

    if response == 'y':
        print("\n✓ Great! Your GPS_intersection.png is ready to use!")
        print("  We can proceed with building the visualization.")
    else:
        print("\n✗ The positions don't align perfectly.")
        print("  Next step: Run the interactive alignment tool:")
        print("  python tools/alignment_verification.py")
        print("  This will let you adjust scale/rotation/offset with sliders.")

if __name__ == '__main__':
    main()
