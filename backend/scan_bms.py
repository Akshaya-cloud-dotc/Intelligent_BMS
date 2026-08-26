import asyncio
from bleak import BleakScanner

async def main():
    print("Scanning for Bluetooth LE devices for 10 seconds...")
    devices = await BleakScanner.discover(timeout=10.0)
    print(f"\nFound {len(devices)} device(s):")
    print("-" * 50)
    for d in devices:
        name = d.name if d.name else "Unknown Name"
        print(f"Name: {name}")
        print(f"Address/MAC: {d.address}")
        print(f"Details: {d.details}")
        print("-" * 50)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print("Error running scanner. Make sure your PC's Bluetooth is turned ON!")
        print(e)
