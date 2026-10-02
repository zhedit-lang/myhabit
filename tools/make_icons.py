"""生成应用图标 PNG（不依赖 Pillow，只用标准库）。

用法：  python tools/make_icons.py
输出：  app/static/icons/icon-180.png / icon-192.png / icon-512.png / icon-512-maskable.png

- apple-touch-icon（180）与 maskable 需要不透明背景，圆角由系统自行裁切；
- PWA 普通图标（192/512）自带圆角并保留透明边角。
"""

from __future__ import annotations

import math
import struct
import zlib
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent.parent / "app" / "static" / "icons"

BG = (52, 199, 89)      # #34c759
FG = (255, 255, 255)    # 白色对勾
CORNER_RADIUS = 0.223   # 圆角半径（占边长比例）
CHECK_WIDTH = 0.098     # 对勾线宽（占边长比例）

# 归一化坐标下的对勾折线
CHECK_POINTS = ((0.285, 0.520), (0.435, 0.672), (0.720, 0.350))

# (文件名, 尺寸, 背景是否铺满, 对勾缩放)
JOBS = (
    ("icon-180.png", 180, True, 0.86),
    ("icon-192.png", 192, False, 1.0),
    ("icon-512.png", 512, False, 1.0),
    ("icon-512-maskable.png", 512, True, 0.74),
)


def _distance_to_segment(px, py, ax, ay, bx, by) -> float:
    dx, dy = bx - ax, by - ay
    length_sq = dx * dx + dy * dy
    if length_sq == 0.0:
        return math.hypot(px - ax, py - ay)
    t = ((px - ax) * dx + (py - ay) * dy) / length_sq
    t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def _in_rounded_square(x: float, y: float) -> bool:
    if x < 0.0 or x > 1.0 or y < 0.0 or y > 1.0:
        return False
    radius = CORNER_RADIUS
    cx = min(max(x, radius), 1.0 - radius)
    cy = min(max(y, radius), 1.0 - radius)
    return math.hypot(x - cx, y - cy) <= radius


def _on_check(x: float, y: float, scale: float) -> bool:
    half = CHECK_WIDTH / 2.0
    points = [(0.5 + (px - 0.5) * scale, 0.5 + (py - 0.5) * scale) for px, py in CHECK_POINTS]
    return any(
        _distance_to_segment(x, y, ax, ay, bx, by) <= half
        for (ax, ay), (bx, by) in zip(points, points[1:])
    )


def _sample(x: float, y: float, full_bleed: bool, scale: float) -> tuple[float, float]:
    """单个采样点的 (背景覆盖率, 前景覆盖率)。坐标为 0~1 归一化值。"""
    if _on_check(x, y, scale):
        return 1.0, 1.0
    if full_bleed or _in_rounded_square(x, y):
        return 1.0, 0.0
    return 0.0, 0.0


def _pixel(px: int, py: int, size: int, full_bleed: bool, scale: float, samples: int = 4):
    """返回像素的 (背景覆盖率, 前景覆盖率)。

    内部与外部区域直接判定，只有跨越边界的像素才做超采样，兼顾质量与速度。
    """
    probes = [
        (px, py),
        (px + 1.0, py),
        (px, py + 1.0),
        (px + 1.0, py + 1.0),
        (px + 0.5, py + 0.5),
    ]
    results = [_sample(x / size, y / size, full_bleed, scale) for x, y in probes]
    if all(result == results[0] for result in results):
        return results[0]

    total_bg = total_fg = 0.0
    step = 1.0 / samples
    for i in range(samples):
        for j in range(samples):
            bg, fg = _sample(
                (px + (i + 0.5) * step) / size,
                (py + (j + 0.5) * step) / size,
                full_bleed,
                scale,
            )
            total_bg += bg
            total_fg += fg
    count = samples * samples
    return total_bg / count, total_fg / count


def render(size: int, full_bleed: bool, scale: float) -> bytearray:
    pixels = bytearray(size * size * 4)
    for py in range(size):
        row_offset = py * size * 4
        for px in range(size):
            bg, fg = _pixel(px, py, size, full_bleed, scale)
            if bg <= 0.0:
                continue
            ratio = min(1.0, fg / bg)
            offset = row_offset + px * 4
            pixels[offset] = round(BG[0] + (FG[0] - BG[0]) * ratio)
            pixels[offset + 1] = round(BG[1] + (FG[1] - BG[1]) * ratio)
            pixels[offset + 2] = round(BG[2] + (FG[2] - BG[2]) * ratio)
            pixels[offset + 3] = round(min(1.0, bg) * 255)
    return pixels


def write_png(path: Path, size: int, pixels: bytearray) -> None:
    raw = bytearray()
    stride = size * 4
    for y in range(size):
        raw.append(0)  # filter type: None
        raw.extend(pixels[y * stride:(y + 1) * stride])

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    header = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + chunk(b"IEND", b"")
    )
    path.write_bytes(png)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, size, full_bleed, scale in JOBS:
        target = OUT_DIR / name
        write_png(target, size, render(size, full_bleed, scale))
        print(f"生成 {name}  ({target.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
