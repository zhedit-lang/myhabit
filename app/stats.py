"""打卡统计：累计天数、连续天数、完成率。"""

from __future__ import annotations

import datetime as _dt
from typing import Iterable

from .dates import today as _today


def longest_streak(days: Iterable[_dt.date]) -> int:
    """历史最长连续打卡天数。"""
    ordered = sorted(set(days))
    if not ordered:
        return 0
    best = run = 1
    for previous, current in zip(ordered, ordered[1:]):
        run = run + 1 if (current - previous).days == 1 else 1
        if run > best:
            best = run
    return best


def current_streak(days: set[_dt.date], reference: _dt.date | None = None) -> int:
    """当前连续打卡天数。

    今天已打卡就从今天往前数；今天还没打卡则从昨天往前数（今天还没打卡不算断，
    否则每天早上打开就会看到连续天数变成 0）。
    """
    reference = reference or _today()
    cursor = reference if reference in days else reference - _dt.timedelta(days=1)
    total = 0
    while cursor in days:
        total += 1
        cursor -= _dt.timedelta(days=1)
    return total


def completion_rate(days: set[_dt.date], reference: _dt.date, window: int = 30) -> float:
    """最近 window 天里打卡的占比。"""
    first = reference - _dt.timedelta(days=window - 1)
    hit = sum(1 for offset in range(window) if first + _dt.timedelta(days=offset) in days)
    return hit / window


def summarize(day_values: Iterable[str], reference: _dt.date | None = None) -> dict:
    """把日期字符串集合汇总成统计数字。"""
    ref = reference or _today()
    days = {_dt.date.fromisoformat(value) for value in day_values}
    return {
        "days": days,
        "total": len(days),
        "current": current_streak(days, ref),
        "longest": longest_streak(days),
        "rate30": completion_rate(days, ref),
        "done_today": ref in days,
    }
