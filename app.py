from flask import Flask, Response, jsonify, request
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from PIL import Image, ImageDraw, ImageFont
import threading
import time
import os
import json
from datetime import datetime
import io
import cv2
import random
import numpy as np


app = Flask(__name__)

CORS(app, resources={
    r"/api/*": {
        "origins": "*",
        "methods": ["GET", "POST", "DELETE", "PUT", "OPTIONS"],
        "allow_headers": ["Content-Type"]
    },
    r"/video_feed": {"origins": "*"},
    r"/processed_feed": {"origins": "*"}
})

socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov', 'mkv', 'webm'}
MAX_FILE_SIZE = 500 * 1024 * 1024
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

current_video_data = None
current_video_mimetype = 'video/mp4'
backend_polling_rate = 5
polling_rate_lock = threading.Lock()

DEFAULT_THRESHOLDS = {
    'out': {
        'time_period': 5,
        '2WHLR': {'max_count': 100},
        'LMV': {'max_count': 80},
        'HMV': {'max_count': 50}
    },
    'in': {
        'time_period': 5,
        '2WHLR': {'max_count': 100},
        'LMV': {'max_count': 80},
        'HMV': {'max_count': 50}
    }
}

current_thresholds = DEFAULT_THRESHOLDS.copy()
THRESHOLDS_FILE = 'thresholds.json'

print("Server started")


class AlarmManager:
    def __init__(self):
        self.alarms = []
        self.alarm_id_counter = 1
        self.alarm_history_file = 'alarm_history.json'
        self.lock = threading.Lock()
        self.load_alarms()
        
        if len(self.alarms) == 0:
            self._generate_dummy_alarms()
    
    def _generate_dummy_alarms(self):
        dummy_alarms = [
            {
                'type': 'parked_vehicle',
                'lane': 'OUT',
                'vehicle_type': 'HMV',
                'duration': '5 mins',
                'message': 'Truck parked in no-parking zone'
            },
            {
                'type': 'wrong_lane',
                'lane': 'OUT',
                'vehicle_type': 'LMV',
                'message': 'Car detected in wrong lane'
            },
            {
                'type': 'parked_vehicle',
                'lane': 'IN',
                'vehicle_type': '2WHLR',
                'duration': '3 mins',
                'message': 'Bike parked in restricted area'
            },
            {
                'type': 'wrong_lane',
                'lane': 'IN',
                'vehicle_type': 'HMV',
                'message': 'Truck detected in wrong lane'
            },
        ]
        
        for alarm_data in dummy_alarms:
            self.add_alarm(
                alarm_type=alarm_data['type'],
                lane=alarm_data['lane'],
                vehicle_type=alarm_data.get('vehicle_type'),
                duration=alarm_data.get('duration'),
                message=alarm_data.get('message')
            )
        
        print(f'Generated {len(dummy_alarms)} dummy alarms for testing')
    
    def add_alarm(self, alarm_type, lane, vehicle_type=None, speed=None, 
                  duration=None, count=None, max_count=None, message=None, 
                  details=None, **kwargs):
        with self.lock:
            alarm = {
                'id': f'alarm_{self.alarm_id_counter}',
                'type': alarm_type,
                'lane': lane.upper(),
                'vehicle_type': vehicle_type,
                'timestamp': datetime.now().isoformat(),
                'status': 'active',
                'message': message or details or f'{alarm_type} detected in {lane} lane'
            }
            
            if speed is not None:
                alarm['speed'] = speed
            if duration is not None:
                alarm['duration'] = duration
            if count is not None:
                alarm['count'] = count
            if max_count is not None:
                alarm['max_count'] = max_count
            if details is not None:
                alarm['details'] = details
            
            alarm.update(kwargs)
            
            self.alarms.append(alarm)
            self.alarm_id_counter += 1
            self.save_alarms()
            
            try:
                socketio.emit('alarm_added', alarm)
            except:
                pass
            
            print(f"Alarm added: {alarm_type} - {alarm.get('message', 'No message')}")
            return alarm
    
    def get_all_alarms(self):
        with self.lock:
            return self.alarms.copy()
    
    def get_active_alarms(self):
        with self.lock:
            return [alarm for alarm in self.alarms if alarm.get('status') == 'active']
    
    def get_active_count(self):
        return len(self.get_active_alarms())
    
    def clear_alarms(self, alarm_ids):
        with self.lock:
            cleared_count = 0
            for alarm in self.alarms:
                if alarm['id'] in alarm_ids:
                    alarm['status'] = 'cleared'
                    cleared_count += 1
            
            if cleared_count > 0:
                self.save_alarms()
            
            return cleared_count
    
    def reset_alarms(self):
        with self.lock:
            self.alarms = []
            self.alarm_id_counter = 1
            self.save_alarms()
            self._generate_dummy_alarms()
    
    def delete_alarm(self, alarm_id):
        with self.lock:
            initial_length = len(self.alarms)
            self.alarms = [alarm for alarm in self.alarms if alarm['id'] != alarm_id]
            
            if len(self.alarms) < initial_length:
                self.save_alarms()
                print(f'Deleted alarm: {alarm_id}')
                return True
            
            print(f'Alarm not found: {alarm_id}')
            return False
    
    def delete_all_alarms(self):
        with self.lock:
            count = len(self.alarms)
            self.alarms = []
            self.alarm_id_counter = 1
            self.save_alarms()
            print(f'Deleted all alarms ({count} total)')
            return count
    
    def save_alarms(self):
        try:
            with open(self.alarm_history_file, 'w') as f:
                json.dump(self.alarms, f, indent=2)
        except Exception as e:
            print(f'Failed to save alarms: {e}')
    
    def load_alarms(self):
        try:
            with open(self.alarm_history_file, 'r') as f:
                self.alarms = json.load(f)
                if self.alarms:
                    max_id = max([int(a['id'].split('_')[1]) for a in self.alarms])
                    self.alarm_id_counter = max_id + 1
                print(f'Loaded {len(self.alarms)} alarms from {self.alarm_history_file}')
        except FileNotFoundError:
            self.alarms = []
            print(f'No alarm history found, starting fresh')
        except Exception as e:
            print(f'Failed to load alarms: {e}')
            self.alarms = []


class TrafficDataSimulator:
    def __init__(self):
        self.in_counts = {"2WHLR": 0, "LMV": 0, "HMV": 0}
        self.out_counts = {"2WHLR": 0, "LMV": 0, "HMV": 0}
        self.total_counts = {"2WHLR": 0, "LMV": 0, "HMV": 0}
        
        self.rates = {"2WHLR": 0, "LMV": 0, "HMV": 0}
        self.previous_total = {"2WHLR": 0, "LMV": 0, "HMV": 0}
        
        self.thresholds_crossed = []
        self.processing_status = "Waiting for video upload..."
        self.last_rate_update = time.time()
        self.is_processing = False
    
    def update_counts(self):
        if not self.is_processing:
            return
        
        in_increment = {
            "2WHLR": random.randint(0, 5),
            "LMV": random.randint(0, 3),
            "HMV": random.randint(0, 2)
        }
        
        out_increment = {
            "2WHLR": random.randint(0, 4),
            "LMV": random.randint(0, 2),
            "HMV": random.randint(0, 1)
        }
        
        for vehicle_type in ["2WHLR", "LMV", "HMV"]:
            self.in_counts[vehicle_type] += in_increment[vehicle_type]
            self.out_counts[vehicle_type] += out_increment[vehicle_type]
            self.total_counts[vehicle_type] = self.in_counts[vehicle_type] - self.out_counts[vehicle_type]
        
        current_time = time.time()
        
        if current_time - self.last_rate_update >= 1:
            time_elapsed = current_time - self.last_rate_update
            
            for vehicle_type in ["2WHLR", "LMV", "HMV"]:
                count_change = self.total_counts[vehicle_type] - self.previous_total[vehicle_type]
                self.rates[vehicle_type] = round((count_change / time_elapsed) * 60, 1)
                self.previous_total[vehicle_type] = self.total_counts[vehicle_type]
            
            self.last_rate_update = current_time
    
    def check_thresholds(self, current_thresholds):
        self.thresholds_crossed = []
        
        for vehicle_type in ["2WHLR", "LMV", "HMV"]:
            try:
                max_count = current_thresholds['in'][vehicle_type]['max_count']
                time_period = current_thresholds['in']['time_period']
                
                if self.in_counts[vehicle_type] >= max_count:
                    self.thresholds_crossed.append({
                        "lane": "IN",
                        "vehicle_type": vehicle_type,
                        "count": self.in_counts[vehicle_type],
                        "max_count": max_count,
                        "time_period": time_period,
                        "message": f"{vehicle_type} count exceeded in IN lane: {self.in_counts[vehicle_type]} (limit: {max_count})"
                    })
            except KeyError:
                pass
        
        for vehicle_type in ["2WHLR", "LMV", "HMV"]:
            try:
                max_count = current_thresholds['out'][vehicle_type]['max_count']
                time_period = current_thresholds['out']['time_period']
                
                if self.out_counts[vehicle_type] >= max_count:
                    self.thresholds_crossed.append({
                        "lane": "OUT",
                        "vehicle_type": vehicle_type,
                        "count": self.out_counts[vehicle_type],
                        "max_count": max_count,
                        "time_period": time_period,
                        "message": f"{vehicle_type} count exceeded in OUT lane: {self.out_counts[vehicle_type]} (limit: {max_count})"
                    })
            except KeyError:
                pass
    
    def get_current_stats(self):
        return {
            "counts": {
                "total": self.total_counts.copy(),
                "in": self.in_counts.copy(),
                "out": self.out_counts.copy()
            },
            "rates": self.rates.copy(),
            "thresholds_crossed": self.thresholds_crossed.copy(),
            "processing_status": self.processing_status
        }
    
    def get_count(self, lane, vehicle_type):
        if lane == 'in':
            return self.in_counts.get(vehicle_type, 0)
        elif lane == 'out':
            return self.out_counts.get(vehicle_type, 0)
        return 0
    
    def reset_stats(self):
        self.total_counts = {"2WHLR": 0, "LMV": 0, "HMV": 0}
        self.in_counts = {"2WHLR": 0, "LMV": 0, "HMV": 0}
        self.out_counts = {"2WHLR": 0, "LMV": 0, "HMV": 0}
        self.rates = {"2WHLR": 0, "LMV": 0, "HMV": 0}
        self.previous_total = {"2WHLR": 0, "LMV": 0, "HMV": 0}
        self.thresholds_crossed = []
        self.processing_status = "Waiting for video upload..."
        self.is_processing = False
        self.last_rate_update = time.time()
    
    def start_processing(self):
        self.is_processing = True
        self.processing_status = "Processing video..."
        self.last_rate_update = time.time()
    
    def stop_processing(self):
        self.is_processing = False
        self.processing_status = "Processing stopped"


class VideoProcessor:
    def __init__(self, alarm_manager, traffic_data, current_thresholds_getter):
        self.alarm_manager = alarm_manager
        self.traffic_data = traffic_data
        self.get_current_thresholds = current_thresholds_getter
        
        self.is_processing = False
        self.processing_thread = None
        self.video_path = None
        
        self.current_frame = None
        self.frame_lock = threading.Lock()
        
        self.PROCESS_EVERY_N_FRAMES = 2
        self.FPS = 30
        
        print("Simple VideoProcessor initialized")
    
    def start_processing(self, video_path):
        if self.is_processing:
            print("Processing already running")
            return False
        
        if not video_path or not isinstance(video_path, str):
            print("Invalid video path")
            return False
        
        self.video_path = video_path
        self.is_processing = True
        
        self.processing_thread = threading.Thread(
            target=self._process_video,
            daemon=True
        )
        self.processing_thread.start()
        
        print("Simple video processing started")
        return True
    
    def stop_processing(self):
        if not self.is_processing:
            return
        
        print("Stopping simple video processing...")
        self.is_processing = False
        
        if self.processing_thread and self.processing_thread.is_alive():
            self.processing_thread.join(timeout=2)
        
        with self.frame_lock:
            self.current_frame = None
        
        print("Simple video processing stopped")
    
    def get_current_frame(self):
        with self.frame_lock:
            if self.current_frame is not None:
                return self.current_frame.copy()
        return None
    
    def _process_video(self):
        print(f"Opening video: {self.video_path}")
        cap = cv2.VideoCapture(self.video_path)
        
        if not cap.isOpened():
            print(f"Failed to open video: {self.video_path}")
            self.is_processing = False
            return
        
        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps and fps > 0:
            self.FPS = fps
        else:
            self.FPS = 30
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        print(f"Video info: {total_frames} frames @ {self.FPS:.2f} FPS")
        
        frame_count = 0
        
        while cap.isOpened() and self.is_processing:
            ret, frame = cap.read()
            if not ret:
                print("Video ended, looping...")
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                frame_count = 0
                continue
            
            frame_count += 1
            
            if frame_count % self.PROCESS_EVERY_N_FRAMES != 0:
                with self.frame_lock:
                    self.current_frame = frame
                continue
            
            try:
                annotated = self._draw_dummy_boxes(frame, frame_count)
                
                with self.frame_lock:
                    self.current_frame = annotated
            
            except Exception as e:
                print(f"Frame {frame_count} error: {e}")
            
            time.sleep(0.01)
        
        cap.release()
        print("Simple video processing loop ended")
    
    def _draw_dummy_boxes(self, frame, frame_count):
        h, w, _ = frame.shape
        boxes = []
        
        x1 = int((frame_count * 5) % (w - 100))
        y1 = int(h * 0.3)
        boxes.append((x1, y1, x1 + 120, y1 + 60, (0, 255, 0), "2WHLR"))
        
        x2 = int((frame_count * 3) % (w - 150))
        y2 = int(h * 0.5)
        boxes.append((x2, y2, x2 + 160, y2 + 80, (255, 0, 0), "LMV"))
        
        x3 = int((frame_count * 2) % (w - 180))
        y3 = int(h * 0.7)
        boxes.append((x3, y3, x3 + 180, y3 + 90, (0, 165, 255), "HMV"))
        
        annotated = frame.copy()
        
        for (x1, y1, x2, y2, color, label) in boxes:
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
            cv2.putText(
                annotated,
                label,
                (x1 + 5, y1 - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                color,
                2,
                cv2.LINE_AA,
            )
        
        cv2.putText(
            annotated,
            f"Frame: {frame_count}",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
        
        return annotated


traffic_data = TrafficDataSimulator()
alarm_manager = AlarmManager()


def get_current_thresholds():
    global current_thresholds
    return current_thresholds


video_processor = VideoProcessor(
    alarm_manager,
    traffic_data,
    get_current_thresholds
)
print("VideoProcessor initialized")


def load_thresholds():
    global current_thresholds
    try:
        if os.path.exists(THRESHOLDS_FILE):
            with open(THRESHOLDS_FILE, 'r') as f:
                current_thresholds = json.load(f)
                print(f'Thresholds loaded from {THRESHOLDS_FILE}')
                print(json.dumps(current_thresholds, indent=2))
        else:
            current_thresholds = DEFAULT_THRESHOLDS.copy()
            save_thresholds()
            print('Default thresholds created')
    except Exception as e:
        print(f'Failed to load thresholds: {e}')
        current_thresholds = DEFAULT_THRESHOLDS.copy()


def save_thresholds():
    try:
        with open(THRESHOLDS_FILE, 'w') as f:
            json.dump(current_thresholds, f, indent=2)
        print(f'Thresholds saved to {THRESHOLDS_FILE}')
        print(json.dumps(current_thresholds, indent=2))
    except Exception as e:
        print(f'Failed to save thresholds: {e}')


def check_violation(vehicle_type, lane, count_in_period):
    try:
        time_period = current_thresholds[lane]['time_period']
        max_count = current_thresholds[lane][vehicle_type]['max_count']
        
        if count_in_period > max_count:
            violation_message = f'{vehicle_type} count exceeded in {lane.upper()} lane: {count_in_period} vehicles (limit: {max_count})'
            
            alarm_manager.add_alarm(
                alarm_type='threshold_exceeded',
                lane=lane.upper(),
                vehicle_type=vehicle_type,
                details=violation_message,
                count=count_in_period,
                max_count=max_count
            )
            
            return {
                'type': 'count_exceeded',
                'lane': lane.upper(),
                'vehicle_type': vehicle_type,
                'message': violation_message,
                'count': count_in_period,
                'max_count': max_count,
            }
        
        return None
    except KeyError:
        return None


def background_data_updater():
    global backend_polling_rate, current_thresholds
    print("Background data updater started")
    
    last_violation_time = {}
    VIOLATION_COOLDOWN = 60
    
    while True:
        with polling_rate_lock:
            current_rate = backend_polling_rate
        
        traffic_data.update_counts()
        
        violations = []
        current_time = time.time()
        
        for vehicle_type in ['2WHLR', 'LMV', 'HMV']:
            try:
                time_period = current_thresholds['out']['time_period']
                max_count = current_thresholds['out'][vehicle_type]['max_count']
                count = traffic_data.get_count('out', vehicle_type)
                
                violation_key = f"out_{vehicle_type}"
                if count > max_count:
                    if violation_key not in last_violation_time or \
                       (current_time - last_violation_time[violation_key]) > VIOLATION_COOLDOWN:
                        violation = check_violation(vehicle_type, 'out', count)
                        if violation:
                            violations.append(violation)
                            last_violation_time[violation_key] = current_time
            except KeyError:
                pass
        
        for vehicle_type in ['2WHLR', 'LMV', 'HMV']:
            try:
                time_period = current_thresholds['in']['time_period']
                max_count = current_thresholds['in'][vehicle_type]['max_count']
                count = traffic_data.get_count('in', vehicle_type)
                
                violation_key = f"in_{vehicle_type}"
                if count > max_count:
                    if violation_key not in last_violation_time or \
                       (current_time - last_violation_time[violation_key]) > VIOLATION_COOLDOWN:
                        violation = check_violation(vehicle_type, 'in', count)
                        if violation:
                            violations.append(violation)
                            last_violation_time[violation_key] = current_time
            except KeyError:
                pass
        
        traffic_data.thresholds_crossed = violations
        
        try:
            stats = traffic_data.get_current_stats()
            socketio.emit('stats_update', stats)
        except:
            pass
        
        time.sleep(current_rate)


data_thread = threading.Thread(target=background_data_updater, daemon=True)
data_thread.start()


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def generate_placeholder_frame():
    img = Image.new('RGB', (640, 480), color=(30, 30, 50))
    draw = ImageDraw.Draw(img)
    
    try:
        font_large = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 40)
        font_small = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 20)
    except:
        font_large = ImageFont.load_default()
        font_small = ImageFont.load_default()
    
    draw.text((320, 200), "No Video Uploaded", fill=(200, 200, 200), anchor="mm", font=font_large)
    draw.text((320, 280), "Please upload a video", fill=(150, 150, 150), anchor="mm", font=font_small)
    
    draw.rectangle([(20, 20), (620, 60)], outline=(100, 100, 100), width=2)
    draw.text((30, 40), "Traffic Monitoring System", fill=(255, 255, 255), font=font_small)
    
    buffer = io.BytesIO()
    img.save(buffer, format='JPEG')
    buffer.seek(0)
    return buffer.getvalue()


@socketio.on('connect')
def handle_connect():
    print('Client connected')
    emit('stats_update', traffic_data.get_current_stats())


@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')


@socketio.on('request_stats')
def handle_request_stats():
    emit('stats_update', traffic_data.get_current_stats())


@app.route('/')
def index():
    with polling_rate_lock:
        current_rate = backend_polling_rate
    
    return jsonify({
        'status': 'running',
        'message': 'Traffic Monitoring Backend with Socket.IO',
        'version': '2.0',
        'port': 5001,
        'video_uploaded': current_video_data is not None,
        'polling_rate_seconds': current_rate,
        'socket_io_enabled': True
    })


@app.route('/video_feed')
def video_feed():
    global current_video_data, current_video_mimetype
    
    if current_video_data is None:
        def generate_placeholder():
            while True:
                frame_bytes = generate_placeholder_frame()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                time.sleep(0.1)
        
        return Response(generate_placeholder(), mimetype='multipart/x-mixed-replace; boundary=frame')
    
    def send_video():
        chunk_size = 1024 * 1024
        video_stream = io.BytesIO(current_video_data)
        data = video_stream.read(chunk_size)
        while data:
            yield data
            data = video_stream.read(chunk_size)
    
    return Response(
        send_video(),
        mimetype=current_video_mimetype,
        headers={
            'Content-Disposition': 'inline',
            'Accept-Ranges': 'bytes'
        }
    )


@app.route('/processed_feed')
def processed_feed():
    def generate_frames():
        while True:
            try:
                frame = video_processor.get_current_frame()
                
                if frame is None:
                    placeholder_bytes = generate_placeholder_frame()
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + placeholder_bytes + b'\r\n')
                    time.sleep(0.1)
                    continue
                
                ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                
                if not ret:
                    continue
                
                frame_bytes = buffer.tobytes()
                
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                
            except Exception as e:
                print(f"Frame streaming error: {e}")
                time.sleep(0.1)
            
            time.sleep(0.033)
    
    return Response(
        generate_frames(),
        mimetype='multipart/x-mixed-replace; boundary=frame',
        headers={
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'Pragma': 'no-cache',
            'Expires': '0'
        }
    )


@app.route('/api/upload-video', methods=['POST'])
def upload_video():
    global current_video_data, current_video_mimetype
    
    try:
        print("\nReceiving video upload...")
        
        if 'video' not in request.files:
            return jsonify({
                'status': 'error',
                'message': 'No video file provided'
            }), 400
        
        video_file = request.files['video']
        
        if video_file.filename == '':
            return jsonify({
                'status': 'error',
                'message': 'No file selected'
            }), 400
        
        if not allowed_file(video_file.filename):
            return jsonify({
                'status': 'error',
                'message': f'Invalid file type'
            }), 400
        
        current_video_data = video_file.read()
        
        file_extension = video_file.filename.rsplit('.', 1)[1].lower()
        mime_types = {
            'mp4': 'video/mp4',
            'avi': 'video/x-msvideo',
            'mov': 'video/quicktime',
            'mkv': 'video/x-matroska',
            'webm': 'video/webm'
        }
        current_video_mimetype = mime_types.get(file_extension, 'video/mp4')
        
        video_path = 'temp_video.mp4'
        with open(video_path, 'wb') as f:
            f.write(current_video_data)
        print(f"Video saved to: {video_path}")
        
        traffic_data.reset_stats()
        traffic_data.start_processing()
        video_processor.start_processing(video_path)
        
        video_size_mb = len(current_video_data) / (1024 * 1024)
        
        with polling_rate_lock:
            current_rate = backend_polling_rate
        
        print(f"Video loaded into memory")
        print(f"Size: {video_size_mb:.2f} MB")
        print(f"Type: {current_video_mimetype}")
        print(f"Video processing started")
        print(f"Backend polling rate: {current_rate}s\n")
        
        socketio.emit('video_uploaded', {
            'filename': video_file.filename,
            'size_mb': round(video_size_mb, 2)
        })
        
        return jsonify({
            'status': 'success',
            'message': 'Video uploaded successfully',
            'data': {
                'video_size_mb': round(video_size_mb, 2),
                'processing_status': 'Video uploaded - monitoring started',
                'polling_rate_seconds': current_rate
            }
        }), 200
        
    except Exception as e:
        print(f"Upload failed: {str(e)}\n")
        return jsonify({
            'status': 'error',
            'message': f'Upload failed: {str(e)}'
        }), 500


@app.route('/api/stats/current', methods=['GET'])
def get_current_stats():
    stats = traffic_data.get_current_stats()
    
    with polling_rate_lock:
        stats['backend_polling_rate'] = backend_polling_rate
    
    return jsonify(stats)


@app.route('/api/stats/reset', methods=['POST'])
def reset_stats():
    global current_video_data
    traffic_data.reset_stats()
    current_video_data = None
    return jsonify({
        'status': 'success',
        'message': 'Statistics and alarms reset successfully',
        'data': traffic_data.get_current_stats()
    })


@app.route('/api/thresholds', methods=['GET'])
def get_thresholds():
    return jsonify({
        'status': 'success',
        'thresholds': current_thresholds
    })


@app.route('/api/thresholds', methods=['POST'])
def update_thresholds():
    global current_thresholds
    try:
        data = request.get_json()
        new_thresholds = data.get('thresholds')
        
        if not new_thresholds:
            return jsonify({
                'status': 'error',
                'message': 'No thresholds provided'
            }), 400
        
        required_lanes = ['out', 'in']
        required_vehicles = ['2WHLR', 'LMV', 'HMV']
        
        for lane in required_lanes:
            if lane not in new_thresholds:
                return jsonify({
                    'status': 'error',
                    'message': f'Missing lane: {lane}'
                }), 400
            
            if 'time_period' not in new_thresholds[lane]:
                return jsonify({
                    'status': 'error',
                    'message': f'Missing time_period for {lane} lane'
                }), 400
            
            for vehicle in required_vehicles:
                if vehicle not in new_thresholds[lane]:
                    return jsonify({
                        'status': 'error',
                        'message': f'Missing vehicle type: {vehicle} in {lane} lane'
                    }), 400
                
                if 'max_count' not in new_thresholds[lane][vehicle]:
                    return jsonify({
                        'status': 'error',
                        'message': f'Missing max_count for {vehicle} in {lane} lane'
                    }), 400
        
        current_thresholds = new_thresholds
        save_thresholds()
        
        socketio.emit('threshold_updated', current_thresholds)
        
        print(f'\nThresholds updated successfully!')
        
        return jsonify({
            'status': 'success',
            'message': 'Thresholds updated successfully',
            'thresholds': current_thresholds
        })
    except Exception as e:
        print(f'Error updating thresholds: {e}')
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/api/polling-rate', methods=['POST'])
def update_polling_rate():
    global backend_polling_rate
    
    try:
        data = request.get_json()
        new_rate = data.get('interval')
        
        if new_rate is None:
            return jsonify({
                'success': False,
                'message': 'No interval provided'
            }), 400
        
        if not isinstance(new_rate, (int, float)) or new_rate < 5 or new_rate > 300:
            return jsonify({
                'success': False,
                'message': 'Invalid polling rate. Must be between 5 and 300 seconds.'
            }), 400
        
        with polling_rate_lock:
            backend_polling_rate = new_rate
        
        print(f"\nBackend polling rate updated to: {backend_polling_rate} seconds")
        
        return jsonify({
            'success': True,
            'message': f'Backend polling rate updated to {backend_polling_rate} seconds',
            'polling_rate': backend_polling_rate
        }), 200
        
    except Exception as e:
        print(f"Error updating polling rate: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/polling-rate', methods=['GET'])
def get_polling_rate():
    with polling_rate_lock:
        current_rate = backend_polling_rate
    
    return jsonify({
        'success': True,
        'polling_rate': current_rate,
        'unit': 'seconds'
    }), 200


@app.route('/api/stop-processing', methods=['POST'])
def stop_processing():
    global current_video_data
    traffic_data.stop_processing()
    video_processor.stop_processing()
    current_video_data = None
    return jsonify({'status': 'success', 'message': 'Processing stopped'})


@app.route('/api/alarms', methods=['GET'])
def get_alarms():
    try:
        alarms = alarm_manager.get_all_alarms()
        return jsonify({
            'status': 'success',
            'total': len(alarms),
            'active': alarm_manager.get_active_count(),
            'alarms': alarms
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/api/alarms/clear', methods=['POST'])
def clear_alarms():
    try:
        data = request.json
        alarm_ids = data.get('alarm_ids', [])
        
        if not alarm_ids:
            return jsonify({
                'status': 'error',
                'message': 'No alarm IDs provided'
            }), 400
        
        cleared_count = alarm_manager.clear_alarms(alarm_ids)
        
        return jsonify({
            'status': 'success',
            'message': f'{cleared_count} alarms cleared',
            'cleared_count': cleared_count
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/api/alarms/reset', methods=['POST'])
def reset_alarms_route():
    try:
        alarm_manager.reset_alarms()
        return jsonify({
            'status': 'success',
            'message': 'All alarms cleared'
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/api/alarms/add-test', methods=['GET', 'POST'])
def add_test_alarms():
    try:
        alarm_manager.add_alarm('over_speeding', 'OUT', speed=85, vehicle_type='LMV')
        alarm_manager.add_alarm('wrong_lane', 'IN', vehicle_type='2WHLR')
        alarm_manager.add_alarm('parked_vehicle', 'OUT', duration='5 mins', vehicle_type='HMV')
        alarm_manager.add_alarm('over_speeding', 'IN', speed=92, vehicle_type='2WHLR')
        alarm_manager.add_alarm('wrong_lane', 'OUT', vehicle_type='LMV')
        
        return jsonify({
            'status': 'success',
            'message': '5 test alarms added',
            'total': len(alarm_manager.get_all_alarms())
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/api/alarms/delete/<alarm_id>', methods=['DELETE'])
def delete_alarm(alarm_id):
    try:
        deleted = alarm_manager.delete_alarm(alarm_id)
        
        if deleted:
            return jsonify({
                'status': 'success',
                'message': f'Alarm {alarm_id} deleted'
            })
        else:
            return jsonify({
                'status': 'error',
                'message': f'Alarm {alarm_id} not found'
            }), 404
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/api/alarms/delete-all', methods=['DELETE'])
def delete_all_alarms():
    try:
        count = alarm_manager.delete_all_alarms()
        
        return jsonify({
            'status': 'success',
            'message': f'{count} alarms deleted',
            'deleted_count': count
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


if __name__ == '__main__':
    load_thresholds()
    
    print(f"Backend polling rate: {backend_polling_rate} seconds")
    print(f"Socket.IO enabled")
    print(f"Total formula: Incoming - Outgoing\n")
    
    socketio.run(
        app,
        debug=False,
        host='0.0.0.0',
        port=5001,
        use_reloader=False,
        allow_unsafe_werkzeug=True
    )
