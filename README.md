# Cross-Camera Vehicle Tracking System

A real-time multi-camera vehicle tracking system with synchronized timestamp-based tracking and web visualization.

## Project Overview

This project implements a cross-camera vehicle tracking system that:

- Emulates multiple camera feeds with synchronized timestamps
- Performs real-time cross-camera vehicle matching and tracking
- Provides interactive web-based visualization
- Supports network simulation with configurable latency and packet loss

## Directory Structure

```
FYP-final/
├── cross_camera_tracking/   # Core tracking algorithm
│   ├── tracker.py           # Main tracking logic
│   ├── data_loader.py       # JSON data loading
│   ├── matching.py          # Vehicle matching algorithm
│   ├── clustering.py        # Agglomerative clustering
│   └── geometry.py          # Geometric utilities
├── emulator/                # Camera stream emulator
│   ├── app.py              # Main emulator entry point
│   ├── camera_sender.py    # Camera feed simulation
│   ├── hub.py              # Central processing hub
│   ├── network_sim.py      # Network simulation
│   └── websocket_server.py # WebSocket server
├── visualization/           # Web visualization
│   └── frame_server.py     # Flask server for frame extraction
├── scripts/                 # Utility scripts
├── tools/                   # Analysis tools
├── notebooks/               # Jupyter notebooks
├── assets/                  # Static assets
├── json/                    # Camera detection data (auto-generated)
├── output/                  # Processing results (auto-generated)
└── videos/                  # Source videos (auto-generated)
```

## Setup Instructions

### Prerequisites

- Python 3.7 or higher
- Git

### Installation

1. **Clone the repository**

   ```bash
   git clone <repository-url>
   cd FYP-final
   ```

2. **Create a virtual environment**

   ```bash
   python -m venv venv
   ```

3. **Activate the virtual environment**

   - Windows:
     ```bash
     venv\Scripts\activate
     ```
   - Linux/Mac:
     ```bash
     source venv/bin/activate
     ```

4. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

5. **Prepare data directories**

   Create the following directories and add your data:

   ```bash
   mkdir json output videos
   ```

   - `json/`: Place your camera detection JSON files here (format: `S01_<camera_id>.json`)
   - `videos/`: Place your camera video files here (format: `S01_<camera_id>.mp4`)
   - `output/`: Will be auto-generated during tracking

## Usage

### Running the Cross-Camera Tracking

```bash
python run_tracking.py
```

This will:

- Load detection data from the `json/` directory
- Process all timestamps with the tracking algorithm
- Generate results in the `output/` directory

### Running the Emulator

```bash
cd emulator
python app.py
```

The emulator will:

- Start WebSocket server on `ws://localhost:8765`
- Simulate camera feeds with synchronized timestamps
- Support network simulation (latency, jitter, packet loss)

### Running the Visualization Server

```bash
cd visualization
python frame_server.py
```

The server will start on `http://localhost:5000` and provide:

- Frame extraction API
- Health check endpoint at `/health`

## Configuration

### Camera Configuration

Edit `cross_camera_tracking/config.py` or `emulator/config.py` to configure:

- Camera IDs
- Time offsets for synchronization
- Processing parameters
- Network simulation settings

### Example Configuration

```python
CAMERAS = ['c001', 'c002', 'c003', 'c004', 'c005']
CAMERA_TIME_OFFSETS = {
    'c001': 0.0,
    'c002': 0.1,
    'c003': 0.2,
    # ...
}
```

## Key Features

### 1. Timestamp-Based Synchronization

- Handles camera time offsets
- Synchronized global timeline
- Configurable time tolerance

### 2. Cross-Camera Matching

- Geometric footprint matching
- Agglomerative clustering
- Global ID assignment with conflict resolution

### 3. Network Simulation

- Configurable latency and jitter
- Packet loss simulation
- Real-time configuration updates via WebSocket

### 4. Web Visualization

- Real-time tracking display
- Interactive ground plane view
- Multi-camera frame display

## Development

### Running Tests

```bash
# Run validation scripts
python scripts/validate_results.py
python scripts/validate_global_id.py
```

### Analyzing Results

```bash
# Visualize tracking results
python scripts/visualize_tracking.py

# Analyze ground plane coordinates
python tools/analyze_ground_plane.py
```

## Branch Protection & Workflow

This repository uses branch protection on `main`:

- Only the repository owner can commit directly to `main`
- All other changes require pull requests
- Pull requests require owner review before merging

### Recommended Workflow

1. Create a feature branch:

   ```bash
   git checkout -b feature/your-feature-name
   ```

2. Make your changes and commit:

   ```bash
   git add .
   git commit -m "Description of changes"
   ```

3. Push to GitHub:

   ```bash
   git push origin feature/your-feature-name
   ```

4. Create a Pull Request on GitHub
5. Wait for review and approval
6. Merge after approval

## Troubleshooting

### Common Issues

1. **Missing data directories**: Ensure `json/`, `output/`, and `videos/` directories exist
2. **Import errors**: Make sure virtual environment is activated and dependencies are installed
3. **WebSocket connection failed**: Check if port 8765 is available
4. **Frame server errors**: Verify video files exist in `videos/` directory

## License

[Add your license information here]

## Contributors

[Add contributor information here]

## Acknowledgments

[Add acknowledgments here]
