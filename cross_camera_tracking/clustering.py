"""
Agglomerative clustering for grouping detections
Clusters detections based on matching scores
"""

import numpy as np
from .config import SCORE_THRESHOLD


def compute_cluster_score(cluster1, cluster2, score_matrix):
    """
    Compute average score between two clusters

    Args:
        cluster1: List of detection indices
        cluster2: List of detection indices
        score_matrix: N x N score matrix

    Returns:
        float: Average score between clusters
    """
    total_score = 0.0
    count = 0

    for i in cluster1:
        for j in cluster2:
            total_score += score_matrix[i][j]
            count += 1

    if count == 0:
        return 0.0

    return total_score / count


def agglomerative_clustering(detections, score_matrix, threshold=None):
    """
    Perform agglomerative clustering based on score matrix

    Args:
        detections: List of detection dictionaries
        score_matrix: N x N score matrix
        threshold: Minimum score to merge clusters (default: from config)

    Returns:
        list: List of clusters, each cluster is a list of detection indices
    """
    if threshold is None:
        threshold = SCORE_THRESHOLD

    n = len(detections)

    # Initialize: each detection is its own cluster
    clusters = [[i] for i in range(n)]

    while True:
        # Find pair of clusters with highest score
        best_score = -1
        best_i = -1
        best_j = -1

        for i in range(len(clusters)):
            for j in range(i + 1, len(clusters)):
                cluster_score = compute_cluster_score(
                    clusters[i], clusters[j], score_matrix
                )

                if cluster_score > best_score:
                    best_score = cluster_score
                    best_i = i
                    best_j = j

        # Stop if best score is below threshold
        if best_score < threshold:
            break

        # Merge the two best clusters
        clusters[best_i].extend(clusters[best_j])
        clusters.pop(best_j)

    return clusters


def get_cluster_info(cluster, detections):
    """
    Get human-readable information about a cluster

    Args:
        cluster: List of detection indices
        detections: List of detection dictionaries

    Returns:
        dict: Cluster information
    """
    cameras = set()
    track_ids = []

    for idx in cluster:
        det = detections[idx]
        cameras.add(det['camera'])
        track_ids.append(f"{det['camera']}-T{det['track_id']}")

    return {
        'size': len(cluster),
        'cameras': list(cameras),
        'tracks': track_ids
    }
