# Core2 Fleet Dashboard
# Touch-screen robot status monitor via ESP-NOW mesh
# Device: M5Stack Core2 AWS Kit

import time
import machine
import ili9341

try:
    from lib.display_utils import COLORS, draw_battery_icon, draw_status_dot, draw_header
    from lib.espnow_mesh import ESPNowMesh, MSG_TYPES, DEVICE_TYPES
except:
    import sys
    sys.path.append('/projects/lib')
    from display_utils import COLORS, draw_battery_icon, draw_status_dot, draw_header
    from espnow_mesh import ESPNowMesh, MSG_TYPES, DEVICE_TYPES

# Display configuration (Core2: 2.0" IPS 320x240)
DISPLAY_WIDTH = 320
DISPLAY_HEIGHT = 240

# Device type names
DEVICE_NAMES = {
    DEVICE_TYPES['CARDPUTER']: 'Cardputer',
    DEVICE_TYPES['CORE2']: 'Core2',
    DEVICE_TYPES['BALA2']: 'BALA2',
    DEVICE_TYPES['BUGC2']: 'BugC2',
    DEVICE_TYPES['BALA_C']: 'BALA-C',
    DEVICE_TYPES['ATOMS3']: 'AtomS3',
    DEVICE_TYPES['TLITE']: 'T-Lite',
    DEVICE_TYPES['JOYSTICK']: 'Joystick',
    DEVICE_TYPES['FLY']: 'Fly',
}

# Device icons
DEVICE_ICONS = {
    DEVICE_TYPES['CARDPUTER']: '🖥️',
    DEVICE_TYPES['CORE2']: '📱',
    DEVICE_TYPES['BALA2']: '🤖',
    DEVICE_TYPES['BUGC2']: '🐛',
    DEVICE_TYPES['BALA_C']: '⚖️',
    DEVICE_TYPES['ATOMS3']: '👁️',
    DEVICE_TYPES['TLITE']: '🌡️',
    DEVICE_TYPES['JOYSTICK']: '🎮',
    DEVICE_TYPES['FLY']: '🚁',
}

class RobotCard:
    """Status card for a single robot/device"""
    
    def __init__(self, mac, name, device_type):
        self.mac = mac
        self.name = name
        self.device_type = device_type
        self.battery = 100
        self.status = 'offline'
        self.last_seen = 0
        self.rssi = 0
        self.position = (0, 0)
        self.temp = 0  # For thermal devices
        self.alerts = []
        
    def update(self, data):
        """Update from status message"""
        self.battery = data.get('bat', self.battery)
        self.status = 'online'
        self.last_seen = time.time()
        self.rssi = data.get('rssi', 0)
        self.position = (data.get('x', 0), data.get('y', 0))
        self.temp = data.get('temp', 0)
        
    def is_stale(self):
        """Check if device hasn't reported recently"""
        return time.time() - self.last_seen > 10
    
    def time_since_seen(self):
        """Get human-readable time since last seen"""
        if self.last_seen == 0:
            return "Never"
        delta = int(time.time() - self.last_seen)
        if delta < 60:
            return f"{delta}s ago"
        return f"{delta // 60}m ago"


class FleetDashboard:
    def __init__(self):
        self.display = None
        self.touch = None
        self.mesh = None
        self.robots = {}  # mac -> RobotCard
        self.alerts = []
        self.selected_robot = None
        self.view_mode = 'grid'  # 'grid' or 'detail'
        
    def init(self):
        """Initialize Core2 hardware"""
        # SPI Display (ILI9341)
        spi = machine.SPI(2, baudrate=40000000, sck=machine.Pin(18), 
                         mosi=machine.Pin(23), miso=machine.Pin(19))
        self.display = ili9341.ILI9341(
            spi, 
            cs=machine.Pin(5),
            dc=machine.Pin(15),
            rst=machine.Pin(33),
            rotation=1,
            width=DISPLAY_WIDTH,
            height=DISPLAY_HEIGHT
        )
        self.display.fill(COLORS['black'])
        
        # Touch controller (FT6336U via I2C)
        try:
            self.touch_i2c = machine.I2C(1, scl=machine.Pin(22), sda=machine.Pin(21), freq=400000)
            self.touch = True
        except:
            self.touch = None
        
        # ESP-NOW mesh
        self.mesh = ESPNowMesh(DEVICE_TYPES['CORE2'], "FleetHQ")
        self.mesh.init()
        
        # Register message handlers
        self.mesh.on_message(MSG_TYPES['STATUS'], self.on_status)
        self.mesh.on_message(MSG_TYPES['ALERT'], self.on_alert)
        self.mesh.on_message(MSG_TYPES['POSITION'], self.on_position)
        self.mesh.on_message(MSG_TYPES['THERMAL'], self.on_thermal)
        self.mesh.on_message(MSG_TYPES['PONG'], self.on_pong)
        
        print("🎛️ Fleet Dashboard initialized!")
        self.draw_splash()
        return True
    
    def on_status(self, mac, packet):
        """Handle status updates"""
        mac_str = self.mesh.mac_to_str(mac)
        
        if mac_str not in self.robots:
            self.robots[mac_str] = RobotCard(
                mac_str, 
                packet['device_name'],
                packet['device_type']
            )
        
        self.robots[mac_str].update(packet['data'])
    
    def on_alert(self, mac, packet):
        """Handle alert messages"""
        alert = {
            'time': time.time(),
            'from': packet['device_name'],
            'type': packet['data'].get('type', 'unknown'),
            'msg': packet['data'].get('msg', '')
        }
        self.alerts.insert(0, alert)
        self.alerts = self.alerts[:10]  # Keep last 10
        
        # Flash screen for alerts
        self.flash_alert()
    
    def on_position(self, mac, packet):
        """Handle position updates"""
        mac_str = self.mesh.mac_to_str(mac)
        if mac_str in self.robots:
            data = packet['data']
            self.robots[mac_str].position = (data.get('x', 0), data.get('y', 0))
            self.robots[mac_str].last_seen = time.time()
            self.robots[mac_str].status = 'online'
    
    def on_thermal(self, mac, packet):
        """Handle thermal data"""
        mac_str = self.mesh.mac_to_str(mac)
        if mac_str in self.robots:
            self.robots[mac_str].temp = packet['data'].get('max', 0)
            self.robots[mac_str].last_seen = time.time()
    
    def on_pong(self, mac, packet):
        """Handle ping responses"""
        mac_str = self.mesh.mac_to_str(mac)
        if mac_str not in self.robots:
            self.robots[mac_str] = RobotCard(
                mac_str,
                packet['device_name'],
                packet['device_type']
            )
        self.robots[mac_str].status = 'online'
        self.robots[mac_str].last_seen = time.time()
    
    def read_touch(self):
        """Read touch input"""
        if not self.touch:
            return None
        
        try:
            data = self.touch_i2c.readfrom(0x38, 7)
            touches = data[2] & 0x0F
            if touches > 0:
                x = ((data[3] & 0x0F) << 8) | data[4]
                y = ((data[5] & 0x0F) << 8) | data[6]
                return (x, y)
        except:
            pass
        return None
    
    def flash_alert(self):
        """Flash screen for alert"""
        for _ in range(2):
            self.display.fill(COLORS['red'])
            time.sleep_ms(100)
            self.display.fill(COLORS['black'])
            time.sleep_ms(100)
    
    def draw_splash(self):
        """Show startup splash"""
        self.display.fill(COLORS['black'])
        self.display.fill_rect(0, 0, DISPLAY_WIDTH, 40, COLORS['blue'])
        self.display.text("FLEET DASHBOARD", 80, 12, COLORS['white'], 2)
        
        self.display.text("Scanning for devices...", 80, 100, COLORS['cyan'])
        
        # Discover devices
        self.mesh.discover(3000)
        
    def draw_header(self):
        """Draw header bar"""
        self.display.fill_rect(0, 0, DISPLAY_WIDTH, 30, COLORS['blue'])
        self.display.text("FLEET DASHBOARD", 10, 8, COLORS['white'])
        
        # Device count
        online = sum(1 for r in self.robots.values() if r.status == 'online')
        total = len(self.robots)
        self.display.text(f"Online: {online}/{total}", 200, 8, COLORS['green'])
        
        # Time
        t = time.localtime()
        time_str = f"{t[3]:02d}:{t[4]:02d}"
        self.display.text(time_str, 275, 8, COLORS['gray'])
    
    def draw_robot_card(self, robot, x, y, width, height, selected=False):
        """Draw a single robot status card"""
        # Card background
        bg_color = COLORS['dark_gray'] if selected else 0x1082
        self.display.fill_rect(x, y, width, height, bg_color)
        
        # Border
        border_color = COLORS['cyan'] if selected else COLORS['gray']
        self.display.rect(x, y, width, height, border_color)
        
        # Status indicator
        status_colors = {
            'online': COLORS['green'],
            'offline': COLORS['red'],
            'idle': COLORS['yellow'],
        }
        status_color = status_colors.get(robot.status, COLORS['gray'])
        self.display.fill_circle(x + 10, y + 15, 5, status_color)
        
        # Device name and type
        name = robot.name[:10]
        type_name = DEVICE_NAMES.get(robot.device_type, 'Unknown')[:8]
        self.display.text(name, x + 20, y + 8, COLORS['white'])
        self.display.text(type_name, x + 20, y + 22, COLORS['gray'])
        
        # Battery
        self.draw_battery(x + width - 30, y + 8, robot.battery)
        
        # Last seen
        seen = robot.time_since_seen()
        self.display.text(seen, x + 5, y + height - 15, COLORS['gray'])
        
        # Special data (temp for thermal)
        if robot.device_type == DEVICE_TYPES['TLITE'] and robot.temp > 0:
            self.display.text(f"{robot.temp:.1f}C", x + width - 45, y + height - 15, COLORS['orange'])
    
    def draw_battery(self, x, y, percent):
        """Draw mini battery indicator"""
        # Body
        self.display.rect(x, y, 20, 10, COLORS['white'])
        self.display.fill_rect(x + 20, y + 3, 2, 4, COLORS['white'])
        
        # Fill
        if percent > 60:
            color = COLORS['green']
        elif percent > 20:
            color = COLORS['yellow']
        else:
            color = COLORS['red']
        
        fill = int((percent / 100) * 16)
        if fill > 0:
            self.display.fill_rect(x + 2, y + 2, fill, 6, color)
    
    def draw_grid_view(self):
        """Draw grid layout of all robots"""
        self.draw_header()
        
        # Grid layout: 2 columns, 3 rows
        card_width = 150
        card_height = 60
        margin = 8
        start_y = 38
        
        robots = list(self.robots.values())
        
        for i, robot in enumerate(robots[:6]):  # Max 6 visible
            col = i % 2
            row = i // 2
            
            x = margin + col * (card_width + margin)
            y = start_y + row * (card_height + margin)
            
            selected = (robot.mac == self.selected_robot)
            self.draw_robot_card(robot, x, y, card_width, card_height, selected)
        
        if not robots:
            self.display.text("No devices found", 100, 120, COLORS['gray'])
            self.display.text("Tap to scan", 115, 140, COLORS['yellow'])
        
        # Footer with controls
        self.display.fill_rect(0, 220, DISPLAY_WIDTH, 20, COLORS['dark_gray'])
        self.display.text("Tap card for details | Tap scan to refresh", 20, 224, COLORS['gray'])
    
    def draw_detail_view(self):
        """Draw detailed view of selected robot"""
        if not self.selected_robot or self.selected_robot not in self.robots:
            self.view_mode = 'grid'
            return
        
        robot = self.robots[self.selected_robot]
        
        self.display.fill(COLORS['black'])
        
        # Header
        self.display.fill_rect(0, 0, DISPLAY_WIDTH, 35, COLORS['blue'])
        icon = DEVICE_ICONS.get(robot.device_type, '📦')
        self.display.text(f"{icon} {robot.name}", 10, 10, COLORS['white'], 2)
        
        # Back button
        self.display.fill_rect(270, 5, 45, 25, COLORS['dark_gray'])
        self.display.text("Back", 280, 10, COLORS['white'])
        
        # Status section
        y = 45
        
        def info_row(label, value, color=COLORS['white']):
            nonlocal y
            self.display.text(label, 20, y, COLORS['gray'])
            self.display.text(str(value), 120, y, color)
            y += 25
        
        # Status
        status_color = COLORS['green'] if robot.status == 'online' else COLORS['red']
        info_row("Status:", robot.status.upper(), status_color)
        
        # Battery
        bat_color = COLORS['green'] if robot.battery > 50 else COLORS['yellow']
        if robot.battery < 20:
            bat_color = COLORS['red']
        info_row("Battery:", f"{robot.battery}%", bat_color)
        
        # Last seen
        info_row("Last Seen:", robot.time_since_seen())
        
        # MAC address
        info_row("MAC:", robot.mac[:17], COLORS['cyan'])
        
        # Device-specific info
        if robot.device_type == DEVICE_TYPES['TLITE'] and robot.temp > 0:
            info_row("Temp:", f"{robot.temp:.1f}°C", COLORS['orange'])
        
        if robot.position != (0, 0):
            info_row("Position:", f"({robot.position[0]}, {robot.position[1]})")
        
        # Command buttons
        btn_y = 200
        self.display.fill_rect(20, btn_y, 80, 30, COLORS['green'])
        self.display.text("Ping", 45, btn_y + 8, COLORS['white'])
        
        self.display.fill_rect(120, btn_y, 80, 30, COLORS['yellow'])
        self.display.text("Stop", 145, btn_y + 8, COLORS['black'])
        
        self.display.fill_rect(220, btn_y, 80, 30, COLORS['red'])
        self.display.text("Alert", 243, btn_y + 8, COLORS['white'])
    
    def handle_touch(self, pos):
        """Handle touch input"""
        if pos is None:
            return
        
        x, y = pos
        
        if self.view_mode == 'grid':
            # Check if touched a robot card
            card_width = 150
            card_height = 60
            margin = 8
            start_y = 38
            
            robots = list(self.robots.values())
            
            for i, robot in enumerate(robots[:6]):
                col = i % 2
                row = i // 2
                
                cx = margin + col * (card_width + margin)
                cy = start_y + row * (card_height + margin)
                
                if cx <= x <= cx + card_width and cy <= y <= cy + card_height:
                    self.selected_robot = robot.mac
                    self.view_mode = 'detail'
                    return
            
            # Check scan button area
            if y > 220:
                self.mesh.discover(2000)
                
        elif self.view_mode == 'detail':
            # Back button
            if 270 <= x <= 315 and 5 <= y <= 30:
                self.view_mode = 'grid'
                return
            
            # Command buttons
            if 200 <= y <= 230:
                if 20 <= x <= 100:  # Ping
                    self.mesh.broadcast(MSG_TYPES['PING'], {})
                elif 120 <= x <= 200:  # Stop
                    if self.selected_robot:
                        # Send stop command
                        pass
                elif 220 <= x <= 300:  # Alert
                    self.mesh.send_alert("test", "Emergency stop!")
    
    def update_device_status(self):
        """Update device online/offline status"""
        for robot in self.robots.values():
            if robot.is_stale():
                robot.status = 'offline'
    
    def run(self):
        """Main loop"""
        print("🎛️ Fleet Dashboard running!")
        
        last_ping = time.time()
        
        try:
            while True:
                # Poll mesh for messages
                self.mesh.poll()
                
                # Handle touch
                touch = self.read_touch()
                if touch:
                    self.handle_touch(touch)
                    time.sleep_ms(200)  # Debounce
                
                # Update status
                self.update_device_status()
                
                # Refresh display
                if self.view_mode == 'grid':
                    self.draw_grid_view()
                else:
                    self.draw_detail_view()
                
                # Periodic ping
                if time.time() - last_ping > 5:
                    self.mesh.broadcast(MSG_TYPES['PING'], {})
                    last_ping = time.time()
                
                time.sleep_ms(50)
                
        except KeyboardInterrupt:
            pass
        finally:
            self.mesh.cleanup()
            print("Dashboard stopped.")


# Entry point
if __name__ == "__main__":
    dashboard = FleetDashboard()
    if dashboard.init():
        dashboard.run()
