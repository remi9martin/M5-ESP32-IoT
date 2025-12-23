# T-Lite Intruder Alert System
# Human heat detection with buzzer alarm
# Device: M5Stack T-Lite (MLX90640)

import time
import machine
from mlx90640 import MLX90640
import st7789

try:
    from lib.display_utils import temp_to_color, COLORS
    from lib.espnow_mesh import ESPNowMesh, MSG_TYPES, DEVICE_TYPES
except:
    import sys
    sys.path.append('/projects/lib')
    from display_utils import temp_to_color, COLORS
    from espnow_mesh import ESPNowMesh, MSG_TYPES, DEVICE_TYPES

# Configuration
HUMAN_TEMP_MIN = 30.0  # Minimum temperature to consider "human"
HUMAN_TEMP_MAX = 40.0  # Maximum expected human temp
BLOB_SIZE_THRESHOLD = 8  # Minimum connected pixels for human detection
ALERT_COOLDOWN_MS = 5000  # Time between alerts

# Display config
DISPLAY_WIDTH = 240
DISPLAY_HEIGHT = 135
THERMAL_WIDTH = 32
THERMAL_HEIGHT = 24

class IntruderAlert:
    def __init__(self):
        self.display = None
        self.sensor = None
        self.buzzer = None
        self.mesh = None
        self.frame = [0] * (THERMAL_WIDTH * THERMAL_HEIGHT)
        self.armed = True
        self.last_alert_time = 0
        self.alert_count = 0
        
    def init(self):
        """Initialize all hardware"""
        # Display
        spi = machine.SPI(1, baudrate=40000000, polarity=1, phase=0,
                         sck=machine.Pin(36), mosi=machine.Pin(35))
        self.display = st7789.ST7789(
            spi, DISPLAY_WIDTH, DISPLAY_HEIGHT,
            reset=machine.Pin(33, machine.Pin.OUT),
            dc=machine.Pin(34, machine.Pin.OUT),
            cs=machine.Pin(37, machine.Pin.OUT),
            rotation=1
        )
        self.display.init()
        
        # Thermal sensor
        i2c = machine.I2C(0, scl=machine.Pin(22), sda=machine.Pin(21), freq=400000)
        self.sensor = MLX90640(i2c)
        self.sensor.refresh_rate = 4
        
        # Buzzer (PWM)
        self.buzzer = machine.PWM(machine.Pin(2))
        self.buzzer.duty(0)
        
        # ESP-NOW mesh for alerts
        self.mesh = ESPNowMesh(DEVICE_TYPES['TLITE'], "Intruder")
        self.mesh.init()
        
        print("Intruder Alert System initialized")
        self.show_status("ARMED", COLORS['green'])
        return True
    
    def show_status(self, status, color):
        """Display status message"""
        self.display.fill(COLORS['black'])
        self.display.fill_rect(0, 0, DISPLAY_WIDTH, 30, color)
        self.display.text("INTRUDER ALERT", 60, 8, COLORS['white'])
        
        # Status box
        self.display.fill_rect(20, 50, DISPLAY_WIDTH - 40, 40, COLORS['dark_gray'])
        self.display.text(status, 80, 65, color)
        
        # Stats
        self.display.text(f"Alerts: {self.alert_count}", 10, 110, COLORS['gray'])
    
    def read_frame(self):
        """Read thermal frame"""
        try:
            self.sensor.getFrame(self.frame)
            return True
        except:
            return False
    
    def find_human_blobs(self):
        """Detect human-sized heat blobs"""
        # Create binary mask of human-temperature pixels
        mask = [[False] * THERMAL_WIDTH for _ in range(THERMAL_HEIGHT)]
        
        for y in range(THERMAL_HEIGHT):
            for x in range(THERMAL_WIDTH):
                temp = self.frame[y * THERMAL_WIDTH + x]
                if HUMAN_TEMP_MIN <= temp <= HUMAN_TEMP_MAX:
                    mask[y][x] = True
        
        # Simple flood-fill blob detection
        visited = [[False] * THERMAL_WIDTH for _ in range(THERMAL_HEIGHT)]
        blobs = []
        
        def flood_fill(start_x, start_y):
            stack = [(start_x, start_y)]
            pixels = []
            
            while stack:
                x, y = stack.pop()
                if x < 0 or x >= THERMAL_WIDTH or y < 0 or y >= THERMAL_HEIGHT:
                    continue
                if visited[y][x] or not mask[y][x]:
                    continue
                    
                visited[y][x] = True
                pixels.append((x, y))
                
                # Check 4-connected neighbors
                stack.extend([(x+1, y), (x-1, y), (x, y+1), (x, y-1)])
            
            return pixels
        
        for y in range(THERMAL_HEIGHT):
            for x in range(THERMAL_WIDTH):
                if mask[y][x] and not visited[y][x]:
                    blob = flood_fill(x, y)
                    if len(blob) >= BLOB_SIZE_THRESHOLD:
                        # Calculate blob centroid and max temp
                        cx = sum(p[0] for p in blob) // len(blob)
                        cy = sum(p[1] for p in blob) // len(blob)
                        max_temp = max(self.frame[p[1] * THERMAL_WIDTH + p[0]] for p in blob)
                        blobs.append({
                            'x': cx,
                            'y': cy,
                            'size': len(blob),
                            'max_temp': max_temp
                        })
        
        return blobs
    
    def trigger_alarm(self, blob):
        """Sound the alarm!"""
        now = time.ticks_ms()
        if time.ticks_diff(now, self.last_alert_time) < ALERT_COOLDOWN_MS:
            return  # Still in cooldown
        
        self.last_alert_time = now
        self.alert_count += 1
        
        print(f"🚨 INTRUDER DETECTED at ({blob['x']}, {blob['y']}) - {blob['max_temp']:.1f}°C")
        
        # Visual alert
        for _ in range(3):
            self.display.fill(COLORS['red'])
            self.display.text("!! INTRUDER !!", 60, 60, COLORS['white'])
            
            # Buzzer alarm pattern
            self.buzzer.freq(2000)
            self.buzzer.duty(512)
            time.sleep_ms(200)
            self.buzzer.duty(0)
            time.sleep_ms(100)
        
        # Broadcast alert to mesh network
        self.mesh.send_alert("intruder", {
            'x': blob['x'],
            'y': blob['y'],
            'temp': blob['max_temp'],
            'size': blob['size']
        })
        
        # Return to armed state
        self.show_status("ARMED", COLORS['green'])
    
    def toggle_arm(self):
        """Toggle armed state"""
        self.armed = not self.armed
        if self.armed:
            self.show_status("ARMED", COLORS['green'])
        else:
            self.show_status("DISARMED", COLORS['yellow'])
    
    def render_thermal_mini(self):
        """Show small thermal preview"""
        # Mini thermal view in corner
        scale = 2
        x_offset = DISPLAY_WIDTH - THERMAL_WIDTH * scale - 5
        y_offset = 35
        
        for y in range(THERMAL_HEIGHT):
            for x in range(THERMAL_WIDTH):
                temp = self.frame[y * THERMAL_WIDTH + x]
                color = temp_to_color(temp, 15, 40)
                self.display.fill_rect(
                    x_offset + x * scale,
                    y_offset + y * scale,
                    scale, scale, color
                )
    
    def run(self):
        """Main monitoring loop"""
        print("Intruder Alert System running...")
        
        while True:
            # Check for mesh messages
            self.mesh.poll()
            
            if not self.armed:
                time.sleep_ms(500)
                continue
            
            if self.read_frame():
                # Detect human-sized heat blobs
                blobs = self.find_human_blobs()
                
                if blobs:
                    # Trigger on largest blob
                    largest = max(blobs, key=lambda b: b['size'])
                    self.trigger_alarm(largest)
                else:
                    # Update mini thermal preview
                    self.render_thermal_mini()
            
            time.sleep_ms(100)


# Entry point
if __name__ == "__main__":
    alert = IntruderAlert()
    if alert.init():
        alert.run()
