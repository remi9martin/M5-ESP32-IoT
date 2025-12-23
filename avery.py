"""
AVERY - M5Stack Arsenal Assistant
==================================
CLI tool to manage, generate, and flash your M5Stack arsenal.

Usage:
  python avery.py list
  python avery.py detect
  python avery.py generate <project-name>
  python avery.py flash <project-name> <port>
"""

import os
import sys
import shutil
import argparse
import time
from pathlib import Path

# Project registry
PROJECTS_DIR = Path("projects")
PROJECTS = {
    # Cardputer
    "wifi-scanner": PROJECTS_DIR / "cardputer/wifi_scanner.py",
    "probe-sniffer": PROJECTS_DIR / "cardputer/probe_sniffer.py",
    
    # T-Lite
    "cat-tracker": PROJECTS_DIR / "thermal/cat_tracker.py",
    "intruder-alert": PROJECTS_DIR / "thermal/intruder_alert.py",
    
    # BugC2
    "cat-chaos": PROJECTS_DIR / "bugc2/cat_chaos_toy.py",
    "bugc-rc": PROJECTS_DIR / "bugc2/joystick_rc.py",
    "roach": PROJECTS_DIR / "bugc2/roach_simulator.py",
    
    # AtomS3
    "ble-tracker": PROJECTS_DIR / "atoms3/ble_tracker.py",
    "deauth-detector": PROJECTS_DIR / "atoms3/deauth_detector.py",
    
    # BALA
    "dance-bot": PROJECTS_DIR / "bala/dance_bot.py",
    "guard-dog": PROJECTS_DIR / "bala/guard_dog.py",
    
    # Joystick
    "multi-robot": PROJECTS_DIR / "joystick/multi_robot.py",
    
    # Fly
    "gesture-launch": PROJECTS_DIR / "fly/gesture_launch.py",
    
    # Core2
    "fleet-dash": PROJECTS_DIR / "core2/fleet_dashboard.py",
    
    # Combined
    "thermal-hunter": PROJECTS_DIR / "combined/thermal_hunter.py",
    "cat-entertainment": PROJECTS_DIR / "combined/cat_entertainment.py",
    
    # Utils
    "get-mac": PROJECTS_DIR / "utils/get_mac.py",
}

def list_projects():
    print(f"\n{'PROJECT':<20} {'PATH':<40} {'CATEGORY'}")
    print("-" * 75)
    for name, path in sorted(PROJECTS.items()):
        category = str(path).split(os.sep)[1].upper()
        print(f"{name:<20} {str(path):<40} {category}")
    print("-" * 75)
    print(f"Total: {len(PROJECTS)} projects")

def detect_devices():
    print("Scanning for M5Stack devices...")
    try:
        import serial.tools.list_ports
        ports = list(serial.tools.list_ports.comports())
        
        found = []
        for p in ports:
            # Simple heuristic for ESP32 devices
            if "CP210" in p.description or "CH340" in p.description or "USB Serial" in p.description:
                found.append(p)
        
        if not found:
            print("No devices found.")
            return
            
        print(f"\n{'PORT':<10} {'DESCRIPTION'}")
        print("-" * 40)
        for p in found:
            print(f"{p.device:<10} {p.description}")
            
    except ImportError:
        print("Error: 'pyserial' not installed. Run: pip install pyserial")

def generate_project(name, output_dir=None):
    if name not in PROJECTS:
        print(f"Error: Project '{name}' not found.")
        return
    
    src = PROJECTS[name]
    if not src.exists():
        print(f"Error: Source file {src} is missing!")
        return
        
    content = src.read_text(encoding='utf-8')
    
    if output_dir:
        out_path = Path(output_dir) / "main.py"
        out_path.write_text(content, encoding='utf-8')
        print(f"✅ Generated {name} -> {out_path}")
    else:
        print(f"\n--- CODE FOR {name.upper()} ---")
        print(content)
        print("-------------------------------")

def flash_project(name, port):
    if name not in PROJECTS:
        print(f"Error: Project '{name}' not found.")
        return
        
    src = PROJECTS[name]
    if not src.exists():
        print(f"Error: Source file {src} is missing!")
        return
    
    print(f"Flashing {name} to {port}...")
    
    # Use ampy to put file
    cmd = f"ampy --port {port} put {src} main.py"
    print(f"Running: {cmd}")
    
    ret = os.system(cmd)
    
    if ret == 0:
        print("✅ Flash complete! Reset device to run.")
    else:
        print("❌ Flash failed. Is ampy installed? (pip install adafruit-ampy)")

def main():
    parser = argparse.ArgumentParser(description="Avery - M5Stack Arsenal Assistant")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # List
    subparsers.add_parser("list", help="List available projects")
    
    # Detect
    subparsers.add_parser("detect", help="Detect connected devices")
    
    # Generate
    gen_parser = subparsers.add_parser("generate", help="Generate project code")
    gen_parser.add_argument("project", help="Project name")
    gen_parser.add_argument("--out", help="Output directory", default=None)
    
    # Flash
    flash_parser = subparsers.add_parser("flash", help="Flash to device")
    flash_parser.add_argument("project", help="Project name")
    flash_parser.add_argument("port", help="COM port (e.g., COM3)")
    
    args = parser.parse_args()
    
    if args.command == "list":
        list_projects()
    elif args.command == "detect":
        detect_devices()
    elif args.command == "generate":
        generate_project(args.project, args.out)
    elif args.command == "flash":
        flash_project(args.project, args.port)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
