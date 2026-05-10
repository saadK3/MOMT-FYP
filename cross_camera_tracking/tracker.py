"""
Main cross-camera tracking algorithm
Orchestrates the entire tracking pipeline using synchronized timestamps
"""

from .data_loader import get_all_detections_at_timestamp, get_timestamp_range
from .matching import build_score_matrix
from .clustering import agglomerative_clustering
from .utils import save_json
from .config import OUTPUT_DIR
import os


class CrossCameraTracker:
    """
    Main tracker class for cross-camera vehicle tracking
    """

    def __init__(self):
        """Initialize tracker"""
        self.global_id_counter = 1
        self.global_id_map = {}  # Maps (camera, track_id) -> global_id
        self.timestamp_history = []  # Track processing history

    def assign_global_ids(self, clusters, current_detections, timestamp):
        """
        Assign Global IDs to clusters

        Args:
            clusters: List of clusters (each cluster is list of indices)
            current_detections: List of all detections at current timestamp
            timestamp: Current timestamp

        Returns:
            dict: Mapping of assigned Global IDs for this timestamp
        """
        timestamp_assignments = {}

        for cluster in clusters:
            # Check if any detection in cluster already has a Global ID
            existing_global_ids = []

            for det_idx in cluster:
                det = current_detections[det_idx]
                key = (det['camera'], det['track_id'])

                if key in self.global_id_map:
                    existing_global_ids.append(self.global_id_map[key])

            # Determine Global ID for this cluster
            if len(existing_global_ids) == 0:
                # New vehicle - assign new Global ID
                assigned_global_id = self.global_id_counter
                self.global_id_counter += 1
            else:
                # Use existing Global ID
                unique_ids = set(existing_global_ids)

                if len(unique_ids) == 1:
                    # All have same ID
                    assigned_global_id = list(unique_ids)[0]
                else:
                    # ID CONFLICT - merge IDs
                    assigned_global_id = min(unique_ids)

                    # Update all occurrences of higher IDs
                    for old_id in unique_ids:
                        if old_id != assigned_global_id:
                            # Merge old_id into assigned_global_id
                            for key in list(self.global_id_map.keys()):
                                if self.global_id_map[key] == old_id:
                                    self.global_id_map[key] = assigned_global_id

            # Assign Global ID to all detections in cluster
            for det_idx in cluster:
                det = current_detections[det_idx]
                key = (det['camera'], det['track_id'])
                self.global_id_map[key] = assigned_global_id

                # Track assignment for this timestamp
                if assigned_global_id not in timestamp_assignments:
                    timestamp_assignments[assigned_global_id] = []
                timestamp_assignments[assigned_global_id].append({
                    'camera': det['camera'],
                    'track_id': det['track_id']
                })

        return timestamp_assignments

    def process_timestamp(self, all_camera_data, timestamp):
        """
        Process a single timestamp

        Args:
            all_camera_data: Dictionary of all camera data
            timestamp: Synchronized timestamp to process

        Returns:
            dict: Timestamp processing results
        """
        # Step 1: Collect all detections at this timestamp
        current_detections = get_all_detections_at_timestamp(all_camera_data, timestamp)

        if len(current_detections) == 0:
            return {
                'timestamp': timestamp,
                'num_detections': 0,
                'num_clusters': 0,
                'assignments': {}
            }

        # Step 2: Build score matrix
        score_matrix = build_score_matrix(current_detections)

        # Step 3: Cluster detections
        clusters = agglomerative_clustering(current_detections, score_matrix)

        # Step 4: Assign Global IDs
        assignments = self.assign_global_ids(clusters, current_detections, timestamp)

        return {
            'timestamp': timestamp,
            'num_detections': len(current_detections),
            'num_clusters': len(clusters),
            'assignments': assignments
        }

    def run(self, all_camera_data, start_time=None, end_time=None, time_step=0.2, progress_interval=10.0):
        """
        Run tracking algorithm on all timestamps

        Args:
            all_camera_data: Dictionary of all camera data
            start_time: Starting timestamp (default: auto-detect)
            end_time: Ending timestamp (default: auto-detect)
            time_step: Time step in seconds (default: 0.2s = 5 FPS)
            progress_interval: Print progress every N seconds

        Returns:
            dict: Tracking results
        """
        # Determine timestamp range
        if start_time is None or end_time is None:
            min_t, max_t = get_timestamp_range(all_camera_data)
            if start_time is None:
                start_time = min_t
            if end_time is None:
                end_time = max_t

        print(f"\n{'='*70}")
        print(f"CROSS-CAMERA TRACKING (Timestamp-Based with Synchronization)")
        print(f"{'='*70}")
        print(f"Time range: {start_time:.2f}s to {end_time:.2f}s")
        print(f"Duration: {end_time - start_time:.2f}s")
        print(f"Time step: {time_step}s")
        print(f"{'='*70}\n")

        # Process each timestamp
        current_time = start_time
        processed_count = 0

        while current_time <= end_time:
            result = self.process_timestamp(all_camera_data, current_time)
            self.timestamp_history.append(result)

            # Progress update
            if processed_count % int(progress_interval / time_step) == 0:
                print(f"Time {current_time:.2f}s: {result['num_detections']} detections, "
                      f"{result['num_clusters']} clusters")

            current_time += time_step
            processed_count += 1

        print(f"\n{'='*70}")
        print(f"TRACKING COMPLETE")
        print(f"{'='*70}")
        print(f"Total Global IDs assigned: {self.global_id_counter - 1}")
        print(f"Processed {processed_count} timestamps")
        print(f"{'='*70}\n")

        return {
            'total_global_ids': self.global_id_counter - 1,
            'timestamp_history': self.timestamp_history
        }

    def export_results(self, output_path=None):
        """
        Export Global ID mapping to JSON

        Args:
            output_path: Output file path (default: output/global_id_mapping.json)
        """
        if output_path is None:
            output_path = os.path.join(OUTPUT_DIR, 'global_id_mapping.json')

        # Convert to output format
        output = {}

        for (camera, track_id), global_id in self.global_id_map.items():
            global_id_str = str(global_id)

            if global_id_str not in output:
                output[global_id_str] = {}

            if camera not in output[global_id_str]:
                output[global_id_str][camera] = {
                    'track_id': track_id
                }

        save_json(output, output_path)
        return output
