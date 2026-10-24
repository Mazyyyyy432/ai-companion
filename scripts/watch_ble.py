"""持续监听 BLE 广播，边发现边打印。用来等玩具出现。

用法：  .venv\\Scripts\\python.exe scripts\\watch_ble.py [秒数]
"""
import asyncio
import sys

from bleak import BleakScanner

seen: dict[str, str] = {}


def on_detect(device, adv):
    key = device.address
    name = device.name or adv.local_name or "(无名称)"
    if seen.get(key) == name:
        return
    seen[key] = name
    mark = "  <== 玩具！" if name.upper().startswith("SOSEXY") else ""
    print(f"[{len(seen):>2}] {name:<30} {key}  rssi={adv.rssi}{mark}", flush=True)


async def main(seconds: float) -> int:
    print(f"监听 {seconds:g} 秒…", flush=True)
    async with BleakScanner(detection_callback=on_detect):
        await asyncio.sleep(seconds)

    if not seen:
        print(f"\n这 {seconds:g} 秒里没有任何 BLE 设备广播。", flush=True)
        return 1

    toys = [n for n in seen.values() if n.upper().startswith("SOSEXY")]
    print(f"\n共发现 {len(seen)} 个设备，其中玩具 {len(toys)} 个。", flush=True)
    return 0 if toys else 2


if __name__ == "__main__":
    secs = float(sys.argv[1]) if len(sys.argv) > 1 else 90
    sys.exit(asyncio.run(main(secs)))
