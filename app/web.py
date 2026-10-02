"""HTML 页面路由（服务端渲染）。

页面用 form POST + 重定向，无需前端框架；打卡按钮另外走 /api/checkin 做局部刷新。
"""

from __future__ import annotations

import asyncio
import datetime as _dt
import hmac
import json
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from . import __version__, db, stats
from .config import APP_PASSWORD, BASE_DIR, DATA_DIR
from .dates import (
    WEEKDAY_SHORT,
    add_months,
    build_month_grid,
    month_label,
    month_start,
    now,
    parse_day,
    today,
    utc_now_iso,
    week_start,
)
from .validators import PALETTE, clean_color, clean_emoji, clean_name

router = APIRouter()

templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))
templates.env.globals.update(
    WEEKDAY_SHORT=WEEKDAY_SHORT,
    palette=PALETTE,
    version=__version__,
)

WEEK_MINI_CELLS = 7
MAX_IMPORT_BYTES = 5 * 1024 * 1024  # 备份文件最大 5MB
KEEP_BACKUPS = 20                    # 覆盖导入前的自动快照，最多保留最近 20 份
STATIC_DIR = BASE_DIR / "app" / "static"


def static_version() -> str:
    """按静态文件的最新修改时间生成版本号，用于给 CSS/JS 加 ?v= 做缓存失效。"""
    latest = 0
    for path in STATIC_DIR.rglob("*"):
        if path.is_file():
            latest = max(latest, path.stat().st_mtime_ns)
    return format(latest % (2**32), "x")


def render(request: Request, name: str, **context):
    context.setdefault("nav", "")
    context.setdefault("msg", request.query_params.get("msg", ""))
    context.setdefault("err", request.query_params.get("err", ""))
    context.setdefault("today", today())
    context.setdefault("asset_version", static_version())
    return templates.TemplateResponse(request, name, context)


def redirect(path: str, msg: str = "", err: str = "") -> RedirectResponse:
    query = ""
    if msg:
        query = f"?msg={quote(msg)}"
    elif err:
        query = f"?err={quote(err)}"
    return RedirectResponse(f"{path}{query}", status_code=303)


# ------------------------------------------------------------------ 登录登出


@router.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    if request.session.get("auth") is True:
        return RedirectResponse("/", status_code=303)
    return render(request, "login.html")


@router.post("/login")
async def login_submit(request: Request):
    form = await request.form()
    password = str(form.get("password", ""))
    if hmac.compare_digest(password, APP_PASSWORD):
        request.session.clear()
        request.session["auth"] = True
        return RedirectResponse("/", status_code=303)
    # 让爆破变慢一点，顺便给用户一点「密码错误」的感知
    await asyncio.sleep(0.6)
    return redirect("/login", err="口令不正确")


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


# -------------------------------------------------------------------- 今日


@router.get("/", response_class=HTMLResponse)
def today_page(request: Request):
    habits = db.list_habits()
    days_map = db.checkin_map_for([habit["id"] for habit in habits])
    rows = [
        {"habit": habit, "summary": stats.summarize(days_map.get(habit["id"], []))}
        for habit in habits
    ]
    return render(
        request,
        "today.html",
        nav="today",
        rows=rows,
        done_count=sum(1 for row in rows if row["summary"]["done_today"]),
    )


# -------------------------------------------------------------------- 统计


@router.get("/stats", response_class=HTMLResponse)
def stats_page(request: Request):
    view = request.query_params.get("view", "week")
    if view not in {"week", "month"}:
        view = "week"

    try:
        anchor = parse_day(request.query_params.get("anchor", ""))
    except ValueError:
        anchor = today()

    reference = today()
    habits = db.list_habits()
    habit_ids = [habit["id"] for habit in habits]

    # 统计数字用全量历史
    all_days = db.checkin_map_for(habit_ids)
    stat_rows = [
        {"habit": habit, "summary": stats.summarize(all_days.get(habit["id"], []))}
        for habit in habits
    ]

    if view == "month":
        period_start = month_start(anchor)
        period_end = month_start(add_months(anchor, 1)) - _dt.timedelta(days=1)
        previous_anchor = add_months(anchor, -1)
        next_anchor = add_months(anchor, 1)
        label = month_label(anchor)
        can_go_next = month_start(add_months(anchor, 1)) <= reference
    else:
        period_start = week_start(anchor)
        period_end = period_start + _dt.timedelta(days=6)
        previous_anchor = anchor - _dt.timedelta(days=7)
        next_anchor = anchor + _dt.timedelta(days=7)
        label = f"{period_start.month}月{period_start.day}日 – {period_end.month}月{period_end.day}日"
        can_go_next = week_start(anchor) + _dt.timedelta(days=7) <= reference

    period_days = db.checkins_in_range(habit_ids, period_start, period_end)
    habit_count = len(habits)

    context: dict = {
        "nav": "stats",
        "view": view,
        "label": label,
        "anchor": anchor.isoformat(),
        "prev_anchor": previous_anchor.isoformat(),
        "next_anchor": next_anchor.isoformat(),
        "stat_rows": stat_rows,
        "habit_count": habit_count,
        "can_go_next": can_go_next,
    }

    if view == "week":
        week_dates = [period_start + _dt.timedelta(days=offset) for offset in range(WEEK_MINI_CELLS)]
        rows = []
        for habit in habits:
            checked = period_days.get(habit["id"], set())
            rows.append(
                {
                    "habit": habit,
                    "summary": stats.summarize(all_days.get(habit["id"], [])),
                    "cells": [
                        {
                            "iso": day.isoformat(),
                            "label": f"{day.month}/{day.day}",
                            "on": day.isoformat() in checked,
                            "future": day > reference,
                            "is_today": day == reference,
                        }
                        for day in week_dates
                    ],
                }
            )
        context["week_rows"] = rows
        context["week_dates"] = [
            {"label": f"{day.month}/{day.day}", "is_today": day == reference}
            for day in week_dates
        ]
    else:
        day_counts: dict[str, int] = {}
        for days in period_days.values():
            for day in days:
                day_counts[day] = day_counts.get(day, 0) + 1

        weeks = []
        for week in build_month_grid(anchor):
            cells = []
            for day in week:
                if day is None:
                    cells.append(None)
                    continue
                count = day_counts.get(day.isoformat(), 0)
                ratio = count / habit_count if habit_count else 0.0
                cells.append(
                    {
                        "iso": day.isoformat(),
                        "day": day.day,
                        "count": count,
                        "level": 0 if count == 0 else 1 + min(3, int(ratio * 3.999)),
                        "future": day > reference,
                        "is_today": day == reference,
                    }
                )
            weeks.append(cells)

        context["month_weeks"] = weeks
        context["month_totals"] = [
            {
                "habit": habit,
                "count": len(period_days.get(habit["id"], set())),
                "days_in_month": period_end.day,
            }
            for habit in habits
        ]

    return render(request, "stats.html", **context)


# ------------------------------------------------------------------ 习惯管理


@router.get("/habits", response_class=HTMLResponse)
def habits_page(request: Request):
    all_habits = db.list_habits(include_archived=True)
    return render(
        request,
        "habits.html",
        nav="habits",
        habits=[habit for habit in all_habits if not habit["archived"]],
        archived=[habit for habit in all_habits if habit["archived"]],
    )


@router.post("/habits")
async def create_habit(request: Request):
    form = await request.form()
    try:
        name = clean_name(str(form.get("name", "")))
        emoji = clean_emoji(str(form.get("emoji", "")))
        color = clean_color(str(form.get("color", "")))
    except ValueError as exc:
        return redirect("/habits", err=str(exc))
    db.create_habit(name=name, emoji=emoji, color=color)
    return redirect("/habits", msg=f"已添加「{name}」")


@router.post("/habits/{habit_id}/update")
async def edit_habit(request: Request, habit_id: int):
    if db.get_habit(habit_id) is None:
        return redirect("/habits", err="习惯不存在")
    form = await request.form()
    try:
        name = clean_name(str(form.get("name", "")))
        emoji = clean_emoji(str(form.get("emoji", "")))
        color = clean_color(str(form.get("color", "")))
    except ValueError as exc:
        return redirect("/habits", err=str(exc))
    db.update_habit(habit_id, name=name, emoji=emoji, color=color)
    return redirect("/habits", msg="已保存")


@router.post("/habits/{habit_id}/delete")
async def remove_habit(request: Request, habit_id: int):
    habit = db.get_habit(habit_id)
    if habit is None:
        return redirect("/habits", err="习惯不存在")
    db.delete_habit(habit_id)
    return redirect("/habits", msg=f"已删除「{habit['name']}」及其全部打卡记录")


@router.post("/habits/{habit_id}/archive")
async def archive_habit(request: Request, habit_id: int):
    if db.get_habit(habit_id) is None:
        return redirect("/habits", err="习惯不存在")
    form = await request.form()
    archived = 1 if str(form.get("archived", "1")) == "1" else 0
    db.update_habit(habit_id, archived=archived)
    return redirect("/habits", msg="已归档，打卡记录保留" if archived else "已恢复")


@router.post("/habits/{habit_id}/move")
async def move_habit(request: Request, habit_id: int):
    form = await request.form()
    direction = -1 if str(form.get("dir", "up")) == "up" else 1
    db.shift_habit(habit_id, direction)
    return redirect("/habits")


# ---------------------------------------------------------------- 数据导出


@router.get("/export.json")
def export_json():
    payload = db.export_all()
    payload.update({"app": "myhabit", "version": __version__, "exported_at": utc_now_iso()})
    filename = f"myhabit-{today().isoformat()}.json"
    return Response(
        json.dumps(payload, ensure_ascii=False, indent=2),
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def snapshot_before_import() -> Path:
    """覆盖导入前把现有数据落一份备份文件，防止误操作后无法回头。"""
    backup_dir = DATA_DIR / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)

    snapshot = db.export_all()
    snapshot.update({"app": "myhabit", "version": __version__, "exported_at": utc_now_iso()})
    target = backup_dir / f"before-import-{now():%Y%m%d-%H%M%S}.json"
    target.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")

    for stale in sorted(backup_dir.glob("before-import-*.json"))[:-KEEP_BACKUPS]:
        stale.unlink(missing_ok=True)
    return target


@router.post("/import")
async def import_json(request: Request):
    form = await request.form()
    upload = form.get("file")
    mode = str(form.get("mode", "merge"))
    if mode not in {"merge", "replace"}:
        mode = "merge"

    if not getattr(upload, "filename", ""):
        return redirect("/habits", err="请先选择要导入的备份文件")

    raw = await upload.read()
    if not raw:
        return redirect("/habits", err="这个文件是空的")
    if len(raw) > MAX_IMPORT_BYTES:
        return redirect("/habits", err="文件超过 5MB，正常的备份文件不会这么大")

    try:
        payload = json.loads(raw.decode("utf-8"))
    except UnicodeDecodeError:
        return redirect("/habits", err="文件不是 UTF-8 编码，无法读取")
    except json.JSONDecodeError:
        return redirect("/habits", err="这不是一个有效的 JSON 文件")
    if not isinstance(payload, dict):
        return redirect("/habits", err="备份文件格式不正确")

    snapshot_path: Path | None = None
    if mode == "replace":
        try:
            snapshot_path = snapshot_before_import()
        except OSError as exc:
            return redirect("/habits", err=f"覆盖前的自动备份失败，已中止导入：{exc}")

    try:
        result = db.import_backup(payload, mode)
    except ValueError as exc:
        return redirect("/habits", err=str(exc))

    summary = (
        f"导入完成：新增 {result['habits_created']} 个习惯、"
        f"合并 {result['habits_merged']} 个，"
        f"写入 {result['checkins_added']} 条打卡记录"
    )
    if result["skipped"]:
        summary += f"，跳过 {result['skipped']} 项无效或重复的数据"
    if snapshot_path is not None:
        summary += f"。覆盖前的旧数据已存为 {snapshot_path.name}"
    return redirect("/habits", msg=summary)
