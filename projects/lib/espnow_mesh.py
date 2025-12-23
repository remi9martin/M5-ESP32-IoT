# ESP-NOW Mesh Communication Library
# For M5Stack device-to-device communication

import network
import espnow
import ubinascii
import json
import time

# Message types for the mesh network
MSG_TYPES = {
    'PING': 0x01,
    'PONG': 0x02,
    'STATUS': 0x10,
    'COMMAND': 0x20,
    'POSITION': 0x30,
    'THERMAL': 0x40,
    'ALERT': 0x50,
}

# Device type identifiers
DEVICE_TYPES = {
    'CARDPUTER': 0x01,
    'CORE2': 0x02,
    'BALA2': 0x03,
    'BUGC2': 0x04,
    'BALA_C': 0x05,
    'ATOMS3': 0x06,
    'TLITE': 0x07,
    'JOYSTICK': 0x08,
    'FLY': 0x09,
}

class ESPNowMesh:
    """ESP-NOW mesh network manager for M5Stack devices"""
    
    BROADCAST_MAC = b'\xff\xff\xff\xff\xff\xff'
    
    def __init__(self, device_type, device_name="M5Device"):
        self.device_type = device_type
        self.device_name = device_name
        self.peers = {}  # MAC -> {name, type, last_seen, rssi}
        self.callbacks = {}
        self.esp = None
        self.sta = None
        self.mac = None
        
    def init(self):
        """Initialize ESP-NOW"""
        # Activate WiFi station interface
        self.sta = network.WLAN(network.STA_IF)
        self.sta.active(True)
        
        # Get our MAC address
        self.mac = self.sta.config('mac')
        
        # Initialize ESP-NOW
        self.esp = espnow.ESPNow()
        self.esp.active(True)
        
        # Add broadcast peer for discovery
        try:
            self.esp.add_peer(self.BROADCAST_MAC)
        except:
            pass  # Already added
            
        print(f"ESP-NOW initialized: {self.mac_to_str(self.mac)}")
        return True
    
    def mac_to_str(self, mac):
        """Convert MAC bytes to readable string"""
        return ubinascii.hexlify(mac, ':').decode()
    
    def add_peer(self, mac):
        """Add a peer device"""
        try:
            self.esp.add_peer(mac)
            return True
        except Exception as e:
            print(f"Failed to add peer: {e}")
            return False
    
    def send(self, mac, msg_type, data):
        """Send a message to a specific peer"""
        packet = self._encode_packet(msg_type, data)
        try:
            self.esp.send(mac, packet)
            return True
        except Exception as e:
            print(f"Send failed: {e}")
            return False
    
    def broadcast(self, msg_type, data):
        """Broadcast message to all devices"""
        return self.send(self.BROADCAST_MAC, msg_type, data)
    
    def _encode_packet(self, msg_type, data):
        """Encode a packet for transmission"""
        packet = {
            't': msg_type,
            'd': data,
            's': self.device_type,
            'n': self.device_name[:10],  # Truncate name
        }
        return json.dumps(packet).encode()
    
    def _decode_packet(self, raw):
        """Decode a received packet"""
        try:
            packet = json.loads(raw.decode())
            return {
                'msg_type': packet.get('t'),
                'data': packet.get('d'),
                'device_type': packet.get('s'),
                'device_name': packet.get('n'),
            }
        except:
            return None
    
    def on_message(self, msg_type, callback):
        """Register callback for message type"""
        self.callbacks[msg_type] = callback
    
    def poll(self):
        """Check for incoming messages (non-blocking)"""
        if self.esp.any():
            mac, raw = self.esp.recv(0)  # Non-blocking
            if mac and raw:
                return self._handle_message(mac, raw)
        return None
    
    def recv(self, timeout_ms=1000):
        """Wait for a message with timeout"""
        mac, raw = self.esp.recv(timeout_ms)
        if mac and raw:
            return self._handle_message(mac, raw)
        return None
    
    def _handle_message(self, mac, raw):
        """Process received message"""
        packet = self._decode_packet(raw)
        if not packet:
            return None
        
        # Update peer registry
        mac_str = self.mac_to_str(mac)
        self.peers[mac_str] = {
            'name': packet['device_name'],
            'type': packet['device_type'],
            'last_seen': time.time(),
        }
        
        # Handle ping/pong automatically
        msg_type = packet['msg_type']
        if msg_type == MSG_TYPES['PING']:
            self.send(mac, MSG_TYPES['PONG'], {'uptime': time.ticks_ms()})
        
        # Call registered callback
        if msg_type in self.callbacks:
            self.callbacks[msg_type](mac, packet)
        
        return packet
    
    def discover(self, duration_ms=2000):
        """Discover nearby devices via broadcast ping"""
        self.broadcast(MSG_TYPES['PING'], {'discover': True})
        
        start = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), start) < duration_ms:
            self.poll()
            time.sleep_ms(10)
        
        return list(self.peers.values())
    
    def send_status(self, status_data):
        """Broadcast device status"""
        self.broadcast(MSG_TYPES['STATUS'], status_data)
    
    def send_position(self, x, y, heading=0):
        """Broadcast position update (for robots)"""
        self.broadcast(MSG_TYPES['POSITION'], {
            'x': x, 
            'y': y, 
            'h': heading
        })
    
    def send_thermal(self, hotspot_x, hotspot_y, max_temp):
        """Broadcast thermal detection (for T-Lite)"""
        self.broadcast(MSG_TYPES['THERMAL'], {
            'hx': hotspot_x,
            'hy': hotspot_y,
            'max': max_temp
        })
    
    def send_alert(self, alert_type, message):
        """Broadcast alert message"""
        self.broadcast(MSG_TYPES['ALERT'], {
            'type': alert_type,
            'msg': message
        })
    
    def send_command(self, target_mac, command, params=None):
        """Send command to specific device"""
        self.send(target_mac, MSG_TYPES['COMMAND'], {
            'cmd': command,
            'params': params or {}
        })
    
    def get_peers(self):
        """Get list of known peers"""
        return self.peers
    
    def cleanup(self):
        """Cleanup resources"""
        if self.esp:
            self.esp.active(False)
        if self.sta:
            self.sta.active(False)
