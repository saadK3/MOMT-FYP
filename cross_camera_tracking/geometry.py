"""
Geometric operations for footprint matching
Includes IOU computation, orientation calculation, and polygon utilities
"""

import numpy as np
from shapely.geometry import Polygon
from shapely.ops import unary_union
import math


def parse_footprint(det_birdeye):
    """
    Convert det_birdeye array to Shapely Polygon with validation

    Args:
        det_birdeye: List of 8 values [x1, y1, x2, y2, x3, y3, x4, y4]

    Returns:
        Shapely Polygon object (or None if invalid)
    """
    points = [
        (det_birdeye[0], det_birdeye[1]),
        (det_birdeye[2], det_birdeye[3]),
        (det_birdeye[4], det_birdeye[5]),
        (det_birdeye[6], det_birdeye[7])
    ]

    try:
        polygon = Polygon(points)

        # Fix invalid polygons using buffer(0) trick
        if not polygon.is_valid:
            polygon = polygon.buffer(0)

        return polygon
    except Exception:
        # Return a very small valid polygon as fallback
        return Polygon([(0, 0), (0.01, 0), (0.01, 0.01), (0, 0.01)])


def compute_iou(polygon1, polygon2):
    """
    Compute Intersection over Union of two polygons

    Args:
        polygon1: Shapely Polygon
        polygon2: Shapely Polygon

    Returns:
        float: IOU value between 0.0 and 1.0
    """
    try:
        if polygon1 is None or polygon2 is None:
            return 0.0

        # Compute intersection
        intersection = polygon1.intersection(polygon2)
        intersection_area = intersection.area

        # Compute union
        union_area = polygon1.area + polygon2.area - intersection_area

        if union_area == 0:
            return 0.0

        iou = intersection_area / union_area
        return iou

    except Exception:
        # Silently handle errors
        return 0.0


def compute_orientation(footprint):
    """
    Compute vehicle heading angle from footprint

    Args:
        footprint: List of 8 values [x1, y1, x2, y2, x3, y3, x4, y4]
                  Points: [front-left, front-right, rear-left, rear-right]

    Returns:
        float: Heading angle in degrees [0, 360)
    """
    # Extract points
    front_left = np.array([footprint[0], footprint[1]])
    front_right = np.array([footprint[2], footprint[3]])
    rear_left = np.array([footprint[4], footprint[5]])
    rear_right = np.array([footprint[6], footprint[7]])

    # Compute centers
    front_center = (front_left + front_right) / 2
    rear_center = (rear_left + rear_right) / 2

    # Compute heading vector (rear → front)
    dx = front_center[0] - rear_center[0]
    dy = front_center[1] - rear_center[1]

    # Compute angle in degrees
    angle = math.atan2(dy, dx) * 180 / math.pi

    # Normalize to [0, 360)
    if angle < 0:
        angle += 360

    return angle


def compute_centroid(footprint):
    """
    Compute center point of footprint

    Args:
        footprint: List of 8 values [x1, y1, x2, y2, x3, y3, x4, y4]

    Returns:
        tuple: (x, y) coordinates of centroid
    """
    x_coords = [footprint[i] for i in range(0, 8, 2)]
    y_coords = [footprint[i] for i in range(1, 8, 2)]

    centroid_x = sum(x_coords) / 4
    centroid_y = sum(y_coords) / 4

    return (centroid_x, centroid_y)


def angle_difference(angle1, angle2):
    """
    Compute the smallest difference between two angles
    Handles wraparound (e.g., 359° and 1° = 2° difference)

    Args:
        angle1: Angle in degrees [0, 360)
        angle2: Angle in degrees [0, 360)

    Returns:
        float: Angle difference in degrees [0, 180]
    """
    diff = abs(angle1 - angle2)
    if diff > 180:
        diff = 360 - diff
    return diff
