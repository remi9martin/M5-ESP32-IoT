# BALA2 Thermal Hunter
# Self-balancing robot that chases the hottest object in view
# Device: M5Stack BALA2 Fire + T-Lite Thermal Camera

import time
import math
import machine
from mlx90640 import MLX90640

try:
    from lib.display_utils import COLORS, temp_to_color
    from lib.espnow_mesh import ESPNowMesh, MSG_TYPES, DEVICE_TYPES
except:
    import sys
    sys.path.append('/projects/lib')
    from display_utils import COLORS, temp_to_color
    from espnow_mesh import ESPNowMesh, MSG_TYPES, DEVICE_TYPES

# BALA2 Motor configuration
MOTOR_I2C_ADDR = 0x00
THERMAL_WIDTH = 32
THERMAL_HEIGHT = 24

# PID constants for steering
KP = 2.0   # Proportional
KI = 0.1   # Integral
KD = 0.5   # Derivative

# Hunting configuration
HUNT_TEMP_MIN = 28.0      # Minimum temp to hunt
CHASE_SPEED = 80          # Base chase speed
CLOSE_DISTANCE = 10       # Pixels from center = "caught"
ACQUISITION_THRESHOLD = 5  # Frames to confirm target

class ThermalHunter:
    def __init__(self):
        # Hardware
        self.i2c_motor = None
        self.i2c_sensor = None
        self.thermal = None
        self.display = None
        self.mesh = None
        
        # State
        self.frame = [0] * (THERMAL_WIDTH * THERMAL_HEIGHT)
        self.target_x = THERMAL_WIDTH // 2  # Center
        self.target_acquired = False
        self.acquisition_count = 0
        
        # PID state
        self.last_error = 0
        self.integral = 0
        
        # Balancing state
        self.is_balanced = False
        
    def init(self):
        """Initialize all hardware"""
        # Motor I2C (BALA2 uses secondary I2C)
        self.i2c_motor = machine.I2C(1, scl=machine.Pin(22), sda=machine.Pin(21), freq=400000)
        
        # Thermal sensor I2C (same bus)
        self.thermal = MLX90640(self.i2c_motor)
        self.thermal.refresh_rate = 4  # 4Hz
        
        # Display (M5Fire has ILI9341)
        try:
            import ili9341
            spi = machine.SPI(1, baudrate=40000000, sck=machine.Pin(18), 
                             mosi=machine.Pin(23), miso=machine.Pin(19))
            self.display = ili9341.ILI9341(spi, 
                                           cs=machine.Pin(14),
                                           dc=machine.Pin(27),
                                           rst=machine.Pin(33),
                                           rotation=1)
            self.display.fill(COLORS['black'])
        except:
            print("Display not available")
        
        # ESP-NOW for mesh communication
        self.mesh = ESPNowMesh(DEVICE_TYPES['BALA2'], "Hunter")
        self.mesh.init()
        
        # Register for thermal broadcasts (from secondary T-Lite)
        self.mesh.on_message(MSG_TYPES['THERMAL'], self.on_thermal_data)
        
        print("🎯 Thermal Hunter initialized!")
        self.show_status("HUNTING MODE", COLORS['red'])
        return True
    
    def on_thermal_data(self, mac, packet):
        """Handle thermal data from external T-Lite sensor"""
        data = packet['data']
        # Update target position from external source
        self.target_x = data.get('hx', THERMAL_WIDTH // 2)
    
    def show_status(self, text, color):
        """Update display status"""
        if self.display:
            self.display.fill_rect(0, 0, 320, 30, COLORS['black'])
            self.display.text(text, 10, 8, color)
    
    def set_motors(self, left, right):
        """Set motor speeds for balance + steering"""
        # Clamp to valid range
        left = max(-127, min(127, int(left)))
        right = max(-127, min(127, int(right)))
        
        # Convert to unsigned for I2C
        left_byte = left if left >= 0 else 256 + left
        right_byte = right if right >= 0 else 256 + right
        
        try:
            # BALA2 uses Grove port, write to motor driver
            self.i2c_motor.writeto(MOTOR_I2C_ADDR, bytes([left_byte, right_byte]))
        except Exception as e:
            print(f"Motor error: {e}")
    
    def stop(self):
        """Stop motors"""
        self.set_motors(0, 0)
    
    def read_thermal(self):
        """Read thermal frame and find hotspot"""
        try:
            self.thermal.getFrame(self.frame)
            
            # Find hottest pixel
            max_temp = max(self.frame)
            
            if max_temp < HUNT_TEMP_MIN:
                return None  # Nothing hot enough
            
            max_idx = self.frame.index(max_temp)
            hot_x = max_idx % THERMAL_WIDTH
            hot_y = max_idx // THERMAL_WIDTH
            
            return {'x': hot_x, 'y': hot_y, 'temp': max_temp}
            
        except Exception as e:
            print(f"Thermal read error: {e}")
            return None
    
    def calculate_steering(self, target_x):
        """PID controller for steering toward target"""
        # Error is pixels from center
        center = THERMAL_WIDTH // 2
        error = target_x - center
        
        # PID calculation
        self.integral += error
        self.integral = max(-100, min(100, self.integral))  # Anti-windup
        
        derivative = error - self.last_error
        self.last_error = error
        
        output = KP * error + KI * self.integral + KD * derivative
        return output
    
    def hunt(self, hotspot):
        """Chase the hotspot"""
        steer = self.calculate_steering(hotspot['x'])
        
        # Calculate differential drive
        left_speed = CHASE_SPEED - steer
        right_speed = CHASE_SPEED + steer
        
        self.set_motors(left_speed, right_speed)
        
        # Check if target is centered (caught!)
        center = THERMAL_WIDTH // 2
        distance = abs(hotspot['x'] - center)
        
        return distance < CLOSE_DISTANCE
    
    def render_hunting_view(self, hotspot):
        """Show hunting HUD on display"""
        if not self.display:
            return
        
        # Clear main area
        self.display.fill_rect(0, 30, 320, 210, COLORS['black'])
        
        # Draw thermal mini-map
        scale = 3
        x_off, y_off = 10, 40
        
        for y in range(THERMAL_HEIGHT):
            for x in range(THERMAL_WIDTH):
                temp = self.frame[y * THERMAL_WIDTH + x]
                color = temp_to_color(temp, 15, 40)
                self.display.fill_rect(x_off + x * scale, y_off + y * scale, 
                                       scale, scale, color)
        
        # Draw crosshair on target
        if hotspot:
            tx = x_off + hotspot['x'] * scale
            ty = y_off + hotspot['y'] * scale
            
            # Pulsing target reticle
            self.display.rect(tx - 5, ty - 5, 10, 10, COLORS['red'])
            self.display.line(tx - 8, ty, tx + 8, ty, COLORS['white'])
            self.display.line(tx, ty - 8, tx, ty + 8, COLORS['white'])
        
        # Status info
        info_x = 120
        self.display.text(f"Target: {hotspot['temp']:.1f}C" if hotspot else "Scanning...", 
                         info_x, 50, COLORS['yellow'])
        self.display.text(f"Status: {'LOCKED' if self.target_acquired else 'SEEKING'}", 
                         info_x, 70, COLORS['green'] if self.target_acquired else COLORS['red'])
        
        # Center indicator
        center_x = x_off + (THERMAL_WIDTH // 2) * scale
        self.display.vline(center_x, y_off - 5, 5, COLORS['cyan'])
        self.display.vline(center_x, y_off + THERMAL_HEIGHT * scale, 5, COLORS['cyan'])
    
    def victory_dance(self):
        """Celebrate catching target!"""
        print("🎯 TARGET ACQUIRED!")
        self.show_status("CAUGHT!", COLORS['green'])
        
        # Victory spin
        for _ in range(3):
            self.set_motors(60, -60)
            time.sleep_ms(200)
            self.set_motors(-60, 60)
            time.sleep_ms(200)
        
        self.stop()
        
        # Broadcast success
        self.mesh.send_alert("caught", {"temp": self.frame[self.frame.index(max(self.frame))]})
        
        # Reset
        time.sleep(1)
        self.target_acquired = False
        self.acquisition_count = 0
    
    def run(self):
        """Main hunting loop"""
        print("🔥 Thermal Hunter active! Looking for heat signatures...")
        
        try:
            while True:
                # Check mesh messages
                self.mesh.poll()
                
                # Read thermal
                hotspot = self.read_thermal()
                
                if hotspot:
                    # Target found!
                    self.acquisition_count += 1
                    
                    if self.acquisition_count >= ACQUISITION_THRESHOLD:
                        self.target_acquired = True
                    
                    if self.target_acquired:
                        self.show_status(f"HUNTING: {hotspot['temp']:.1f}C", COLORS['red'])
                        caught = self.hunt(hotspot)
                        
                        if caught:
                            self.victory_dance()
                    else:
                        self.show_status("ACQUIRING...", COLORS['yellow'])
                else:
                    # Lost target
                    self.acquisition_count = 0
                    self.target_acquired = False
                    self.show_status("SCANNING...", COLORS['cyan'])
                    self.stop()  # Stop and look
                
                # Render display
                self.render_hunting_view(hotspot)
                
                time.sleep_ms(100)
                
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()
            self.mesh.cleanup()
            print("Hunter stopped.")


# Entry point
if __name__ == "__main__":
    hunter = ThermalHunter()
    if hunter.init():
        hunter.run()
