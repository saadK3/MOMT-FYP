"""
Flask backend server for frame extraction
Serves video frames for the visualization
Uses same logic as validate_global_id.py
"""

from flask import Flask, send_file, jsonify
from flask_cors import CORS
import cv2
import os
import io
from PIL import Image
import numpy as np

app = Flask(__name__)
CORS(app)  # Enable CORS for local development

# Use relative path from script location (same as validate_global_id.py)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
VIDEO_DIR = os.path.join(PROJECT_ROOT, 'videos')
FOOTPRINT_INDICES = [12, 13, 14, 15]

CAMERA_COLORS = {
    'c001': (255, 107, 107),  # Red
    'c002': (78, 205, 196),   # Teal
    'c003': (69, 183, 209),   # Blue
    'c004': (255, 160, 122),  # Orange
    'c005': (152, 216, 200)   # Green
}

print(f"Frame server initialized")
print(f"Video directory: {VIDEO_DIR}")
print(f"Videos exist: {os.path.exists(VIDEO_DIR)}")
if os.path.exists(VIDEO_DIR):
    print(f"Video files: {os.listdir(VIDEO_DIR)}")


@app.route('/frame/<camera>/<int:frame_number>', methods=['GET'])
def get_frame(camera, frame_number):
    """Extract a specific frame from a camera video"""
    try:
        video_path = os.path.join(VIDEO_DIR, f'S01_{camera}.mp4')

        print(f"Requesting frame {frame_number} from {camera}")
        print(f"Video path: {video_path}")
        print(f"File exists: {os.path.exists(video_path)}")

        if not os.path.exists(video_path):
            return jsonify({'error': f'Video not found: {video_path}'}), 404

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return jsonify({'error': f'Could not open video: {video_path}'}), 500

        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
        ret, frame = cap.read()
        cap.release()

        if not ret:
            return jsonify({'error': f'Frame {frame_number} not found in {camera}'}), 404

        # Convert BGR to RGB
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Convert to PIL Image
        img = Image.fromarray(frame)

        # Save to bytes
        img_io = io.BytesIO()
        img.save(img_io, 'JPEG', quality=85)
        img_io.seek(0)

        return send_file(img_io, mimetype='image/jpeg')

    except Exception as e:
        print(f"Error extracting frame: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/frame_with_footprint/<camera>/<int:frame_number>/<track_id>/<keypoints>', methods=['GET'])
def get_frame_with_footprint(camera, frame_number, track_id, keypoints):
    """Extract frame with footprint overlay (same as validate_global_id.py)"""
    try:
        video_path = os.path.join(VIDEO_DIR, f'S01_{camera}.mp4')

        print(f"Requesting frame with footprint: {camera}, frame {frame_number}, track {track_id}")

        if not os.path.exists(video_path):
            return jsonify({'error': f'Video not found: {video_path}'}), 404

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return jsonify({'error': f'Could not open video: {video_path}'}), 500

        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
        ret, frame = cap.read()
        cap.release()

        if not ret:
            return jsonify({'error': f'Frame {frame_number} not found'}), 404

        # Parse keypoints
        kp_list = [float(x) for x in keypoints.split(',')]

        # Draw footprint (same logic as validate_global_id.py)
        img_h, img_w = frame.shape[:2]

        footprint_pts = []
        for kp_idx in FOOTPRINT_INDICES:
            x = int(kp_list[kp_idx * 2] * img_w)
            y = int(kp_list[kp_idx * 2 + 1] * img_h)
            footprint_pts.append([x, y])

        # Draw polygon (same order as validate_global_id.py)
        pts = np.array([
            footprint_pts[0], footprint_pts[1],
            footprint_pts[3], footprint_pts[2]
        ], dtype=np.int32)

        cv2.polylines(frame, [pts], True, (0, 255, 0), 4)

        # Add label (same as validate_global_id.py)
        center = np.array(footprint_pts).mean(axis=0).astype(int)
        label = f'{camera}-T{track_id}'
        cv2.putText(frame, label, tuple(center - [0, 30]),
                   cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 0), 3)

        # Convert BGR to RGB
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Convert to PIL Image
        img = Image.fromarray(frame)

        # Save to bytes
        img_io = io.BytesIO()
        img.save(img_io, 'JPEG', quality=85)
        img_io.seek(0)

        return send_file(img_io, mimetype='image/jpeg')

    except Exception as e:
        print(f"Error extracting frame with footprint: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'ok',
        'video_dir': VIDEO_DIR,
        'video_dir_exists': os.path.exists(VIDEO_DIR),
        'videos': os.listdir(VIDEO_DIR) if os.path.exists(VIDEO_DIR) else []
    })


if __name__ == '__main__':
    print("\n" + "="*70)
    print("Starting Frame Extraction Server")
    print("="*70)
    print(f"Video directory: {VIDEO_DIR}")
    print(f"Server running at http://localhost:5000")
    print(f"Health check: http://localhost:5000/health")
    print("="*70 + "\n")
    app.run(host='0.0.0.0', port=5000, debug=True)
