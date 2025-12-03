from flask import Flask, Response, jsonify, request
from flask_cors import CORS
from data_simulator import TrafficDataSimulator
from alarm_manager import AlarmManager  
from PIL import Image, ImageDraw, ImageFont
import threading
import time
import os
from pathlib import Path
import io


app = Flask(__name__)


CORS(app, resources={
    r"/api/*": {"origins": "*"},
    r"/video_feed": {"origins": "*"}
})


ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov', 'mkv', 'webm'}
MAX_FILE_SIZE = 500 * 1024 * 1024


app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE


traffic_data = TrafficDataSimulator()
alarm_manager = AlarmManager()
current_video_data = None  
current_video_mimetype = 'video/mp4'


print("server started")



def background_data_updater():
    print("✓ Background data updater started")
    while True:
        traffic_data.update_counts()
        time.sleep(1)


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


@app.route('/')
def index():
    return jsonify({
        'status': 'running',
        'message': 'Traffic Monitoring Backend (No Storage)',
        'version': '1.0',
        'port': 5001,
        'video_uploaded': current_video_data is not None
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


@app.route('/api/upload-video', methods=['POST'])
def upload_video():
    global current_video_data, current_video_mimetype
    
    try:
        print("\n📤 Receiving video upload...")
        
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
        
        traffic_data.reset_stats()
        traffic_data.start_processing()
        
        video_size_mb = len(current_video_data) / (1024 * 1024)
        print(f"✓ Video loaded into memory")
        print(f"✓ Size: {video_size_mb:.2f} MB")
        print(f"✓ Type: {current_video_mimetype}\n")
        
        return jsonify({
            'status': 'success',
            'message': 'Video uploaded successfully',
            'data': {
                'video_size_mb': round(video_size_mb, 2),
                'processing_status': 'Video uploaded - monitoring started'
            }
        }), 200
        
    except Exception as e:
        print(f"✗ Upload failed: {str(e)}\n")
        return jsonify({
            'status': 'error',
            'message': f'Upload failed: {str(e)}'
        }), 500


@app.route('/api/stats/current', methods=['GET'])
def get_current_stats():
    stats = traffic_data.get_current_stats()
    return jsonify(stats)


@app.route('/api/stats/reset', methods=['POST'])
def reset_stats():
    global current_video_data
    traffic_data.reset_stats()
    # alarm_manager.reset_alarms()
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
        'thresholds': traffic_data.thresholds
    })


@app.route('/api/thresholds', methods=['POST'])
def update_thresholds():
    try:
        new_thresholds = request.json
        if not new_thresholds:
            return jsonify({'status': 'error', 'message': 'No data'}), 400
        
        traffic_data.update_thresholds(new_thresholds)
        return jsonify({
            'status': 'success',
            'message': 'Thresholds updated',
            'thresholds': traffic_data.thresholds
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400


@app.route('/api/stop-processing', methods=['POST'])
def stop_processing():
    global current_video_data
    traffic_data.stop_processing()
    current_video_data = None  
    return jsonify({'status': 'success', 'message': 'Processing stopped'})




@app.route('/api/alarms', methods=['GET'])
def get_alarms():
    """Get all alarms"""
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
    """Clear selected alarms"""
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
    """Reset all alarms"""
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
    """Add test alarms for debugging"""
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


if __name__ == '__main__':
    app.run(
        debug=True,
        host='0.0.0.0',
        port=5001,
        threaded=True,
        use_reloader=False
    )
