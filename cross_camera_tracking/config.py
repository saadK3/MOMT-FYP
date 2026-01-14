"""
Configuration file for cross-camera tracking algorithm
Contains all hyperparameters and settings
"""

# ============================================
# MATCHING THRESHOLDS
# ============================================
IOU_THRESHOLD = 0.3              # Minimum IOU to consider a match
SCORE_THRESHOLD = 0.3            # Minimum IOU score for clustering (same as IOU_THRESHOLD)

# ============================================
# MATCHING SCORE WEIGHTS
# ============================================
# Using IOU only (orientation constraint removed)
# Vehicle class is a hard constraint (not weighted)

# ============================================
# CAMERA CONFIGURATION
# ============================================
CAMERAS = ['c001', 'c002', 'c003', 'c004', 'c005']
JSON_DIR = 'json'
VIDEO_DIR = 'videos'
OUTPUT_DIR = 'output'

# Camera time offsets (in seconds)
# These account for different start times across cameras
CAMERA_TIME_OFFSETS = {
    'c001': 0.0,
    'c002': 1.640,
    'c003': 2.049,
    'c004': 2.177,
    'c005': 2.235
}

# Timestamp matching tolerance (in seconds)
# At 10 FPS, frames are 0.1s apart, so 0.05s = half a frame
TIMESTAMP_TOLERANCE = 0.05

# ============================================
# KEYPOINT CONFIGURATION
# ============================================
FOOTPRINT_INDICES = [12, 13, 14, 15]  # Ground contact points
# Indices: [front-left, front-right, rear-left, rear-right]

# ============================================
# FILE NAMING
# ============================================
JSON_PATTERN = 'S01_{camera}_tracks_data.json'
VIDEO_PATTERN = 'S01_{camera}.mp4'
