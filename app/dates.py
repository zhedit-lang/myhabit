"""日期与时区工具。

所有「今天」的判断都以 APP_TZ（默认 Asia/Shanghai）为准，避免因为服务器
运行在 UTC 而把晚上 8 点之后的打卡算到第二天。
"""

from __future__ import annotations

import calendar as _calendar
import datetime as _dt
from zoneinfo import ZoneInfo

from .config import APP_TZ

TZ = ZoneInfo(APP_TZ)

WEEKDAY_SHORT = ("一", "二", "三", "四", "五", "六", "日")
WEEKDAY_FULL = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")


def now() -> _dt.datetime:
    return _dt.datetime.now(TZ)


def today() -> _dt.date:
    return now().date()


def today_iso() -> str:
    return today().isoformat()


def utc_now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


def parse_day(value: str) -> _dt.date:
    return _dt.date.fromisoformat(value)


def week_start(day: _dt.date) -> _dt.date:
    """周一作为一周的第一天。"""
    return day - _dt.timedelta(days=day.weekday())


def month_start(day: _dt.date) -> _dt.date:
    return day.replace(day=1)


def add_months(day: _dt.date, delta: int) -> _dt.date:
    total = day.year * 12 + (day.month - 1) + delta
    year, month = divmod(total, 12)
    return _dt.date(year, month + 1, 1)


def month_label(day: _dt.date) -> str:
    return f"{day.year}年{day.month}月"


def build_month_grid(day: _dt.date) -> list[list[_dt.date | None]]:
    """按周分组的月历网格，周开头，空格用 None 补齐。"""
    first = month_start(day)
    last = first.replace(day=_calendar.monthrange(first.year, first.month)[1])

    grid: list[list[_dt.date | None]] = []
    week: list[_dt.date | None] = [None] * first.weekday()
    cursor = first
    while cursor <= last:
        week.append(cursor)
        if len(week) == 7:
            grid.append(week)
            week = []
        cursor += _dt.timedelta(days=1)
    if week:
        week.extend([None] * (7 - len(week)))
        grid.append(week)
    return grid
