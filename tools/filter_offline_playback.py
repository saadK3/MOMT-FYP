"""
Quality-based demo filter for offline playback.

Reads a full offline playback file, computes per-track quality metrics,
selects high-quality tracks using hard gates + demo-impact scoring,
and writes a filtered playback file while preserving full timeline.

Default I/O:
  input  : dashboard/public/offline_playback.json
  output : dashboard/public/offline_playback_demo.json
  report : output/offline_filter_report.json
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, pstdev
from typing import Dict, List, Tuple


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_INPUT = ROOT / "dashboard" / "public" / "offline_playback.json"
DEFAULT_OUTPUT = ROOT / "dashboard" / "public" / "offline_playback_demo.json"
DEFAULT_REPORT = ROOT / "output" / "offline_filter_report.json"

FILTER_VERSION = "v1.0.0"


CRITERIA = {
    # "Hygiene" preset: remove only clearly problematic tracks.
    "duration_s_min": 2.5,
    "max_gap_frames_max": 12,
    "path_length_min": 5.0,
    "visible_frames_min": 15,
    "jitter_score_max": 0.92,
    # Set to 0 to keep all hard-pass tracks (no extra score pruning).
    "score_min": 0.0,
}


@dataclass
class TrackStats:
    global_id: int
    first_ts: float | None = None
    last_ts: float | None = None
    visible_frames: int = 0
    max_gap_frames: int = 0
    last_seen_idx: int | None = None
    path_length: float = 0.0
    camera_count: int = 0
    cameras: set = field(default_factory=set)
    transition_count: int = 0
    last_camera_label: str | None = None
    real_count: int = 0
    total_count: int = 0
    prev_centroid: Tuple[float, float] | None = None
    step_lengths: List[float] = field(default_factory=list)
    step_headings: List[float] = field(default_factory=list)
    # Computed outputs
    duration_s: float = 0.0
    jitter_score: float = 1.0
    real_ratio: float = 1.0
    score: float = 0.0
    hard_pass: bool = False
    selected: bool = False
    reject_reasons: List[str] = field(default_factory=list)


def load_playback(path: Path) -> Dict:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError(f"Input file is empty: {path}")

    if text.startswith("{"):
        payload = json.loads(text)
        if not isinstance(payload, dict) or "frames" not in payload:
            raise ValueError("Expected JSON object with top-level 'frames'.")
        return payload

    # JSONL fallback support
    frames = [json.loads(line) for line in text.splitlines() if line.strip()]
    return {"type": "offline_playback", "metadata": {}, "frames": frames}


def angle_diff_deg(a: float, b: float) -> float:
    diff = abs(a - b) % 360.0
    if diff > 180.0:
        diff = 360.0 - diff
    return diff


def clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def infer_camera_label(vehicle: Dict) -> str:
    label = vehicle.get("camera_state_label")
    if isinstance(label, str) and label.strip():
        return label.strip()
    state = vehicle.get("camera_state")
    if isinstance(state, list) and state:
        return " + ".join(str(cam).upper() for cam in state)
    camera = vehicle.get("camera")
    return str(camera).upper() if camera else "UNKNOWN"


def aggregate_track_stats(frames: List[Dict]) -> Dict[int, TrackStats]:
    by_gid: Dict[int, TrackStats] = {}

    for frame_idx, frame in enumerate(frames):
        ts = float(frame.get("timestamp", 0.0))
        for vehicle in frame.get("vehicles", []):
            try:
                gid = int(vehicle["global_id"])
            except (KeyError, TypeError, ValueError):
                continue

            stats = by_gid.setdefault(gid, TrackStats(global_id=gid))
            stats.total_count += 1
            if not vehicle.get("is_ghost", False):
                stats.real_count += 1
            if stats.first_ts is None:
                stats.first_ts = ts
            stats.last_ts = ts
            stats.visible_frames += 1

            if stats.last_seen_idx is not None:
                gap = frame_idx - stats.last_seen_idx - 1
                if gap > stats.max_gap_frames:
                    stats.max_gap_frames = gap
            stats.last_seen_idx = frame_idx

            camera = vehicle.get("camera")
            if camera:
                stats.cameras.add(camera)
            camera_label = infer_camera_label(vehicle)
            if stats.last_camera_label and camera_label != stats.last_camera_label:
                stats.transition_count += 1
            stats.last_camera_label = camera_label

            centroid = vehicle.get("centroid")
            if (
                isinstance(centroid, list)
                and len(centroid) == 2
                and all(isinstance(v, (int, float)) for v in centroid)
            ):
                cx, cy = float(centroid[0]), float(centroid[1])
                if stats.prev_centroid is not None:
                    dx = cx - stats.prev_centroid[0]
                    dy = cy - stats.prev_centroid[1]
                    step = math.hypot(dx, dy)
                    if step > 0:
                        stats.path_length += step
                        stats.step_lengths.append(step)
                        heading = math.degrees(math.atan2(dy, dx))
                        if heading < 0:
                            heading += 360.0
                        stats.step_headings.append(heading)
                stats.prev_centroid = (cx, cy)

    for stats in by_gid.values():
        stats.duration_s = max(0.0, (stats.last_ts or 0.0) - (stats.first_ts or 0.0))
        stats.camera_count = len(stats.cameras)
        stats.real_ratio = (
            stats.real_count / stats.total_count if stats.total_count > 0 else 1.0
        )

        if len(stats.step_headings) >= 2:
            diffs = [
                angle_diff_deg(stats.step_headings[i], stats.step_headings[i - 1])
                for i in range(1, len(stats.step_headings))
            ]
            heading_jitter = mean(diffs)
            heading_norm = clamp01(heading_jitter / 90.0)
        else:
            heading_norm = 0.0

        if len(stats.step_lengths) >= 2 and mean(stats.step_lengths) > 1e-9:
            step_cv = pstdev(stats.step_lengths) / mean(stats.step_lengths)
            step_norm = clamp01(step_cv / 1.5)
        else:
            step_norm = 0.0

        # Lower is better: 0 = smooth, 1 = noisy.
        stats.jitter_score = clamp01(0.6 * heading_norm + 0.4 * step_norm)

    return by_gid


def apply_hard_gate(stats: TrackStats) -> Tuple[bool, List[str]]:
    reasons = []
    if stats.duration_s < CRITERIA["duration_s_min"]:
        reasons.append(f"duration_s<{CRITERIA['duration_s_min']}")
    if stats.max_gap_frames > CRITERIA["max_gap_frames_max"]:
        reasons.append(f"max_gap_frames>{CRITERIA['max_gap_frames_max']}")
    if stats.path_length < CRITERIA["path_length_min"]:
        reasons.append(f"path_length<{CRITERIA['path_length_min']}")
    if stats.visible_frames < CRITERIA["visible_frames_min"]:
        reasons.append(f"visible_frames<{CRITERIA['visible_frames_min']}")
    if stats.jitter_score > CRITERIA["jitter_score_max"]:
        reasons.append(f"jitter_score>{CRITERIA['jitter_score_max']}")
    return (len(reasons) == 0), reasons


def compute_scores(survivors: List[TrackStats]) -> None:
    if not survivors:
        return

    duration_cap = max(60.0, max(s.duration_s for s in survivors))
    path_cap = max(200.0, max(s.path_length for s in survivors))

    for s in survivors:
        duration_norm = clamp01(s.duration_s / duration_cap)
        continuity_norm = clamp01(1.0 - (s.max_gap_frames / max(1.0, CRITERIA["max_gap_frames_max"])))
        path_norm = clamp01(s.path_length / path_cap)
        smoothness_norm = clamp01(1.0 - s.jitter_score)
        multicam_bonus = 1.0 if s.camera_count >= 2 else 0.4

        s.score = (
            0.35 * duration_norm
            + 0.25 * continuity_norm
            + 0.20 * path_norm
            + 0.15 * smoothness_norm
            + 0.05 * multicam_bonus
        )


def select_tracks(by_gid: Dict[int, TrackStats]) -> Tuple[List[int], List[int]]:
    survivors: List[TrackStats] = []
    rejected_ids: List[int] = []

    for gid in sorted(by_gid):
        s = by_gid[gid]
        passed, reasons = apply_hard_gate(s)
        s.hard_pass = passed
        s.reject_reasons = reasons
        if passed:
            survivors.append(s)
        else:
            rejected_ids.append(gid)

    compute_scores(survivors)

    if CRITERIA["score_min"] <= 0:
        selected = survivors[:]
    else:
        selected = [s for s in survivors if s.score >= CRITERIA["score_min"]]
        if not selected:
            selected = survivors[:]  # fallback per requirement

    selected_ids = sorted(s.global_id for s in selected)
    selected_set = set(selected_ids)
    for gid, s in by_gid.items():
        s.selected = gid in selected_set
        if s.hard_pass and not s.selected:
            s.reject_reasons = [f"score<{CRITERIA['score_min']}"]

    return selected_ids, rejected_ids


def recompute_frame_stats(frame: Dict, vehicles: List[Dict], selected_gid_count: int) -> Dict:
    arrived_cameras = sorted(
        {v.get("camera") for v in vehicles if isinstance(v.get("camera"), str)}
    )
    unique_gids = {int(v["global_id"]) for v in vehicles if "global_id" in v}
    old_stats = frame.get("stats", {}) or {}
    decision_type = old_stats.get("decision_type", "offline_batch")
    return {
        "num_detections": len(vehicles),
        "num_clusters": len(unique_gids),
        "num_global_ids": selected_gid_count,
        "arrived_cameras": arrived_cameras,
        "decision_type": f"{decision_type}|demo_filter",
    }


def build_filtered_payload(payload: Dict, selected_ids: List[int]) -> Dict:
    selected_set = set(selected_ids)
    out_frames = []

    for frame in payload.get("frames", []):
        vehicles = [
            v for v in frame.get("vehicles", [])
            if int(v.get("global_id", -1)) in selected_set
        ]
        journey_updates = {
            gid: data
            for gid, data in (frame.get("journey_updates", {}) or {}).items()
            if int(gid) in selected_set
        }
        camera_events = [
            ev for ev in (frame.get("camera_change_events", []) or [])
            if int(ev.get("global_id", -1)) in selected_set
        ]

        out_frames.append(
            {
                "type": frame.get("type", "tracking_update"),
                "timestamp": frame.get("timestamp"),
                "vehicles": vehicles,
                "journey_updates": journey_updates,
                "camera_change_events": camera_events,
                "stats": recompute_frame_stats(frame, vehicles, len(selected_ids)),
            }
        )

    metadata = dict(payload.get("metadata", {}) or {})
    metadata.update(
        {
            "num_frames": len(out_frames),
            "num_global_ids": len(selected_ids),
            "filter_version": FILTER_VERSION,
            "filter_criteria": CRITERIA,
            "selected_gid_count": len(selected_ids),
            "selected_gids": selected_ids,
            "source_file": str(DEFAULT_INPUT),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
    )

    return {
        "type": payload.get("type", "offline_playback"),
        "metadata": metadata,
        "frames": out_frames,
    }


def summarize_quality(stats_list: List[TrackStats]) -> Dict:
    if not stats_list:
        return {}
    return {
        "count": len(stats_list),
        "avg_duration_s": mean(s.duration_s for s in stats_list),
        "avg_visible_frames": mean(s.visible_frames for s in stats_list),
        "avg_max_gap_frames": mean(s.max_gap_frames for s in stats_list),
        "avg_path_length": mean(s.path_length for s in stats_list),
        "avg_camera_count": mean(s.camera_count for s in stats_list),
        "multi_camera_ratio": (
            sum(1 for s in stats_list if s.camera_count >= 2) / len(stats_list)
        ),
        "avg_jitter_score": mean(s.jitter_score for s in stats_list),
    }


def build_report(
    input_path: Path,
    output_path: Path,
    by_gid: Dict[int, TrackStats],
    selected_ids: List[int],
) -> Dict:
    stats_all = list(by_gid.values())
    selected_set = set(selected_ids)
    selected_stats = [s for s in stats_all if s.global_id in selected_set]
    rejected_stats = [s for s in stats_all if s.global_id not in selected_set]

    reason_buckets: Dict[str, int] = {}
    rejected_items = []
    for s in rejected_stats:
        reasons = s.reject_reasons or ["not_selected"]
        for r in reasons:
            reason_buckets[r] = reason_buckets.get(r, 0) + 1
        rejected_items.append(
            {
                "global_id": s.global_id,
                "reasons": reasons,
                "duration_s": round(s.duration_s, 3),
                "visible_frames": s.visible_frames,
                "max_gap_frames": s.max_gap_frames,
                "path_length": round(s.path_length, 3),
                "camera_count": s.camera_count,
                "jitter_score": round(s.jitter_score, 4),
                "score": round(s.score, 4),
            }
        )

    selected_items = [
        {
            "global_id": s.global_id,
            "duration_s": round(s.duration_s, 3),
            "visible_frames": s.visible_frames,
            "max_gap_frames": s.max_gap_frames,
            "path_length": round(s.path_length, 3),
            "camera_count": s.camera_count,
            "transition_count": s.transition_count,
            "jitter_score": round(s.jitter_score, 4),
            "real_ratio": round(s.real_ratio, 4),
            "score": round(s.score, 4),
        }
        for s in sorted(selected_stats, key=lambda x: x.score, reverse=True)
    ]

    return {
        "filter_version": FILTER_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input_file": str(input_path),
        "output_file": str(output_path),
        "criteria": CRITERIA,
        "gid_counts": {
            "total": len(stats_all),
            "hard_pass": sum(1 for s in stats_all if s.hard_pass),
            "selected": len(selected_stats),
            "rejected": len(rejected_stats),
        },
        "quality_summary": {
            "before": summarize_quality(stats_all),
            "after": summarize_quality(selected_stats),
        },
        "selected_gids": [s["global_id"] for s in selected_items],
        "selected_tracks": selected_items,
        "rejected_reason_counts": reason_buckets,
        "rejected_tracks": rejected_items,
    }


def main():
    parser = argparse.ArgumentParser(description="Filter offline playback for demo")
    parser.add_argument("--in", dest="input_path", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--out", dest="output_path", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", dest="report_path", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()

    payload = load_playback(args.input_path)
    frames = payload.get("frames", [])
    if not frames:
        raise ValueError(f"No frames found in input: {args.input_path}")

    by_gid = aggregate_track_stats(frames)
    selected_ids, _rejected_ids = select_tracks(by_gid)

    filtered = build_filtered_payload(payload, selected_ids)

    args.output_path.parent.mkdir(parents=True, exist_ok=True)
    args.output_path.write_text(json.dumps(filtered, indent=2), encoding="utf-8")

    report = build_report(args.input_path, args.output_path, by_gid, selected_ids)
    args.report_path.parent.mkdir(parents=True, exist_ok=True)
    args.report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("=" * 72)
    print("Offline playback demo filter complete")
    print("-" * 72)
    print(f"Input   : {args.input_path}")
    print(f"Output  : {args.output_path}")
    print(f"Report  : {args.report_path}")
    print(f"Frames  : {len(frames)} (timeline preserved)")
    print(f"GIDs    : {len(by_gid)} -> {len(selected_ids)} selected")
    print("=" * 72)


if __name__ == "__main__":
    main()
