"""
AtomS3 - BLE Beacon Tracker
============================
Device: AtomS3 Dev Kit (ESP32-S3)
Difficulty: Easy

Logs all Bluetooth beacons/devices that pass by.
Shows device name, MAC, RSSI, and timestamp.
Great for seeing what devices are nearby!
"""

import time
import bluetooth
from micropython import const

# BLE scan parameters
_IRQ_SCAN_RESULT = const(5)
_IRQ_SCAN_DONE = const(6)

try:
    from m5stack import LCD
    lcd = LCD()
    HAS_DISPLAY = True
except:
    HAS_DISPLAY = False

C_CYAN = 0x07FF
C_WHITE = 0xFFFF
C_GREEN = 0x07E0

devices = {}  # MAC -> {name, rssi, last_seen, count}

def bt_irq(event, data):
    if event == _IRQ_SCAN_RESULT:
        addr_type, addr, adv_type, rssi, adv_data = data
        mac = ':'.join(['%02x' % b for b in bytes(addr)])
        
        # Try to get device name from adv_data
        name = parse_name(adv_data) or "Unknown"
        
        now = time.ticks_ms()
        if mac in devices:
            devices[mac]['rssi'] = rssi
            devices[mac]['last_seen'] = now
            devices[mac]['count'] += 1
        else:
            devices[mac] = {
                'name': name,
                'rssi': rssi,
                'first_seen': now,
                'last_seen': now,
                'count': 1
            }
            print(f"[NEW] {name} ({mac}) RSSI:{rssi}")

def parse_name(adv_data):
    """Extract device name from advertisement data"""
    i = 0
    while i < len(adv_data) - 1:
        length = adv_data[i]
        if length == 0:
            break
        ad_type = adv_data[i + 1]
        if ad_type in (0x08, 0x09):  # Short/Complete name
            try:
                return bytes(adv_data[i+2:i+1+length]).decode()
            except:
                pass
        i += 1 + length
    return None

def display_devices():
    # Sort by RSSI (strongest first)
    sorted_devs = sorted(devices.items(), key=lambda x: x[1]['rssi'], reverse=True)
    
    if HAS_DISPLAY:
        lcd.clear()
        lcd.text(f"BLE: {len(devices)} devices", 5, 5, C_CYAN)
        
        y = 25
        for mac, info in sorted_devs[:4]:  # Top 4
            name = info['name'][:12]
            lcd.text(f"{name}", 5, y, C_WHITE)
            lcd.text(f"{info['rssi']}dB", 100, y, C_GREEN)
            y += 18
    else:
        print(f"\n=== {len(devices)} BLE Devices ===")
        for mac, info in sorted_devs[:8]:
            print(f"{info['name'][:15]:15} {info['rssi']:4}dB  x{info['count']}")

def main():
    print("BLE Beacon Tracker")
    
    ble = bluetooth.BLE()
    ble.active(True)
    ble.irq(bt_irq)
    
    # Start continuous scanning
    ble.gap_scan(0, 30000, 30000)  # Continuous
    
    try:
        while True:
            display_devices()
            time.sleep(2)
    except KeyboardInterrupt:
        ble.gap_scan(None)
        ble.active(False)
        print(f"\nTotal unique devices: {len(devices)}")

if __name__ == "__main__":
    main()
