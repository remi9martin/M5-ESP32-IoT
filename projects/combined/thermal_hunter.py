"""
COMBINED PROJECT: Thermal Hunter
==================================
Devices: BALA2 Fire + T-Lite Thermal Camera
Difficulty: Hard

Autonomous robot that hunts the hottest object!
The BALA2 uses the thermal camera to:
- Find warmest heat signature
- Turn toward it
- Chase it down!

Great for cat chasing or playing with pets.
"""

import time
from machine import Pin, I2C

# Thermal camera
try:
    import mlx90640
    i2c = I2C(0, scl=Pin(22), sda=Pin(21), freq=400000)
    thermal = mlx90640.MLX90640(i2c)
    HAS_THERMAL = True
except:
    HAS_THERMAL = False

# Balancing robot
try:
    from m5stack import Bala2
    bala = Bala2()
    HAS_BALA = True
except:
    HAS_BALA = False

SENSOR_W = 32
SENSOR_H = 24
TARGET_TEMP = 28  # Min temp to track

class ThermalHunter:
    def __init__(self):
        self.target_x = SENSOR_W // 2
        self.target_y = SENSOR_H // 2
        self.target_temp = 0
        self.hunting = False
    
    def get_thermal(self):
        if HAS_THERMAL:
            frame = thermal.get_frame()
            data = []
            for y in range(SENSOR_H):
                data.append(frame[y * SENSOR_W:(y+1) * SENSOR_W])
            return data
        else:
            # Simulate thermal with random hotspot
            import random
            data = [[random.uniform(20, 22) for _ in range(SENSOR_W)] for _ in range(SENSOR_H)]
            hx, hy = random.randint(5, 27), random.randint(5, 19)
            for dy in range(-3, 4):
                for dx in range(-3, 4):
                    if 0 <= hy+dy < SENSOR_H and 0 <= hx+dx < SENSOR_W:
                        data[hy+dy][hx+dx] = random.uniform(30, 36)
            return data
    
    def find_target(self, thermal_data):
        max_temp = 0
        max_x, max_y = SENSOR_W // 2, SENSOR_H // 2
        
        for y, row in enumerate(thermal_data):
            for x, temp in enumerate(row):
                if temp > max_temp:
                    max_temp = temp
                    max_x, max_y = x, y
        
        self.target_x = max_x
        self.target_y = max_y
        self.target_temp = max_temp
        
        return max_temp >= TARGET_TEMP
    
    def calculate_steering(self):
        # Target position relative to center
        center_x = SENSOR_W // 2
        offset = self.target_x - center_x
        
        # Proportional steering
        turn = int(offset * 3)  # Gain
        turn = max(-50, min(50, turn))
        
        return turn
    
    def hunt(self):
        turn = self.calculate_steering()
        base_speed = 40
        
        # Tank drive
        left = base_speed + turn
        right = base_speed - turn
        
        if HAS_BALA:
            bala.set_motor(int(left), int(right))
        
        print(f"Target: ({self.target_x}, {self.target_y}) {self.target_temp:.1f}C | Turn: {turn:+3d}")
    
    def stop(self):
        if HAS_BALA:
            bala.set_motor(0, 0)

def main():
    print("=== THERMAL HUNTER ===")
    print("Hunting the hottest target!\n")
    
    hunter = ThermalHunter()
    
    try:
        while True:
            thermal_data = hunter.get_thermal()
            
            if hunter.find_target(thermal_data):
                hunter.hunting = True
                hunter.hunt()
            else:
                hunter.hunting = False
                hunter.stop()
                print("No target found...")
            
            time.sleep(0.2)
            
    except KeyboardInterrupt:
        hunter.stop()
        print("\nHunt complete!")

if __name__ == "__main__":
    main()
