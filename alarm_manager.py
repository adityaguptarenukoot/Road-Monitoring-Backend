import json
import os
from datetime import datetime
import time


class AlarmManager:
    def __init__(self, alarm_file='alarm_history.json'):
        """Initialize alarm manager with JSON file storage"""
        self.alarm_file = alarm_file
        self.alarm_history = []
        self.load_alarms()
    
    def load_alarms(self):
        """Load alarms from JSON file"""
        try:
            if os.path.exists(self.alarm_file):
                with open(self.alarm_file, 'r') as f:
                    self.alarm_history = json.load(f)
                print(f"✓ Loaded {len(self.alarm_history)} alarms from {self.alarm_file}")
            else:
                print(f"✓ No existing alarm file found, starting fresh")
                self.alarm_history = []
        except Exception as e:
            print(f"✗ Error loading alarms: {str(e)}")
            self.alarm_history = []
    
    def save_alarms(self):
        """Save alarms to JSON file"""
        try:
            with open(self.alarm_file, 'w') as f:
                json.dump(self.alarm_history, f, indent=2)
            print(f"✓ Saved {len(self.alarm_history)} alarms to {self.alarm_file}")
        except Exception as e:
            print(f"✗ Error saving alarms: {str(e)}")
    
    def add_alarm(self, alarm_type, lane, **details):
        """Add a new alarm to history"""
        alarm_data = {
            'id': f"ALM-{int(time.time() * 1000)}",
            'type': alarm_type,
            'timestamp': datetime.now().isoformat(),
            'lane': lane,
            'status': 'active',
            **details
        }
        
        self.alarm_history.insert(0, alarm_data)
        self.save_alarms()
        
        print(f"✓ Alarm added: {alarm_type} in {lane} lane")
        return alarm_data
    
    def get_all_alarms(self):
        """Get all alarms (newest first)"""
        return self.alarm_history
    
    def get_active_alarms(self):
        """Get only active (uncleared) alarms"""
        return [alarm for alarm in self.alarm_history if alarm.get('status') == 'active']
    
    def clear_alarms(self, alarm_ids):
        """Clear selected alarms"""
        cleared_count = 0
        for alarm in self.alarm_history:
            if alarm['id'] in alarm_ids:
                alarm['status'] = 'cleared'
                alarm['cleared_at'] = datetime.now().isoformat()
                cleared_count += 1
        
        self.save_alarms()
        print(f"✓ Cleared {cleared_count} alarms")
        return cleared_count
    
    def reset_alarms(self):
        """Clear all alarms"""
        self.alarm_history = []
        self.save_alarms()
        print("✓ All alarms reset")
    
    def get_active_count(self):
        """Get count of active alarms"""
        return len(self.get_active_alarms())
