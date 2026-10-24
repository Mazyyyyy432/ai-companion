"""扫描附近的 BLE 设备，用来确认电脑能不能看见玩具。

用法：  .venv\\Scripts\\python.exe scripts\\scan_ble.py
"""
import asyncio
import sys

from bleak import BleakScanner


async def main(seconds: float = 12.0) -> int:
    print(f"扫描 {seconds:g} 秒（玩具要开机，手机上官方 App 要先断开）…")
    devices = await BleakScanner.discover(timeout=seconds)
    if not devices:
        print("\n一个设备都没扫到。")
        print("可能原因：蓝牙适配器不支持 BLE / 玩具没开机 / 被手机占用。")
        return 1

    print(f"\n共 {len(devices)} 个设备：")
    found = False
    for d in sorted(devices, key=lambda x: -(x.rssi or -999)):
        name = d.name or "(无名称)"
        mark = ""
        if name.upper().startswith("SOSEXY"):
            mark = "   <-- 玩具"
            found = True
        print(f"  {d.rssi:>4} dBm  {name:<28} {d.address}{mark}")

    if found:
        print("\n找到玩具了，可以直接用。")
        return 0
    print("\n没看到名字以 SOSEXY 开头的设备。")
    return 2


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        sys.exit(130)
