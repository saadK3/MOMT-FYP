"""
Cross-Camera Vehicle Tracking Package

This package implements multi-camera vehicle tracking with global ID assignment
using IOU-based matching, orientation constraints, and agglomerative clustering.

Supports both offline (JSON files) and real-time (emulator WebSocket) input.
"""

from .emulator_client import EmulatorClient

__version__ = "1.0.0"
__all__ = ['EmulatorClient']
