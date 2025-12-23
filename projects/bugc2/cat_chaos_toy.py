"""
BugC2 + StickC Plus2 - Cat Chaos Toy
=====================================
Device: BugC2 with M5StickC Plus2
Difficulty: Easy

Features:
- Random chaotic movement patterns
- RGB LED effects that cats love
- Sudden direction changes
- Variable speed bursts
- Auto-pause for cat to catch up
- Button triggers turbo mode
"""

import time
import random
from machine import Pin, PWM
import gc

# Try to import M5 specific modules
try:
    from m5stack import StickC, BugC
    bugc = BugC()
    HAS_BUGC = True
except:
    HAS_BUGC = False
    print("BugC not found - running in simulation mode")

try:
    from m5stack import LCD
    lcd = LCD()
    HAS_DISPLAY = True
except:
    HAS_DISPLAY = False

# RGB LED colors (R, G, B)
COLORS = [
    (255, 0, 0),    # Red
    (0, 255, 0),    # Green
    (0, 0, 255),    # Blue
    (255, 255, 0),  # Yellow
    (255, 0, 255),  # Magenta
    (0, 255, 255),  # Cyan
    (255, 128, 0),  # Orange
]

# Movement modes
MODE_WANDER = 0
MODE_ZIGZAG = 1
MODE_SPIN = 2
MODE_BURST = 3
MODE_PAUSE = 4

class CatToy:
    def __init__(self):
        self.mode = MODE_WANDER
        self.speed = 50
        self.mode_timer = 0
        self.led_timer = 0
        self.current_color = 0
        self.turbo = False
        
        # Motor values: -100 to 100
        self.left_speed = 0
        self.right_speed = 0
    
    def set_motors(self, left, right):
        """Set motor speeds (-100 to 100)"""
        self.left_speed = left
        self.right_speed = right
        
        if HAS_BUGC:
            # BugC has 4 motors, pair them for tank drive
            bugc.set_motor(0, int(left))
            bugc.set_motor(1, int(left))
            bugc.set_motor(2, int(right))
            bugc.set_motor(3, int(right))
        else:
            print(f"Motors: L={left:+4.0f} R={right:+4.0f}")
    
    def set_led(self, r, g, b):
        """Set RGB LED color"""
        if HAS_BUGC:
            bugc.set_rgb(r, g, b)
        # else just logged
    
    def flash_led(self):
        """Cycle through colors rapidly"""
        self.current_color = (self.current_color + 1) % len(COLORS)
        r, g, b = COLORS[self.current_color]
        self.set_led(r, g, b)
    
    def wander(self):
        """Random wandering movement"""
        base_speed = 40 if not self.turbo else 80
        
        # Slight curve left or right
        curve = random.randint(-30, 30)
        self.set_motors(base_speed + curve, base_speed - curve)
        
        # Random LED flash
        if random.random() < 0.3:
            self.flash_led()
    
    def zigzag(self):
        """Sharp zig-zag pattern"""
        speed = 60 if not self.turbo else 100
        
        # Alternate sharp turns
        if (time.ticks_ms() // 300) % 2 == 0:
            self.set_motors(speed, speed // 3)
        else:
            self.set_motors(speed // 3, speed)
        
        self.flash_led()
    
    def spin(self):
        """Spin in place"""
        spin_speed = 70 if not self.turbo else 100
        direction = random.choice([-1, 1])
        
        self.set_motors(spin_speed * direction, -spin_speed * direction)
        self.flash_led()
    
    def burst(self):
        """Sudden speed burst forward"""
        self.set_motors(100, 100)
        self.set_led(255, 0, 0)  # Red during burst
    
    def pause(self):
        """Stop and flash - let cat catch up"""
        self.set_motors(0, 0)
        
        # Enticing flash pattern
        if (time.ticks_ms() // 100) % 2 == 0:
            self.flash_led()
        else:
            self.set_led(0, 0, 0)
    
    def update(self):
        """Main update loop"""
        self.mode_timer -= 1
        
        # Time to change mode?
        if self.mode_timer <= 0:
            self.change_mode()
        
        # Execute current mode
        if self.mode == MODE_WANDER:
            self.wander()
        elif self.mode == MODE_ZIGZAG:
            self.zigzag()
        elif self.mode == MODE_SPIN:
            self.spin()
        elif self.mode == MODE_BURST:
            self.burst()
        elif self.mode == MODE_PAUSE:
            self.pause()
    
    def change_mode(self):
        """Randomly switch to a new movement mode"""
        modes = [MODE_WANDER, MODE_ZIGZAG, MODE_SPIN, MODE_BURST, MODE_PAUSE]
        weights = [30, 20, 15, 10, 25]  # Weighted probability
        
        # Weighted random choice
        total = sum(weights)
        r = random.randint(0, total - 1)
        cumulative = 0
        for mode, weight in zip(modes, weights):
            cumulative += weight
            if r < cumulative:
                self.mode = mode
                break
        
        # Set duration for this mode
        durations = {
            MODE_WANDER: (20, 50),
            MODE_ZIGZAG: (15, 30),
            MODE_SPIN: (5, 15),
            MODE_BURST: (3, 8),
            MODE_PAUSE: (10, 30),
        }
        min_d, max_d = durations[self.mode]
        self.mode_timer = random.randint(min_d, max_d)
        
        mode_names = ["WANDER", "ZIGZAG", "SPIN", "BURST!", "PAUSE"]
        print(f"Mode: {mode_names[self.mode]} ({self.mode_timer} ticks)")
    
    def display_status(self):
        """Update display"""
        if HAS_DISPLAY:
            lcd.clear()
            mode_names = ["WANDER", "ZIGZAG", "SPIN", "BURST!", "PAUSE"]
            
            lcd.text("CAT CHAOS TOY", 10, 10, 0x07FF)
            lcd.text(f"Mode: {mode_names[self.mode]}", 10, 40, 0xFFFF)
            lcd.text(f"L:{self.left_speed:+4.0f} R:{self.right_speed:+4.0f}", 10, 60, 0xFFE0)
            
            if self.turbo:
                lcd.text("TURBO!", 10, 80, 0xF800)
    
    def stop(self):
        """Emergency stop"""
        self.set_motors(0, 0)
        self.set_led(0, 0, 0)

def main():
    """Main cat toy loop"""
    print("="*50)
    print("  BugC2 Cat Chaos Toy")
    print("  Press Ctrl+C to stop")
    print("="*50)
    
    toy = CatToy()
    
    # Initial mode
    toy.change_mode()
    
    display_counter = 0
    
    try:
        while True:
            toy.update()
            
            # Update display every 10 loops
            display_counter += 1
            if display_counter >= 10:
                toy.display_status()
                display_counter = 0
            
            # Check for button press (turbo mode)
            # On StickC Plus2, button A triggers turbo
            try:
                if StickC.btnA.wasPressed():
                    toy.turbo = not toy.turbo
                    print(f"Turbo: {'ON' if toy.turbo else 'OFF'}")
            except:
                pass
            
            time.sleep(0.05)  # 20Hz update rate
            gc.collect()
            
    except KeyboardInterrupt:
        print("\nStopping cat toy...")
        toy.stop()
        print("Cat can rest now! 😺")

if __name__ == "__main__":
    main()
