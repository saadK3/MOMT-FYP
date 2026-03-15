"""
Archive builder for full Global ID journey visualization.

Builds per-vehicle journey summaries and full path data for every Global ID
using the same clustering + assignment logic as the live tracker, but on a
pre-synchronized in-memory index for fast startup.
"""

from collections import Counter, defaultdict
from typing import Dict, List, Optional

from .clustering import agglomerative_clustering
from .geometry import compute_centroid
from .matching import build_score_matrix
from .tracker import CrossCameraTracker


class JourneyArchive:
    """Precomputed journey summaries + full path data for all Global IDs."""

    def __init__(self):
        self.summaries: Dict[int, Dict] = {}
        self.full_journeys: Dict[int, Dict] = {}
        self.total_global_ids = 0

    @staticmethod
    def _normalize_camera_state(cameras) -> List[str]:
        return sorted(set(cameras))

    @staticmethod
    def _camera_state_label(camera_state: List[str]) -> str:
        if not camera_state:
            return "Unknown"
        return " + ".join(camera.upper() for camera in camera_state)

    @staticmethod
    def _round_point(centroid) -> List[float]:
        return [round(float(centroid[0]), 3), round(float(centroid[1]), 3)]

    @staticmethod
    def _bucket_timestamp(timestamp: float, time_step: float) -> float:
        return round(round(timestamp / time_step) * time_step, 2)

    def _build_record(self, global_id: int, timestamp: float, point: Dict) -> Dict:
        camera_state = point["camera_state"]
        camera_label = point["camera_label"]

        return {
            "global_id": global_id,
            "color": point["color"],
            "vehicle_class": point["class"],
            "class_counts": Counter([point["class"]]),
            "current_camera_state": camera_state,
            "previous_camera_state": None,
            "unique_cameras": set(camera_state),
            "transition_count": 0,
            "has_camera_changed": False,
            "last_seen_at": timestamp,
            "journey": [
                {
                    "camera_state": camera_state,
                    "camera_label": camera_label,
                    "entered_at": timestamp,
                    "last_seen_at": timestamp,
                }
            ],
            "segments": [
                {
                    "camera_state": camera_state,
                    "camera_label": camera_label,
                    "start_time": timestamp,
                    "end_time": timestamp,
                    "points": [point],
                }
            ],
            "points": [point],
            "transitions": [],
            "last_transition": None,
        }

    def _append_point(self, record: Dict, timestamp: float, point: Dict) -> None:
        camera_state = point["camera_state"]
        camera_label = point["camera_label"]
        record["class_counts"].update([point["class"]])
        record["vehicle_class"] = record["class_counts"].most_common(1)[0][0]
        record["last_seen_at"] = timestamp
        record["points"].append(point)

        current_segment = record["segments"][-1]
        if current_segment["camera_state"] == camera_state:
            current_segment["end_time"] = timestamp
            current_segment["points"].append(point)
            record["journey"][-1]["last_seen_at"] = timestamp
            record["current_camera_state"] = camera_state
            return

        previous_state = record["current_camera_state"]
        transition = {
            "event_id": (
                f"{record['global_id']}:{timestamp:.2f}:"
                f"{'-'.join(previous_state)}>{'-'.join(camera_state)}"
            ),
            "global_id": record["global_id"],
            "timestamp": round(timestamp, 2),
            "centroid": point["centroid"],
            "from_camera_state": previous_state,
            "from_camera_label": self._camera_state_label(previous_state),
            "to_camera_state": camera_state,
            "to_camera_label": camera_label,
            "transition_index": record["transition_count"] + 1,
        }

        record["previous_camera_state"] = previous_state
        record["current_camera_state"] = camera_state
        record["unique_cameras"].update(camera_state)
        record["transition_count"] += 1
        record["has_camera_changed"] = True
        record["transitions"].append(transition)
        record["last_transition"] = transition
        record["journey"].append({
            "camera_state": camera_state,
            "camera_label": camera_label,
            "entered_at": timestamp,
            "last_seen_at": timestamp,
        })
        record["segments"].append({
            "camera_state": camera_state,
            "camera_label": camera_label,
            "start_time": timestamp,
            "end_time": timestamp,
            "points": [point],
        })

    def _serialize_summary(self, record: Dict) -> Dict:
        return {
            "global_id": record["global_id"],
            "color": record["color"],
            "vehicle_class": record["vehicle_class"],
            "current_camera_state": record["current_camera_state"],
            "current_camera_label": self._camera_state_label(
                record["current_camera_state"]
            ),
            "previous_camera_state": record["previous_camera_state"],
            "previous_camera_label": (
                self._camera_state_label(record["previous_camera_state"])
                if record["previous_camera_state"]
                else None
            ),
            "unique_cameras": sorted(record["unique_cameras"]),
            "transition_count": record["transition_count"],
            "has_camera_changed": record["has_camera_changed"],
            "last_seen_at": round(record["last_seen_at"], 2),
            "journey": [
                {
                    "camera_state": segment["camera_state"],
                    "camera_label": segment["camera_label"],
                    "entered_at": round(segment["entered_at"], 2),
                    "last_seen_at": round(segment["last_seen_at"], 2),
                }
                for segment in record["journey"]
            ],
            "last_transition": record["last_transition"],
        }

    def _serialize_full(self, record: Dict) -> Dict:
        points = record["points"]
        xs = [point["centroid"][0] for point in points]
        ys = [point["centroid"][1] for point in points]
        padding_x = max((max(xs) - min(xs)) * 0.2, 8.0)
        padding_y = max((max(ys) - min(ys)) * 0.2, 8.0)

        return {
            "global_id": record["global_id"],
            "summary": self._serialize_summary(record),
            "path_points": points,
            "segments": [
                {
                    "camera_state": segment["camera_state"],
                    "camera_label": segment["camera_label"],
                    "start_time": round(segment["start_time"], 2),
                    "end_time": round(segment["end_time"], 2),
                    "points": segment["points"],
                }
                for segment in record["segments"]
            ],
            "transitions": record["transitions"],
            "bounds": {
                "xmin": round(min(xs) - padding_x, 3),
                "xmax": round(max(xs) + padding_x, 3),
                "ymin": round(min(ys) - padding_y, 3),
                "ymax": round(max(ys) + padding_y, 3),
            },
        }

    def _build_synchronized_index(
        self,
        all_camera_data: Dict[str, Dict[float, List[Dict]]],
        camera_offsets: Dict[str, float],
        time_step: float,
        start_time: float,
        end_time: float,
    ) -> Dict[float, List[Dict]]:
        detections_by_global_timestamp = defaultdict(list)

        for camera_id, detections_by_timestamp in all_camera_data.items():
            offset = camera_offsets.get(camera_id, 0.0)

            for local_timestamp, detections in detections_by_timestamp.items():
                global_timestamp = self._bucket_timestamp(
                    local_timestamp + offset, time_step
                )
                if global_timestamp < start_time or global_timestamp > end_time:
                    continue

                for detection in detections:
                    detections_by_global_timestamp[global_timestamp].append({
                        "camera": camera_id,
                        "track_id": detection.get("track_id", 0),
                        "footprint": detection.get("det_birdeye", []),
                        "class": detection.get(
                            "det_kp_class_name", "unknown"
                        ),
                        "timestamp": global_timestamp,
                        "frame": int(detection.get("det_impath", 0)),
                    })

        return {
            timestamp: detections_by_global_timestamp[timestamp]
            for timestamp in sorted(detections_by_global_timestamp)
        }

    def build(
        self,
        all_camera_data: Dict[str, Dict[float, List[Dict]]],
        camera_offsets: Dict[str, float],
        start_time: float,
        end_time: float,
        time_step: float,
        color_fn,
        logger=None,
    ) -> None:
        """Build full journey data for all Global IDs in the dataset."""
        tracker = CrossCameraTracker()
        records: Dict[int, Dict] = {}
        synchronized_index = self._build_synchronized_index(
            all_camera_data,
            camera_offsets,
            time_step,
            start_time,
            end_time,
        )

        for step_index, (timestamp, detections) in enumerate(
            synchronized_index.items()
        ):
            if logger and step_index % 200 == 0:
                logger.info(
                    "[JourneyArchive] %s/%s synchronized buckets processed",
                    step_index + 1,
                    len(synchronized_index),
                )

            if not detections:
                continue

            score_matrix = build_score_matrix(detections)
            clusters = agglomerative_clustering(detections, score_matrix)
            tracker.assign_global_ids(clusters, detections, timestamp)

            detections_by_global_id = defaultdict(list)
            for detection in detections:
                key = (detection["camera"], detection["track_id"])
                global_id = tracker.global_id_map.get(key)
                if global_id is not None:
                    detections_by_global_id[global_id].append(detection)

            for global_id, group in detections_by_global_id.items():
                centroids = [
                    compute_centroid(detection["footprint"])
                    for detection in group
                    if len(detection["footprint"]) == 8
                ]
                if not centroids:
                    continue

                camera_state = self._normalize_camera_state(
                    detection["camera"] for detection in group
                )
                camera_label = self._camera_state_label(camera_state)
                avg_x = sum(point[0] for point in centroids) / len(centroids)
                avg_y = sum(point[1] for point in centroids) / len(centroids)
                primary_detection = group[-1]
                point = {
                    "timestamp": round(timestamp, 2),
                    "centroid": self._round_point((avg_x, avg_y)),
                    "camera_state": camera_state,
                    "camera_label": camera_label,
                    "camera": primary_detection["camera"],
                    "track_ids": sorted(
                        {detection["track_id"] for detection in group}
                    ),
                    "class": primary_detection["class"],
                    "color": color_fn(global_id),
                }

                if global_id not in records:
                    records[global_id] = self._build_record(
                        global_id, timestamp, point
                    )
                else:
                    self._append_point(records[global_id], timestamp, point)

        self.summaries = {}
        self.full_journeys = {}
        for global_id, record in sorted(records.items()):
            self.summaries[global_id] = self._serialize_summary(record)
            self.full_journeys[global_id] = self._serialize_full(record)

        self.total_global_ids = tracker.global_id_counter - 1

        if logger:
            logger.info(
                "[JourneyArchive] Built archive for %s global IDs",
                len(self.full_journeys),
            )

    def build_snapshot(self, recent_events: Optional[List[Dict]] = None) -> Dict:
        """Build a lightweight summary snapshot for dashboard clients."""
        return {
            "type": "camera_journey_snapshot",
            "journeys": {
                str(global_id): summary
                for global_id, summary in sorted(self.summaries.items())
            },
            "recent_events": recent_events or [],
        }

    def get_journey(self, global_id: int) -> Optional[Dict]:
        """Return full journey-view data for one Global ID."""
        return self.full_journeys.get(global_id)
