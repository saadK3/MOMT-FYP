"""
Network Simulator - Realism Engine
Conceptually , this module sits between the cameras and the hub and answers one question:
"If the cameras were deployed in the real world, how would packets actually arrive ?"

models 3 things:
1. Latency
2. Jitter
3. Packet Loss
"""
import asyncio
import logging
import random
import time
from typing import Dict

logger = logging.getLogger(__name__)


class NetworkSimulator:
    """
    Simulates network conditions by applying jitter and delays to packets.
    """

    def __init__(self,
                 base_latency_ms: int = 60,
                 jitter_ms: int = 120,
                 packet_loss_prob: float = 0.01):
        """
        Initialize network simulator.

        Args:
            base_latency_ms: Base latency in milliseconds
            jitter_ms: Jitter range in milliseconds (normal distribution)
            packet_loss_prob: Probability of packet loss (0.0 - 1.0)
        """
        # these stored parameters come directly from the config.py
        self.base_latency_ms = base_latency_ms
        self.jitter_ms = jitter_ms
        self.packet_loss_prob = packet_loss_prob

        logger.info(f"[NetworkSim] Initialized. "
                   f"Base latency: {base_latency_ms}ms, "
                   f"Jitter: {jitter_ms}ms, "
                   f"Loss: {packet_loss_prob*100:.1f}%")

    def _calculate_delay(self) -> int:
        """
        Calculate delay with jitter using normal distribution.

        Returns:
            Delay in milliseconds
        """
        # Normal distribution: mean=0, std=jitter/3
        # This ensures ~99.7% of values are within ±jitter
        noise = random.gauss(0, self.jitter_ms / 3)
        # clamping at 0, as negative delay would imply that the packets arrive earlier than they were sent.
        delay_ms = max(0, self.base_latency_ms + noise)
        return int(delay_ms)

    async def _schedule_delivery(self, packet: Dict, delay_ms: int, output_queue: asyncio.Queue):
        """
        Wait for delay and then deliver packet.

        Args:
            packet: Packet to deliver
            delay_ms: Delay in milliseconds
            output_queue: Queue to deliver packet to
        """
        try:
            # does not block the main network loop,
            # multiple packets can be "in-flight" at the same time.(real networks are parallel)
            await asyncio.sleep(delay_ms / 1000.0)

            # Set receive timestamp : we can then compute end-to-end latency, delay variance, late-arrival statistics etc.
            packet['ts_recv_ms'] = int(time.time() * 1000)
            packet['actual_delay_ms'] = delay_ms

            # send the packet to the hub
            await output_queue.put(packet)

            logger.debug(f"[NetworkSim] Delivered packet from {packet['camera_id']} "
                        f"@ t={packet['timestamp']:.1f}s (delay: {delay_ms}ms)")

        except asyncio.CancelledError:
            logger.info(f"[NetworkSim] Delivery cancelled for {packet['camera_id']}")

    async def run(self, input_queue: asyncio.Queue, output_queue: asyncio.Queue):
        """
        Main loop - consume packets and apply network simulation.

        Args:
            input_queue: Queue to receive packets from camera senders
            output_queue: Queue to send delayed packets to hub
        """
        logger.info("[NetworkSim] Starting network simulation loop...")

        while True:
            try:
                packet = await input_queue.get()

                # Check for packet loss
                if random.random() < self.packet_loss_prob:
                    logger.debug(f"[NetworkSim] DROPPED packet from {packet['camera_id']} "
                               f"@ t={packet['timestamp']:.1f}s")
                    input_queue.task_done()
                    continue

                # Calculate delay with jitter
                delay_ms = self._calculate_delay()

                # Schedule delivery
                asyncio.create_task(self._schedule_delivery(packet, delay_ms, output_queue))

                input_queue.task_done()

            except asyncio.CancelledError:
                logger.info("[NetworkSim] Simulation loop stopping")
                break
            except Exception as e:
                logger.error(f"[NetworkSim] Error: {e}", exc_info=True)

    def update_config(self, base_latency_ms: int = None, jitter_ms: int = None,
                     packet_loss_prob: float = None):
        """Update network simulation parameters dynamically."""
        if base_latency_ms is not None:
            self.base_latency_ms = base_latency_ms
        if jitter_ms is not None:
            self.jitter_ms = jitter_ms
        if packet_loss_prob is not None:
            self.packet_loss_prob = packet_loss_prob

        logger.info(f"[NetworkSim] Config updated: "
                   f"Latency={self.base_latency_ms}ms, "
                   f"Jitter={self.jitter_ms}ms, "
                   f"Loss={self.packet_loss_prob*100:.1f}%")
