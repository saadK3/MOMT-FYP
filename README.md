# MOMT: Multi-Camera Vehicle Tracking and Visualization Module

A real-time intelligent traffic analytics module that tracks vehicles across multiple camera feeds and visualizes movement in synchronized 2D and 3D environments.

## Overview
MOMT (Multi-Object Multi-Camera Tracking) is an end-to-end module designed for cross-camera vehicle identity continuity, synchronized timeline playback, and interactive spatial monitoring. It is suitable for corridor-level surveillance and complete trajectory reconstruction of vehicles across distributed views.

## Why This Project Matters
- Maintains vehicle identity across multiple non-overlapping camera views.
- Reconstructs complete vehicle trajectories across a monitored corridor.
- Aligns detections on a shared global timeline for coherent replay and analysis.
- Supports both 2D operational monitoring and 3D situational visualization.
- Includes network-condition simulation to evaluate system robustness.

## Core Capabilities
- Cross-camera global ID assignment and consistency management.
- Timestamp-aware synchronization across distributed camera streams.
- Real-time WebSocket delivery of tracking states.
- Browser dashboard for operational insight and playback control.
- Unity WebGL integration for immersive 3D scene visualization.
- Validation and diagnostics tooling for coordinate and tracking quality checks.

## Methodological Foundation
This module uses and builds on core computer vision fundamentals, including detection-driven tracking logic and temporal association across views. It also relies on scene geometry principles to preserve spatial consistency, align multi-camera observations to a shared ground plane, and support reliable trajectory reconstruction.

## System Architecture
The module is organized into modular layers:
- Tracking Engine: Cross-camera association, clustering, and trajectory continuity.
- Camera Emulator: Multi-camera feed simulation with configurable network effects.
- Live Services: Tracking server and frame server for real-time consumption.
- 2D Dashboard: Ground-plane visualization, journey playback, and telemetry panels.
- 3D Visualization: Unity-based WebGL scene for environment-level context.
- Tooling Layer: Alignment, verification, and result-analysis utilities.

## Repository Highlights
- `cross_camera_tracking/`: Core tracking and matching pipeline.
- `emulator/`: Camera stream emulation and transport simulation.
- `dashboard/`: 2D web application and playback interface.
- `unity-view/`: Unity project used to produce WebGL 3D visualization assets.
- `3d-view/`: Additional web-facing 3D layer components.
- `tools/`: Calibration, diagnostics, and evaluation utilities.
- `docs/`: Setup and workflow documentation for contributors.

## Operational Flow
### End-to-End Data Path
1. Camera detections are ingested (live or replayed).
2. Streams are synchronized into a global timeline.
3. Cross-camera matching assigns persistent global IDs.
4. Tracking updates are broadcast to visualization clients.
5. 2D dashboard and 3D view render synchronized vehicle state.

### Flow Diagram (2D + 3D Views)
![System Flow Diagram - 2D and 3D Views](docs/assets/flow-diagram-2d-3d.png)

### Ground Plane View
![Ground Plane View](docs/assets/ground_plane.png)

### Unity Rendering View
![Unity Rendering View](docs/assets/unity_rendering.png)


## Use Cases
- Corridor-level traffic surveillance.
- End-to-end vehicle trajectory reconstruction across camera networks.
- Multi-camera trajectory analysis for transportation research.
- Demonstration environment for cross-view identity tracking methods.

## Performance and Validation Focus
The project includes dedicated workflows for:
- Coordinate consistency checks.
- Global ID validation.
- Projection and ground-plane diagnostics.
- Offline playback verification.

## Technology Stack
- Python services for tracking, simulation, and orchestration.
- WebSocket-based real-time messaging.
- Web frontend for 2D monitoring and playback.
- Unity WebGL pipeline for 3D visualization.

## Roadmap (Suggested Public Backlog)
- Multi-corridor scaling with shared global identity space.
- Model-assisted behavior classification and anomaly detection.
- Automated benchmark reporting for tracking quality metrics.
- Deployment profiles for edge and cloud topologies.



## Contact
Built in collaboration with hazen.ai for our final year project. If you have any queries or questions contact us at:
- saadahmadkhan1612@gmail.com
- abdullahsipra2003@gmail.com
- ibrahim.n.ansari@gmail.com
