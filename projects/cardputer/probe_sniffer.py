"""
M5Stack Cardputer - Probe Request Sniffer
==========================================
Device: M5Stack Cardputer (ESP32-S3)
Difficulty: Medium

Features:
- Captures WiFi probe requests
- Shows what networks nearby devices are searching for
- Logs MAC addresses (anonymized last 3 bytes)
- Reveals hidden network SSIDs being sought
- Real-time display with scroll

Note: Uses promiscuous mode for passive monitoring
"""

import network
import time
import ubinascii
from machine import Pin
import gc

# Try to import ESP-specific modules
try:
    import esp
    from esp import wifi_raw_packet_callback
    HAS_RAW_WIFI = True
except:
    HAS_RAW_WIFI = False

# Display setup
try:
    from m5stack import LCD
    lcd = LCD()
    HAS_DISPLAY = True
except:
    HAS_DISPLAY = False

# Colors
BLACK = 0x0000
WHITE = 0xFFFF
CYAN = 0x07FF
GREEN = 0x07E0
YELLOW = 0xFFE0
MAGENTA = 0xF81F

# Storage for captured probes
probes = []
MAX_PROBES = 50
seen_macs = set()

def anonymize_mac(mac_bytes):
    """Anonymize MAC - show first 3 bytes (vendor) only"""
    hex_str = ubinascii.hexlify(mac_bytes).decode()
    return f"{hex_str[0:2]}:{hex_str[2:4]}:{hex_str[4:6]}:XX:XX:XX"

def parse_probe_request(packet):
    """Parse probe request frame and extract SSID"""
    # 802.11 Management Frame Structure:
    # Frame Control (2) + Duration (2) + Addr1 (6) + Addr2 (6) + Addr3 (6) + Seq (2)
    # = 24 bytes header
    
    if len(packet) < 36:
        return None
        
    # Check if it's a probe request (subtype 0x04)
    frame_control = packet[0:2]
    subtype = (frame_control[0] >> 4) & 0x0F
    
    if subtype != 4:  # Not a probe request
        return None
    
    # Extract source MAC (transmitter address)
    source_mac = packet[10:16]
    
    # Tagged parameters start at byte 24
    i = 24
    ssid = None
    
    while i < len(packet) - 2:
        tag_num = packet[i]
        tag_len = packet[i + 1]
        
        if i + 2 + tag_len > len(packet):
            break
            
        if tag_num == 0:  # SSID element
            ssid_bytes = packet[i + 2:i + 2 + tag_len]
            try:
                ssid = ssid_bytes.decode('utf-8')
            except:
                ssid = "<binary>"
            break
            
        i += 2 + tag_len
    
    return {
        'mac': source_mac,
        'mac_str': anonymize_mac(source_mac),
        'ssid': ssid if ssid else "<broadcast>",
        'time': time.ticks_ms()
    }

def packet_callback(packet):
    """Callback for received raw packets"""
    global probes
    
    result = parse_probe_request(packet)
    if result:
        # Check if we've seen this MAC+SSID combo recently
        key = result['mac_str'] + result['ssid']
        if key not in seen_macs:
            seen_macs.add(key)
            probes.append(result)
            
            # Limit stored probes
            if len(probes) > MAX_PROBES:
                probes.pop(0)
            
            # Print to serial
            print(f"[PROBE] {result['mac_str']} -> \"{result['ssid']}\"")

def display_probes(scroll=0):
    """Display captured probes on screen"""
    if HAS_DISPLAY:
        lcd.clear()
        lcd.text("Probe Sniffer", 5, 5, CYAN)
        lcd.text(f"Captured: {len(probes)}", 5, 20, WHITE)
        lcd.line(0, 32, 240, 32, WHITE)
        
        y = 40
        max_display = 5
        for i in range(scroll, min(scroll + max_display, len(probes))):
            probe = probes[-(i+1)]  # Newest first
            ssid = probe['ssid'][:18] + ".." if len(probe['ssid']) > 20 else probe['ssid']
            
            color = MAGENTA if probe['ssid'] != "<broadcast>" else YELLOW
            lcd.text(f'"{ssid}"', 5, y, color)
            lcd.text(probe['mac_str'], 5, y + 12, WHITE)
            y += 28
        
        lcd.text("Passive monitoring...", 5, 120, GREEN)
    else:
        # Just serial output
        pass

def simulate_probes():
    """Simulate probe detection for demo without raw WiFi"""
    import random
    
    fake_macs = ['AA:BB:CC', 'DE:AD:BE', '12:34:56', 'CA:FE:BA', 'FE:ED:FA']
    fake_ssids = ['HomeWifi', 'Starbucks', 'ATT-Guest', 'xfinitywifi', 
                  'Airport_Free', 'NETGEAR', 'Linksys', 'FBI_VAN',
                  '<broadcast>', 'MyHiddenNetwork', 'Office_5G']
    
    probe = {
        'mac_str': f"{random.choice(fake_macs)}:XX:XX:XX",
        'ssid': random.choice(fake_ssids),
        'time': time.ticks_ms()
    }
    
    key = probe['mac_str'] + probe['ssid']
    if key not in seen_macs:
        seen_macs.add(key)
        probes.append(probe)
        if len(probes) > MAX_PROBES:
            probes.pop(0)
        print(f"[PROBE] {probe['mac_str']} -> \"{probe['ssid']}\"")

def main():
    """Main sniffer loop"""
    print("="*50)
    print("  Probe Request Sniffer")
    print("  Passive WiFi Monitoring")
    print("="*50)
    
    if not HAS_RAW_WIFI:
        print("\n[!] Raw WiFi capture not available")
        print("[!] Running in DEMO mode with simulated data")
        print("[!] For real capture, use firmware with promiscuous mode\n")
    
    # Initialize WiFi in station mode
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    
    # If we have raw WiFi support, enable promiscuous mode
    if HAS_RAW_WIFI:
        wifi_raw_packet_callback(packet_callback)
    
    last_display = 0
    scroll = 0
    
    try:
        while True:
            # Simulate probes in demo mode
            if not HAS_RAW_WIFI:
                import random
                if random.random() < 0.3:  # 30% chance each loop
                    simulate_probes()
            
            # Update display every second
            if time.ticks_ms() - last_display > 1000:
                display_probes(scroll)
                last_display = time.ticks_ms()
                gc.collect()
            
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        print(f"\n\nCaptured {len(probes)} unique probe requests")
        print("Sniffer stopped.")
        wlan.active(False)

if __name__ == "__main__":
    main()
