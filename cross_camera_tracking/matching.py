"""
Matching score computation with constraints
Implements IOU and class-based matching (orientation removed for simplicity)
"""

import numpy as np
from .geometry import parse_footprint, compute_iou
from .config import IOU_THRESHOLD


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
