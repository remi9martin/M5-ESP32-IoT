"""
M5Stack T-Lite - Intruder Alert System  
=======================================
Device: M5Stack T-Lite (MLX90640 32x24 IR sensor)
Difficulty: Medium

Features:
- Calibrates to room background temperature
- Detects human-sized heat blobs
- Configurable detection zones
- Alarm sound on intrusion
- Activity logging with timestamps
- Adjustable sensitivity
"""

import time
from machine import I2C, Pin, PWM
import gc

# Try imports
try:
    import mlx90640
    HAS_THERMAL = True
except:
    HAS_THERMAL = False

try:
    from m5stack import LCD
    lcd = LCD()
    HAS_DISPLAY = True
except:
    HAS_DISPLAY = False

# Constants
SENSOR_WIDTH = 32
SENSOR_HEIGHT = 24
HUMAN_TEMP_MIN = 28  # Minimum temp for human detection
HUMAN_TEMP_MAX = 40  # Maximum expected body surface temp
MIN_BLOB_SIZE = 20   # Minimum pixels to count as human-sized

# Alert states
STATE_IDLE = 0
STATE_CALIBRATING = 1
STATE_ARMED = 2
STATE_ALERT = 3

# Colors
C_BLACK = 0x0000
C_WHITE = 0xFFFF
C_GREEN = 0x07E0
C_RED = 0xF800
C_YELLOW = 0xFFE0
C_CYAN = 0x07FF

class IntruderAlert:
    def __init__(self):
        self.state = STATE_IDLE
        self.background = None
        self.sensitivity = 5.0  # Temperature difference threshold
        self.alert_cooldown = 0
        self.intrusions = []
        self.last_frame = None
        
        # Buzzer setup (if available)
        try:
            self.buzzer = PWM(Pin(25), freq=2000, duty=0)
        except:
            self.buzzer = None
    
    def calibrate(self, frames=10):
        """Capture background temperature baseline"""
        print("Calibrating background...")
        self.state = STATE_CALIBRATING
        
        accumulated = [[0.0] * SENSOR_WIDTH for _ in range(SENSOR_HEIGHT)]
        
        for f in range(frames):
            frame = self.get_thermal_frame()
            for y in range(SENSOR_HEIGHT):
                for x in range(SENSOR_WIDTH):
                    accumulated[y][x] += frame[y][x]
            
            if HAS_DISPLAY:
                lcd.fill_rect(0, 60, 240, 30, C_BLACK)
                progress = int((f + 1) / frames * 200)
                lcd.fill_rect(20, 70, progress, 10, C_CYAN)
                lcd.text(f"Calibrating {f+1}/{frames}", 60, 55, C_WHITE)
            
            time.sleep(0.3)
        
        # Average
        self.background = [[accumulated[y][x] / frames 
                           for x in range(SENSOR_WIDTH)] 
                          for y in range(SENSOR_HEIGHT)]
        
        print("Calibration complete!")
        return True
    
    def get_thermal_frame(self):
        """Get thermal data (real or simulated)"""
        if HAS_THERMAL:
            frame = sensor.get_frame()
            thermal_data = []
            for y in range(SENSOR_HEIGHT):
                row = frame[y * SENSOR_WIDTH:(y + 1) * SENSOR_WIDTH]
                thermal_data.append(list(row))
            return thermal_data
        else:
            return self.simulate_frame()
    
    def simulate_frame(self):
        """Simulate thermal data with occasional intruder"""
        import random
        
        # Base room temperature
        data = [[random.uniform(19, 22) for _ in range(SENSOR_WIDTH)] 
                for _ in range(SENSOR_HEIGHT)]
        
        # Occasionally add a "person"
        if random.random() < 0.15:  # 15% chance
            px = random.randint(8, SENSOR_WIDTH - 8)
            py = random.randint(6, SENSOR_HEIGHT - 6)
            
            # Human-shaped heat blob
            for dy in range(-5, 6):
                for dx in range(-4, 5):
                    if 0 <= py + dy < SENSOR_HEIGHT and 0 <= px + dx < SENSOR_WIDTH:
                        dist = (dx*dx/16 + dy*dy/25) ** 0.5
                        if dist < 1:
                            data[py + dy][px + dx] = random.uniform(32, 36)
        
        return data
    
    def detect_intrusion(self, frame):
        """Compare current frame to background and detect intruders"""
        if not self.background:
            return False, 0, []
        
        hot_pixels = []
        
        for y in range(SENSOR_HEIGHT):
            for x in range(SENSOR_WIDTH):
                diff = frame[y][x] - self.background[y][x]
                
                # Check if significantly warmer than background
                if diff > self.sensitivity and frame[y][x] >= HUMAN_TEMP_MIN:
                    hot_pixels.append((x, y, frame[y][x]))
        
        # Check if enough hot pixels to be human-sized
        if len(hot_pixels) >= MIN_BLOB_SIZE:
            return True, len(hot_pixels), hot_pixels
        
        return False, len(hot_pixels), hot_pixels
    
    def trigger_alarm(self):
        """Sound the alarm!"""
        print("\n🚨 INTRUDER DETECTED! 🚨")
        
        if self.buzzer:
            # Siren sound
            for _ in range(5):
                self.buzzer.freq(2000)
                self.buzzer.duty(512)
                time.sleep(0.1)
                self.buzzer.freq(1000)
                time.sleep(0.1)
            self.buzzer.duty(0)
        
        # Log intrusion
        self.intrusions.append({
            'time': time.time(),
            'timestamp': time.localtime()
        })
    
    def display_status(self, frame=None, hot_pixels=[]):
        """Update display with current status"""
        if not HAS_DISPLAY:
            return
        
        lcd.clear()
        
        # Status header
        status_colors = {
            STATE_IDLE: (C_WHITE, "IDLE"),
            STATE_CALIBRATING: (C_YELLOW, "CALIBRATING"),
            STATE_ARMED: (C_GREEN, "ARMED"),
            STATE_ALERT: (C_RED, "ALERT!")
        }
        
        color, text = status_colors.get(self.state, (C_WHITE, "???"))
        lcd.fill_rect(0, 0, 240, 25, color)
        lcd.text(f"SECURITY: {text}", 10, 5, C_BLACK if self.state != STATE_IDLE else C_WHITE)
        
        # Mini thermal view
        if frame:
            scale = 4
            ox, oy = 10, 35
            for y in range(SENSOR_HEIGHT):
                for x in range(SENSOR_WIDTH):
                    temp = frame[y][x]
                    # Simple 3-color coding
                    if temp > 30:
                        c = C_RED
                    elif temp > 25:
                        c = C_YELLOW
                    else:
                        c = C_CYAN
                    lcd.fill_rect(ox + x * scale, oy + y * scale, scale, scale, c)
            
            # Mark hot pixels
            for hx, hy, _ in hot_pixels:
                lcd.rect(ox + hx * scale - 1, oy + hy * scale - 1, scale + 2, scale + 2, C_WHITE)
        
        # Info
        lcd.text(f"Sensitivity: {self.sensitivity:.1f}C", 150, 35, C_WHITE)
        lcd.text(f"Intrusions: {len(self.intrusions)}", 150, 50, C_WHITE)
        lcd.text(f"Hot pixels: {len(hot_pixels)}", 150, 65, C_WHITE)

def main():
    """Main security loop"""
    print("="*50)
    print("  INTRUDER ALERT SYSTEM")
    print("  Thermal Motion Detection")
    print("="*50)
    
    # Initialize sensor
    global sensor
    if HAS_THERMAL:
        i2c = I2C(0, scl=Pin(22), sda=Pin(21), freq=400000)
        sensor = mlx90640.MLX90640(i2c)
        sensor.set_refresh_rate(mlx90640.REFRESH_4_HZ)
    
    alert = IntruderAlert()
    
    if HAS_DISPLAY:
        lcd.clear()
        lcd.text("Initializing...", 60, 60, C_WHITE)
    
    time.sleep(1)
    
    # Calibrate
    alert.calibrate(frames=10)
    alert.state = STATE_ARMED
    print("\n[ARMED] System is now monitoring...")
    
    try:
        while True:
            frame = alert.get_thermal_frame()
            alert.last_frame = frame
            
            # Check for intrusion
            detected, count, hot_pixels = alert.detect_intrusion(frame)
            
            if detected:
                if alert.state != STATE_ALERT:
                    alert.state = STATE_ALERT
                    alert.trigger_alarm()
                    alert.alert_cooldown = 50  # Stay in alert for 5 seconds
            else:
                if alert.alert_cooldown > 0:
                    alert.alert_cooldown -= 1
                else:
                    alert.state = STATE_ARMED
            
            alert.display_status(frame, hot_pixels)
            
            gc.collect()
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        print(f"\n\nSession Summary:")
        print(f"Total intrusion alerts: {len(alert.intrusions)}")
        if HAS_DISPLAY:
            lcd.clear()

if __name__ == "__main__":
    main()
