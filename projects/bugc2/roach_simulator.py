"""
BugC2 - Roach Simulator
=======================
Device: BugC2 with StickC Plus2
Difficulty: Medium

Scurries away from light like a cockroach!
Uses ambient light sensor for light detection.
Hides under furniture and freezes when exposed.
"""

import time
import random
from machine import Pin, ADC

try:
    from m5stack import BugC
    bugc = BugC()
    HAS_BUGC = True
except:
    HAS_BUGC = False

# Light sensor (adjust pin)
light_sensor = None
try:
    light_sensor = ADC(Pin(36))
    light_sensor.atten(ADC.ATTN_11DB)
except:
    pass

LIGHT_THRESHOLD = 2000  # Above = bright, below = dark
FREEZE_TIME = 30  # Ticks to freeze when exposed

class Roach:
    def __init__(self):
        self.freeze_timer = 0
        self.scurry_timer = 0
        self.direction = 0  # -1=left, 0=forward, 1=right
    
    def read_light(self):
        if light_sensor:
            return light_sensor.read()
        return random.randint(1000, 3000)  # Simulate
    
    def set_motors(self, l, r):
        if HAS_BUGC:
            bugc.set_motor(0, l)
            bugc.set_motor(1, l)
            bugc.set_motor(2, r)
            bugc.set_motor(3, r)
        print(f"L:{l:+4d} R:{r:+4d}")
    
    def freeze(self):
        self.set_motors(0, 0)
        if HAS_BUGC:
            bugc.set_rgb(0, 0, 0)  # Lights off - hiding
    
    def scurry(self):
        # Random jerky movement
        speed = random.randint(60, 100)
        turn = random.randint(-50, 50)
        
        self.set_motors(speed + turn, speed - turn)
        
        if HAS_BUGC:
            bugc.set_rgb(50, 25, 0)  # Brown-ish
        
        # Random scurry duration
        self.scurry_timer = random.randint(3, 15)
    
    def update(self):
        light = self.read_light()
        is_bright = light > LIGHT_THRESHOLD
        
        if is_bright:
            # LIGHT! Freeze then flee!
            if self.freeze_timer > 0:
                self.freeze()
                self.freeze_timer -= 1
            else:
                # Flee from light
                self.scurry()
                self.freeze_timer = FREEZE_TIME
        else:
            # Dark = safe, slow wander
            if self.scurry_timer > 0:
                self.scurry_timer -= 1
            else:
                speed = random.randint(20, 40)
                self.set_motors(speed, speed + random.randint(-20, 20))
                if HAS_BUGC:
                    bugc.set_rgb(20, 10, 0)

def main():
    print("Roach Simulator - scurries from light!")
    roach = Roach()
    
    try:
        while True:
            roach.update()
            time.sleep(0.1)
    except KeyboardInterrupt:
        roach.freeze()
        print("Roach squashed!")

if __name__ == "__main__":
    main()
