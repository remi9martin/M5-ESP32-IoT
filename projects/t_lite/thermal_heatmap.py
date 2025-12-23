# T-Lite Thermal Heatmap Display
# Live thermal imaging with color gradients
# Device: M5Stack T-Lite (MLX90640)

import time
import machine
from mlx90640 import MLX90640
import st7789

# Import shared display utils
try:
    from lib.display_utils import temp_to_color, COLORS, draw_header
except:
    # Fallback for direct execution
    import sys
    sys.path.append('/projects/lib')
    from display_utils import temp_to_color, COLORS, draw_header

# Display configuration (T-Lite has 1.14" TFT, 135x240)
DISPLAY_WIDTH = 240
DISPLAY_HEIGHT = 135

# Thermal sensor resolution
THERMAL_WIDTH = 32
THERMAL_HEIGHT = 24

# Scaling factor for display
PIXEL_WIDTH = DISPLAY_WIDTH // THERMAL_WIDTH   # ~7 pixels
PIXEL_HEIGHT = (DISPLAY_HEIGHT - 25) // THERMAL_HEIGHT  # ~4 pixels (leave room for header)

class ThermalHeatmap:
    def __init__(self):
        self.display = None
        self.sensor = None
        self.frame = [0] * (THERMAL_WIDTH * THERMAL_HEIGHT)
        self.min_temp = 20.0
        self.max_temp = 35.0
        self.auto_range = True
        
    def init(self):
        """Initialize display and thermal sensor"""
        # Initialize SPI display
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
        self.display.fill(COLORS['black'])
        
        # Initialize I2C for MLX90640
        i2c = machine.I2C(0, scl=machine.Pin(22), sda=machine.Pin(21), freq=400000)
        self.sensor = MLX90640(i2c)
        self.sensor.refresh_rate = 4  # 4Hz for smoother updates
        
        print("Thermal Heatmap initialized")
        return True
        
    def read_frame(self):
        """Read a frame from the thermal sensor"""
        try:
            self.sensor.getFrame(self.frame)
            
            # Auto-range temperature scale
            if self.auto_range:
                self.min_temp = min(self.frame)
                self.max_temp = max(self.frame)
                # Add some margin
                self.min_temp = max(self.min_temp - 2, 0)
                self.max_temp = min(self.max_temp + 2, 100)
                
            return True
        except Exception as e:
            print(f"Sensor read error: {e}")
            return False
    
    def render(self):
        """Render thermal frame to display"""
        # Draw header with temp range
        self.display.fill_rect(0, 0, DISPLAY_WIDTH, 20, COLORS['black'])
        temp_text = f"{self.min_temp:.1f}C - {self.max_temp:.1f}C"
        self.display.text(temp_text, 5, 5, COLORS['white'])
        
        # Draw hotspot indicator
        max_idx = self.frame.index(max(self.frame))
        max_x = max_idx % THERMAL_WIDTH
        max_y = max_idx // THERMAL_WIDTH
        hotspot_text = f"HOT: ({max_x},{max_y}) {max(self.frame):.1f}C"
        self.display.text(hotspot_text, 130, 5, COLORS['red'])
        
        # Render thermal pixels
        y_offset = 22  # Below header
        for y in range(THERMAL_HEIGHT):
            for x in range(THERMAL_WIDTH):
                idx = y * THERMAL_WIDTH + x
                temp = self.frame[idx]
                color = temp_to_color(temp, self.min_temp, self.max_temp)
                
                # Draw scaled pixel
                px = x * PIXEL_WIDTH
                py = y_offset + y * PIXEL_HEIGHT
                self.display.fill_rect(px, py, PIXEL_WIDTH, PIXEL_HEIGHT, color)
        
        # Draw hotspot crosshair
        cross_x = max_x * PIXEL_WIDTH + PIXEL_WIDTH // 2
        cross_y = y_offset + max_y * PIXEL_HEIGHT + PIXEL_HEIGHT // 2
        self.display.hline(cross_x - 5, cross_y, 10, COLORS['white'])
        self.display.vline(cross_x, cross_y - 5, 10, COLORS['white'])
    
    def get_hotspot(self):
        """Get position and temperature of hottest point"""
        max_temp = max(self.frame)
        max_idx = self.frame.index(max_temp)
        return (max_idx % THERMAL_WIDTH, max_idx // THERMAL_WIDTH, max_temp)
    
    def run(self):
        """Main loop"""
        print("Starting thermal heatmap...")
        self.display.fill(COLORS['black'])
        
        frame_count = 0
        start_time = time.ticks_ms()
        
        while True:
            if self.read_frame():
                self.render()
                frame_count += 1
                
                # Show FPS every 30 frames
                if frame_count % 30 == 0:
                    elapsed = time.ticks_diff(time.ticks_ms(), start_time)
                    fps = 30000 / elapsed
                    print(f"FPS: {fps:.1f}")
                    start_time = time.ticks_ms()
            
            time.sleep_ms(50)  # ~20Hz max update rate


# Entry point
if __name__ == "__main__":
    heatmap = ThermalHeatmap()
    if heatmap.init():
        heatmap.run()
