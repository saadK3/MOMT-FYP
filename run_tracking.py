"""
Main script to run cross-camera tracking algorithm
"""

from cross_camera_tracking.data_loader import load_all_cameras
from cross_camera_tracking.tracker import CrossCameraTracker
from cross_camera_tracking.utils import create_output_dirs
from cross_camera_tracking.config import OUTPUT_DIR


def main():
    """Main execution function"""

    # Create output directories
    print("Setting up output directories...")
    create_output_dirs(OUTPUT_DIR)

    # Load camera data
    print("\nLoading camera data...")
    all_camera_data = load_all_cameras()

    # Initialize tracker
    print("\nInitializing tracker...")
    tracker = CrossCameraTracker()

    # Run tracking algorithm
    print("\nRunning cross-camera tracking...")
    results = tracker.run(all_camera_data)

    # Export results
    print("\nExporting results...")
    tracker.export_results()

    print("\n✅ Cross-camera tracking complete!")
    print(f"   Total Global IDs: {results['total_global_ids']}")
    print(f"   Output saved to: {OUTPUT_DIR}/global_id_mapping.json")


if __name__ == "__main__":
    main()
