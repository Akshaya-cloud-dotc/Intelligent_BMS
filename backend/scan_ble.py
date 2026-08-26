import asyncio
from bleak import BleakScanner

async def main():
    print("Starting BLE scan for 10 seconds...")
    devices = await BleakScanner.discover(timeout=10.0)
    print(f"Found {len(devices)} devices:")
    for d in devices:
        print(f"Address: {d.address} | Name: {d.name}")

if __name__ == "__main__":
    asyncio.run(main())
