"""
COMBINED PROJECT: Cat Entertainment System
============================================
Devices: BugC2 + T-Lite + Joystick
Difficulty: Medium

The ultimate automated cat toy!
- T-Lite detects cat position via thermal
- BugC2 FLEES from the heat (cat)
- Joystick for manual override

Cat chases, robot runs away = endless fun!
"""

import time
import network
import espnow
from machine import Pin

# Device mode: CAR (BugC2+T-Lite) or CONTROLLER (Joystick)
MODE = 'CAR'  # or 'CONTROLLER'

PEER_MAC = b'\x00\x00\x00\x00\x00\x00'

# Try imports
try:
    from m5stack import BugC
    bugc = BugC()
    HAS_BUGC = True
except:
    HAS_BUGC = False

# Thermal simplified - just find hot zone
THERMAL_W = 32
CAT_TEMP = 28

def simulate_cat_position():
    import random
    if random.random() < 0.7:  # 70% cat visible
        return random.randint(0, 31), random.uniform(30, 36)
    return 16, 20  # No cat

def flee_from_cat(cat_x):
    """Calculate motor speeds to flee FROM cat"""
    center = THERMAL_W // 2
    
    # If cat is left of center, turn right
    # If cat is right of center, turn left
    offset = cat_x - center
    
    base = 60
    turn = int(offset * -2)  # Negative = flee AWAY
    
    left = base - turn
    right = base + turn
    
    return max(-100, min(100, left)), max(-100, min(100, right))

def set_motors(l, r):
    if HAS_BUGC:
        bugc.set_motor(0, l)
        bugc.set_motor(1, l)
        bugc.set_motor(2, r)
        bugc.set_motor(3, r)
    print(f"L:{l:+4d} R:{r:+4d}")

def car_loop():
    print("Cat Entertainment - CAR MODE")
    print("Running from the cat!\n")
    
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    
    esp = espnow.ESPNow()
    esp.active(True)
    
    manual_override = False
    
    try:
        while True:
            # Check for controller override
            host, msg = esp.recv()
            if msg:
                try:
                    x, y = map(int, msg.decode().split(':'))
                    if abs(x) > 20 or abs(y) > 20:
                        manual_override = True
                        left = max(-100, min(100, y + x))
                        right = max(-100, min(100, y - x))
                        set_motors(left, right)
                        continue
                except:
                    pass
            
            manual_override = False
            
            # Auto flee mode
            cat_x, cat_temp = simulate_cat_position()
            
            if cat_temp >= CAT_TEMP:
                print(f"Cat at x={cat_x} ({cat_temp:.1f}C) - FLEE!")
                left, right = flee_from_cat(cat_x)
                set_motors(left, right)
            else:
                # Slow wander to entice cat
                import random
                set_motors(30, 30 + random.randint(-20, 20))
            
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        set_motors(0, 0)
        print("Cat toy stopped")

def controller_loop():
    from machine import ADC
    
    print("Cat Entertainment - CONTROLLER")
    
    joy_x = ADC(Pin(33))
    joy_y = ADC(Pin(32))
    joy_x.atten(ADC.ATTN_11DB)
    joy_y.atten(ADC.ATTN_11DB)
    
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    
    esp = espnow.ESPNow()
    esp.active(True)
    esp.add_peer(PEER_MAC)
    
    try:
        while True:
            x = int((joy_x.read() - 2048) / 20.48)
            y = int((joy_y.read() - 2048) / 20.48)
            x = max(-100, min(100, x))
            y = max(-100, min(100, y))
            
            esp.send(PEER_MAC, f"{x}:{y}")
            time.sleep(0.02)
            
    except KeyboardInterrupt:
        print("Controller stopped")

if __name__ == "__main__":
    if MODE == 'CAR':
        car_loop()
    else:
        controller_loop()
