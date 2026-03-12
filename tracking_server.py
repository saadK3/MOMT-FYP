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

                if detections:
                    score_matrix = build_score_matrix(detections)
                    clusters = agglomerative_clustering(detections, score_matrix)
                    num_clusters = len(clusters)
                    assignments = self.tracker.assign_global_ids(
                        clusters, detections, timestamp
                    )

                    # Build vehicle list for the frontend
                    for det in detections:
                        key = (det["camera"], det["track_id"])
                        gid = self.tracker.global_id_map.get(key)
                        if gid is None:
                            continue
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
                        })

                # --- Build tracking_update message -------------------------
                tracking_update = {
                    "type": "tracking_update",
                    "timestamp": round(timestamp, 2),
                    "vehicles": vehicles,
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

    def __init__(self, host: str = "localhost", port: int = 8765):
        self.host = host
        self.port = port
        self.clients: Set[websockets.WebSocketServerProtocol] = set()

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
