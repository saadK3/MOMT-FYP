"""
Matching score computation with constraints
Implements IOU and class-based matching (orientation removed for simplicity)
"""

import numpy as np
from .geometry import parse_footprint, compute_iou
from .config import (
    IOU_THRESHOLD,
    DIRECTION_TOLERANCE_DEG,
    SPEED_REL_TOLERANCE,
    MIN_DIRECTION_SPEED,
)


def _angle_diff_deg(a, b):
    """Smallest difference between two angles in degrees."""
    if a is None or b is None:
        return None
    diff = abs(a - b) % 360.0
    if diff > 180.0:
        diff = 360.0 - diff
    return diff


def _speed_close(a, b):
    """Relative speed tolerance check."""
    if a is None or b is None:
        return True
    denom = max(a, b, 1e-6)
    return abs(a - b) / denom <= SPEED_REL_TOLERANCE


def compute_match_score(det1, det2):
    """
    Compute matching score between two detections
    Uses only IOU and vehicle class constraints

    Args:
        det1: First detection dictionary
        det2: Second detection dictionary

    Returns:
        float: IOU score (0.0 to 1.0) if constraints pass, else 0.0
    """
    # CONSTRAINT 1: Same camera check (can't be same vehicle)
    if det1['camera'] == det2['camera']:
        return 0.0

    # CONSTRAINT 2: Vehicle Class (Hard Constraint)
    if det1['class'] != det2['class']:
        return 0.0  # Different vehicle types, reject

    # CONSTRAINT 3: IOU (Only metric)
    polygon1 = parse_footprint(det1['footprint'])
    polygon2 = parse_footprint(det2['footprint'])

    iou = compute_iou(polygon1, polygon2)

    if iou < IOU_THRESHOLD:
        return 0.0  # Insufficient overlap

    # CONSTRAINT 4: Speed consistency (if both available)
    if not _speed_close(det1.get("speed"), det2.get("speed")):
        return 0.0

    # CONSTRAINT 5: Direction consistency (when both are moving enough)
    speed1 = det1.get("speed")
    speed2 = det2.get("speed")
    if (
        speed1 is not None
        and speed2 is not None
        and speed1 >= MIN_DIRECTION_SPEED
        and speed2 >= MIN_DIRECTION_SPEED
    ):
        angle_diff = _angle_diff_deg(det1.get("direction"), det2.get("direction"))
        if angle_diff is not None and angle_diff > DIRECTION_TOLERANCE_DEG:
            return 0.0

    # Return IOU as the final score (no orientation weighting)
    return iou


def build_score_matrix(detections):
    """
    Build pairwise score matrix for all detections

    Args:
        detections: List of detection dictionaries

    Returns:
        numpy.ndarray: N x N score matrix
    """
    n = len(detections)
    score_matrix = np.zeros((n, n))

    for i in range(n):
        for j in range(i + 1, n):
            score = compute_match_score(detections[i], detections[j])
            score_matrix[i][j] = score
            score_matrix[j][i] = score  # Symmetric

    return score_matrix
