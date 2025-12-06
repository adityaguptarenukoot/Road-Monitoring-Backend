from flask import Flask, Response, jsonify, request
from flask_cors import CORS
from data_simulator import TrafficDataSimulator
from alarm_manager import AlarmManager  
from PIL import Image, ImageDraw, ImageFont
import threading
import time
import os
import json
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




backend_polling_rate = 5  # Default 
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



# Global thresholds variable
current_thresholds = DEFAULT_THRESHOLDS.copy()
THRESHOLDS_FILE = 'thresholds.json'



print("✓ Server started")



# Load thresholds from file on startup
def load_thresholds():
    global current_thresholds
    try:
        if os.path.exists(THRESHOLDS_FILE):
            with open(THRESHOLDS_FILE, 'r') as f:
                current_thresholds = json.load(f)
                print(f'✓ Thresholds loaded from {THRESHOLDS_FILE}')
                print(json.dumps(current_thresholds, indent=2))
        else:
            current_thresholds = DEFAULT_THRESHOLDS.copy()
            save_thresholds()
            print('✓ Default thresholds created')
    except Exception as e:
        print(f'✗ Failed to load thresholds: {e}')
        current_thresholds = DEFAULT_THRESHOLDS.copy()



# Save thresholds to file
def save_thresholds():
    try:
        with open(THRESHOLDS_FILE, 'w') as f:
            json.dump(current_thresholds, f, indent=2)
        print(f'✓ Thresholds saved to {THRESHOLDS_FILE}')
        print(json.dumps(current_thresholds, indent=2))
    except Exception as e:
        print(f'✗ Failed to save thresholds: {e}')



# Check if threshold is violated (count-based with time period)
def check_violation(vehicle_type, lane, count_in_period):
    """
    Check if vehicle count threshold is violated within time period
    
    Args:
        vehicle_type: '2WHLR', 'LMV', or 'HMV'
        lane: 'in' or 'out'
        count_in_period: Number of vehicles detected in the time period
    
    Returns:
        Violation dict or None
    """
    try:
        # Get time_period from lane level
        time_period = current_thresholds[lane]['time_period']
        # Get max_count from vehicle type
        max_count = current_thresholds[lane][vehicle_type]['max_count']
        
        # Check if count exceeded within time period
        if count_in_period > max_count:
            return {
                'type': 'count_exceeded',
                'lane': lane.upper(),
                'vehicle_type': vehicle_type, 
                'message': f'{vehicle_type} count exceeded in {lane} lane: {count_in_period} vehicles in {time_period} minutes (limit: {max_count})',
                'count': count_in_period,
                'max_count': max_count,
               
            }
        
        return None
    except KeyError:
        return None



def background_data_updater():
    global backend_polling_rate, current_thresholds  
    print("✓ Background data updater started")
    
    while True:
        with polling_rate_lock:
            current_rate = backend_polling_rate
        
        # Update traffic data
        traffic_data.update_counts()
        
        # CHECK THRESHOLDS with current_thresholds
        traffic_data.check_thresholds(current_thresholds)
        
        # dynamic polling rate
        print(f"⏱️  Backend processing with {current_rate}s interval")
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



@app.route('/')
def index():
    with polling_rate_lock:
        current_rate = backend_polling_rate
    
    return jsonify({
        'status': 'running',
        'message': 'Traffic Monitoring Backend (No Storage)',
        'version': '1.0',
        'port': 5001,
        'video_uploaded': current_video_data is not None,
        'polling_rate_seconds': current_rate
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
        
        with polling_rate_lock:
            current_rate = backend_polling_rate
        
        print(f"✓ Video loaded into memory")
        print(f"✓ Size: {video_size_mb:.2f} MB")
        print(f"✓ Type: {current_video_mimetype}")
        print(f"✓ Backend polling rate: {current_rate}s\n")
        
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
        print(f"✗ Upload failed: {str(e)}\n")
        return jsonify({
            'status': 'error',
            'message': f'Upload failed: {str(e)}'
        }), 500



@app.route('/api/stats/current', methods=['GET'])
def get_current_stats():
    stats = traffic_data.get_current_stats()
    
    # Add polling rate to stats
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



# GET: Fetch current thresholds
@app.route('/api/thresholds', methods=['GET'])
def get_thresholds():
    return jsonify({
        'status': 'success',
        'thresholds': current_thresholds
    })



#  Update thresholds
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
        
        # Validate structure
        required_lanes = ['out', 'in']
        required_vehicles = ['2WHLR', 'LMV', 'HMV']
        
        for lane in required_lanes:
            if lane not in new_thresholds:
                return jsonify({
                    'status': 'error',
                    'message': f'Missing lane: {lane}'
                }), 400
            
            # Check time_period exists at lane level
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
        
        # Update global thresholds
        current_thresholds = new_thresholds
        
        # Save to file for persistence
        save_thresholds()
        
        print(f'\n✓ Thresholds updated successfully!')
        
        return jsonify({
            'status': 'success',
            'message': 'Thresholds updated successfully',
            'thresholds': current_thresholds
        })
    except Exception as e:
        print(f'✗ Error updating thresholds: {e}')
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500



# POST endpoint to update backend polling rate
@app.route('/api/polling-rate', methods=['POST'])
def update_polling_rate():
    """Update the backend polling rate dynamically"""
    global backend_polling_rate
    
    try:
        data = request.get_json()
        new_rate = data.get('interval')
        
        if new_rate is None:
            return jsonify({
                'success': False,
                'message': 'No interval provided'
            }), 400
        
        # Validate rate (between 5 and 300 seconds)
        if not isinstance(new_rate, (int, float)) or new_rate < 5 or new_rate > 300:
            return jsonify({
                'success': False,
                'message': 'Invalid polling rate. Must be between 5 and 300 seconds.'
            }), 400
        
        # Update polling rate 
        with polling_rate_lock:
            backend_polling_rate = new_rate
        
        print(f"\n✅ Backend polling rate updated to: {backend_polling_rate} seconds")
        
        return jsonify({
            'success': True,
            'message': f'Backend polling rate updated to {backend_polling_rate} seconds',
            'polling_rate': backend_polling_rate
        }), 200
        
    except Exception as e:
        print(f"❌ Error updating polling rate: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500



#  GET endpoint to fetch current polling rate
@app.route('/api/polling-rate', methods=['GET'])
def get_polling_rate():
    """Get current backend polling rate"""
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



# ========================================
# 🆕 DELETE ALARM ENDPOINTS
# ========================================
@app.route('/api/alarms/delete/<alarm_id>', methods=['DELETE'])
def delete_alarm(alarm_id):
    """Delete a specific alarm permanently"""
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
    """Delete all alarms permanently"""
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
    # Load thresholds on startup
    load_thresholds()
    
    print(f"✓ Backend polling rate: {backend_polling_rate} seconds\n")
    
    app.run(
        debug=True,
        host='0.0.0.0',
        port=5001,
        threaded=True,
        use_reloader=False
    )
