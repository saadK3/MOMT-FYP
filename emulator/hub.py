"""
Hub Aggregator - Collects packets from all cameras and makes decisions
"""
import asyncio
import logging
import time
from typing import Dict, List, Set, Any
from collections import defaultdict

logger = logging.getLogger(__name__)


class Hub:
    """
    Central aggregator that collects packets and decides when to process.
    """

    def __init__(self,
                 camera_ids: List[str],
                 camera_time_offsets: Dict[str, float],
                 watermark_ms: int = 200,
                 quorum: int = 3,
                 time_step: float = 0.1):
        """
        Initialize hub aggregator.

        Args:
            camera_ids: List of camera IDs
            camera_time_offsets: Time offsets for synchronization
            watermark_ms: Maximum wait time for packets (milliseconds)
            quorum: Minimum cameras needed for partial decision
            time_step: Time step for bucketing (seconds)
        """
        self.camera_ids = camera_ids
        self.camera_time_offsets = camera_time_offsets
        self.watermark_ms = watermark_ms
        self.quorum = quorum
        self.time_step = time_step

        # Internal state
        self._frame_buckets: Dict[float, Dict[str, Dict]] = {}  # {timestamp: {camera_id: packet}}
        self._frame_timers: Dict[float, asyncio.Task] = {}
        # stored when the first packet arrives for a given timestamp.
        self._frame_first_arrival: Dict[float, int] = {}  # {timestamp: first_arrival_ms}

        logger.info(f"[Hub] Initialized. Watermark: {watermark_ms}ms, Quorum: {quorum}")

    def _get_synchronized_timestamp(self, camera_id: str, original_timestamp: float) -> float:
        """Apply camera time offset for synchronization."""
        offset = self.camera_time_offsets.get(camera_id, 0.0)
        return original_timestamp + offset

    def _get_bucket_key(self, synced_timestamp: float) -> float:
        """Round timestamp to nearest time step for bucketing."""
        return round(synced_timestamp / self.time_step) * self.time_step


    async def _handle_packet(self, packet: Dict):
        """Process incoming packet."""
        camera_id = packet['camera_id']
        original_timestamp = packet['timestamp']

        # Timestamps are already synchronized by CameraSenders (they apply time_offset when creating packets)
        # So we can use the timestamp directly for bucketing
        bucket_key = self._get_bucket_key(original_timestamp)

        # Initialize bucket if new
        if bucket_key not in self._frame_buckets:
            self._frame_buckets[bucket_key] = {}
            self._frame_first_arrival[bucket_key] = int(time.time() * 1000)

            # Start watermark timer
            self._frame_timers[bucket_key] = asyncio.create_task(
                self._start_watermark_timer(bucket_key)
            )

            logger.debug(f"[Hub] New bucket @ t={bucket_key:.1f}s")

        # Check for duplicate
        if camera_id in self._frame_buckets[bucket_key]:
            logger.debug(f"[Hub] Duplicate packet from {camera_id} @ t={bucket_key:.1f}s")
            return

        # Store packet
        self._frame_buckets[bucket_key][camera_id] = packet
        arrived_cameras = set(self._frame_buckets[bucket_key].keys())

        logger.debug(f"[Hub] Packet from {camera_id} @ t={bucket_key:.1f}s "
                    f"({len(arrived_cameras)}/{len(self.camera_ids)} arrived)")

        # Check for early completion
        if len(arrived_cameras) == len(self.camera_ids):
            logger.debug(f"[Hub] COMPLETE (early) @ t={bucket_key:.1f}s")
            # Cancel timer and make decision
            if bucket_key in self._frame_timers:
                self._frame_timers[bucket_key].cancel()
                del self._frame_timers[bucket_key]
            await self._make_decision(bucket_key, "complete")

    async def _start_watermark_timer(self, bucket_key: float):
        """Watermark timer for a specific timestamp bucket."""
        try:
            await asyncio.sleep(self.watermark_ms / 1000.0)
            # Timer expired - make decision
            await self._on_watermark_expiry(bucket_key)
        except asyncio.CancelledError:
            # Early completion - timer cancelled
            pass

    async def _on_watermark_expiry(self, bucket_key: float):
        """Handle watermark expiry."""
        if bucket_key not in self._frame_buckets:
            return

        arrived_cameras = set(self._frame_buckets[bucket_key].keys())
        num_arrived = len(arrived_cameras)

        if num_arrived >= len(self.camera_ids):
            decision = "complete"
        elif num_arrived >= self.quorum:
            decision = "partial"
        else:
            decision = "drop"

        logger.debug(f"[Hub] Watermark expired @ t={bucket_key:.1f}s -> {decision.upper()}")
        await self._make_decision(bucket_key, decision)

    async def _make_decision(self, bucket_key: float, decision: str):
        """Make final decision and emit event."""
        if bucket_key not in self._frame_buckets:
            return

        arrived_cameras = list(self._frame_buckets[bucket_key].keys())
        missing_cameras = [c for c in self.camera_ids if c not in arrived_cameras]

        first_arrival_ms = self._frame_first_arrival.get(bucket_key, 0)
        decision_ms = int(time.time() * 1000)
        latency_ms = decision_ms - first_arrival_ms

        # Build sentence status
        sentence_status = {}
        for camera_id in self.camera_ids:
            if camera_id in self._frame_buckets[bucket_key]:
                packet = self._frame_buckets[bucket_key][camera_id]
                sentence_status[camera_id] = {
                    'word': packet['sentence_word'],
                    'arrived': True,
                    'delay_ms': packet.get('actual_delay_ms', 0),
                    'detections': packet.get('detections', [])  # Include detections for tracking
                }
            else:
                sentence_status[camera_id] = {
                    'word': '',
                    'arrived': False,
                    'delay_ms': 0
                }

        # Create decision event
        decision_event = {
            'type': 'decision',
            'timestamp': bucket_key,
            'decision': decision,
            'arrived_cameras': arrived_cameras,
            'missing_cameras': missing_cameras,
            'latency_ms': latency_ms,
            'sentence_status': sentence_status,
            'ts_decision_ms': decision_ms
        }

        # Emit decision (will be sent to WebSocket)
        await self.decision_queue.put(decision_event)

        logger.info(f"[Hub] Decision @ t={bucket_key:.1f}s: {decision.upper()} "
                   f"({len(arrived_cameras)}/{len(self.camera_ids)} cameras, {latency_ms}ms)")

        # Cleanup
        del self._frame_buckets[bucket_key]
        if bucket_key in self._frame_first_arrival:
            del self._frame_first_arrival[bucket_key]
        if bucket_key in self._frame_timers:
            del self._frame_timers[bucket_key]

    async def run(self, input_queue: asyncio.Queue, decision_queue: asyncio.Queue):
        """
        Main loop - consume packets from network simulator.

        Args:
            input_queue: Queue to receive packets from network simulator
            decision_queue: Queue to send decision events to
        """
        self.decision_queue = decision_queue
        logger.info("[Hub] Starting aggregation loop...")

        while True:
            try:
                packet = await input_queue.get()
                await self._handle_packet(packet)
                input_queue.task_done()

            except asyncio.CancelledError:
                logger.info("[Hub] Aggregation loop stopping")
                # Cancel all timers
                for timer in self._frame_timers.values():
                    timer.cancel()
                break
            except Exception as e:
                logger.error(f"[Hub] Error: {e}", exc_info=True)
