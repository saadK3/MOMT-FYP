"""
Flask backend server for frame extraction
Serves video frames for the visualization
Uses same logic as validate_global_id.py
"""

from flask import Flask, send_file, jsonify, request, Response
from flask_cors import CORS
import cv2
import os
import io
import atexit
import threading
from collections import OrderedDict
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

VALID_CAMERAS = {'c001', 'c002', 'c003', 'c004', 'c005'}
MAX_JPEG_CACHE = 500
JPEG_CACHE = OrderedDict()  # (camera, frame_number) -> bytes
CAPTURE_CACHE = {}          # camera -> cv2.VideoCapture
CAPTURE_LOCKS = {camera: threading.Lock() for camera in VALID_CAMERAS}

print("Frame server initialized")
print(f"Video directory: {VIDEO_DIR}")


def _video_path(camera: str) -> str:
    return os.path.join(VIDEO_DIR, f'S01_{camera}.mp4')


def _cache_get(camera: str, frame_number: int):
    key = (camera, frame_number)
    payload = JPEG_CACHE.get(key)
    if payload is None:
        return None
    JPEG_CACHE.move_to_end(key)
    return payload


def _cache_put(camera: str, frame_number: int, payload: bytes):
    key = (camera, frame_number)
    JPEG_CACHE[key] = payload
    JPEG_CACHE.move_to_end(key)
    if len(JPEG_CACHE) > MAX_JPEG_CACHE:
        JPEG_CACHE.popitem(last=False)


def _get_capture(camera: str):
    video_path = _video_path(camera)
    cap = CAPTURE_CACHE.get(camera)
    if cap is not None and cap.isOpened():
        return cap, video_path

    if cap is not None:
        try:
            cap.release()
        except Exception:
            pass

    cap = cv2.VideoCapture(video_path)
    CAPTURE_CACHE[camera] = cap
    return cap, video_path


def _extract_frame_jpeg(camera: str, frame_number: int):
    if camera not in VALID_CAMERAS:
        return None, {'error': f'Unknown camera: {camera}'}, 404

    if frame_number < 0:
        frame_number = 0

    cached = _cache_get(camera, frame_number)
    if cached is not None:
        return cached, None, None

    lock = CAPTURE_LOCKS[camera]
    with lock:
        cap, video_path = _get_capture(camera)
        if not os.path.exists(video_path):
            return None, {'error': f'Video not found: {video_path}'}, 404
        if cap is None or not cap.isOpened():
            return None, {'error': f'Could not open video: {video_path}'}, 500

        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
        ok, frame = cap.read()
        if not ok:
            return None, {'error': f'Frame {frame_number} not found in {camera}'}, 404

    ok, encoded = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
    if not ok:
        return None, {'error': f'Failed to encode frame {frame_number} in {camera}'}, 500
    payload = encoded.tobytes()
    _cache_put(camera, frame_number, payload)
    return payload, None, None


def _jpeg_response(payload: bytes):
    response = Response(payload, mimetype='image/jpeg')
    response.headers['Cache-Control'] = 'public, max-age=3600'
    return response


@atexit.register
def _release_captures():
    for cap in CAPTURE_CACHE.values():
        try:
            cap.release()
        except Exception:
            pass


@app.route('/frame/<camera>/<int:frame_number>', methods=['GET'])
def get_frame(camera, frame_number):
    """Extract a specific frame from a camera video"""
    try:
        payload, error, code = _extract_frame_jpeg(camera, frame_number)
        if error is not None:
            return jsonify(error), code
        return _jpeg_response(payload)

    except Exception as e:
        print(f"Error extracting frame: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/video/<camera>', methods=['GET'])
def get_video(camera):
    """Serve full camera video stream with range support for HTML5 <video>."""
    try:
        video_path = _video_path(camera)
        if not os.path.exists(video_path):
            return jsonify({'error': f'Video not found: {video_path}'}), 404

        file_size = os.path.getsize(video_path)
        range_header = request.headers.get('Range')

        if not range_header:
            return send_file(video_path, mimetype='video/mp4', conditional=True)

        # Example: "bytes=0-1023" or "bytes=1024-"
        units, _, range_spec = range_header.partition('=')
        if units.strip().lower() != 'bytes' or '-' not in range_spec:
            return send_file(video_path, mimetype='video/mp4', conditional=True)

        start_s, _, end_s = range_spec.partition('-')
        start = int(start_s) if start_s.strip() else 0
        end = int(end_s) if end_s.strip() else file_size - 1

        start = max(0, min(start, file_size - 1))
        end = max(start, min(end, file_size - 1))
        length = end - start + 1

        with open(video_path, 'rb') as handle:
            handle.seek(start)
            chunk = handle.read(length)

        response = Response(
            chunk,
            206,
            mimetype='video/mp4',
            direct_passthrough=True,
        )
        response.headers.add('Content-Range', f'bytes {start}-{end}/{file_size}')
        response.headers.add('Accept-Ranges', 'bytes')
        response.headers.add('Content-Length', str(length))
        return response
    except Exception as e:
        print(f"Error serving video: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/frame_with_footprint/<camera>/<int:frame_number>/<track_id>/<keypoints>', methods=['GET'])
def get_frame_with_footprint(camera, frame_number, track_id, keypoints):
    """Extract frame with footprint overlay (same as validate_global_id.py)"""
    try:
        payload, error, code = _extract_frame_jpeg(camera, frame_number)
        if error is not None:
            return jsonify(error), code
        frame_arr = np.frombuffer(payload, dtype=np.uint8)
        frame = cv2.imdecode(frame_arr, cv2.IMREAD_COLOR)
        if frame is None:
            return jsonify({'error': f'Frame decode failed for {camera}:{frame_number}'}), 500

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
        'videos': os.listdir(VIDEO_DIR) if os.path.exists(VIDEO_DIR) else [],
        'jpeg_cache_size': len(JPEG_CACHE),
        'open_captures': sorted([cam for cam, cap in CAPTURE_CACHE.items() if cap is not None and cap.isOpened()]),
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
