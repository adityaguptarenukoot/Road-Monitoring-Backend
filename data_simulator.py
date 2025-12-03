import random
import time

class TrafficDataSimulator:
    def __init__(self):
        self.total_counts = {
            "2WHLR": 0,
            "LMV": 0,
            "HMV": 0
        }
        
        self.in_counts = {
            "2WHLR": 0,
            "LMV": 0,
            "HMV": 0
        }
        
        self.out_counts = {
            "2WHLR": 0,
            "LMV": 0,
            "HMV": 0
        }
        
        self.rates = {
            "2WHLR": 0,
            "LMV": 0,
            "HMV": 0
        }
        
        self.previous_total = {
            "2WHLR": 0,
            "LMV": 0,
            "HMV": 0
        }
        
        self.thresholds = {
            "2WHLR": 100,
            "LMV": 80,
            "HMV": 50
        }
        
        self.thresholds_crossed = []
        self.processing_status = "Waiting for video upload..."
        self.last_rate_update = time.time()
        self.is_processing = False
        
    def update_counts(self):

        if not self.is_processing:
           return

        in_increment = {
            "2WHLR": random.randint(0, 3),
            "LMV": random.randint(0, 2),
            "HMV": random.randint(0, 1)
        }
        
        out_increment = {
            "2WHLR": random.randint(0, 2),
            "LMV": random.randint(0, 1),
            "HMV": random.randint(0, 1)
        }
        
        for vehicle_type in ["2WHLR", "LMV", "HMV"]:
            self.in_counts[vehicle_type] += in_increment[vehicle_type]
            self.out_counts[vehicle_type] += out_increment[vehicle_type]
            self.total_counts[vehicle_type] = self.in_counts[vehicle_type] + self.out_counts[vehicle_type]
        
        current_time = time.time()
        
        if current_time - self.last_rate_update >= 1:
            #  to hardcode time interval
            time_elapsed = current_time - self.last_rate_update
            
            for vehicle_type in ["2WHLR", "LMV", "HMV"]:
                count_change = self.total_counts[vehicle_type] - self.previous_total[vehicle_type]
                self.rates[vehicle_type] = round((count_change / time_elapsed) * 60, 1)
                self.previous_total[vehicle_type] = self.total_counts[vehicle_type]
            
            self.last_rate_update = current_time
        
        self.check_thresholds()
    
    def check_thresholds(self):
        self.thresholds_crossed = []
        
        for vehicle_type in ["2WHLR", "LMV", "HMV"]:
            if self.total_counts[vehicle_type] >= self.thresholds[vehicle_type]:
                self.thresholds_crossed.append({
                    "type": vehicle_type,
                    "count": self.total_counts[vehicle_type],
                    "threshold": self.thresholds[vehicle_type],
                    "message": f"{vehicle_type} count exceeded threshold!"
                })
    
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
    
    def update_thresholds(self, new_thresholds):
        self.thresholds.update(new_thresholds)
        self.check_thresholds()
