"""
Utility: Get MAC Address
=========================
Flash to any device to get its MAC address.
Needed for ESP-NOW pairing!
"""

import network

wlan = network.WLAN(network.STA_IF)
wlan.active(True)

mac = wlan.config('mac')
mac_str = ':'.join(['%02X' % b for b in mac])

print("\n" + "="*40)
print("         MAC ADDRESS")
print("="*40)
print(f"\n  {mac_str}\n")
print("="*40)
print("\nCopy this MAC to pair devices!")
print("Use bytes format in code:")
print(f"  MAC = {mac}")
