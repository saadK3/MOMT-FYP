"""
Emulator client for real-time cross-camera tracking
Connects to emulator WebSocket and receives detection data
"""

import asyncio
import websockets
import json
from collections import defaultdict


class EmulatorClient:
    """
    Client to receive detections from emulator WebSocket.
    """

    def __init__(self, ws_url='ws://localhost:8765'):
        """
        Initialize emulator client.

        Args:
            ws_url: WebSocket URL of emulator
        """
        self.ws_url = ws_url
        self.websocket = None
        self.is_connected = False

        # Detection buffer: {timestamp: [detections]}
        self.detection_buffer = defaultdict(list)

        # Statistics
        self.total_decisions = 0
        self.total_detections = 0

    async def connect(self):
        """Connect to emulator WebSocket."""
        print(f"Connecting to emulator at {self.ws_url}...")
        self.websocket = await websockets.connect(self.ws_url)
        self.is_connected = True
        print("✅ Connected to emulator")

    async def disconnect(self):
        """Disconnect from emulator."""
        if self.websocket:
            await self.websocket.close()
            self.is_connected = False
            print("Disconnected from emulator")

    def _extract_detections(self, decision_event):
        """
        Extract detections from emulator decision event.

        Args:
            decision_event: Decision event from emulator

        Returns:
            list: List of detections in cross-camera tracking format
        """
        detections = []
        timestamp = decision_event['timestamp']
        sentence_status = decision_event.get('sentence_status', {})

        for camera_id, camera_data in sentence_status.items():
            if not camera_data.get('arrived', False):
                continue  # Camera didn't send packet

            camera_detections = camera_data.get('detections', [])

            for det in camera_detections:
                # Convert emulator format to tracker format
                detections.append({
                    'camera': camera_id,
                    'track_id': det.get('track_id', 0),
                    'footprint': det.get('det_birdeye', []),
                    'class': det.get('det_kp_class_name', 'unknown'),
                    'timestamp': timestamp,  # Already synchronized by emulator
                    'original_timestamp': det.get('det_timestamp', timestamp),
                    'frame': int(det.get('det_impath', 0))
                })

        return detections

    async def receive_decision(self):
        """
        Receive one decision from emulator.

        Returns:
            dict: Decision event, or None if disconnected
        """
        if not self.is_connected:
            return None

        try:
            message = await self.websocket.recv()
            decision = json.loads(message)

            if decision.get('type') == 'decision':
                self.total_decisions += 1

                # Extract detections
                detections = self._extract_detections(decision)
                self.total_detections += len(detections)

                # Add to buffer
                timestamp = decision['timestamp']
                self.detection_buffer[timestamp].extend(detections)

                return decision

            return None

        except websockets.exceptions.ConnectionClosed:
            self.is_connected = False
            return None
        except Exception as e:
            print(f"Error receiving decision: {e}")
            return None

    def get_detections_at_timestamp(self, timestamp):
        """
        Get all detections at a specific timestamp.

        Args:
            timestamp: Target timestamp

        Returns:
            list: List of detections
        """
        return self.detection_buffer.get(timestamp, [])

    def get_all_timestamps(self):
        """
        Get all timestamps in buffer.

        Returns:
            list: Sorted list of timestamps
        """
        return sorted(self.detection_buffer.keys())

    def clear_old_detections(self, before_timestamp):
        """
        Clear detections older than specified timestamp.

        Args:
            before_timestamp: Clear detections before this time
        """
        to_remove = [ts for ts in self.detection_buffer.keys()
                     if ts < before_timestamp]

        for ts in to_remove:
            del self.detection_buffer[ts]

    def get_statistics(self):
        """
        Get client statistics.

        Returns:
            dict: Statistics dictionary
        """
        return {
            'total_decisions': self.total_decisions,
            'total_detections': self.total_detections,
            'buffer_size': len(self.detection_buffer),
            'is_connected': self.is_connected
        }
