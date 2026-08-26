#!/usr/bin/env python3
"""
AI-PBMS Crash Simulator
-----------------------
This script runs on the Raspberry Pi and allows you to safely simulate 
different crash scenarios to see how the automatic watchdog recovery system reacts.
"""

import os
import sys
import time
import subprocess

def run_cmd(cmd):
    try:
        subprocess.run(cmd, shell=True, check=True)
    except Exception as e:
        print(f"Error running command: {e}")

def print_header():
    print("======================================================================")
    print("                  AI-PBMS WATCHDOG CRASH SIMULATOR                   ")
    print("======================================================================")

def simulate_flask_crash():
    print_header()
    print("[SIMULATION] Simulating Flask Backend Crash...")
    print("Steps:")
    print("1. Stopping bms-backend.service...")
    run_cmd("sudo systemctl stop bms-backend.service")
    
    print("\n[WHAT TO WATCH FOR]:")
    print("- On the Pi: The watchdog script (watchdog.py) will fail to query Flask.")
    print("  After 10 seconds, watchdog.log will show:")
    print("  'CRITICAL: Flask backend is dead. Sending PI_OFFLINE.'")
    print("- On the Arduino: The LED Matrix will immediately FLATLINE.")
    print("  Arduino will pulse Pin 7 LOW for 200ms to HARD REBOOT the Raspberry Pi.")
    
    print("\nPress Enter to return to the menu...")
    input()

def simulate_pi_freeze():
    print_header()
    print("[SIMULATION] Simulating Complete Pi Freeze/Hang...")
    print("Steps:")
    print("1. Stopping bms-watchdog.service (stops all serial heartbeats)...")
    run_cmd("sudo systemctl stop bms-watchdog.service")
    
    print("\n[WHAT TO WATCH FOR]:")
    print("- On the Pi: The heartbeat signals to the Arduino stop immediately.")
    print("- On the Arduino: The 10-second heartbeat timeout timer is running.")
    print("  After exactly 10 seconds, the Arduino debug console will output:")
    print("  'PI_CRASH_DETECTED_TRIGGERING_RESET'")
    print("  The Arduino LED Matrix will FLATLINE, and Pin 7 will pulse LOW to reboot the Pi.")
    
    print("\nPress Enter to return to the menu...")
    input()

def simulate_gateway_crash():
    print_header()
    print("[SIMULATION] Simulating Bluetooth Gateway Process Crash...")
    print("Steps:")
    print("1. Killing bms_bluetooth_gateway.py process...")
    run_cmd("sudo pkill -f bms_bluetooth_gateway.py")
    
    print("\n[WHAT TO WATCH FOR]:")
    print("- On the Pi: The watchdog script (watchdog.py) detects the missing PID.")
    print("  It will immediately log: 'CRASH DETECTED: bms_bluetooth_gateway.py is not running.'")
    print("  It will issue: 'sudo systemctl restart bms-bluetooth.service'")
    print("- The Bluetooth Gateway should restart and log new readings automatically.")
    print("- On the Arduino: The display stays in STATE_RUN (scrolling ECG) because")
    print("  the watchdog self-healed the process without needing a hard system reset!")
    
    print("\nPress Enter to return to the menu...")
    input()

def main():
    while True:
        os.system('clear' if os.name == 'posix' else 'cls')
        print_header()
        print("Please choose a crash scenario to simulate:")
        print("1) Flask Backend Crash (Triggers hard reboot via PI_OFFLINE)")
        print("2) Complete Pi Freeze / Watchdog Stop (Triggers hard reboot via 10s timeout)")
        print("3) Bluetooth Gateway Crash (Triggers automatic service restart / self-healing)")
        print("4) Exit Simulator")
        print("======================================================================")
        
        choice = input("Enter choice (1-4): ").strip()
        
        if choice == '1':
            simulate_flask_crash()
        elif choice == '2':
            simulate_pi_freeze()
        elif choice == '3':
            simulate_gateway_crash()
        elif choice == '4':
            print("Exiting simulator. Have a nice day!")
            break
        else:
            print("Invalid choice. Press Enter to retry...")
            input()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nExiting simulator.")
