"""输入清洗与校验。"""

from __future__ import annotations

import re

COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
DAY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# 可选的习惯配色（前端色板用同一份）
PALETTE = (
    "#0a84ff",  # 蓝
    "#34c759",  # 绿
    "#ff9f0a",  # 橙
    "#ff375f",  # 红
    "#bf5af2",  # 紫
    "#5ac8fa",  # 青
    "#ffd60a",  # 黄
    "#8e8e93",  # 灰
)

DEFAULT_COLOR = PALETTE[0]
MAX_NAME_LEN = 40


def clean_name(value: str | None) -> str:
    name = (value or "").strip()
    name = re.sub(r"\s+", " ", name)
    if not name:
        raise ValueError("习惯名称不能为空")
    if len(name) > MAX_NAME_LEN:
        raise ValueError(f"习惯名称不能超过 {MAX_NAME_LEN} 个字")
    return name


def clean_emoji(value: str | None) -> str:
    """只保留开头的 1~2 个字符，避免有人塞进一长串文字。"""
    emoji = (value or "").strip()
    if not emoji:
        return ""
    # 组合 emoji（如 👨‍👩‍👧）会包含零宽连接符，这里简单地按 4 个字符截断
    return emoji[:4]


def clean_color(value: str | None) -> str:
    color = (value or "").strip()
    if not color:
        return DEFAULT_COLOR
    if not COLOR_RE.match(color):
        raise ValueError("颜色格式不正确")
    return color.lower()


def clean_day(value: str | None) -> str:
    day = (value or "").strip()
    if not DAY_RE.match(day):
        raise ValueError("日期格式应为 YYYY-MM-DD")
    try:
        import datetime as _dt

        _dt.date.fromisoformat(day)
    except ValueError as exc:
        raise ValueError("日期不存在") from exc
    return day
