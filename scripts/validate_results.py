"""
Validation script to analyze tracking results
Helps interpret if the algorithm is working correctly
"""

import json
import sys


def analyze_results(results_file):
    """
    Analyze tracking results and print validation metrics

    Args:
        results_file: Path to global_id_mapping.json
    """
    with open(results_file, 'r') as f:
        data = json.load(f)

    print("\n" + "="*70)
    print("TRACKING RESULTS ANALYSIS")
    print("="*70)

    # Overall statistics
    total_global_ids = len(data)
    print(f"\n📊 OVERALL STATISTICS:")
    print(f"   Total Global IDs: {total_global_ids}")

    # Analyze multi-camera vs single-camera tracks
    multi_camera = 0
    single_camera = 0
    camera_distribution = {}

    for global_id, cameras in data.items():
        num_cameras = len(cameras)

        if num_cameras > 1:
            multi_camera += 1
        else:
            single_camera += 1

        # Track camera distribution
        for camera in cameras.keys():
            camera_distribution[camera] = camera_distribution.get(camera, 0) + 1

    print(f"\n🎯 CROSS-CAMERA MATCHING:")
    print(f"   Multi-camera tracks: {multi_camera} ({multi_camera/total_global_ids*100:.1f}%)")
    print(f"   Single-camera tracks: {single_camera} ({single_camera/total_global_ids*100:.1f}%)")

    print(f"\n📹 CAMERA DISTRIBUTION:")
    for camera in sorted(camera_distribution.keys()):
        count = camera_distribution[camera]
        print(f"   {camera}: {count} vehicles")

    # Show examples of multi-camera matches
    print(f"\n✅ MULTI-CAMERA MATCH EXAMPLES:")
    count = 0
    for global_id, cameras in data.items():
        if len(cameras) > 1:
            print(f"\n   Global ID {global_id} (seen in {len(cameras)} cameras):")
            for camera, info in cameras.items():
                print(f"      - {camera}: Track {info['track_id']}")
            count += 1
            if count >= 5:  # Show first 5 examples
                break

    # Show examples of single-camera tracks
    print(f"\n📍 SINGLE-CAMERA EXAMPLES:")
    count = 0
    for global_id, cameras in data.items():
        if len(cameras) == 1:
            camera = list(cameras.keys())[0]
            track_id = cameras[camera]['track_id']
            print(f"   Global ID {global_id}: {camera} Track {track_id}")
            count += 1
            if count >= 5:
                break

    # Validation checks
    print(f"\n🔍 VALIDATION CHECKS:")

    # Check 1: Are there multi-camera matches?
    if multi_camera > 0:
        print(f"   ✅ Algorithm found {multi_camera} cross-camera matches")
    else:
        print(f"   ⚠️  No cross-camera matches found - check thresholds")

    # Check 2: Reasonable distribution
    if multi_camera > total_global_ids * 0.1:  # At least 10% multi-camera
        print(f"   ✅ Good cross-camera matching rate")
    else:
        print(f"   ⚠️  Low cross-camera matching - consider lowering thresholds")

    # Check 3: Camera coverage
    if len(camera_distribution) == 5:
        print(f"   ✅ All 5 cameras have detections")
    else:
        print(f"   ⚠️  Only {len(camera_distribution)}/5 cameras have detections")

    print("\n" + "="*70)
    print("INTERPRETATION GUIDE:")
    print("="*70)
    print("""
    ✅ GOOD SIGNS:
       - Multi-camera tracks > 10% of total
       - Examples show same vehicle across cameras
       - Camera distribution is balanced

    ⚠️  POTENTIAL ISSUES:
       - Very few multi-camera matches → Lower IOU_THRESHOLD
       - Too many multi-camera matches → Raise SCORE_THRESHOLD
       - Unbalanced cameras → Check data quality
    """)
    print("="*70 + "\n")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        results_file = sys.argv[1]
    else:
        results_file = 'output/test_sample_results.json'

    analyze_results(results_file)
