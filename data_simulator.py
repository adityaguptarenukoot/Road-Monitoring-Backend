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
        
        self.thresholds_crossed = []
        self.processing_status = "Waiting for video upload..."
        self.last_rate_update = time.time()
        self.is_processing = False
        
    def update_counts(self):
        """
        Update vehicle counts with random increments
        Simulates real traffic detection
        """
        if not self.is_processing:
           return

        # ========================================
        # 🎲 RANDOM DATA GENERATION
        # Adjust these ranges to control how fast counts grow
        # ========================================
        in_increment = {
            "2WHLR": random.randint(0, 5),  # 0-5 bikes per update
            "LMV": random.randint(0, 3),     # 0-3 cars per update
            "HMV": random.randint(0, 2)      # 0-2 trucks per update
        }
        
        out_increment = {
            "2WHLR": random.randint(0, 4),  # 0-4 bikes per update
            "LMV": random.randint(0, 2),     # 0-2 cars per update
            "HMV": random.randint(0, 1)      # 0-1 trucks per update
        }
        
        # Update counts
        for vehicle_type in ["2WHLR", "LMV", "HMV"]:
            self.in_counts[vehicle_type] += in_increment[vehicle_type]
            self.out_counts[vehicle_type] += out_increment[vehicle_type]
            self.total_counts[vehicle_type] = self.in_counts[vehicle_type] + self.out_counts[vehicle_type]
        
        # Calculate rates (vehicles per minute)
        current_time = time.time()
        
        if current_time - self.last_rate_update >= 1:
            time_elapsed = current_time - self.last_rate_update
            
            for vehicle_type in ["2WHLR", "LMV", "HMV"]:
                count_change = self.total_counts[vehicle_type] - self.previous_total[vehicle_type]
                self.rates[vehicle_type] = round((count_change / time_elapsed) * 60, 1)
                self.previous_total[vehicle_type] = self.total_counts[vehicle_type]
            
            self.last_rate_update = current_time
    
    def check_thresholds(self, current_thresholds):
        """
        Check thresholds using the current_thresholds from app.py
        
        Args:
            current_thresholds: Dictionary with structure from app.py
        """
        self.thresholds_crossed = []
        
        # Check IN lane
        for vehicle_type in ["2WHLR", "LMV", "HMV"]:
            try:
                max_count = current_thresholds['in'][vehicle_type]['max_count']
                time_period = current_thresholds['in']['time_period']
                
                if self.in_counts[vehicle_type] >= max_count:
                    self.thresholds_crossed.append({
                        "lane": "IN",  # ✅ Fixed: Uppercase
                        "vehicle_type": vehicle_type,
                        "count": self.in_counts[vehicle_type],
                        "max_count": max_count,
                        "time_period": time_period,
                        "message": f"{vehicle_type} count exceeded in IN lane: {self.in_counts[vehicle_type]} (limit: {max_count})"
                    })
            except KeyError:
                pass
        
        # Check OUT lane
        for vehicle_type in ["2WHLR", "LMV", "HMV"]:
            try:
                max_count = current_thresholds['out'][vehicle_type]['max_count']
                time_period = current_thresholds['out']['time_period']
                
                if self.out_counts[vehicle_type] >= max_count:
                    self.thresholds_crossed.append({
                        "lane": "OUT",  # ✅ Fixed: Uppercase
                        "vehicle_type": vehicle_type,
                        "count": self.out_counts[vehicle_type],
                        "max_count": max_count,
                        "time_period": time_period,
                        "message": f"{vehicle_type} count exceeded in OUT lane: {self.out_counts[vehicle_type]} (limit: {max_count})"
                    })
            except KeyError:
                pass
    
    def get_current_stats(self):
        """
        Get current statistics
        
        ✅ Returns REAL calculated data - no hardcoded values
        """
        
        # ========================================
        # ✅ REAL DATA - Dynamic threshold calculation
        # Thresholds will trigger naturally as counts increase
        # ========================================
        return {
            "counts": {
                "total": self.total_counts.copy(),
                "in": self.in_counts.copy(),
                "out": self.out_counts.copy()
            },
            "rates": self.rates.copy(),
            "thresholds_crossed": self.thresholds_crossed.copy(),  # ✅ Real data!
            "processing_status": self.processing_status
        }
    
    def reset_stats(self):
        """Reset all statistics to zero"""
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
        """Start processing and counting"""
        self.is_processing = True
        self.processing_status = "Processing video..."
        self.last_rate_update = time.time()
    
    def stop_processing(self):
        """Stop processing"""
        self.is_processing = False
        self.processing_status = "Processing stopped"
