import sys
import asyncio

try:
    from bleak import BleakScanner
    from bleak.exc import BleakBluetoothNotAvailableError
except ImportError:
    print("NO_BLEAK")
    sys.exit(1)

async def scan():
    try:
        # Quick 5-second discovery
        print("Scanning for Bluetooth devices...")
        devices = await BleakScanner.discover(timeout=5.0)
        
        bms_devices = []
        other_devices = []
        for d in devices:
            name = str(d.name or "").strip()
            # Common BMS names or patterns
            is_bms = any(keyword in name.lower() for keyword in ["bms", "jbd", "daly", "xiaoxiang", "ant", "smart", "battery"])
            if is_bms:
                bms_devices.append(d)
            else:
                other_devices.append(d)
                
        print("BT_OK")
        if bms_devices:
            print("\nFound BMS devices nearby:")
            for idx, d in enumerate(bms_devices):
                print(f"[{idx+1}] MAC: {d.address} | Name: {d.name}")
        else:
            print("\nNo devices explicitly matching 'BMS' name patterns found nearby.")
            
        print("\nOther BLE devices nearby:")
        for idx, d in enumerate(other_devices[:10]):
            print(f"  MAC: {d.address} | Name: {d.name or 'Unknown Device'}")
            
    except BleakBluetoothNotAvailableError:
        print("BT_OFF")
        sys.exit(2)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(3)

if __name__ == "__main__":
    asyncio.run(scan())
