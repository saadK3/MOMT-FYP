"""
WebSocket Server - Broadcasts events to frontend clients
"""
import asyncio
import json
import logging
import websockets
from typing import Set

logger = logging.getLogger(__name__)


class WebSocketServer:
    """
    WebSocket server that broadcasts emulator events to connected clients.
    """

    def __init__(self, host: str = 'localhost', port: int = 8765, network_sim=None):
        """
        Initialize WebSocket server.

        Args:
            host: Server host
            port: Server port
            network_sim: Reference to NetworkSimulator for dynamic config updates
        """
        self.host = host
        self.port = port
        self.clients: Set[websockets.WebSocketServerProtocol] = set()
        self.network_sim = network_sim  # For dynamic configuration

        logger.info(f"[WebSocket] Initialized on {host}:{port}")

    async def register(self, websocket):
        """Register a new client."""
        self.clients.add(websocket)
        logger.info(f"[WebSocket] Client connected. Total clients: {len(self.clients)}")

    async def unregister(self, websocket):
        """Unregister a client."""
        self.clients.discard(websocket)
        logger.info(f"[WebSocket] Client disconnected. Total clients: {len(self.clients)}")

    async def handle_config_update(self, data: dict, websocket):
        """
        Handle dynamic network configuration update from frontend.

        Args:
            data: Message containing config parameters
            websocket: Client websocket connection
        """
        if not self.network_sim:
            logger.warning("[WebSocket] No NetworkSimulator reference, cannot update config")
            await websocket.send(json.dumps({
                'type': 'config_ack',
                'success': False,
                'error': 'NetworkSimulator not available'
            }))
            return

        try:
            # Extract parameters (only update if provided)
            base_latency_ms = data.get('base_latency_ms')
            jitter_ms = data.get('jitter_ms')
            packet_loss_prob = data.get('packet_loss_prob')

            # Update NetworkSimulator
            self.network_sim.update_config(
                base_latency_ms=base_latency_ms,
                jitter_ms=jitter_ms,
                packet_loss_prob=packet_loss_prob
            )

            # Send acknowledgment
            await websocket.send(json.dumps({
                'type': 'config_ack',
                'success': True,
                'config': {
                    'base_latency_ms': self.network_sim.base_latency_ms,
                    'jitter_ms': self.network_sim.jitter_ms,
                    'packet_loss_prob': self.network_sim.packet_loss_prob
                }
            }))

            logger.info(f"[WebSocket] Config updated: "
                       f"latency={self.network_sim.base_latency_ms}ms, "
                       f"jitter={self.network_sim.jitter_ms}ms, "
                       f"loss={self.network_sim.packet_loss_prob*100:.1f}%")

        except Exception as e:
            logger.error(f"[WebSocket] Error updating config: {e}", exc_info=True)
            await websocket.send(json.dumps({
                'type': 'config_ack',
                'success': False,
                'error': str(e)
            }))

    async def broadcast(self, message: dict):
        """
        Broadcast message to all connected clients.

        Args:
            message: Message dictionary to broadcast
        """
        if not self.clients:
            return

        message_json = json.dumps(message)

        # Send to all clients
        disconnected_clients = set()
        for client in self.clients:
            try:
                await client.send(message_json)
            except websockets.exceptions.ConnectionClosed:
                disconnected_clients.add(client)

        # Remove disconnected clients
        for client in disconnected_clients:
            await self.unregister(client)

    async def handle_client(self, websocket):
        """
        Handle a single client connection.

        Args:
            websocket: WebSocket connection
        """
        await self.register(websocket)

        try:
            # Listen for messages from client (for control commands)
            async for message in websocket:
                try:
                    data = json.loads(message)
                    logger.info(f"[WebSocket] Received: {data.get('type', 'unknown')}")

                    # Handle control commands
                    if data.get('type') == 'ping':
                        await websocket.send(json.dumps({'type': 'pong'}))

                    elif data.get('type') == 'config_update':
                        # Handle dynamic network configuration update
                        await self.handle_config_update(data, websocket)

                except json.JSONDecodeError:
                    logger.warning(f"[WebSocket] Invalid JSON received")

        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            await self.unregister(websocket)

    async def broadcast_loop(self, decision_queue: asyncio.Queue):
        """
        Loop that consumes decision events and broadcasts them.

        Args:
            decision_queue: Queue to receive decision events from Hub
        """
        logger.info("[WebSocket] Starting broadcast loop...")

        while True:
            try:
                event = await decision_queue.get()
                await self.broadcast(event)
                decision_queue.task_done()

            except asyncio.CancelledError:
                logger.info("[WebSocket] Broadcast loop stopping")
                break
            except Exception as e:
                logger.error(f"[WebSocket] Broadcast error: {e}", exc_info=True)

    async def run(self, decision_queue: asyncio.Queue):
        """
        Start WebSocket server and broadcast loop.

        Args:
            decision_queue: Queue to receive events from Hub
        """
        # Start server
        async with websockets.serve(self.handle_client, self.host, self.port):
            logger.info(f"[WebSocket] Server running on ws://{self.host}:{self.port}")

            # Run broadcast loop
            await self.broadcast_loop(decision_queue)
