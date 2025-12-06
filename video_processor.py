# Import check_violation function from app.py
from app import check_violation, current_thresholds

def process_detection(detection, lane):
    """Process each vehicle detection"""
    vehicle_type = detection['class_name']  # '2WHLR', 'LMV', 'HMV'
    speed = detection['speed']
    
    # Get current count for this vehicle type in this lane
    current_count = traffic_data.counts[lane][vehicle_type]
    
    # Check for violations using dynamic thresholds
    violation = check_violation(vehicle_type, lane, current_count, speed)
    
    if violation:
        # Generate alarm
        alarm_manager.add_alarm(
            alarm_type=violation['type'],
            vehicle_type=vehicle_type,
            lane=lane,
            speed=speed,
            count=current_count,
            message=violation['message']
        )
        print(f'⚠️ {violation["message"]}')
