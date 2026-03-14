# Emulator configuration
# Contains all settings for the packet emulator

# Camera settings
# naming is deteministic and scalable (add c006 and json files)
CAMERAS = ['c001', 'c002', 'c003', 'c004', 'c005']
JSON_DIR = 'data'
JSON_PATTERN = 'S01_{camera}_tracks_data.json'

# Camera time offsets (in seconds) - for timestamp synchronization
# These offsets represent how much LATER each camera started recording compared to c001.
# We ADD the offset to align to global time: global_time = local_time + offset
# Example: c002 started 1.64s after c001, so c002's local t=5.0s = global t=6.64s
CAMERA_TIME_OFFSETS = {
    'c001': 0.0,
    'c002': 1.640,
    'c003': 2.049,
    'c004': 2.177,
    'c005': 2.235
}

# Emulator settings
FPS = 10 # Slow down to 1 frame per second for better visualization
TIME_STEP = 1 / FPS  # 1/FPS = 1.0 seconds

# Time range to emulate (in seconds)
# Global clock strategy: use full timeline where all cameras have data
# Cameras start/stop naturally at their data boundaries
GLOBAL_START_TIME = 1.6    # Earliest camera start (c002 at local 0.0s + offset 1.6s)
GLOBAL_END_TIME = 213.1    # Latest camera end (c004/c005 at local 210.9s + offset 2.2s)
LOOP_ENABLED = True        # Loop continuously for live dashboard

# Network simulation defaults
BASE_LATENCY_MS = 0
JITTER_MS = 0
PACKET_LOSS_PROB = 0.0  # 1% packet loss

# Hub aggregator settings
WATERMARK_MS = 200  # Wait up to 200ms for late packets before making decision
QUORUM = 1          # Minimum cameras required for decision (1 = accept all detections)

# WebSocket server
WS_HOST = 'localhost'
WS_PORT = 8765

# Sentence words for visualization (assigned to cameras)
SENTENCE_WORDS = {
    'c001': 'The quick',
    'c002': 'brown fox',
    'c003': 'jumps over',
    'c004': 'the lazy',
    'c005': 'dog'
}
