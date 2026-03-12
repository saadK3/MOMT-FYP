"""
Camera Sender - Simulates a single camera streaming detection packets
A `CameraSender` instance represents ONE physical camera.
"""
import asyncio
import logging
import time
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class CameraSender:
    """
    Simulates a single camera emitting detection packets at a fixed FPS.
    """

    def __init__(self,
                 camera_id: str,
                 fps: int,
                 detections_by_timestamp: Dict[float, List[Dict]],
                 start_time: float,
                 end_time: float,
                 sentence_word: str,
                 time_offset: float = 0.0,
                 loop_enabled: bool = False):
        """
        Initialize camera sender.

        Args:
            camera_id: Camera identifier (e.g., 'c001')
            fps: Frames per second to emit
            detections_by_timestamp: Detection data organized by timestamp
            start_time: Start timestamp (seconds)
            end_time: End timestamp (seconds)
            sentence_word: Word(s) assigned to this camera for visualization
            time_offset: Time offset to synchronize local time to global time (seconds)
            loop_enabled: If True, restart from start_time when end_time is reached
        """
        # real time simulation
        self.camera_id = camera_id
        self.fps = fps
        self.frame_duration_s = 1.0 / fps
        self.time_offset = time_offset  # Offset to convert local time -> global time
        self.loop_enabled = loop_enabled  # Enable infinite looping

        # static dataset the camera will replay. data never changes only the _current_timestamp moves.
        self.detections_by_timestamp = detections_by_timestamp
        self.start_time = start_time
        self.end_time = end_time
        self.sentence_word = sentence_word

        self._on_status = True
        self._current_timestamp = start_time

        logger.info(f"[{self.camera_id}] Initialized. FPS: {fps}, "
                   f"Time range: {start_time:.1f}s - {end_time:.1f}s, "
                   f"Word: '{sentence_word}'")

    def _get_detections_at_timestamp(self, timestamp: float, tolerance: float = 0.05) -> List[Dict]:
        """
        Get detections at a specific timestamp (with tolerance).

        Args:
            timestamp: Target timestamp
            tolerance: Time tolerance in seconds

        Returns:
            List of detections
        """
        # Look for exact match first
        if timestamp in self.detections_by_timestamp:
            return self.detections_by_timestamp[timestamp]

        # Search within tolerance
        for ts, dets in self.detections_by_timestamp.items():
            if abs(ts - timestamp) < tolerance:
                return dets

        return []

    def _create_packet(self) -> Dict:
        """
        Create a detection packet for the current timestamp.

        Returns:
            Packet dictionary
        """
        detections = self._get_detections_at_timestamp(self._current_timestamp)

        # Calculate frame number (approximate)
        frame = int((self._current_timestamp - self.start_time) * self.fps)

        # Apply time offset to convert local camera time to global synchronized time
        # ADD offset because: if c002 started 1.64s AFTER c001, then
        # c002's local t=5.0s happened at global t=5.0+1.64=6.64s (later in real-world time)
        # So: global_time = local_time + offset
        global_timestamp = self._current_timestamp + self.time_offset

        # Debug logging for first few packets
        if self._current_timestamp <= self.start_time + 5.0:
            logger.info(f"[{self.camera_id}] Sync check: "
                       f"local={self._current_timestamp:.3f}s + offset={self.time_offset:.3f}s = "
                       f"global={global_timestamp:.3f}s")

        packet = {
            'type': 'packet',
            'camera_id': self.camera_id,
            'timestamp': global_timestamp,  # Synchronized global timestamp
            'local_timestamp': self._current_timestamp,  # Original local timestamp (for debugging)
            'frame': frame,
            'ts_send_ms': int(time.time() * 1000),
            'ts_recv_ms': 0,  # Will be set by Hub
            'sentence_word': self.sentence_word,
            'detections': detections
        }

        return packet

    # Toggle to set the camera on/off
    def toggle(self, status: bool):
        """Toggle camera ON/OFF."""
        if self._on_status != status:
            self._on_status = status
            logger.info(f"[{self.camera_id}] Status set to {'ON' if status else 'OFF'}")

    async def run(self, output_queue: asyncio.Queue):
        """
        Main simulation loop - emits packets at fixed FPS.

        Args:
            output_queue: Queue to send packets to
        """
        logger.info(f"[{self.camera_id}] Starting emission loop (loop={'enabled' if self.loop_enabled else 'disabled'})...")

        while True:  # Infinite loop if loop_enabled, otherwise breaks at end
            loop_start_time = time.monotonic()

            if self._on_status:
                # Create and send packet
                packet = self._create_packet()
                await output_queue.put(packet)

                if packet['detections']:
                    logger.debug(f"[{self.camera_id}] Sent packet @ t={self._current_timestamp:.1f}s "
                               f"({len(packet['detections'])} detections)")

            # Increment timestamp
            self._current_timestamp += self.frame_duration_s

            # Check if we've reached the end
            if self._current_timestamp > self.end_time:
                if self.loop_enabled:
                    # Loop back to start
                    # IMPORTANT: All cameras must restart at the same GLOBAL time (GLOBAL_START_TIME)
                    # This means each camera restarts at its original local start time
                    # which was calculated as: local_start = GLOBAL_START - offset
                    # This ensures synchronization is maintained across loops
                    logger.info(f"[{self.camera_id}] Reached end @ t={self.end_time:.1f}s, "
                               f"looping back to local t={self.start_time:.1f}s "
                               f"(global t={self.start_time + self.time_offset:.1f}s)")
                    self._current_timestamp = self.start_time
                else:
                    # Exit loop
                    logger.info(f"[{self.camera_id}] Emission complete @ t={self.end_time:.1f}s")
                    break

            # FPS throttling
            elapsed_s = time.monotonic() - loop_start_time
            sleep_s = self.frame_duration_s - elapsed_s

            if sleep_s > 0:
                await asyncio.sleep(sleep_s)


"""
From the tracker's point of view, this camera:
> emits one packet per second
-packets may have:
    zero detections
    multiple detections

> timestamps are consistent
>packets may arrive late or be dropped(later)
"""
