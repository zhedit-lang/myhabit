"""JSON 接口：页面上的打卡按钮走这里，避免整页刷新。"""

from __future__ import annotations

import datetime as _dt

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from . import db, stats
from .dates import parse_day, today
from .validators import clean_day

router = APIRouter(prefix="/api", tags=["api"])

# 允许「明天」是为了容忍跨时区使用；再往后的日期没有意义，直接拒绝。
MAX_FUTURE_DAYS = 1


class CheckinPayload(BaseModel):
    habit_id: int
    day: str | None = None
    present: bool | None = None  # 省略表示「切换」当前状态


@router.post("/checkin")
def toggle_checkin(payload: CheckinPayload) -> dict:
    habit = db.get_habit(payload.habit_id)
    if habit is None:
        raise HTTPException(status_code=404, detail="习惯不存在")

    try:
        day = clean_day(payload.day) if payload.day else today().isoformat()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    target = parse_day(day)
    if target > today() + _dt.timedelta(days=MAX_FUTURE_DAYS):
        raise HTTPException(status_code=400, detail="不能给未来的日期打卡")

    existing = day in db.checkins_in_range([habit["id"]], target, target)[habit["id"]]
    present = (not existing) if payload.present is None else bool(payload.present)
    db.set_checkin(habit["id"], day, present)

    summary = stats.summarize(db.all_checkin_days(habit["id"]))
    return {
        "ok": True,
        "habit_id": habit["id"],
        "day": day,
        "present": present,
        "total": summary["total"],
        "current": summary["current"],
        "longest": summary["longest"],
    }


@router.get("/healthz")
def healthz() -> dict:
    return {"ok": True}
