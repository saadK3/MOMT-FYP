"""
Analyze camera time synchronization for cross-camera tracking
"""
import json
from pathlib import Path

# Camera time offsets (from config.py)
CAMERA_TIME_OFFSETS = {
    'c001': 0.000,
    'c002': 1.640,
    'c003': 2.049,
    'c004': 2.177,
    'c005': 2.235
}

cameras = ['c001', 'c002', 'c003', 'c004', 'c005']

print("="*70)
print("CAMERA TIME SYNCHRONIZATION ANALYSIS")
print("="*70)

print("\n📊 LOCAL vs GLOBAL TIME RANGES:")
print("-"*70)

global_min_all = float('inf')
global_max_all = 0.0

for cam in cameras:
    json_path = Path('json') / f'S01_{cam}_tracks_data.json'
    with open(json_path) as f:
        data = json.load(f)

    timestamps = [
        det['det_timestamp']
        for track in data['tracks']
        for det in track['dets']
    ]

    local_min = min(timestamps)
    local_max = max(timestamps)
    offset = CAMERA_TIME_OFFSETS[cam]

    # Global time = local time + offset
    global_min = local_min + offset
    global_max = local_max + offset

    global_min_all = min(global_min_all, global_min)
    global_max_all = max(global_max_all, global_max)

    print(f"{cam}: local [{local_min:6.1f}s - {local_max:6.1f}s] "
          f"→ global [{global_min:6.1f}s - {global_max:6.1f}s]")

print("-"*70)
print(f"\n🌐 SYNCHRONIZED GLOBAL TIME RANGE:")
print(f"   Start: {global_min_all:.1f}s")
print(f"   End:   {global_max_all:.1f}s")
print(f"   Duration: {global_max_all - global_min_all:.1f}s")

print("\n"+"="*70)
print("OVERLAP ANALYSIS")
print("="*70)

# Find common overlap where all cameras have data
print("\n📍 When do all 5 cameras have data?")
print("-"*70)

camera_ranges = {}
for cam in cameras:
    json_path = Path('json') / f'S01_{cam}_tracks_data.json'
    with open(json_path) as f:
        data = json.load(f)

    timestamps = [
        det['det_timestamp']
        for track in data['tracks']
        for det in track['dets']
    ]

    local_min = min(timestamps)
    local_max = max(timestamps)
    offset = CAMERA_TIME_OFFSETS[cam]

    global_min = local_min + offset
    global_max = local_max + offset

    camera_ranges[cam] = (global_min, global_max)
    print(f"{cam}: {global_min:6.1f}s - {global_max:6.1f}s")

# Find overlap
overlap_start = max(start for start, _ in camera_ranges.values())
overlap_end = min(end for _, end in camera_ranges.values())

print("-"*70)
if overlap_start < overlap_end:
    print(f"\n✅ ALL 5 CAMERAS OVERLAP:")
    print(f"   Time range: {overlap_start:.1f}s - {overlap_end:.1f}s")
    print(f"   Duration: {overlap_end - overlap_start:.1f}s")
else:
    print(f"\n❌ NO COMPLETE OVERLAP")
    print(f"   Gap: {overlap_start:.1f}s - {overlap_end:.1f}s")

print("\n"+"="*70)
print("RECOMMENDATION")
print("="*70)

print(f"""
For cross-camera tracking, you need temporal synchronization.

Option 1: USE OVERLAP RANGE (RECOMMENDED)
   - Time range: {overlap_start:.1f}s - {overlap_end:.1f}s
   - All 5 cameras have data
   - Perfect synchronization
   - Duration: {overlap_end - overlap_start:.1f}s

Option 2: USE FULL RANGE (with buffering)
   - Time range: {global_min_all:.1f}s - {global_max_all:.1f}s
   - Some periods have <5 cameras
   - Requires buffering/matching logic
   - Duration: {global_max_all - global_min_all:.1f}s
""")
