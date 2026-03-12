"""
Reference Point Alignment Tool

Click matching points in the satellite image and trajectory map to compute
an accurate transformation matrix for overlaying the satellite image.

Usage:
    python tools/reference_point_alignment.py

Instructions:
    1. Left-click on a distinctive feature in the LEFT panel (satellite image)
    2. Left-click on the SAME feature in the RIGHT panel (trajectory map)
    3. Repeat for at least 4 point pairs
    4. Press 'C' to compute and preview alignment
    5. Press 'S' to save configuration
    6. Press 'R' to reset all points
    7. Press 'U' to undo last point pair
"""

import json
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Circle
from matplotlib.widgets import Button
from PIL import Image
from pathlib import Path
import cv2

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
SATELLITE_IMAGE_PATH = PROJECT_ROOT / 'assets' / 'GPS_intersection_rotated.jpg'
BOUNDS_CONFIG_PATH = PROJECT_ROOT / 'visualization' / 'ground_plane_bounds.json'
OUTPUT_CONFIG_PATH = PROJECT_ROOT / 'visualization' / 'alignment_config.json'
JSON_DIR = PROJECT_ROOT / 'json'


class ReferencePointAligner:
    def __init__(self):
        # Load data
        print("Loading satellite image...")
        self.satellite_img = np.array(Image.open(SATELLITE_IMAGE_PATH))
        self.img_height, self.img_width = self.satellite_img.shape[:2]

        print("Loading bounds configuration...")
        with open(BOUNDS_CONFIG_PATH, 'r') as f:
            self.bounds_config = json.load(f)

        print("Loading vehicle trajectories...")
        self.trajectories = self._load_trajectories()

        # Reference points storage
        self.image_points = []  # Pixel coordinates in satellite image
        self.ground_points = []  # Ground plane coordinates

        # State
        self.waiting_for_ground_point = False
        self.current_image_point = None
        self.transform_matrix = None
        self.preview_mode = False

        # Setup plot
        self._setup_plot()

    def _load_trajectories(self):
        """Load all vehicle trajectories from JSON files"""
        camera_ids = ['c001', 'c002', 'c003', 'c004', 'c005']
        trajectories = []

        for camera_id in camera_ids:
            json_path = JSON_DIR / f'S01_{camera_id}_tracks_data.json'
            if not json_path.exists():
                print(f"  Warning: {json_path} not found")
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

        print(f"  Loaded {len(trajectories)} trajectories")
        return trajectories

    def _setup_plot(self):
        """Setup the matplotlib figure with two panels"""
        self.fig, (self.ax_img, self.ax_traj) = plt.subplots(1, 2, figsize=(16, 8))
        self.fig.canvas.manager.set_window_title('Reference Point Alignment Tool')
        plt.subplots_adjust(bottom=0.15)

        # Left panel: Satellite image
        self.ax_img.imshow(self.satellite_img)
        self.ax_img.set_title('1. Click a feature in SATELLITE IMAGE', fontsize=12, fontweight='bold')
        self.ax_img.set_xlabel('Pixel X')
        self.ax_img.set_ylabel('Pixel Y')

        # Right panel: Trajectories
        cropped = self.bounds_config['cropped_bounds']
        for traj in self.trajectories:
            xs, ys = zip(*traj)
            self.ax_traj.plot(xs, ys, 'b-', alpha=0.3, linewidth=0.8)

        self.ax_traj.set_xlim(cropped['x_min'] - 5, cropped['x_max'] + 5)
        self.ax_traj.set_ylim(cropped['y_min'] - 5, cropped['y_max'] + 5)
        self.ax_traj.set_title('2. Click SAME feature in TRAJECTORY MAP', fontsize=12, fontweight='bold')
        self.ax_traj.set_xlabel('X (meters)')
        self.ax_traj.set_ylabel('Y (meters)')
        self.ax_traj.set_aspect('equal')
        self.ax_traj.grid(True, alpha=0.3)

        # Point markers storage
        self.img_markers = []
        self.traj_markers = []

        # Status text
        self.status_text = self.fig.text(
            0.5, 0.02,
            'Click a point in the satellite image to start | Points: 0 | Need at least 4',
            ha='center', fontsize=11,
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8)
        )

        # Instructions text
        self.fig.text(
            0.5, 0.06,
            'Keys: [C] Compute & Preview | [S] Save Config | [R] Reset | [U] Undo | [Q] Quit',
            ha='center', fontsize=10, color='gray'
        )

        # Connect events
        self.fig.canvas.mpl_connect('button_press_event', self._on_click)
        self.fig.canvas.mpl_connect('key_press_event', self._on_key)

    def _on_click(self, event):
        """Handle mouse clicks"""
        if event.inaxes is None:
            return

        if self.preview_mode:
            self._update_status("In preview mode. Press 'R' to reset or 'S' to save.")
            return

        if event.inaxes == self.ax_img:
            # Clicked on satellite image
            if self.waiting_for_ground_point:
                self._update_status("⚠️ First click the corresponding point in the trajectory map!")
                return

            self.current_image_point = (event.xdata, event.ydata)
            self.waiting_for_ground_point = True

            # Add temporary marker
            marker = Circle((event.xdata, event.ydata), 15,
                           color='yellow', fill=False, linewidth=2)
            self.ax_img.add_patch(marker)
            self.img_markers.append(marker)

            self._update_status(f"✓ Image point {len(self.image_points)+1}: ({event.xdata:.0f}, {event.ydata:.0f}) | Now click same spot in trajectory map →")
            self.fig.canvas.draw()

        elif event.inaxes == self.ax_traj:
            # Clicked on trajectory map
            if not self.waiting_for_ground_point:
                self._update_status("⚠️ First click a point in the satellite image!")
                return

            # Save the point pair
            self.image_points.append(self.current_image_point)
            self.ground_points.append((event.xdata, event.ydata))

            # Finalize image marker (change color)
            self.img_markers[-1].set_color('green')
            self.img_markers[-1].set_linewidth(3)

            # Add number label to image
            self.ax_img.text(self.current_image_point[0]+20, self.current_image_point[1],
                           str(len(self.image_points)), fontsize=12, color='green', fontweight='bold')

            # Add marker on trajectory map
            marker = Circle((event.xdata, event.ydata), 2,
                           color='green', fill=True)
            self.ax_traj.add_patch(marker)
            self.traj_markers.append(marker)

            # Add number label
            self.ax_traj.text(event.xdata+1, event.ydata+1,
                            str(len(self.ground_points)), fontsize=12, color='green', fontweight='bold')

            self.waiting_for_ground_point = False
            self.current_image_point = None

            n_points = len(self.image_points)
            if n_points >= 4:
                self._update_status(f"✓ Point pair {n_points} added | {n_points} points (Ready! Press 'C' to compute alignment)")
            else:
                self._update_status(f"✓ Point pair {n_points} added | Need {4 - n_points} more points")

            self.fig.canvas.draw()

    def _on_key(self, event):
        """Handle keyboard events"""
        if event.key == 'c':
            self._compute_alignment()
        elif event.key == 's':
            self._save_config()
        elif event.key == 'r':
            self._reset()
        elif event.key == 'u':
            self._undo()
        elif event.key == 'q':
            plt.close()

    def _compute_alignment(self):
        """Compute the affine transformation matrix"""
        if len(self.image_points) < 4:
            self._update_status(f"⚠️ Need at least 4 points! Currently have {len(self.image_points)}")
            return

        print("\n" + "="*60)
        print("COMPUTING ALIGNMENT")
        print("="*60)

        # Convert to numpy arrays
        src_pts = np.array(self.image_points, dtype=np.float32)
        dst_pts = np.array(self.ground_points, dtype=np.float32)

        print(f"Image points (pixels):\n{src_pts}")
        print(f"Ground points (meters):\n{dst_pts}")

        # Compute affine transformation (or homography for 4+ points)
        if len(self.image_points) == 4:
            # Use perspective transform for exactly 4 points
            self.transform_matrix, _ = cv2.findHomography(src_pts, dst_pts)
        else:
            # Use affine for 3 points, or least-squares fit for more
            self.transform_matrix, _ = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC)

        print(f"\nTransformation Matrix:\n{self.transform_matrix}")

        # Calculate error
        transformed_pts = cv2.perspectiveTransform(src_pts.reshape(-1, 1, 2), self.transform_matrix)
        transformed_pts = transformed_pts.reshape(-1, 2)
        errors = np.linalg.norm(transformed_pts - dst_pts, axis=1)

        print(f"\nPoint-wise errors (meters): {errors}")
        print(f"Mean error: {errors.mean():.3f}m")
        print(f"Max error: {errors.max():.3f}m")
        print("="*60 + "\n")

        # Show preview
        self._show_preview()

        self.preview_mode = True
        self._update_status(f"✓ Alignment computed! Mean error: {errors.mean():.2f}m | Press 'S' to save or 'R' to reset")

    def _show_preview(self):
        """Show the aligned satellite image overlaid on trajectories"""
        if self.transform_matrix is None:
            return

        cropped = self.bounds_config['cropped_bounds']

        # Calculate output image dimensions
        output_width = int(cropped['width'] * 10)  # 10 pixels per meter
        output_height = int(cropped['height'] * 10)

        # Create transformation for image warping
        # We need to map: image pixels -> ground coords -> output pixels
        # ground coords to output pixels: x' = (x - x_min) * scale, y' = (y_max - y) * scale

        scale = 10  # pixels per meter

        # Build full transformation matrix
        # Step 1: Image pixels -> Ground coordinates (our computed transform)
        # Step 2: Ground coordinates -> Output pixels
        T_ground_to_output = np.array([
            [scale, 0, -cropped['x_min'] * scale],
            [0, -scale, cropped['y_max'] * scale],
            [0, 0, 1]
        ], dtype=np.float64)

        full_transform = T_ground_to_output @ self.transform_matrix

        # Warp the satellite image
        warped = cv2.warpPerspective(
            self.satellite_img,
            full_transform,
            (output_width, output_height),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(0, 0, 0)
        )

        # Create preview figure
        preview_fig, preview_ax = plt.subplots(figsize=(12, 10))
        preview_fig.canvas.manager.set_window_title('Alignment Preview')

        # Show warped satellite image
        extent = [cropped['x_min'], cropped['x_max'], cropped['y_min'], cropped['y_max']]
        preview_ax.imshow(warped, extent=extent, alpha=0.7, origin='upper')

        # Overlay trajectories
        for traj in self.trajectories:
            xs, ys = zip(*traj)
            preview_ax.plot(xs, ys, 'lime', alpha=0.6, linewidth=1)

        # Mark reference points
        for gp in self.ground_points:
            preview_ax.plot(gp[0], gp[1], 'ro', markersize=8)

        preview_ax.set_xlim(cropped['x_min'] - 5, cropped['x_max'] + 5)
        preview_ax.set_ylim(cropped['y_min'] - 5, cropped['y_max'] + 5)
        preview_ax.set_aspect('equal')
        preview_ax.set_title('ALIGNMENT PREVIEW\nGreen = Vehicle trajectories | Red = Reference points',
                            fontsize=14, fontweight='bold')
        preview_ax.set_xlabel('X (meters)')
        preview_ax.set_ylabel('Y (meters)')

        plt.show(block=False)

    def _save_config(self):
        """Save the alignment configuration"""
        if self.transform_matrix is None:
            self._update_status("⚠️ Compute alignment first! Press 'C'")
            return

        config = {
            **self.bounds_config,
            'alignment': {
                'transform_matrix': self.transform_matrix.tolist(),
                'image_points': self.image_points,
                'ground_points': self.ground_points,
                'num_points': len(self.image_points),
                'image_path': str(SATELLITE_IMAGE_PATH.relative_to(PROJECT_ROOT)),
                'image_width': self.img_width,
                'image_height': self.img_height
            }
        }

        with open(OUTPUT_CONFIG_PATH, 'w') as f:
            json.dump(config, f, indent=2)

        print("\n" + "="*60)
        print("✓ ALIGNMENT CONFIGURATION SAVED")
        print("="*60)
        print(f"Output: {OUTPUT_CONFIG_PATH}")
        print(f"Points used: {len(self.image_points)}")
        print("="*60 + "\n")

        self._update_status(f"✓ Saved to {OUTPUT_CONFIG_PATH.name}!")

    def _reset(self):
        """Reset all points and state"""
        self.image_points = []
        self.ground_points = []
        self.waiting_for_ground_point = False
        self.current_image_point = None
        self.transform_matrix = None
        self.preview_mode = False

        # Clear markers
        for marker in self.img_markers:
            marker.remove()
        for marker in self.traj_markers:
            marker.remove()
        self.img_markers = []
        self.traj_markers = []

        # Clear text annotations (the number labels)
        for ax in [self.ax_img, self.ax_traj]:
            texts_to_remove = [child for child in ax.get_children()
                              if isinstance(child, plt.Text) and child.get_text().isdigit()]
            for text in texts_to_remove:
                text.remove()

        self._update_status("Reset complete. Click a point in the satellite image to start.")
        self.fig.canvas.draw()

    def _undo(self):
        """Undo the last point pair"""
        if len(self.image_points) == 0:
            self._update_status("Nothing to undo!")
            return

        self.image_points.pop()
        self.ground_points.pop()

        # Remove last markers
        if self.img_markers:
            self.img_markers[-1].remove()
            self.img_markers.pop()
        if self.traj_markers:
            self.traj_markers[-1].remove()
            self.traj_markers.pop()

        self.waiting_for_ground_point = False
        self.current_image_point = None

        n = len(self.image_points)
        self._update_status(f"Undone! Points: {n} | Need {max(0, 4-n)} more")
        self.fig.canvas.draw()

    def _update_status(self, message):
        """Update the status text"""
        self.status_text.set_text(message)
        self.fig.canvas.draw()

    def run(self):
        """Run the alignment tool"""
        print("\n" + "="*60)
        print("REFERENCE POINT ALIGNMENT TOOL")
        print("="*60)
        print("Instructions:")
        print("  1. Click a feature in the LEFT panel (satellite image)")
        print("  2. Click the SAME feature in the RIGHT panel (trajectories)")
        print("  3. Repeat for at least 4 point pairs")
        print("  4. Press 'C' to compute and preview alignment")
        print("  5. Press 'S' to save configuration")
        print("\nKeyboard shortcuts:")
        print("  C = Compute alignment")
        print("  S = Save configuration")
        print("  R = Reset all points")
        print("  U = Undo last point")
        print("  Q = Quit")
        print("="*60 + "\n")

        plt.show()


if __name__ == '__main__':
    aligner = ReferencePointAligner()
    aligner.run()
