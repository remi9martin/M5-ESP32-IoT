"""
AtomS3 - WiFi Deauth Detector
==============================
Device: AtomS3 Dev Kit (ESP32-S3)
Difficulty: Medium

Monitors for deauthentication attacks on your network.
Alerts when suspicious activity is detected.
Passive monitoring - doesn't interfere with network.
"""

import time
import network
from machine import Pin, PWM

try:
    from m5stack import LCD
    lcd = LCD()
    HAS_DISPLAY = True
except:
    HAS_DISPLAY = False

# Buzzer for alerts
try:
    buzzer = PWM(Pin(25), freq=1000, duty=0)
except:
    buzzer = None

C_RED = 0xF800
C_GREEN = 0x07E0
C_WHITE = 0xFFFF
C_YELLOW = 0xFFE0

# Detection state
alerts = []
deauth_count = 0
monitoring = True

# Simulated detection for demo
# Real implementation needs promiscuous mode

def simulate_detection():
    """Simulates occasional deauth detection"""
    import random
    if random.random() < 0.05:  # 5% chance per check
        return {
            'type': 'DEAUTH',
            'target': f"XX:XX:XX:{random.randint(10,99):02X}:XX:XX",
            'channel': random.randint(1, 11),
            'time': time.localtime()
        }
    return None

def alert(info):
    global deauth_count
    deauth_count += 1
    alerts.append(info)
    if len(alerts) > 10:
        alerts.pop(0)
    
    print(f"\n🚨 DEAUTH DETECTED! Ch:{info['channel']} Target:{info['target']}")
    
    if buzzer:
        buzzer.duty(512)
        time.sleep(0.2)
        buzzer.duty(0)

def display_status():
    if HAS_DISPLAY:
        lcd.clear()
        lcd.text("Deauth Detector", 5, 5, C_WHITE)
        
        status = "MONITORING" if monitoring else "PAUSED"
        color = C_GREEN if deauth_count == 0 else C_RED
        lcd.text(status, 5, 25, color)
        lcd.text(f"Alerts: {deauth_count}", 5, 45, C_YELLOW)
        
        if alerts:
            last = alerts[-1]
            lcd.text(f"Last: Ch{last['channel']}", 5, 65, C_RED)
    else:
        print(f"[{time.time()}] Monitoring... Alerts: {deauth_count}")

def main():
    print("WiFi Deauth Detector")
    print("Monitoring for attacks...")
    
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    
    display_timer = 0
    
    try:
        while True:
            if monitoring:
                # Check for deauth (simulated in demo)
                detected = simulate_detection()
                if detected:
                    alert(detected)
            
            display_timer += 1
            if display_timer >= 20:
                display_status()
                display_timer = 0
            
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        if buzzer:
            buzzer.duty(0)
        print(f"\nTotal alerts: {deauth_count}")

if __name__ == "__main__":
    main()
