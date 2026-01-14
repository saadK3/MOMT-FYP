"""
Test script to run cross-camera tracking on a small sample with timestamp synchronization
"""

from cross_camera_tracking.data_loader import load_all_cameras
from cross_camera_tracking.tracker import CrossCameraTracker
from cross_camera_tracking.utils import create_output_dirs
from cross_camera_tracking.config import OUTPUT_DIR


def main():
    """Test on first 5 seconds"""

    # Create output directories
    print("Setting up output directories...")
    create_output_dirs(OUTPUT_DIR)

    # Load camera data
    print("\nLoading camera data...")
    all_camera_data = load_all_cameras()

    # Initialize tracker
    print("\nInitializing tracker...")
    tracker = CrossCameraTracker()

    # Run tracking on SAMPLE timestamps (0-5 seconds)
    print("\nRunning cross-camera tracking on SAMPLE (0-5 seconds)...")
    results = tracker.run(all_camera_data, start_time=0.0, end_time=5.0, time_step=0.1)

    # Export results
    print("\nExporting results...")
    output = tracker.export_results(f'{OUTPUT_DIR}/test_sample_results.json')

    # Print summary
    print("\n" + "="*70)
    print("TEST COMPLETE - RESULTS SUMMARY")
    print("="*70)
    print(f"Total Global IDs assigned: {results['total_global_ids']}")
    print(f"\nSample Global ID assignments:")

    # Show first 5 Global IDs
    for i, (global_id, cameras) in enumerate(list(output.items())[:5]):
        print(f"\n  Global ID {global_id}:")
        for camera, info in cameras.items():
            print(f"    - {camera}: Track {info['track_id']}")

    print("\n" + "="*70)
    print(f"Full results saved to: {OUTPUT_DIR}/test_sample_results.json")
    print("="*70)


if __name__ == "__main__":
    main()
