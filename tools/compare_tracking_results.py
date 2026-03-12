"""
Compare offline and real-time cross-camera tracking results
"""

import json
from pathlib import Path
from collections import Counter, defaultdict


def load_mapping(path):
    """Load global ID mapping from JSON file."""
    with open(path) as f:
        return json.load(f)


def analyze_mapping(mapping, name=""):
    """Analyze a global ID mapping."""

    print(f"\n{'='*70}")
    print(f"{name} ANALYSIS")
    print(f"{'='*70}\n")

    print(f"Total Global IDs: {len(mapping)}")

    # Count cameras per global ID
    cameras_per_id = []
    for global_id, cameras in mapping.items():
        cameras_per_id.append(len(cameras))

    camera_counts = Counter(cameras_per_id)

    print(f"\nGlobal IDs by camera count:")
    for num_cameras in sorted(camera_counts.keys(), reverse=True):
        count = camera_counts[num_cameras]
        pct = (count / len(mapping)) * 100
        print(f"  {num_cameras} camera(s): {count:4d} IDs ({pct:5.1f}%)")

    # Show examples of multi-camera IDs
    print(f"\nExample multi-camera IDs (first 5):")
    multi_cam_count = 0
    for global_id, cameras in mapping.items():
        if len(cameras) >= 2:
            camera_list = ', '.join(cameras.keys())
            print(f"  ID {global_id}: {camera_list}")
            multi_cam_count += 1
            if multi_cam_count >= 5:
                break

    return camera_counts


def compare_mappings(offline_path, realtime_path):
    """Compare offline and real-time mappings."""

    offline = load_mapping(offline_path)
    realtime = load_mapping(realtime_path)

    print(f"\n{'='*70}")
    print(f"COMPARISON: OFFLINE vs REAL-TIME")
    print(f"{'='*70}\n")

    print(f"Offline:   {len(offline):4d} global IDs")
    print(f"Real-time: {len(realtime):4d} global IDs")
    print(f"Difference: {abs(len(offline) - len(realtime)):4d} IDs")

    if len(offline) == len(realtime):
        print(f"\n✅ Same number of global IDs!")
    else:
        diff_pct = (abs(len(offline) - len(realtime)) / len(offline)) * 100
        print(f"\n⚠️  Difference: {diff_pct:.1f}%")

    # Build reverse mapping: (camera, track_id) -> global_id
    def build_reverse_mapping(mapping):
        reverse = {}
        for global_id, cameras in mapping.items():
            for camera_id, info in cameras.items():
                key = (camera_id, info['track_id'])
                reverse[key] = global_id
        return reverse

    offline_reverse = build_reverse_mapping(offline)
    realtime_reverse = build_reverse_mapping(realtime)

    # Find common tracks
    offline_tracks = set(offline_reverse.keys())
    realtime_tracks = set(realtime_reverse.keys())

    common_tracks = offline_tracks & realtime_tracks
    only_offline = offline_tracks - realtime_tracks
    only_realtime = realtime_tracks - offline_tracks

    print(f"\n📊 Track Coverage:")
    print(f"  Common tracks:        {len(common_tracks):4d}")
    print(f"  Only in offline:      {len(only_offline):4d}")
    print(f"  Only in real-time:    {len(only_realtime):4d}")

    if len(only_offline) > 0:
        print(f"\n  Example tracks only in offline (first 5):")
        for track in list(only_offline)[:5]:
            print(f"    {track[0]} track {track[1]}")

    if len(only_realtime) > 0:
        print(f"\n  Example tracks only in real-time (first 5):")
        for track in list(only_realtime)[:5]:
            print(f"    {track[0]} track {track[1]}")

    # Check grouping consistency
    print(f"\n🔍 Grouping Consistency Check:")

    # For each offline global ID, check if same tracks are grouped in real-time
    consistent_groups = 0
    total_groups = 0

    for offline_gid, offline_cameras in offline.items():
        # Get all tracks in this offline group
        offline_group_tracks = set()
        for cam_id, info in offline_cameras.items():
            offline_group_tracks.add((cam_id, info['track_id']))

        # Skip if any tracks not in real-time
        if not offline_group_tracks.issubset(realtime_tracks):
            continue

        # Find which real-time global IDs these tracks belong to
        realtime_gids = set()
        for track in offline_group_tracks:
            if track in realtime_reverse:
                realtime_gids.add(realtime_reverse[track])

        total_groups += 1

        # If all tracks map to same real-time global ID, grouping is consistent
        if len(realtime_gids) == 1:
            consistent_groups += 1

    if total_groups > 0:
        consistency_pct = (consistent_groups / total_groups) * 100
        print(f"  Consistent groups: {consistent_groups}/{total_groups} ({consistency_pct:.1f}%)")

        if consistency_pct >= 95:
            print(f"\n  ✅ Excellent consistency! Tracking is nearly identical.")
        elif consistency_pct >= 80:
            print(f"\n  ⚠️  Good consistency, but some differences exist.")
        else:
            print(f"\n  ❌ Low consistency - significant differences in grouping.")

    # Summary
    print(f"\n{'='*70}")
    print(f"SUMMARY")
    print(f"{'='*70}\n")

    if len(offline) == len(realtime) and len(only_offline) == 0 and len(only_realtime) == 0:
        print(f"✅ PERFECT MATCH!")
        print(f"   - Same number of global IDs")
        print(f"   - Same tracks detected")
        print(f"   - Offline and real-time are equivalent")
    elif abs(len(offline) - len(realtime)) <= 10 and len(common_tracks) / len(offline_tracks) > 0.95:
        print(f"✅ VERY CLOSE MATCH!")
        print(f"   - Similar number of global IDs (±{abs(len(offline) - len(realtime))})")
        print(f"   - {len(common_tracks)/len(offline_tracks)*100:.1f}% track overlap")
        print(f"   - Minor differences acceptable")
    else:
        print(f"⚠️  SIGNIFICANT DIFFERENCES")
        print(f"   - Different number of global IDs")
        print(f"   - Track coverage differs")
        print(f"   - May indicate data loss or timing issues")


def main():
    offline_path = Path('output/global_id_mapping_offline.json')
    realtime_path = Path('output/global_id_mapping.json')

    if not offline_path.exists():
        print(f"❌ Offline mapping not found: {offline_path}")
        print(f"   Run: python run_tracking.py")
        print(f"   Then: copy output\\global_id_mapping.json output\\global_id_mapping_offline.json")
        return

    if not realtime_path.exists():
        print(f"❌ Real-time mapping not found: {realtime_path}")
        print(f"   Run: run_integrated_system.bat")
        return

    # Analyze each mapping
    analyze_mapping(load_mapping(offline_path), "OFFLINE")
    analyze_mapping(load_mapping(realtime_path), "REAL-TIME")

    # Compare
    compare_mappings(offline_path, realtime_path)


if __name__ == "__main__":
    main()
