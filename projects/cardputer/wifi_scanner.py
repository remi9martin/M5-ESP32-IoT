# Cardputer WiFi Scanner
# Network visualization dashboard with keyboard navigation
# Device: M5Stack Cardputer (ESP32-S3)

import time
import network
import machine
import st7789

try:
    from lib.display_utils import COLORS, draw_signal_bars, draw_header
except:
    import sys
    sys.path.append('/projects/lib')
    from display_utils import COLORS, draw_signal_bars, draw_header

# Display configuration (Cardputer: 1.14" TFT 135x240)
DISPLAY_WIDTH = 240
DISPLAY_HEIGHT = 135

# Security type icons
SECURITY_ICONS = {
    0: '🔓',  # Open
    1: 'WEP',
    2: 'WPA',
    3: 'WPA2',
    4: 'WPA3',
    5: 'WPA2E',
}

# Colors for encryption types
SECURITY_COLORS = {
    0: COLORS['red'],      # Open = danger
    1: COLORS['orange'],   # WEP = weak
    2: COLORS['yellow'],   # WPA = okay
    3: COLORS['green'],    # WPA2 = good
    4: COLORS['cyan'],     # WPA3 = best
    5: COLORS['green'],    # WPA2 Enterprise
}

class WiFiScanner:
    def __init__(self):
        self.display = None
        self.wlan = None
        self.keyboard = None
        self.networks = []
        self.selected_idx = 0
        self.scroll_offset = 0
        self.detail_mode = False
        self.scanning = False
        self.last_scan_time = 0
        
        # Visible network rows
        self.visible_rows = 5
        
    def init(self):
        """Initialize hardware"""
        # SPI Display
        spi = machine.SPI(1, baudrate=40000000, polarity=1, phase=0,
                         sck=machine.Pin(36), mosi=machine.Pin(35))
        self.display = st7789.ST7789(
            spi, DISPLAY_WIDTH, DISPLAY_HEIGHT,
            reset=machine.Pin(33, machine.Pin.OUT),
            dc=machine.Pin(34, machine.Pin.OUT),
            cs=machine.Pin(37, machine.Pin.OUT),
            rotation=1
        )
        self.display.init()
        self.display.fill(COLORS['black'])
        
        # WiFi station mode
        self.wlan = network.WLAN(network.STA_IF)
        self.wlan.active(True)
        
        # Keyboard matrix (Cardputer uses I2C keyboard)
        self.init_keyboard()
        
        print("WiFi Scanner initialized")
        self.show_splash()
        return True
    
    def init_keyboard(self):
        """Initialize Cardputer keyboard"""
        # Cardputer uses dedicated keyboard controller
        try:
            self.kbd_i2c = machine.I2C(0, scl=machine.Pin(1), sda=machine.Pin(2), freq=100000)
            self.keyboard = True
        except:
            self.keyboard = None
            print("Keyboard not available, using buttons")
    
    def read_key(self):
        """Read keyboard input"""
        if not self.keyboard:
            return None
        
        try:
            data = self.kbd_i2c.readfrom(0x5F, 1)
            if data[0] != 0:
                return chr(data[0])
        except:
            pass
        return None
    
    def show_splash(self):
        """Show startup splash"""
        self.display.fill(COLORS['black'])
        self.display.text("WIFI SCANNER", 60, 30, COLORS['cyan'])
        self.display.text("═" * 20, 30, 50, COLORS['dark_gray'])
        self.display.text("↑↓ Navigate", 20, 70, COLORS['gray'])
        self.display.text("ENTER Details", 20, 85, COLORS['gray'])
        self.display.text("R Rescan", 20, 100, COLORS['gray'])
        self.display.text("Press any key...", 50, 120, COLORS['yellow'])
        
    def scan_networks(self):
        """Scan for WiFi networks"""
        self.scanning = True
        self.display.fill(COLORS['black'])
        self.display.text("Scanning...", 80, 60, COLORS['yellow'])
        
        # Animate scanning
        for i in range(3):
            self.display.text("." * (i + 1), 160, 60, COLORS['yellow'])
            time.sleep_ms(300)
        
        try:
            raw_networks = self.wlan.scan()
            
            # Parse and sort by signal strength
            self.networks = []
            for n in raw_networks:
                ssid = n[0].decode('utf-8', 'ignore')
                bssid = ':'.join([f'{b:02x}' for b in n[1]])
                channel = n[2]
                rssi = n[3]
                authmode = n[4]
                hidden = n[5]
                
                self.networks.append({
                    'ssid': ssid if ssid else '[Hidden]',
                    'bssid': bssid,
                    'channel': channel,
                    'rssi': rssi,
                    'security': authmode,
                    'hidden': hidden,
                })
            
            # Sort by signal strength (strongest first)
            self.networks.sort(key=lambda x: x['rssi'], reverse=True)
            
            self.last_scan_time = time.time()
            
        except Exception as e:
            print(f"Scan error: {e}")
            self.networks = []
        
        self.scanning = False
        self.selected_idx = 0
        self.scroll_offset = 0
    
    def rssi_to_bars(self, rssi):
        """Convert RSSI to signal bars (0-4)"""
        if rssi >= -50:
            return 4
        elif rssi >= -60:
            return 3
        elif rssi >= -70:
            return 2
        elif rssi >= -80:
            return 1
        return 0
    
    def draw_network_list(self):
        """Draw the network list view"""
        self.display.fill(COLORS['black'])
        
        # Header
        self.display.fill_rect(0, 0, DISPLAY_WIDTH, 18, COLORS['blue'])
        self.display.text(f"Networks: {len(self.networks)}", 5, 3, COLORS['white'])
        
        ago = int(time.time() - self.last_scan_time)
        self.display.text(f"{ago}s ago", 180, 3, COLORS['gray'])
        
        if not self.networks:
            self.display.text("No networks found", 50, 60, COLORS['gray'])
            self.display.text("Press R to rescan", 55, 80, COLORS['yellow'])
            return
        
        # Network list
        y = 22
        row_height = 20
        
        for i in range(self.visible_rows):
            idx = self.scroll_offset + i
            if idx >= len(self.networks):
                break
            
            net = self.networks[idx]
            is_selected = (idx == self.selected_idx)
            
            # Selection highlight
            if is_selected:
                self.display.fill_rect(0, y, DISPLAY_WIDTH, row_height, COLORS['dark_gray'])
            
            # SSID (truncate if needed)
            ssid = net['ssid'][:18]
            ssid_color = COLORS['white'] if is_selected else COLORS['gray']
            self.display.text(ssid, 5, y + 3, ssid_color)
            
            # Signal bars
            bars = self.rssi_to_bars(net['rssi'])
            bar_x = 160
            for b in range(4):
                bar_height = 4 + b * 3
                bar_y = y + row_height - bar_height - 2
                color = COLORS['green'] if b < bars else COLORS['dark_gray']
                self.display.fill_rect(bar_x + b * 6, bar_y, 4, bar_height, color)
            
            # Security indicator
            sec_color = SECURITY_COLORS.get(net['security'], COLORS['gray'])
            self.display.fill_rect(190, y + 5, 8, 8, sec_color)
            
            # Channel
            self.display.text(f"Ch{net['channel']}", 205, y + 3, COLORS['gray'])
            
            y += row_height
        
        # Scrollbar
        if len(self.networks) > self.visible_rows:
            sb_height = int((self.visible_rows / len(self.networks)) * 100)
            sb_y = 22 + int((self.scroll_offset / len(self.networks)) * 100)
            self.display.fill_rect(DISPLAY_WIDTH - 3, sb_y, 2, sb_height, COLORS['cyan'])
        
        # Footer
        self.display.text("↑↓:Nav  Enter:Details  R:Scan", 5, 120, COLORS['dark_gray'])
    
    def draw_detail_view(self):
        """Draw detailed network info"""
        if not self.networks:
            return
        
        net = self.networks[self.selected_idx]
        
        self.display.fill(COLORS['black'])
        
        # Header with SSID
        self.display.fill_rect(0, 0, DISPLAY_WIDTH, 22, COLORS['blue'])
        ssid = net['ssid'][:20]
        self.display.text(ssid, 5, 4, COLORS['white'])
        
        # Details
        y = 28
        line_height = 16
        
        def draw_row(label, value, val_color=COLORS['white']):
            nonlocal y
            self.display.text(label, 5, y, COLORS['gray'])
            self.display.text(str(value), 80, y, val_color)
            y += line_height
        
        # Signal strength with visual bar
        draw_row("Signal:", f"{net['rssi']} dBm", 
                COLORS['green'] if net['rssi'] > -60 else COLORS['yellow'])
        
        # Security
        sec_name = SECURITY_ICONS.get(net['security'], '?')
        sec_color = SECURITY_COLORS.get(net['security'], COLORS['gray'])
        draw_row("Security:", sec_name, sec_color)
        
        # Channel
        draw_row("Channel:", net['channel'])
        
        # BSSID
        draw_row("BSSID:", net['bssid'][:17], COLORS['cyan'])
        
        # Hidden
        draw_row("Hidden:", "Yes" if net['hidden'] else "No",
                COLORS['yellow'] if net['hidden'] else COLORS['gray'])
        
        # Footer
        self.display.text("ESC: Back to list", 60, 120, COLORS['yellow'])
    
    def handle_input(self, key):
        """Handle keyboard input"""
        if key is None:
            return True
        
        key = key.lower()
        
        if self.detail_mode:
            # Detail view controls
            if key == '\x1b' or key == 'q':  # ESC or Q
                self.detail_mode = False
            return True
        
        # List view controls
        if key == 'w' or key == '\x1b[A':  # Up
            if self.selected_idx > 0:
                self.selected_idx -= 1
                if self.selected_idx < self.scroll_offset:
                    self.scroll_offset = self.selected_idx
                    
        elif key == 's' or key == '\x1b[B':  # Down
            if self.selected_idx < len(self.networks) - 1:
                self.selected_idx += 1
                if self.selected_idx >= self.scroll_offset + self.visible_rows:
                    self.scroll_offset = self.selected_idx - self.visible_rows + 1
                    
        elif key == '\r' or key == '\n' or key == 'e':  # Enter/E
            if self.networks:
                self.detail_mode = True
                
        elif key == 'r':  # Rescan
            self.scan_networks()
            
        elif key == 'q':  # Quit
            return False
        
        return True
    
    def run(self):
        """Main loop"""
        print("📡 WiFi Scanner running!")
        
        # Wait for initial keypress
        while self.read_key() is None:
            time.sleep_ms(50)
        
        # Initial scan
        self.scan_networks()
        
        running = True
        while running:
            # Handle input
            key = self.read_key()
            running = self.handle_input(key)
            
            # Draw appropriate view
            if self.detail_mode:
                self.draw_detail_view()
            else:
                self.draw_network_list()
            
            # Auto-rescan every 30 seconds
            if time.time() - self.last_scan_time > 30:
                self.scan_networks()
            
            time.sleep_ms(50)
        
        print("Scanner stopped.")


# Entry point
if __name__ == "__main__":
    scanner = WiFiScanner()
    if scanner.init():
        scanner.run()
