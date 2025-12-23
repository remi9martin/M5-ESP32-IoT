"""
M5Stack T-Lite Thermal Camera - Cat Tracker
=============================================
Device: M5Stack T-Lite (MLX90640 32x24 IR sensor)
Difficulty: Easy

Features:
- Visual thermal display with color gradient
- Auto-detects warmest spot (your cat!)
- Shows hotspot location indicator
- Temperature range display
- Cat-shaped cursor follows warmest point
"""

import time
from machine import I2C, Pin
import gc

# Try to import MLX90640 driver
try:
    import mlx90640
    HAS_THERMAL = True
except:
    HAS_THERMAL = False
    print("MLX90640 driver not found - using simulated data")

# Display setup
try:
    from m5stack import LCD
    lcd = LCD()
    HAS_DISPLAY = True
except:
    HAS_DISPLAY = False

# Constants
SENSOR_WIDTH = 32
SENSOR_HEIGHT = 24
MIN_TEMP = 15  # Expected minimum temp in room
MAX_TEMP = 40  # Cat body temp range
CAT_TEMP_THRESHOLD = 28  # Temperatures above this likely a cat

# Color palette for thermal display (cold to hot)
THERMAL_PALETTE = [
    0x000F,  # Deep blue (cold)
    0x001F,  # Blue
    0x03FF,  # Cyan
    0x07E0,  # Green
    0xFFE0,  # Yellow
    0xFD20,  # Orange
    0xF800,  # Red
    0xF81F,  # Magenta (hot!)
]

def temp_to_color(temp, min_t=MIN_TEMP, max_t=MAX_TEMP):
    """Convert temperature to palette color"""
    if temp <= min_t:
        return THERMAL_PALETTE[0]
    if temp >= max_t:
        return THERMAL_PALETTE[-1]
    
    # Map to palette index
    ratio = (temp - min_t) / (max_t - min_t)
    idx = int(ratio * (len(THERMAL_PALETTE) - 1))
    return THERMAL_PALETTE[idx]

def simulate_thermal_data():
    """Generate fake thermal data with a hot spot"""
    import random
    
    data = []
    
    # Random hot spot position (simulating cat)
    cat_x = random.randint(5, SENSOR_WIDTH - 5)
    cat_y = random.randint(5, SENSOR_HEIGHT - 5)
    cat_temp = random.uniform(32, 38)  # Cat body temp
    
    for y in range(SENSOR_HEIGHT):
        row = []
        for x in range(SENSOR_WIDTH):
            # Distance from cat
            dist = ((x - cat_x)**2 + (y - cat_y)**2) ** 0.5
            
            if dist < 3:
                # Cat body
                temp = cat_temp - dist * 1.5
            else:
                # Room background
                temp = random.uniform(18, 22)
            
            row.append(temp)
        data.append(row)
    
    return data

def find_hotspot(thermal_data):
    """Find the hottest point in the thermal data"""
    max_temp = -100
    max_x, max_y = 0, 0
    
    for y, row in enumerate(thermal_data):
        for x, temp in enumerate(row):
            if temp > max_temp:
                max_temp = temp
                max_x, max_y = x, y
    
    return max_x, max_y, max_temp

def display_thermal(thermal_data, hotspot=None):
    """Render thermal image on display"""
    if HAS_DISPLAY:
        # Scale factor for display (240 pixels wide)
        scale_x = 7  # 32 * 7 = 224
        scale_y = 5  # 24 * 5 = 120
        
        for y, row in enumerate(thermal_data):
            for x, temp in enumerate(row):
                color = temp_to_color(temp)
                
                # Draw scaled pixel
                x1 = x * scale_x + 8
                y1 = y * scale_y + 15
                lcd.fill_rect(x1, y1, scale_x, scale_y, color)
        
        # Draw hotspot indicator
        if hotspot:
            hx, hy, temp = hotspot
            # Scale to display coordinates
            dx = hx * scale_x + 8 + scale_x // 2
            dy = hy * scale_y + 15 + scale_y // 2
            
            # Cat indicator (crosshair with ears!)
            lcd.circle(dx, dy, 10, 0xFFFF)
            lcd.line(dx - 15, dy, dx + 15, dy, 0xFFFF)
            lcd.line(dx, dy - 15, dx, dy + 15, 0xFFFF)
            
            # Cat ears (triangles)
            lcd.line(dx - 8, dy - 10, dx - 4, dy - 18, 0xFFFF)
            lcd.line(dx + 8, dy - 10, dx + 4, dy - 18, 0xFFFF)
        
        # Info bar at top
        lcd.text("Cat Tracker", 5, 2, 0x07FF)
        if hotspot:
            lcd.text(f"Hot: {hotspot[2]:.1f}C", 150, 2, 0xF800)
    else:
        # ASCII thermal in terminal
        print("\033[2J\033[H")  # Clear screen
        print("=== CAT TRACKER ===")
        
        chars = " .:-=+*#%@"
        for y, row in enumerate(thermal_data):
            line = ""
            for x, temp in enumerate(row):
                idx = int((temp - MIN_TEMP) / (MAX_TEMP - MIN_TEMP) * (len(chars) - 1))
                idx = max(0, min(len(chars) - 1, idx))
                
                if hotspot and x == hotspot[0] and y == hotspot[1]:
                    line += "🐱"
                else:
                    line += chars[idx]
            print(line)
        
        if hotspot:
            print(f"\n🐱 Cat detected at ({hotspot[0]}, {hotspot[1]}) - {hotspot[2]:.1f}°C")

def main():
    """Main cat tracker loop"""
    print("="*50)
    print("  T-Lite Cat Tracker")
    print("  Find your cat in the dark!")
    print("="*50)
    
    # Initialize I2C and sensor
    if HAS_THERMAL:
        i2c = I2C(0, scl=Pin(22), sda=Pin(21), freq=400000)
        sensor = mlx90640.MLX90640(i2c)
        sensor.set_refresh_rate(mlx90640.REFRESH_2_HZ)
    
    if HAS_DISPLAY:
        lcd.clear()
    
    try:
        while True:
            # Get thermal frame
            if HAS_THERMAL:
                frame = sensor.get_frame()
                # Reshape to 2D
                thermal_data = []
                for y in range(SENSOR_HEIGHT):
                    row = frame[y * SENSOR_WIDTH:(y + 1) * SENSOR_WIDTH]
                    thermal_data.append(list(row))
            else:
                thermal_data = simulate_thermal_data()
            
            # Find the hottest spot
            hotspot = find_hotspot(thermal_data)
            
            # Check if it's likely a cat
            if hotspot[2] >= CAT_TEMP_THRESHOLD:
                cat_detected = True
                print(f"🐱 Cat detected! Temp: {hotspot[2]:.1f}°C")
            else:
                cat_detected = False
                hotspot = None
            
            # Display
            display_thermal(thermal_data, hotspot)
            
            gc.collect()
            time.sleep(0.5)
            
    except KeyboardInterrupt:
        print("\nCat tracker stopped.")
        if HAS_DISPLAY:
            lcd.clear()

if __name__ == "__main__":
    main()
