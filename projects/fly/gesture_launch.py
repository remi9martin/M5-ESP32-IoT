"""
M5Stamp Fly - Gesture Launch
=============================
Device: M5Stamp Fly (ESP32 quadcopter)
Difficulty: Hard

Wave pattern detection triggers takeoff!
Uses ToF sensor to detect hand gestures.
Auto-hover and auto-land features.
"""

import time
from machine import Pin, I2C

# ToF sensor (VL53L0X compatible)
try:
    from vl53l0x import VL53L0X
    i2c = I2C(0, scl=Pin(22), sda=Pin(21))
    tof = VL53L0X(i2c)
    HAS_TOF = True
except:
    HAS_TOF = False

# Flight controller interface
try:
    from m5fly import FlightController
    fc = FlightController()
    HAS_FC = True
except:
    HAS_FC = False

# Gesture detection
GESTURE_THRESHOLD = 200  # mm change for gesture
WAVE_COUNT_NEEDED = 3    # Waves to trigger launch
WAVE_TIMEOUT = 2.0       # Seconds to complete gesture

class GestureLauncher:
    def __init__(self):
        self.wave_count = 0
        self.last_wave_time = 0
        self.last_dist = 0
        self.flying = False
        self.direction = 0  # 0=waiting, 1=hand coming, -1=hand going
    
    def read_distance(self):
        if HAS_TOF:
            return tof.read()
        import random
        return random.randint(50, 500)  # Simulate
    
    def detect_wave(self, dist):
        now = time.time()
        diff = dist - self.last_dist
        
        # Detect hand approaching
        if diff < -GESTURE_THRESHOLD and self.direction != 1:
            self.direction = 1
            if now - self.last_wave_time > WAVE_TIMEOUT:
                self.wave_count = 0  # Reset if too slow
            self.wave_count += 1
            self.last_wave_time = now
            print(f"Wave {self.wave_count}/{WAVE_COUNT_NEEDED}")
        
        # Detect hand leaving
        elif diff > GESTURE_THRESHOLD and self.direction == 1:
            self.direction = -1
        
        self.last_dist = dist
        
        # Check for launch gesture
        if self.wave_count >= WAVE_COUNT_NEEDED:
            self.wave_count = 0
            return True
        return False
    
    def launch(self):
        print("\n🚁 LAUNCH DETECTED!")
        self.flying = True
        if HAS_FC:
            fc.takeoff()
            fc.hover(height=100)  # 100cm
    
    def land(self):
        print("Landing...")
        self.flying = False
        if HAS_FC:
            fc.land()
    
    def display_status(self, dist):
        status = "FLYING" if self.flying else "READY"
        waves = "🌊" * self.wave_count
        print(f"\r{status} | Dist: {dist:4d}mm | {waves}     ", end="")

def main():
    print("Gesture Launch Controller")
    print("Wave 3 times to launch!\n")
    
    launcher = GestureLauncher()
    
    try:
        while True:
            dist = launcher.read_distance()
            
            if not launcher.flying:
                if launcher.detect_wave(dist):
                    launcher.launch()
            else:
                # Auto-land after 10 seconds for demo
                time.sleep(10)
                launcher.land()
            
            launcher.display_status(dist)
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        if launcher.flying:
            launcher.land()
        print("\nController stopped")

if __name__ == "__main__":
    main()
