"""
Unified Tracking Server
=======================
Single backend process that:
1. Runs the emulator pipeline (CameraSenders -> NetworkSim -> Hub) internally
2. Processes decisions through CrossCameraTracker in real-time
3. Broadcasts tracking results to browser clients via WebSocket

This replaces running emulator/app.py and run_tracking_realtime.py separately.
"""

import asyncio
import json
import logging
import sys
import time
from pathlib import Path
from typing import Dict, Set
from collections import defaultdict

import websockets

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from emulator import config as emulator_config
from emulator.json_reader import load_all_cameras
from emulator.camera_sender import CameraSender
from emulator.network_sim import NetworkSimulator
from emulator.hub import Hub

from cross_camera_tracking.tracker import CrossCameraTracker
from cross_camera_tracking.matching import build_score_matrix
from cross_camera_tracking.clustering import agglomerative_clustering
from cross_camera_tracking.geometry import compute_centroid
from cross_camera_tracking.journey_archive import JourneyArchive

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Color utility — assign a stable HSL color from a global_id
# ---------------------------------------------------------------------------
def id_to_color(global_id: int) -> str:
    """Deterministic HSL color from a global ID (golden-angle spacing)."""
    hue = (global_id * 137.508) % 360  # golden angle for even spread
    return f"hsla({hue:.0f}, 75%, 55%, 0.75)"


# ---------------------------------------------------------------------------
# TrackerService — consumes decisions, runs tracking, produces results
# ---------------------------------------------------------------------------
class TrackerService:
    """
    Sits between the Hub output queue and the WebSocket broadcast queue.
    Consumes 'decision' events, runs the cross-camera matching/clustering
    algorithm, and emits 'tracking_update' messages ready for the frontend.
    """

    def __init__(self):
        self.tracker = CrossCameraTracker()
        self.processed_timestamps: set = set()
        self.total_decisions = 0
        self.total_detections = 0
        self.camera_journeys: Dict[int, Dict] = {}
        self.recent_camera_events = []
        self.max_recent_camera_events = 50

    # --- detection extraction (same logic as EmulatorClient) ---------------
    @staticmethod
    def _extract_detections(decision_event: Dict) -> list:
        """Convert a hub decision event into tracker-format detections."""
        detections = []
        timestamp = decision_event["timestamp"]
        sentence_status = decision_event.get("sentence_status", {})

        for camera_id, camera_data in sentence_status.items():
            if not camera_data.get("arrived", False):
                continue
            for det in camera_data.get("detections", []):
                detections.append({
                    "camera": camera_id,
                    "track_id": det.get("track_id", 0),
                    "footprint": det.get("det_birdeye", []),
                    "class": det.get("det_kp_class_name", "unknown"),
                    "timestamp": timestamp,
                    "frame": int(det.get("det_impath", 0)),
                })
        return detections

    @staticmethod
    def _normalize_camera_state(cameras) -> list:
        """Return a stable, deduplicated camera-state list."""
        return sorted(set(cameras))

    @staticmethod
    def _camera_state_label(camera_state: list) -> str:
        """Human-friendly label for one or more active cameras."""
        if not camera_state:
            return "Unknown"
        return " + ".join(camera.upper() for camera in camera_state)

    def _serialize_camera_journey(self, global_id: int) -> Dict:
        """Convert an internal journey record into a JSON-safe payload."""
        record = self.camera_journeys[global_id]
        return {
            "global_id": global_id,
            "current_camera_state": record["current_camera_state"],
            "current_camera_label": self._camera_state_label(
                record["current_camera_state"]
            ),
            "previous_camera_state": record["previous_camera_state"],
            "previous_camera_label": (
                self._camera_state_label(record["previous_camera_state"])
                if record["previous_camera_state"]
                else None
            ),
            "unique_cameras": record["unique_cameras"],
            "transition_count": record["transition_count"],
            "has_camera_changed": record["has_camera_changed"],
            "last_seen_at": round(record["last_seen_at"], 2),
            "journey": [
                {
                    "camera_state": segment["camera_state"],
                    "camera_label": self._camera_state_label(
                        segment["camera_state"]
                    ),
                    "entered_at": round(segment["entered_at"], 2),
                    "last_seen_at": round(segment["last_seen_at"], 2),
                }
                for segment in record["journey"]
            ],
            "last_transition": record["last_transition"],
        }

    def build_camera_journey_snapshot(self) -> Dict:
        """Build a complete snapshot for newly connected dashboard clients."""
        return {
            "type": "camera_journey_snapshot",
            "journeys": {
                str(global_id): self._serialize_camera_journey(global_id)
                for global_id in sorted(self.camera_journeys)
            },
            "recent_events": self.recent_camera_events,
        }

    def _record_camera_journey(
        self, global_id: int, camera_state: list, timestamp: float
    ):
        """
        Update a global ID's camera journey.

        Returns:
            tuple[bool, dict | None]:
                bool -> whether the serialized journey should be sent to clients
                dict -> camera-change event payload if a transition happened
        """
        record = self.camera_journeys.get(global_id)

        if record is None:
            self.camera_journeys[global_id] = {
                "current_camera_state": camera_state,
                "previous_camera_state": None,
                "unique_cameras": camera_state[:],
                "transition_count": 0,
                "has_camera_changed": False,
                "last_seen_at": timestamp,
                "journey": [
                    {
                        "camera_state": camera_state,
                        "entered_at": timestamp,
                        "last_seen_at": timestamp,
                    }
                ],
                "last_transition": None,
            }
            return True, None

        record["last_seen_at"] = timestamp
        current_segment = record["journey"][-1]

        if current_segment["camera_state"] == camera_state:
            current_segment["last_seen_at"] = timestamp
            record["current_camera_state"] = camera_state
            return False, None

        previous_state = record["current_camera_state"]
        record["previous_camera_state"] = previous_state
        record["current_camera_state"] = camera_state
        record["transition_count"] += 1
        record["has_camera_changed"] = True
        record["unique_cameras"] = sorted(
            set(record["unique_cameras"]) | set(camera_state)
        )
        record["journey"].append({
            "camera_state": camera_state,
            "entered_at": timestamp,
            "last_seen_at": timestamp,
        })

        transition_event = {
            "event_id": (
                f"{global_id}:{timestamp:.2f}:"
                f"{'-'.join(previous_state)}>{'-'.join(camera_state)}"
            ),
            "global_id": global_id,
            "timestamp": round(timestamp, 2),
            "from_camera_state": previous_state,
            "from_camera_label": self._camera_state_label(previous_state),
            "to_camera_state": camera_state,
            "to_camera_label": self._camera_state_label(camera_state),
            "transition_index": record["transition_count"],
        }
        record["last_transition"] = transition_event
        self.recent_camera_events.append(transition_event)
        self.recent_camera_events = self.recent_camera_events[
            -self.max_recent_camera_events:
        ]

        return True, transition_event

    # --- main processing loop ---------------------------------------------
    async def run(self, decision_queue: asyncio.Queue,
                  broadcast_queue: asyncio.Queue):
        """
        Consume decisions from the hub, run tracking, push results.

        Args:
            decision_queue: Input queue (from Hub)
            broadcast_queue: Output queue (to WebSocket broadcast)
        """
        logger.info("[TrackerService] Starting tracking loop...")

        while True:
            try:
                decision = await decision_queue.get()
                decision_queue.task_done()

                if decision.get("type") != "decision":
                    continue

                timestamp = decision["timestamp"]
                self.total_decisions += 1

                # Skip already-processed timestamps
                if timestamp in self.processed_timestamps:
                    continue

                # Extract detections
                detections = self._extract_detections(decision)
                self.total_detections += len(detections)

                # --- Run tracking algorithm --------------------------------
                vehicles = []
                num_clusters = 0
                journey_updates = {}
                camera_change_events = []

                if detections:
                    score_matrix = build_score_matrix(detections)
                    clusters = agglomerative_clustering(detections, score_matrix)
                    num_clusters = len(clusters)
                    assignments = self.tracker.assign_global_ids(
                        clusters, detections, timestamp
                    )

                    detections_by_global_id = defaultdict(list)
                    for det in detections:
                        key = (det["camera"], det["track_id"])
                        gid = self.tracker.global_id_map.get(key)
                        if gid is not None:
                            detections_by_global_id[gid].append(det)

                    for gid, group in detections_by_global_id.items():
                        camera_state = self._normalize_camera_state(
                            det["camera"] for det in group
                        )
                        journey_changed, transition_event = (
                            self._record_camera_journey(
                                gid, camera_state, timestamp
                            )
                        )
                        if journey_changed:
                            journey_updates[str(gid)] = (
                                self._serialize_camera_journey(gid)
                            )
                        if transition_event is not None:
                            camera_change_events.append(transition_event)

                    # Build vehicle list for the frontend
                    for gid, group in detections_by_global_id.items():
                        journey_info = self._serialize_camera_journey(gid)
                        for det in group:
                            footprint = det["footprint"]
                            centroid = (
                                compute_centroid(footprint)
                                if len(footprint) == 8
                                else (0, 0)
                            )
                            vehicles.append({
                                "global_id": gid,
                                "camera": det["camera"],
                                "track_id": det["track_id"],
                                "class": det["class"],
                                "footprint": footprint,
                                "centroid": list(centroid),
                                "color": id_to_color(gid),
                                "camera_state": journey_info["current_camera_state"],
                                "camera_state_label": (
                                    journey_info["current_camera_label"]
                                ),
                                "has_camera_changed": (
                                    journey_info["has_camera_changed"]
                                ),
                            })

                else:
                    assignments = {}

                # --- Build tracking_update message -------------------------
                tracking_update = {
                    "type": "tracking_update",
                    "timestamp": round(timestamp, 2),
                    "vehicles": vehicles,
                    "journey_updates": journey_updates,
                    "camera_change_events": camera_change_events,
                    "stats": {
                        "num_detections": len(detections),
                        "num_clusters": num_clusters,
                        "num_global_ids": self.tracker.global_id_counter - 1,
                        "arrived_cameras": decision.get("arrived_cameras", []),
                        "decision_type": decision.get("decision", "unknown"),
                    },
                }

                await broadcast_queue.put(tracking_update)

                self.processed_timestamps.add(timestamp)

                # Console progress
                if self.total_decisions % 10 == 0 or len(vehicles) > 0:
                    logger.info(
                        f"[TrackerService] t={timestamp:7.1f}s | "
                        f"{len(detections):2d} dets, {num_clusters:2d} clusters, "
                        f"{len(vehicles):2d} vehicles | "
                        f"total GIDs: {self.tracker.global_id_counter - 1}"
                    )

            except asyncio.CancelledError:
                logger.info("[TrackerService] Stopping...")
                break
            except Exception as e:
                logger.error(f"[TrackerService] Error: {e}", exc_info=True)


# ---------------------------------------------------------------------------
# DashboardWebSocketServer — broadcasts tracking results to browsers
# ---------------------------------------------------------------------------
class DashboardWebSocketServer:
    """
    WebSocket server that broadcasts tracking_update messages to all
    connected browser clients.  Also handles ping/pong for keep-alive.
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 8765,
        tracker_service: TrackerService = None,
        journey_archive: JourneyArchive = None,
    ):
        self.host = host
        self.port = port
        self.clients: Set[websockets.WebSocketServerProtocol] = set()
        self.tracker_service = tracker_service
        self.journey_archive = journey_archive

    async def _register(self, ws):
        self.clients.add(ws)
        logger.info(
            f"[WS] Client connected. Total: {len(self.clients)}"
        )
        # Send a welcome message so the client knows it's connected
        await ws.send(json.dumps({
            "type": "connection_ack",
            "message": "Connected to tracking server",
        }))
        if self.journey_archive is not None:
            recent_events = []
            if self.tracker_service is not None:
                recent_events = self.tracker_service.recent_camera_events
            await ws.send(json.dumps(
                self.journey_archive.build_snapshot(recent_events)
            ))
        elif self.tracker_service is not None:
            await ws.send(json.dumps(
                self.tracker_service.build_camera_journey_snapshot()
            ))

    async def _unregister(self, ws):
        self.clients.discard(ws)
        logger.info(
            f"[WS] Client disconnected. Total: {len(self.clients)}"
        )

    async def _handle_client(self, ws):
        """Handle a browser client connection."""
        await self._register(ws)
        try:
            async for message in ws:
                data = json.loads(message)
                if data.get("type") == "ping":
                    await ws.send(json.dumps({"type": "pong"}))
                elif data.get("type") == "journey_view_request":
                    global_id = data.get("global_id")
                    try:
                        global_id = int(global_id)
                    except (TypeError, ValueError):
                        global_id = None

                    journey = None
                    if global_id is not None and self.journey_archive is not None:
                        journey = self.journey_archive.get_journey(global_id)

                    await ws.send(json.dumps({
                        "type": "journey_view_data",
                        "global_id": global_id,
                        "journey": journey,
                        "error": (
                            None
                            if journey is not None
                            else f"Journey not found for Global ID {global_id}"
                        ),
                    }))
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            await self._unregister(ws)

    async def _broadcast(self, message: dict):
        """Send a message to every connected client."""
        if not self.clients:
            return
        payload = json.dumps(message)
        disconnected = set()
        for client in self.clients:
            try:
                await client.send(payload)
            except websockets.exceptions.ConnectionClosed:
                disconnected.add(client)
        for client in disconnected:
            await self._unregister(client)

    async def _broadcast_loop(self, broadcast_queue: asyncio.Queue):
        """Consume tracking_update messages and broadcast them."""
        logger.info("[WS] Starting broadcast loop...")
        while True:
            try:
                msg = await broadcast_queue.get()
                await self._broadcast(msg)
                broadcast_queue.task_done()
            except asyncio.CancelledError:
                logger.info("[WS] Broadcast loop stopping")
                break
            except Exception as e:
                logger.error(f"[WS] Broadcast error: {e}", exc_info=True)

    async def run(self, broadcast_queue: asyncio.Queue):
        """Start the WS server and the broadcast loop."""
        async with websockets.serve(self._handle_client, self.host, self.port):
            logger.info(
                f"[WS] Server running on ws://{self.host}:{self.port}"
            )
            await self._broadcast_loop(broadcast_queue)


# ---------------------------------------------------------------------------
# System status broadcaster (periodic heartbeat)
# ---------------------------------------------------------------------------
async def status_broadcaster(
    tracker_service: TrackerService,
    broadcast_queue: asyncio.Queue,
    interval: float = 2.0,
):
    """Send periodic system_status messages."""
    start_time = time.time()
    while True:
        try:
            await asyncio.sleep(interval)
            status = {
                "type": "system_status",
                "uptime_s": round(time.time() - start_time, 1),
                "total_decisions": tracker_service.total_decisions,
                "total_detections": tracker_service.total_detections,
                "total_global_ids": tracker_service.tracker.global_id_counter - 1,
            }
            await broadcast_queue.put(status)
        except asyncio.CancelledError:
            break


# ---------------------------------------------------------------------------
# main — orchestrate the full pipeline
# ---------------------------------------------------------------------------
async def main():
    """Start the full tracking pipeline."""
    logger = logging.getLogger("App")
    logger.info("=" * 70)
    logger.info("REAL-TIME TRACKING SERVER")
    logger.info("=" * 70)

    # --- Load camera JSON data ---------------------------------------------
    logger.info("Loading JSON data...")
    all_camera_data = load_all_cameras(
        emulator_config.JSON_DIR,
        emulator_config.CAMERAS,
        emulator_config.JSON_PATTERN,
    )
    if not all_camera_data:
        logger.error("Failed to load camera data. Exiting.")
        return

    logger.info("Building full Global ID journey archive...")
    journey_archive = JourneyArchive()
    journey_archive.build(
        all_camera_data=all_camera_data,
        camera_offsets=emulator_config.CAMERA_TIME_OFFSETS,
        start_time=emulator_config.GLOBAL_START_TIME,
        end_time=emulator_config.GLOBAL_END_TIME,
        time_step=emulator_config.TIME_STEP,
        color_fn=id_to_color,
        logger=logger,
    )

    # --- Internal asyncio queues (the pipeline) ----------------------------
    sender_to_network_q = asyncio.Queue()
    network_to_hub_q = asyncio.Queue()
    hub_to_tracker_q = asyncio.Queue()     # hub decisions -> tracker
    tracker_to_ws_q = asyncio.Queue()      # tracking results -> WS broadcast

    # --- Create emulator components ----------------------------------------
    camera_senders = []
    for camera_id in emulator_config.CAMERAS:
        if camera_id not in all_camera_data:
            logger.warning(f"No data for {camera_id}, skipping")
            continue
        offset = emulator_config.CAMERA_TIME_OFFSETS.get(camera_id, 0.0)
        local_start = emulator_config.GLOBAL_START_TIME - offset
        local_end = emulator_config.GLOBAL_END_TIME - offset
        sender = CameraSender(
            camera_id=camera_id,
            fps=emulator_config.FPS,
            detections_by_timestamp=all_camera_data[camera_id],
            start_time=local_start,
            end_time=local_end,
            sentence_word=emulator_config.SENTENCE_WORDS.get(camera_id, ""),
            time_offset=offset,
            loop_enabled=emulator_config.LOOP_ENABLED,
        )
        camera_senders.append(sender)
    logger.info(f"Created {len(camera_senders)} camera senders")

    network_sim = NetworkSimulator(
        base_latency_ms=emulator_config.BASE_LATENCY_MS,
        jitter_ms=emulator_config.JITTER_MS,
        packet_loss_prob=emulator_config.PACKET_LOSS_PROB,
    )

    hub = Hub(
        camera_ids=emulator_config.CAMERAS,
        camera_time_offsets=emulator_config.CAMERA_TIME_OFFSETS,
        watermark_ms=emulator_config.WATERMARK_MS,
        quorum=emulator_config.QUORUM,
        time_step=emulator_config.TIME_STEP,
    )

    # --- Create tracker & WS server ---------------------------------------
    tracker_service = TrackerService()
    ws_server = DashboardWebSocketServer(
        host=emulator_config.WS_HOST,
        port=emulator_config.WS_PORT,
        tracker_service=tracker_service,
        journey_archive=journey_archive,
    )

    # --- Build task list ---------------------------------------------------
    tasks = []

    # Camera senders
    for sender in camera_senders:
        tasks.append(asyncio.create_task(sender.run(sender_to_network_q)))

    # Network simulator
    tasks.append(asyncio.create_task(
        network_sim.run(sender_to_network_q, network_to_hub_q)
    ))

    # Hub aggregator
    tasks.append(asyncio.create_task(
        hub.run(network_to_hub_q, hub_to_tracker_q)
    ))

    # Tracker service
    tasks.append(asyncio.create_task(
        tracker_service.run(hub_to_tracker_q, tracker_to_ws_q)
    ))

    # WebSocket server + broadcast
    tasks.append(asyncio.create_task(
        ws_server.run(tracker_to_ws_q)
    ))

    # Status heartbeat
    tasks.append(asyncio.create_task(
        status_broadcaster(tracker_service, tracker_to_ws_q)
    ))

    logger.info(f"All {len(tasks)} tasks created")
    logger.info("=" * 70)
    logger.info(f"WebSocket server: ws://{emulator_config.WS_HOST}:{emulator_config.WS_PORT}")
    logger.info(f"Emulating time range: {emulator_config.GLOBAL_START_TIME}s - {emulator_config.GLOBAL_END_TIME}s")
    logger.info(f"FPS: {emulator_config.FPS}  |  Loop: {emulator_config.LOOP_ENABLED}")
    logger.info("Press Ctrl+C to stop")
    logger.info("=" * 70)

    # Wait a moment for the WS server to start before emitting data
    logger.info("Waiting 1s for WebSocket server to start...")
    await asyncio.sleep(1)
    logger.info("Pipeline running. Waiting for browser connections...")

    # --- Run everything ----------------------------------------------------
    try:
        await asyncio.gather(*tasks)
    except KeyboardInterrupt:
        logger.info("Shutdown signal received.")
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        logger.info("Shutdown complete.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    # Reduce noise from emulator internals
    logging.getLogger("emulator.camera_sender").setLevel(logging.WARNING)
    logging.getLogger("emulator.network_sim").setLevel(logging.WARNING)
    logging.getLogger("emulator.hub").setLevel(logging.WARNING)


if __name__ == "__main__":
    setup_logging()
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExiting...")
