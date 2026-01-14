"""
Calculate coordinate bounds from tracking data
This tells you what area to capture in Google Earth
"""

import json
import numpy as np
from pathlib import Path

# Paths
JSON_DIR = Path('json')
OUTPUT_FILE = 'tools/coordinate_bounds.txt'

def calculate_bounds():
    """Calculate min/max coordinates from all tracking data"""

    all_x = []
    all_y = []

    # Read all camera tracking files
    json_files = list(JSON_DIR.glob('S01_c*_tracks_data.json'))

    print(f"Reading {len(json_files)} camera files...")

    for json_file in json_files:
        print(f"  Processing {json_file.name}...")

        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Extract all birdeye coordinates
        for track in data['tracks']:
            for det in track['dets']:
                birdeye = det['det_birdeye']
                # birdeye has 8 values: [x1, y1, x2, y2, x3, y3, x4, y4]
                all_x.extend([birdeye[0], birdeye[2], birdeye[4], birdeye[6]])
                all_y.extend([birdeye[1], birdeye[3], birdeye[5], birdeye[7]])

    # Calculate bounds
    min_x = min(all_x)
    max_x = max(all_x)
    min_y = min(all_y)
    max_y = max(all_y)

    center_x = (min_x + max_x) / 2
    center_y = (min_y + max_y) / 2

    width = max_x - min_x
    height = max_y - min_y

    # Add 20% buffer
    buffer = 0.2
    buffered_width = width * (1 + buffer)
    buffered_height = height * (1 + buffer)

    # Results
    results = f"""
================================================================================
          COORDINATE BOUNDS ANALYSIS
================================================================================

TRACKING AREA BOUNDS:
   Min X: {min_x:,.2f}
   Max X: {max_x:,.2f}
   Min Y: {min_y:,.2f}
   Max Y: {max_y:,.2f}

DIMENSIONS:
   Width:  {width:,.2f} units
   Height: {height:,.2f} units

CENTER POINT:
   X: {center_x:,.2f}
   Y: {center_y:,.2f}

RECOMMENDED CAPTURE AREA (with 20% buffer):
   Width:  {buffered_width:,.2f} units
   Height: {buffered_height:,.2f} units

COORDINATE SYSTEM NOTES:
   - Your coordinates appear to be in a PROJECTED coordinate system
   - Format: {min_x:,.2f} (not lat/lon)
   - Likely UTM or similar projection

TO FIND THIS LOCATION IN GOOGLE EARTH:

   Option 1: If you know the lat/lon of your intersection
   - Navigate to that location in Google Earth
   - Zoom to show an area roughly {buffered_width:,.0f} x {buffered_height:,.0f} units

   Option 2: Use existing ground plane image
   - Check if 'unified_ground_plane_frame10.png' shows this area
   - It might already be perfectly aligned!

SAMPLE COORDINATES (for verification):
   First detection: ({all_x[0]:,.2f}, {all_y[0]:,.2f})
   Last detection:  ({all_x[-1]:,.2f}, {all_y[-1]:,.2f})

NEXT STEPS:
   1. Check 'unified_ground_plane_frame10.png' first
   2. If not suitable, capture from Google Earth
   3. Run 'python tools/alignment_verification.py' to verify alignment

"""

    print(results)

    # Save to file
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(results)

    print(f"\nResults saved to: {OUTPUT_FILE}")

    # Return data for potential use
    return {
        'bounds': {
            'min_x': min_x,
            'max_x': max_x,
            'min_y': min_y,
            'max_y': max_y
        },
        'center': {
            'x': center_x,
            'y': center_y
        },
        'dimensions': {
            'width': width,
            'height': height
        },
        'buffered_dimensions': {
            'width': buffered_width,
            'height': buffered_height
        }
    }

if __name__ == '__main__':
    calculate_bounds()
