# BugC2 Cat Chaos Toy
# Random erratic movements with LED flashes for cat entertainment
# Device: M5Stack BugC2 + StickC Plus2

import time
import random
import machine
from neopixel import NeoPixel

try:
    from lib.display_utils import COLORS
except:
    import sys
    sys.path.append('/projects/lib')
    from display_utils import COLORS

# Motor pins for BugC2 (I2C controlled via STM32)
I2C_ADDR = 0x38

# Movement patterns
PATTERNS = {
    'FORWARD': (100, 100, 100, 100),
    'BACKWARD': (-100, -100, -100, -100),
    'SPIN_LEFT': (-80, -80, 80, 80),
    'SPIN_RIGHT': (80, 80, -80, -80),
    'DRIFT_LEFT': (50, 100, 100, 50),
    'DRIFT_RIGHT': (100, 50, 50, 100),
    'STOP': (0, 0, 0, 0),
    'WIGGLE': None,  # Special pattern
}

# Chaos behaviors
CHAOS_MODES = [
    'SCATTER',    # Quick random direction changes
    'CIRCLE',     # Spin in circles
    'DASH',       # Burst forward then stop
    'FREEZE',     # Suddenly stop (cat pounce moment)
    'ZIGZAG',     # Erratic zig-zag
]

class CatChaosToy:
    def __init__(self):
        self.i2c = None
        self.display = None
        self.leds = None
        self.current_mode = 'SCATTER'
        self.speed_multiplier = 1.0
        self.is_running = False
        
    def init(self):
        """Initialize BugC2 hardware"""
        # I2C for motor control
        self.i2c = machine.I2C(0, scl=machine.Pin(26), sda=machine.Pin(0), freq=100000)
        
        # NeoPixel LEDs (2 on BugC2)
        self.leds = NeoPixel(machine.Pin(27), 2)
        self.set_leds((0, 0, 0))
        
        # StickC Plus2 display
        # Using simplified SPI display init
        try:
            import st7789
            spi = machine.SPI(1, baudrate=40000000, polarity=1, phase=0,
                             sck=machine.Pin(36), mosi=machine.Pin(35))
            self.display = st7789.ST7789(spi, 135, 240,
                                         reset=machine.Pin(33, machine.Pin.OUT),
                                         dc=machine.Pin(34, machine.Pin.OUT),
                                         cs=machine.Pin(37, machine.Pin.OUT))
            self.display.init()
            self.show_status("CAT CHAOS", (255, 100, 0))
        except:
            print("Display not available")
        
        print("Cat Chaos Toy initialized!")
        return True
    
    def set_motors(self, m1, m2, m3, m4):
        """Set motor speeds (-127 to 127)"""
        # Apply speed multiplier
        m1 = int(m1 * self.speed_multiplier)
        m2 = int(m2 * self.speed_multiplier)
        m3 = int(m3 * self.speed_multiplier)
        m4 = int(m4 * self.speed_multiplier)
        
        # Clamp values
        clamp = lambda v: max(-127, min(127, v))
        values = [clamp(m1), clamp(m2), clamp(m3), clamp(m4)]
        
        # Convert to unsigned bytes
        data = bytes([v if v >= 0 else 256 + v for v in values])
        
        try:
            self.i2c.writeto(I2C_ADDR, data)
        except:
            pass
    
    def apply_pattern(self, pattern_name):
        """Apply a named movement pattern"""
        if pattern_name == 'WIGGLE':
            # Special wiggle pattern
            for _ in range(3):
                self.set_motors(80, 80, -80, -80)
                time.sleep_ms(100)
                self.set_motors(-80, -80, 80, 80)
                time.sleep_ms(100)
            self.stop()
            return
        
        pattern = PATTERNS.get(pattern_name, PATTERNS['STOP'])
        self.set_motors(*pattern)
    
    def stop(self):
        """Stop all motors"""
        self.set_motors(0, 0, 0, 0)
    
    def set_leds(self, color):
        """Set both LEDs to same color"""
        self.leds[0] = color
        self.leds[1] = color
        self.leds.write()
    
    def flash_leds(self, times=3, color=(255, 0, 255)):
        """Flash LEDs"""
        for _ in range(times):
            self.set_leds(color)
            time.sleep_ms(50)
            self.set_leds((0, 0, 0))
            time.sleep_ms(50)
    
    def random_color(self):
        """Generate random bright color"""
        return (
            random.randint(100, 255),
            random.randint(100, 255),
            random.randint(100, 255)
        )
    
    def show_status(self, text, color):
        """Show status on StickC display"""
        if self.display:
            self.display.fill(0)
            self.display.text(text, 10, 60, 
                            (color[0] << 11) | (color[1] << 5) | color[2])
    
    # === CHAOS BEHAVIORS ===
    
    def scatter_mode(self):
        """Quick random direction changes"""
        patterns = ['FORWARD', 'SPIN_LEFT', 'SPIN_RIGHT', 'DRIFT_LEFT', 'DRIFT_RIGHT']
        
        for _ in range(random.randint(3, 7)):
            pattern = random.choice(patterns)
            self.apply_pattern(pattern)
            self.set_leds(self.random_color())
            time.sleep_ms(random.randint(150, 400))
        
        self.stop()
        self.flash_leds(2)
    
    def circle_mode(self):
        """Spin in circles"""
        direction = random.choice(['SPIN_LEFT', 'SPIN_RIGHT'])
        self.set_leds((255, 255, 0))  # Yellow
        
        # Accelerate
        for speed in range(50, 127, 10):
            self.speed_multiplier = speed / 100
            self.apply_pattern(direction)
            time.sleep_ms(100)
        
        # Full speed circles
        time.sleep_ms(random.randint(500, 1500))
        
        # Decelerate
        for speed in range(127, 0, -15):
            self.speed_multiplier = speed / 100
            self.apply_pattern(direction)
            time.sleep_ms(100)
        
        self.speed_multiplier = 1.0
        self.stop()
        self.flash_leds(3, (255, 255, 0))
    
    def dash_mode(self):
        """Burst forward then stop"""
        self.set_leds((0, 255, 0))  # Green
        
        # Quick burst
        self.speed_multiplier = 1.2
        self.apply_pattern('FORWARD')
        time.sleep_ms(random.randint(300, 600))
        
        # Sudden stop (perfect for cat pounce)
        self.stop()
        self.flash_leds(1, (255, 0, 0))
        time.sleep_ms(random.randint(200, 500))
        
        # Maybe spin away!
        if random.random() > 0.5:
            self.apply_pattern(random.choice(['SPIN_LEFT', 'SPIN_RIGHT']))
            time.sleep_ms(200)
            self.stop()
        
        self.speed_multiplier = 1.0
    
    def freeze_mode(self):
        """Freeze in place (entice cat to approach)"""
        self.stop()
        self.set_leds((0, 0, 255))  # Blue = frozen
        self.show_status("FROZEN...", (0, 0, 255))
        
        # Dramatic pause
        freeze_time = random.randint(1000, 3000)
        time.sleep_ms(freeze_time)
        
        # BURST away!
        self.flash_leds(2, (255, 0, 0))
        self.set_leds((255, 0, 0))
        self.speed_multiplier = 1.3
        self.apply_pattern(random.choice(['BACKWARD', 'SPIN_LEFT', 'SPIN_RIGHT']))
        time.sleep_ms(300)
        self.stop()
        self.speed_multiplier = 1.0
    
    def zigzag_mode(self):
        """Erratic zig-zag pattern"""
        self.set_leds((255, 0, 255))  # Magenta
        
        for _ in range(random.randint(4, 8)):
            # Zig
            self.apply_pattern('DRIFT_LEFT')
            time.sleep_ms(random.randint(100, 250))
            # Zag
            self.apply_pattern('DRIFT_RIGHT')
            time.sleep_ms(random.randint(100, 250))
            
            # Random LED color change
            if random.random() > 0.5:
                self.set_leds(self.random_color())
        
        self.stop()
        self.flash_leds(2)
    
    def execute_chaos(self):
        """Execute random chaos behavior"""
        mode = random.choice(CHAOS_MODES)
        self.current_mode = mode
        self.show_status(mode, self.random_color())
        
        if mode == 'SCATTER':
            self.scatter_mode()
        elif mode == 'CIRCLE':
            self.circle_mode()
        elif mode == 'DASH':
            self.dash_mode()
        elif mode == 'FREEZE':
            self.freeze_mode()
        elif mode == 'ZIGZAG':
            self.zigzag_mode()
    
    def run(self):
        """Main chaos loop"""
        print("🐱 Cat Chaos Toy running! Press Ctrl+C to stop.")
        self.is_running = True
        
        # Startup sequence
        self.flash_leds(5, (255, 255, 255))
        self.show_status("CHAOS MODE!", (255, 0, 0))
        time.sleep(1)
        
        try:
            while self.is_running:
                self.execute_chaos()
                
                # Random pause between behaviors
                pause = random.randint(500, 2000)
                self.set_leds((50, 50, 50))  # Dim = waiting
                time.sleep_ms(pause)
                
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()
            self.set_leds((0, 0, 0))
            print("Cat Chaos stopped.")


# Entry point
if __name__ == "__main__":
    toy = CatChaosToy()
    if toy.init():
        toy.run()
