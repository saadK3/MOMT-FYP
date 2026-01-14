# Emulator configuration
# Contains all settings for the packet emulator

# Camera settings
# naming is deteministic and scalable (add c006 and json files)
CAMERAS = ['c001', 'c002', 'c003', 'c004', 'c005']
JSON_DIR = 'json'
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
FPS = 1  # Slow down to 1 frame per second for better visualization
TIME_STEP = 1.0  # 1/FPS = 1.0 seconds

# Time range to emulate (in seconds)
# GLOBAL_START_TIME is the synchronized global time where all cameras begin
# Each camera will start at a different LOCAL time: local_start = GLOBAL_START - offset
GLOBAL_START_TIME = 2.235  # Set to max(CAMERA_TIME_OFFSETS) to avoid negative local times
END_TIME = 60.0  # Extended to 60 seconds for longer demo
LOOP_ENABLED = True  # If True, restart from GLOBAL_START_TIME when END_TIME is reached

# Network simulation defaults
BASE_LATENCY_MS = 60
JITTER_MS = 120
PACKET_LOSS_PROB = 0.01  # 1% packet loss

# Hub aggregator settings
WATERMARK_MS = 200  # Wait up to 200ms for packets
QUORUM = 3  # Minimum cameras needed for partial decision

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
