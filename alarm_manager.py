import json
from datetime import datetime



class AlarmManager:
    def __init__(self):
        self.alarms = []
        self.alarm_id_counter = 1
        self.alarm_history_file = 'alarm_history.json'
        self.load_alarms()
        

        #  DUMMY DATA - DELETE THIS WHEN ADDING REAL DETECTION
        
        if len(self.alarms) == 0:
            self._generate_dummy_alarms()
    
   
    #  REPLACE WITH REAL DETECTION CODE
    
    def _generate_dummy_alarms(self):
        """
        Generate dummy alarms for testing
        
        🔴 DELETE THIS ENTIRE METHOD when implementing real detection!
        
        For real detection, call add_alarm() from your YOLO detection code:
        
        Example:
        --------
        if vehicle_in_wrong_lane:
            alarm_manager.add_alarm(
                alarm_type='wrong_lane',
                lane='OUT',  # or 'IN'
                vehicle_type='2WHLR',  # or 'LMV' or 'HMV'
                message='2WHLR detected in wrong lane'
            )
        
        if vehicle_parked_too_long:
            alarm_manager.add_alarm(
                alarm_type='parked_vehicle',
                lane='OUT',
                vehicle_type='HMV',
                duration='5 mins'
            )
        """
        dummy_alarms = [
          
            {
                'type': 'parked_vehicle',
                'lane': 'OUT',
                'vehicle_type': 'HMV',  # Truck parked
                'duration': '5 mins',
                'message': 'Truck parked in no-parking zone'
            },
            {
                'type': 'wrong_lane',
                'lane': 'OUT',
                'vehicle_type': 'LMV',  # Car in wrong lane
                'message': 'Car detected in wrong lane'
            },
            
          
            # IN Lane Alarms (Different from OUT Lane)
            
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
        
        print(f'✓ Generated {len(dummy_alarms)} dummy alarms for testing')
    
   
    def add_alarm(self, alarm_type, lane, vehicle_type=None, speed=None, 
                  duration=None, count=None, max_count=None, message=None, **kwargs):
        """
        Add a new alarm
        
        Parameters:
        -----------
        alarm_type : str
            'wrong_lane', 'parked_vehicle', 'over_speeding', etc.
        lane : str
            'OUT' or 'IN'
        vehicle_type : str
            '2WHLR', 'LMV', or 'HMV'
        speed : int (optional)
            Speed in km/h
        duration : str (optional)
            e.g., '5 mins'
        count : int (optional)
            Current count (for thresholds)
        max_count : int (optional)
            Maximum allowed count
        message : str (optional)
            Custom message
        
        Returns:
        --------
        dict : The created alarm
        
        Example Usage:
        --------------
        # Wrong lane detection
        alarm_manager.add_alarm(
            alarm_type='wrong_lane',
            lane='OUT',
            vehicle_type='LMV',
            message='Car in wrong lane'
        )
        
        # Parked vehicle detection
        alarm_manager.add_alarm(
            alarm_type='parked_vehicle',
            lane='IN',
            vehicle_type='HMV',
            duration='10 mins'
        )
        
        # Over speeding detection
        alarm_manager.add_alarm(
            alarm_type='over_speeding',
            lane='OUT',
            vehicle_type='2WHLR',
            speed=95,
            message='Bike exceeding speed limit'
        )
        """
        alarm = {
            'id': f'alarm_{self.alarm_id_counter}',
            'type': alarm_type,
            'lane': lane.upper(),
            'vehicle_type': vehicle_type,
            'timestamp': datetime.now().isoformat(),
            'status': 'active',
            'message': message or f'{alarm_type} detected in {lane} lane'
        }
        
        # Add optional fields
        if speed is not None:
            alarm['speed'] = speed
        if duration is not None:
            alarm['duration'] = duration
        if count is not None:
            alarm['count'] = count
        if max_count is not None:
            alarm['max_count'] = max_count
        
        # Add any extra kwargs
        alarm.update(kwargs)
        
        self.alarms.append(alarm)
        self.alarm_id_counter += 1
        self.save_alarms()
        
        return alarm
    
    def get_all_alarms(self):
        """Get all alarms"""
        return self.alarms
    
    def get_active_alarms(self):
        """Get only active alarms"""
        return [alarm for alarm in self.alarms if alarm.get('status') == 'active']
    
    def get_active_count(self):
        """Get count of active alarms"""
        return len(self.get_active_alarms())
    
    def clear_alarms(self, alarm_ids):
        """Clear specific alarms by marking as cleared"""
        cleared_count = 0
        for alarm in self.alarms:
            if alarm['id'] in alarm_ids:
                alarm['status'] = 'cleared'
                cleared_count += 1
        
        if cleared_count > 0:
            self.save_alarms()
        
        return cleared_count
    
    def reset_alarms(self):
        """Clear all alarms"""
        self.alarms = []
        self.alarm_id_counter = 1
        self.save_alarms()
        
        # Re-generate dummy alarms
        self._generate_dummy_alarms()
    
    
    # DELETE METHODS - PERMANENT DELETION
    
    def delete_alarm(self, alarm_id):
        """
        Delete a specific alarm permanently
        
        Parameters:
        -----------
        alarm_id : str
            The alarm ID to delete (e.g., 'alarm_1')
        
        Returns:
        --------
        bool : True if deleted, False if not found
        
        Example Usage:
        --------------
        deleted = alarm_manager.delete_alarm('alarm_1')
        if deleted:
            print('Alarm deleted')
        else:
            print('Alarm not found')
        """
        initial_length = len(self.alarms)
        self.alarms = [alarm for alarm in self.alarms if alarm['id'] != alarm_id]
        
        if len(self.alarms) < initial_length:
            self.save_alarms()
            print(f'✓ Deleted alarm: {alarm_id}')
            return True
        
        print(f'✗ Alarm not found: {alarm_id}')
        return False
    
    def delete_all_alarms(self):
        """
        Delete all alarms permanently
        
        Returns:
        --------
        int : Number of alarms deleted
        
        Example Usage:
        --------------
        count = alarm_manager.delete_all_alarms()
        print(f'{count} alarms deleted')
        """
        count = len(self.alarms)
        self.alarms = []
        self.alarm_id_counter = 1
        self.save_alarms()
        
        print(f'✓ Deleted all alarms ({count} total)')
        return count
    
   
    # FILE OPERATIONS
    
    def save_alarms(self):
        """Save alarms to file"""
        try:
            with open(self.alarm_history_file, 'w') as f:
                json.dump(self.alarms, f, indent=2)
        except Exception as e:
            print(f'✗ Failed to save alarms: {e}')
    
    def load_alarms(self):
        """Load alarms from file"""
        try:
            with open(self.alarm_history_file, 'r') as f:
                self.alarms = json.load(f)
                if self.alarms:
                    # Get max ID to continue counter
                    max_id = max([int(a['id'].split('_')[1]) for a in self.alarms])
                    self.alarm_id_counter = max_id + 1
                print(f'✓ Loaded {len(self.alarms)} alarms from {self.alarm_history_file}')
        except FileNotFoundError:
            self.alarms = []
            print(f'✓ No alarm history found, starting fresh')
        except Exception as e:
            print(f'✗ Failed to load alarms: {e}')
            self.alarms = []
