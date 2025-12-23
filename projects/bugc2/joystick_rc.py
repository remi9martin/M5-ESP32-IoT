"""
BugC2 + Joystick - RC Car (ESP-NOW)
===================================
Device: BugC2 + Atom Joystick
Difficulty: Easy

TX: Joystick sends X:Y over ESP-NOW
RX: BugC2 receives and drives motors
Set DEVICE_MODE before flashing!
"""

import time
from machine import Pin, ADC
import network
import espnow
import gc

DEVICE_MODE = 'RECEIVER'  # 'RECEIVER' or 'TRANSMITTER'
PEER_MAC = b'\x00\x00\x00\x00\x00\x00'  # Set peer MAC

try:
    from m5stack import BugC
    bugc = BugC()
    HAS_BUGC = True
except:
    HAS_BUGC = False

def receiver_loop():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    print(f"MAC: {wlan.config('mac').hex(':')}")
    
    esp = espnow.ESPNow()
    esp.active(True)
    
    while True:
        host, msg = esp.recv()
        if msg:
            try:
                x, y = map(int, msg.decode().split(':'))
                left = max(-100, min(100, y + x))
                right = max(-100, min(100, y - x))
                if HAS_BUGC:
                    bugc.set_motor(0, left)
                    bugc.set_motor(1, left)
                    bugc.set_motor(2, right)
                    bugc.set_motor(3, right)
                print(f"L:{left:+4d} R:{right:+4d}")
            except:
                pass
        time.sleep(0.01)

def transmitter_loop():
    joy_x = ADC(Pin(33))
    joy_y = ADC(Pin(32))
    joy_x.atten(ADC.ATTN_11DB)
    joy_y.atten(ADC.ATTN_11DB)
    
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    print(f"MAC: {wlan.config('mac').hex(':')}")
    
    esp = espnow.ESPNow()
    esp.active(True)
    esp.add_peer(PEER_MAC)
    
    while True:
        x = int((joy_x.read() - 2048) / 20.48)
        y = int((joy_y.read() - 2048) / 20.48)
        x = max(-100, min(100, x))
        y = max(-100, min(100, y))
        esp.send(PEER_MAC, f"{x}:{y}")
        time.sleep(0.02)

if __name__ == "__main__":
    print(f"RC Car - {DEVICE_MODE}")
    if DEVICE_MODE == 'RECEIVER':
        receiver_loop()
    else:
        transmitter_loop()
