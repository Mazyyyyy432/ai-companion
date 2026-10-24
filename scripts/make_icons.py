"""生成 PWA 图标（不依赖 Pillow，纯标准库写 PNG）。

用法：  .venv\\Scripts\\python.exe scripts\\make_icons.py
"""
import math
import struct
import zlib
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "frontend"


def _heart(x: float, y: float) -> float:
    """心形隐函数，<0 表示在形状内。坐标范围约 -1.2..1.2"""
    a = x * x + y * y - 1
    return a * a * a - x * x * y * y * y


def render(size: int, ss: int = 2) -> bytes:
    """返回 RGBA 原始字节。ss = 超采样倍数（抗锯齿用）"""
    w = size * ss
    px = bytearray(w * w * 4)

    for j in range(w):
        fy = (j + 0.5) / w
        for i in range(w):
            fx = (i + 0.5) / w
            # 背景：从深紫到更深的竖渐变 + 顶部一点光晕
            g = fy
            r = int(26 * (1 - g) + 14 * g)
            gg = int(13 * (1 - g) + 7 * g)
            b = int(21 * (1 - g) + 12 * g)
            glow = max(0.0, 1.0 - ((fx - 0.5) ** 2 / 0.18 + fy ** 2 / 0.5))
            r = min(255, int(r + glow * 46))
            b = min(255, int(b + glow * 24))

            # 心形，居中偏上一点
            hx = (fx - 0.5) / 0.30
            hy = -(fy - 0.52) / 0.30
            d = _heart(hx, hy + 0.12)

            a = 255
            if d < 0:
                # 心内部用柔和的玫瑰色，越靠上越亮
                t = max(0.0, min(1.0, (0.35 - hy) * 1.1))
                r = int(198 + 40 * t)
                gg = int(110 + 60 * t)
                b = int(140 + 40 * t)
            elif d < 0.06:
                # 边缘做一点过渡，避免锯齿
                k = 1 - d / 0.06
                r = int(r * (1 - k) + 210 * k)
                gg = int(gg * (1 - k) + 130 * k)
                b = int(b * (1 - k) + 155 * k)

            o = (j * w + i) * 4
            px[o] = r
            px[o + 1] = gg
            px[o + 2] = b
            px[o + 3] = a

    if ss == 1:
        return bytes(px)

    # 盒式降采样
    out = bytearray(size * size * 4)
    n = ss * ss
    for y in range(size):
        for x in range(size):
            sr = sg = sb = 0
            for dy in range(ss):
                base = ((y * ss + dy) * w + x * ss) * 4
                for dx in range(ss):
                    o = base + dx * 4
                    sr += px[o]
                    sg += px[o + 1]
                    sb += px[o + 2]
            o = (y * size + x) * 4
            out[o] = sr // n
            out[o + 1] = sg // n
            out[o + 2] = sb // n
            out[o + 3] = 255
    return bytes(out)


def write_png(path: Path, size: int, rgba: bytes) -> None:
    raw = b"".join(b"\x00" + rgba[y * size * 4:(y + 1) * size * 4] for y in range(size))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw, 9))
    png += chunk(b"IEND", b"")
    path.write_bytes(png)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for s in (192, 512):
        write_png(OUT / f"icon-{s}.png", s, render(s, ss=2))
        print("wrote", OUT / f"icon-{s}.png")
