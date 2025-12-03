from alarm_manager import AlarmManager

print("Adding test alarms...")
alarm_mgr = AlarmManager()

alarm_mgr.add_alarm('over_speeding', 'OUT', speed=85, vehicle_type='LMV')
alarm_mgr.add_alarm('wrong_lane', 'IN', vehicle_type='2WHLR')
alarm_mgr.add_alarm('parked_vehicle', 'OUT', duration='5 mins', vehicle_type='HMV')
alarm_mgr.add_alarm('over_speeding', 'IN', speed=92, vehicle_type='2WHLR')
alarm_mgr.add_alarm('wrong_lane', 'OUT', vehicle_type='LMV')

print(f"\n Done! Total alarms: {len(alarm_mgr.get_all_alarms())}")
