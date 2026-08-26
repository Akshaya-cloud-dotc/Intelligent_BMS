import os
import subprocess

def kill_gateway_processes():
    # Use wmic to find PIDs of python processes running bms_bluetooth_gateway.py
    try:
        cmd = 'wmic process where "name=\'python.exe\'" get processid,commandline'
        output = subprocess.check_output(cmd, shell=True).decode('utf-8', errors='ignore')
        
        killed_count = 0
        for line in output.splitlines():
            if 'bms_bluetooth_gateway.py' in line:
                parts = line.strip().split()
                if parts:
                    pid = parts[-1]
                    try:
                        print(f"Killing process PID {pid} running: {line.strip()}")
                        subprocess.call(f"taskkill /F /PID {pid}", shell=True)
                        killed_count += 1
                    except Exception as e:
                        print(f"Failed to kill PID {pid}: {e}")
                        
        print(f"Finished killing processes. Total killed: {killed_count}")
    except Exception as e:
        print(f"Error checking processes: {e}")

if __name__ == "__main__":
    kill_gateway_processes()
