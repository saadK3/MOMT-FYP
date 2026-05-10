"""
Build a deterministic offline playback JSON from the 5 camera JSON files.

This reuses the existing cross_camera_tracking matching + clustering + global-ID
assignment pipeline, but runs it in batch over synchronized timestamp buckets.

Usage:
    python tools/build_offline_playback.py
    python tools/build_offline_playback.py --fps 10 --out output/offline_playback.json
"""

import argparse
import json
import math
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cross_camera_tracking.clustering import agglomerative_clustering
from cross_camera_tracking.geometry import compute_centroid, parse_footprint
from cross_camera_tracking.matching import build_score_matrix
from cross_camera_tracking.tracker import CrossCameraTracker
from emulator import config as emulator_config
from emulator.json_reader import load_all_cameras


HISTORY_WINDOW = 3
HISTORY_MAXLEN = 8


# Offline handover smoothing defaults (tuned for 5 FPS demo playback)
HANDOVER_ENTER_HOLD_S = 1.0   # challenger must stay better for this long
HANDOVER_EXIT_GRACE_S = 1.6   # keep ownership while primary briefly disappears
HANDOVER_MIN_DWELL_S = 2.0    # prevent immediate switch-back after a handover
HANDOVER_SWITCH_MARGIN = 0.2  # challenger score must exceed primary by this


def id_to_color(global_id: int) -> str:
    hue = (global_id * 137.508) % 360
    return f"hsla({hue:.0f}, 75%, 55%, 0.75)"


def _camera_state_label(camera_state: List[str]) -> str:
    if not camera_state:
        return "Unknown"
    return " + ".join(camera.upper() for camera in camera_state)


def _bucket_timestamp(timestamp: float, time_step: float) -> float:
    return round(round(timestamp / time_step) * time_step, 6)


def _footprint_area(footprint: List[float]) -> float:
    poly = parse_footprint(footprint)
    return poly.area if poly is not None else 0.0


def _parse_frame_number(value) -> int:
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        match = re.search(r"(\d+)", value)
        if match:
            return int(match.group(1))
    return 0


def _compute_motion(history: List[Tuple[float, Tuple[float, float]]]):
    if len(history) < 2:
        return None, None
    window = history[-HISTORY_WINDOW:]
    dt = window[-1][0] - window[0][0]
    if dt <= 1e-9:
        return None, None
    dx = window[-1][1][0] - window[0][1][0]
    dy = window[-1][1][1] - window[0][1][1]
    speed = math.hypot(dx, dy) / dt
    direction = math.degrees(math.atan2(dy, dx))
    if direction < 0:
        direction += 360.0
    return speed, direction


def _record_camera_journey(
    journeys: Dict[int, Dict],
    recent_events: List[Dict],
    max_events: int,
    global_id: int,
    camera_state: List[str],
    timestamp: float,
):
    """Mimics tracking_server camera-journey logic for offline frames."""
    record = journeys.get(global_id)

    if record is None:
        journeys[global_id] = {
            "current_camera_state": camera_state,
            "previous_camera_state": None,
            "unique_cameras": camera_state[:],
            "transition_count": 0,
            "has_camera_changed": False,
            "last_seen_at": timestamp,
            "journey": [
                {
                    "camera_state": camera_state,
                    "entered_at": timestamp,
                    "last_seen_at": timestamp,
                }
            ],
            "last_transition": None,
        }
        return True, None

    record["last_seen_at"] = timestamp
    segment = record["journey"][-1]
    if segment["camera_state"] == camera_state:
        segment["last_seen_at"] = timestamp
        record["current_camera_state"] = camera_state
        return False, None

    previous_state = record["current_camera_state"]
    record["previous_camera_state"] = previous_state
    record["current_camera_state"] = camera_state
    record["transition_count"] += 1
    record["has_camera_changed"] = True
    record["unique_cameras"] = sorted(set(record["unique_cameras"]) | set(camera_state))
    record["journey"].append(
        {
            "camera_state": camera_state,
            "entered_at": timestamp,
            "last_seen_at": timestamp,
        }
    )

    event = {
        "event_id": (
            f"{global_id}:{timestamp:.2f}:"
            f"{'-'.join(previous_state)}>{'-'.join(camera_state)}"
        ),
        "global_id": global_id,
        "timestamp": round(timestamp, 2),
        "from_camera_state": previous_state,
        "from_camera_label": _camera_state_label(previous_state),
        "to_camera_state": camera_state,
        "to_camera_label": _camera_state_label(camera_state),
        "transition_index": record["transition_count"],
    }
    record["last_transition"] = event
    recent_events.append(event)
    if len(recent_events) > max_events:
        del recent_events[:-max_events]
    return True, event


def _frames_from_seconds(seconds: float, fps: float) -> int:
    return max(1, int(math.ceil(seconds * fps)))


def _camera_presence_scores(
    group: List[Dict],
    primary_camera: Optional[str] = None,
) -> Dict[str, float]:
    """
    Build a per-camera score for one GID at a timestamp.

    Presence dominates (1.0), footprint area provides confidence, and we add a
    slight bias toward the current owner to reduce overlap-zone ping-pong.
    """
    areas_by_camera: Dict[str, float] = defaultdict(float)
    for det in group:
        camera = det["camera"]
        areas_by_camera[camera] = max(
            areas_by_camera[camera],
            _footprint_area(det.get("footprint", [])),
        )

    max_area = max(areas_by_camera.values(), default=0.0)
    scores: Dict[str, float] = {}
    for camera, area in areas_by_camera.items():
        relative_area = (area / max_area) if max_area > 0 else 0.0
        score = 1.0 + relative_area
        if primary_camera is not None and camera == primary_camera:
            score += 0.25
        scores[camera] = score

    return scores


def _pick_best_camera(scores: Dict[str, float]) -> Optional[str]:
    if not scores:
        return None
    return max(scores.items(), key=lambda item: item[1])[0]


def _update_handover_state(
    state: Dict,
    observed_cameras: List[str],
    scores: Dict[str, float],
    timestamp: float,
    frame_idx: int,
    fps: float,
) -> Optional[str]:
    """
    State machine for stable handover decisions.

    Returns:
        primary camera ID after applying stability rules.
    """
    if not observed_cameras:
        return state.get("primary_camera")

    enter_hold_frames = _frames_from_seconds(HANDOVER_ENTER_HOLD_S, fps)
    exit_grace_frames = _frames_from_seconds(HANDOVER_EXIT_GRACE_S, fps)
    min_dwell_frames = _frames_from_seconds(HANDOVER_MIN_DWELL_S, fps)
    primary = state.get("primary_camera")

    if primary is None:
        primary = _pick_best_camera(scores)
        state["primary_camera"] = primary
        state["last_switch_frame"] = frame_idx
        state["last_switch_ts"] = timestamp
        state["absent_streak"] = 0
        state["challenger_camera"] = None
        state["challenger_streak"] = 0
        return primary

    last_switch_frame = state.get("last_switch_frame")
    if last_switch_frame is None:
        frames_since_switch = min_dwell_frames
    else:
        frames_since_switch = frame_idx - last_switch_frame
    in_cooldown = frames_since_switch < min_dwell_frames

    primary_visible = primary in observed_cameras
    if primary_visible:
        state["absent_streak"] = 0
        primary_score = scores.get(primary, 0.0)
        challengers = [
            (camera, score)
            for camera, score in scores.items()
            if camera != primary and score >= primary_score + HANDOVER_SWITCH_MARGIN
        ]
        if not challengers or in_cooldown:
            state["challenger_camera"] = None
            state["challenger_streak"] = 0
            return primary

        challenger = max(challengers, key=lambda item: item[1])[0]
        if state.get("challenger_camera") == challenger:
            state["challenger_streak"] = state.get("challenger_streak", 0) + 1
        else:
            state["challenger_camera"] = challenger
            state["challenger_streak"] = 1

        if state["challenger_streak"] >= enter_hold_frames:
            state["primary_camera"] = challenger
            state["last_switch_frame"] = frame_idx
            state["last_switch_ts"] = timestamp
            state["absent_streak"] = 0
            state["challenger_camera"] = None
            state["challenger_streak"] = 0
            return challenger

        return primary

    state["absent_streak"] = state.get("absent_streak", 0) + 1
    if state["absent_streak"] <= exit_grace_frames:
        state["challenger_camera"] = None
        state["challenger_streak"] = 0
        return primary

    candidate = _pick_best_camera(scores)
    if candidate is None:
        return primary

    if state.get("challenger_camera") == candidate:
        state["challenger_streak"] = state.get("challenger_streak", 0) + 1
    else:
        state["challenger_camera"] = candidate
        state["challenger_streak"] = 1

    required = max(1, enter_hold_frames // 2)
    if state["challenger_streak"] >= required:
        state["primary_camera"] = candidate
        state["last_switch_frame"] = frame_idx
        state["last_switch_ts"] = timestamp
        state["absent_streak"] = 0
        state["challenger_camera"] = None
        state["challenger_streak"] = 0
        return candidate

    return primary


def build_offline_playback(
    fps: float,
    start_time: float,
    end_time: float,
) -> Tuple[Dict, Dict]:
    time_step = round(1.0 / fps, 6)

    all_camera_data = load_all_cameras(
        emulator_config.JSON_DIR,
        emulator_config.CAMERAS,
        emulator_config.JSON_PATTERN,
    )
    if not all_camera_data:
        raise RuntimeError("No camera data loaded.")

    # Build synchronized timestamp buckets from all cameras.
    # bucket_ts -> list[(camera_id, raw_detection)]
    buckets: Dict[float, List[Tuple[str, Dict]]] = defaultdict(list)
    for camera_id, det_map in all_camera_data.items():
        offset = emulator_config.CAMERA_TIME_OFFSETS.get(camera_id, 0.0)
        for local_ts, frame_dets in det_map.items():
            global_ts = local_ts + offset
            bucket_ts = _bucket_timestamp(global_ts, time_step)
            if bucket_ts < start_time or bucket_ts > end_time:
                continue
            for raw in frame_dets:
                buckets[bucket_ts].append((camera_id, raw))

    tracker = CrossCameraTracker()
    motion_history: Dict[Tuple[str, int], List[Tuple[float, Tuple[float, float]]]] = defaultdict(list)
    camera_journeys: Dict[int, Dict] = {}
    recent_camera_events: List[Dict] = []
    frames: List[Dict] = []
    handover_state_by_gid: Dict[int, Dict] = {}
    observations_by_gid: Dict[str, Dict[str, List[Dict]]] = defaultdict(
        lambda: defaultdict(list)
    )

    for frame_idx, ts in enumerate(sorted(buckets.keys())):
        raw_bucket = buckets[ts]
        detections = []

        # Build detection list expected by matching/tracker modules.
        for camera_id, raw in raw_bucket:
            footprint = raw.get("det_birdeye", [])
            track_id = int(raw.get("track_id", 0))
            centroid = compute_centroid(footprint) if len(footprint) == 8 else None

            speed = None
            direction = None
            if centroid is not None:
                key = (camera_id, track_id)
                history = motion_history[key]
                history.append((ts, centroid))
                if len(history) > HISTORY_MAXLEN:
                    del history[0]
                speed, direction = _compute_motion(history)

            detections.append(
                {
                    "camera": camera_id,
                    "track_id": track_id,
                    "footprint": footprint,
                    "bbox": raw.get("det_bbox", []) or [],
                    "class": raw.get("det_kp_class_name", "unknown"),
                    "timestamp": ts,
                    "frame": _parse_frame_number(raw.get("det_impath", 0)),
                    "speed": speed,
                    "direction": direction,
                    "keypoints": raw.get("det_keypoints", []) or [],
                    "image_w": raw.get("det_im_w"),
                    "image_h": raw.get("det_im_h"),
                }
            )

        vehicles = []
        journey_updates = {}
        camera_change_events = []
        num_clusters = 0

        if detections:
            score_matrix = build_score_matrix(detections)
            clusters = agglomerative_clustering(detections, score_matrix)
            num_clusters = len(clusters)
            tracker.assign_global_ids(clusters, detections, ts)

            detections_by_gid: Dict[int, List[Dict]] = defaultdict(list)
            for det in detections:
                key = (det["camera"], det["track_id"])
                gid = tracker.global_id_map.get(key)
                if gid is not None:
                    detections_by_gid[gid].append(det)
                    observations_by_gid[str(gid)][det["camera"]].append(
                        {
                            "global_ts": round(ts, 3),
                            "frame_number": det["frame"],
                            "track_id": det["track_id"],
                            "det_bbox": det["bbox"],
                            "det_keypoints": det["keypoints"],
                            "det_im_w": det["image_w"],
                            "det_im_h": det["image_h"],
                        }
                    )

            for gid, group in detections_by_gid.items():
                observed_cameras = sorted({det["camera"] for det in group})
                state = handover_state_by_gid.setdefault(
                    gid,
                    {
                        "primary_camera": None,
                        "last_switch_frame": None,
                        "last_switch_ts": None,
                        "absent_streak": 0,
                        "challenger_camera": None,
                        "challenger_streak": 0,
                    },
                )
                scores = _camera_presence_scores(
                    group,
                    primary_camera=state.get("primary_camera"),
                )
                primary_camera = _update_handover_state(
                    state=state,
                    observed_cameras=observed_cameras,
                    scores=scores,
                    timestamp=ts,
                    frame_idx=frame_idx,
                    fps=fps,
                )

                camera_state = [primary_camera] if primary_camera else observed_cameras
                changed, transition_event = _record_camera_journey(
                    journeys=camera_journeys,
                    recent_events=recent_camera_events,
                    max_events=50,
                    global_id=gid,
                    camera_state=camera_state,
                    timestamp=ts,
                )
                if changed:
                    rec = camera_journeys[gid]
                    journey_updates[str(gid)] = {
                        "global_id": gid,
                        "current_camera_state": rec["current_camera_state"],
                        "current_camera_label": _camera_state_label(rec["current_camera_state"]),
                        "previous_camera_state": rec["previous_camera_state"],
                        "previous_camera_label": (
                            _camera_state_label(rec["previous_camera_state"])
                            if rec["previous_camera_state"]
                            else None
                        ),
                        "unique_cameras": rec["unique_cameras"],
                        "transition_count": rec["transition_count"],
                        "has_camera_changed": rec["has_camera_changed"],
                        "last_seen_at": round(rec["last_seen_at"], 2),
                        "journey": [
                            {
                                "camera_state": seg["camera_state"],
                                "camera_label": _camera_state_label(seg["camera_state"]),
                                "entered_at": round(seg["entered_at"], 2),
                                "last_seen_at": round(seg["last_seen_at"], 2),
                            }
                            for seg in rec["journey"]
                        ],
                        "last_transition": rec["last_transition"],
                    }
                if transition_event is not None:
                    camera_change_events.append(transition_event)

                # Use the largest-footprint detection as representative vehicle for this GID
                primary = max(group, key=lambda d: _footprint_area(d["footprint"]))
                centroid = (
                    list(compute_centroid(primary["footprint"]))
                    if len(primary["footprint"]) == 8
                    else [0.0, 0.0]
                )
                rec = camera_journeys[gid]
                vehicles.append(
                    {
                        "global_id": gid,
                        "camera": primary["camera"],
                        "track_id": primary["track_id"],
                        "class": primary["class"],
                        "footprint": primary["footprint"],
                        "centroid": centroid,
                        "color": id_to_color(gid),
                        "camera_state": camera_state,
                        "camera_state_label": _camera_state_label(camera_state),
                        "observed_camera_state": observed_cameras,
                        "observed_camera_state_label": _camera_state_label(
                            observed_cameras
                        ),
                        "has_camera_changed": rec["has_camera_changed"],
                    }
                )

        frame = {
            "type": "tracking_update",
            "timestamp": round(ts, 2),
            "vehicles": vehicles,
            "journey_updates": journey_updates,
            "camera_change_events": camera_change_events,
            "stats": {
                "num_detections": len(detections),
                "num_clusters": num_clusters,
                "num_global_ids": tracker.global_id_counter - 1,
                "arrived_cameras": sorted({det["camera"] for det in detections}),
                "decision_type": "offline_batch",
            },
        }
        frames.append(frame)

    playback_payload = {
        "type": "offline_playback",
        "metadata": {
            "fps": fps,
            "time_step": time_step,
            "start_time": start_time,
            "end_time": end_time,
            "num_frames": len(frames),
            "num_global_ids": tracker.global_id_counter - 1,
            "cameras": emulator_config.CAMERAS,
            "handover_smoothing": {
                "enabled": True,
                "enter_hold_seconds": HANDOVER_ENTER_HOLD_S,
                "exit_grace_seconds": HANDOVER_EXIT_GRACE_S,
                "min_dwell_seconds": HANDOVER_MIN_DWELL_S,
                "switch_margin": HANDOVER_SWITCH_MARGIN,
            },
        },
        "frames": frames,
    }

    observation_index = {
        "type": "offline_observation_index",
        "metadata": {
            "fps": fps,
            "time_step": time_step,
            "start_time": start_time,
            "end_time": end_time,
            "camera_offsets": emulator_config.CAMERA_TIME_OFFSETS,
            "cameras": emulator_config.CAMERAS,
            "num_global_ids": len(observations_by_gid),
        },
        "by_gid": {
            gid: {
                camera: sorted(points, key=lambda item: item["global_ts"])
                for camera, points in cameras.items()
            }
            for gid, cameras in observations_by_gid.items()
        },
    }
    return playback_payload, observation_index


def main():
    parser = argparse.ArgumentParser(description="Build offline playback JSON")
    parser.add_argument("--fps", type=float, default=emulator_config.FPS)
    parser.add_argument("--start", type=float, default=emulator_config.GLOBAL_START_TIME)
    parser.add_argument("--end", type=float, default=emulator_config.GLOBAL_END_TIME)
    parser.add_argument(
        "--out",
        type=str,
        default=str(ROOT / "output" / "offline_playback.json"),
    )
    parser.add_argument(
        "--obs-index-out",
        type=str,
        default=str(ROOT / "output" / "offline_observations_index.json"),
        help="Output path for global_id->camera observation index used by video overlays",
    )
    args = parser.parse_args()

    payload, observation_index = build_offline_playback(args.fps, args.start, args.end)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    obs_path = Path(args.obs_index_out)
    obs_path.parent.mkdir(parents=True, exist_ok=True)
    obs_path.write_text(json.dumps(observation_index, indent=2), encoding="utf-8")

    md = payload["metadata"]
    print("=" * 68)
    print("Offline playback build complete")
    print("-" * 68)
    print(f"Output        : {out_path}")
    print(f"Obs index     : {obs_path}")
    print(f"Frames        : {md['num_frames']}")
    print(f"Global IDs    : {md['num_global_ids']}")
    print(f"Range         : {md['start_time']:.2f}s - {md['end_time']:.2f}s")
    print(f"FPS / step    : {md['fps']} / {md['time_step']}")
    print("=" * 68)


if __name__ == "__main__":
    main()
