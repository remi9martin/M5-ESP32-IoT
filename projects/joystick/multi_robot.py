"""
Atom Joystick - Multi-Robot Master Controller
===============================================
Device: Atom Joystick (AtomS3 + analog joystick)
Difficulty: Medium

Controls multiple robots over ESP-NOW.
Button cycles between robots: BugC2, BALA2, BALA-C, Drone
"""

import time
from machine import Pin, ADC
import network
import espnow

# Robot MACs - replace with actual addresses
ROBOTS = {
    'BugC2': b'\x00\x00\x00\x00\x00\x01',
    'BALA2': b'\x00\x00\x00\x00\x00\x02',
    'BALA-C': b'\x00\x00\x00\x00\x00\x03',
    'Drone': b'\x00\x00\x00\x00\x00\x04',
}

try:
    from m5stack import LCD
    lcd = LCD()
    HAS_DISPLAY = True
except:
    HAS_DISPLAY = False

# Joystick
joy_x = ADC(Pin(33))
joy_y = ADC(Pin(32))
joy_x.atten(ADC.ATTN_11DB)
joy_y.atten(ADC.ATTN_11DB)

# Button
button = Pin(39, Pin.IN, Pin.PULL_UP)

# State
current_robot_idx = 0
robot_names = list(ROBOTS.keys())

def read_joystick():
    x = int((joy_x.read() - 2048) / 20.48)
    y = int((joy_y.read() - 2048) / 20.48)
    return max(-100, min(100, x)), max(-100, min(100, y))

def display_status(robot, x, y):
    if HAS_DISPLAY:
        lcd.clear()
        lcd.text("MULTI-ROBOT", 10, 5, 0x07FF)
        lcd.text(f"-> {robot}", 10, 30, 0x07E0)
        lcd.text(f"X:{x:+4d} Y:{y:+4d}", 10, 55, 0xFFFF)
        lcd.text("BTN: Switch", 10, 75, 0xFFE0)

def main():
    global current_robot_idx
    
    print("Multi-Robot Controller")
    print("Button cycles robots\n")
    
    # ESP-NOW setup
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    
    esp = espnow.ESPNow()
    esp.active(True)
    for mac in ROBOTS.values():
        esp.add_peer(mac)
    
    last_btn = 1
    
    try:
        while True:
            robot_name = robot_names[current_robot_idx]
            robot_mac = ROBOTS[robot_name]
            
            # Read joystick
            x, y = read_joystick()
            
            # Send to current robot
            msg = f"{x}:{y}"
            try:
                esp.send(robot_mac, msg)
            except:
                pass
            
            # Check button for robot switch
            btn = button.value()
            if btn == 0 and last_btn == 1:  # Press
                current_robot_idx = (current_robot_idx + 1) % len(robot_names)
                print(f"Switched to: {robot_names[current_robot_idx]}")
            last_btn = btn
            
            display_status(robot_name, x, y)
            time.sleep(0.02)
            
    except KeyboardInterrupt:
        esp.active(False)
        print("Controller stopped")

if __name__ == "__main__":
    main()
