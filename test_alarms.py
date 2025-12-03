from alarm_manager import AlarmManager
import time

alarm_mgr = AlarmManager()


print("Adding test alarms...\n")

alarm_mgr.add_alarm('over_speeding', 'OUT', speed=85, vehicle_type='LMV')
time.sleep(1)

alarm_mgr.add_alarm('wrong_lane', 'IN', vehicle_type='2WHLR')
time.sleep(1)

alarm_mgr.add_alarm('parked_vehicle', 'OUT', duration='5 mins', vehicle_type='HMV')
time.sleep(1)

alarm_mgr.add_alarm('over_speeding', 'IN', speed=92, vehicle_type='2WHLR')
time.sleep(1)

alarm_mgr.add_alarm('wrong_lane', 'OUT', vehicle_type='LMV')

print("\n✅ Test alarms added!")
print(f"Total alarms: {len(alarm_mgr.get_all_alarms())}")
