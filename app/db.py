"""SQLite 数据访问层。

数据库只有一个文件，方便备份和迁移。所有日期都以 YYYY-MM-DD 字符串存储，
且一律是 APP_TZ 时区下的「本地日期」。
"""

from __future__ import annotations

import datetime as _dt
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Sequence

from .config import DB_PATH
from .dates import today_iso, utc_now_iso
from .validators import COLOR_RE, DEFAULT_COLOR, MAX_NAME_LEN

SCHEMA = """
CREATE TABLE IF NOT EXISTS habits (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT    NOT NULL,
    emoji      TEXT    NOT NULL DEFAULT '',
    color      TEXT    NOT NULL DEFAULT '#0a84ff',
    sort_order INTEGER NOT NULL DEFAULT 0,
    archived   INTEGER NOT NULL DEFAULT 0,
    created_at TEXT    NOT NULL,
    start_day  TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS checkins (
    habit_id   INTEGER NOT NULL REFERENCES habits(id) ON DELETE CASCADE,
    day        TEXT    NOT NULL,
    created_at TEXT    NOT NULL,
    PRIMARY KEY (habit_id, day)
);

CREATE INDEX IF NOT EXISTS idx_checkins_day ON checkins(day);
"""

EDITABLE_FIELDS = {"name", "emoji", "color", "sort_order", "archived"}


@contextmanager
def connect(path: Path | None = None) -> Iterator[sqlite3.Connection]:
    """打开一个连接；退出时自动提交，出错则回滚。"""
    target = Path(path or DB_PATH)
    target.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(target, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 15000")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)


def _as_dict(row: sqlite3.Row | None) -> dict | None:
    return dict(row) if row is not None else None


# ------------------------------------------------------------------ 习惯 CRUD


def list_habits(include_archived: bool = False) -> list[dict]:
    sql = "SELECT * FROM habits"
    if not include_archived:
        sql += " WHERE archived = 0"
    sql += " ORDER BY sort_order, id"
    with connect() as conn:
        return [dict(row) for row in conn.execute(sql)]


def get_habit(habit_id: int) -> dict | None:
    with connect() as conn:
        return _as_dict(conn.execute("SELECT * FROM habits WHERE id = ?", (habit_id,)).fetchone())


def create_habit(name: str, emoji: str = "", color: str = "") -> int:
    with connect() as conn:
        next_order = conn.execute(
            "SELECT COALESCE(MAX(sort_order), 0) + 1 FROM habits"
        ).fetchone()[0]
        cursor = conn.execute(
            """
            INSERT INTO habits (name, emoji, color, sort_order, archived, created_at, start_day)
            VALUES (?, ?, ?, ?, 0, ?, ?)
            """,
            (name, emoji, color, next_order, utc_now_iso(), today_iso()),
        )
        return int(cursor.lastrowid)


def update_habit(habit_id: int, **fields) -> None:
    updates = {key: value for key, value in fields.items() if key in EDITABLE_FIELDS}
    if not updates:
        return
    assignments = ", ".join(f"{key} = ?" for key in updates)
    with connect() as conn:
        conn.execute(
            f"UPDATE habits SET {assignments} WHERE id = ?",
            (*updates.values(), habit_id),
        )


def delete_habit(habit_id: int) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM habits WHERE id = ?", (habit_id,))


def reorder_habits(ordered_ids: Sequence[int]) -> None:
    with connect() as conn:
        for position, habit_id in enumerate(ordered_ids, start=1):
            conn.execute(
                "UPDATE habits SET sort_order = ? WHERE id = ?", (position, habit_id)
            )


def shift_habit(habit_id: int, direction: int) -> None:
    """把某个习惯上移/下移一位。direction 为 -1 或 +1。"""
    habits = list_habits(include_archived=True)
    ids = [habit["id"] for habit in habits]
    if habit_id not in ids:
        return
    index = ids.index(habit_id)
    target = index + direction
    if not 0 <= target < len(ids):
        return
    ids[index], ids[target] = ids[target], ids[index]
    reorder_habits(ids)


# ------------------------------------------------------------------ 打卡记录


def set_checkin(habit_id: int, day: str, present: bool) -> None:
    with connect() as conn:
        if present:
            conn.execute(
                "INSERT OR IGNORE INTO checkins (habit_id, day, created_at) VALUES (?, ?, ?)",
                (habit_id, day, utc_now_iso()),
            )
        else:
            conn.execute(
                "DELETE FROM checkins WHERE habit_id = ? AND day = ?", (habit_id, day)
            )


def checkins_in_range(
    habit_ids: Sequence[int], start: _dt.date, end: _dt.date
) -> dict[int, set[str]]:
    """取出指定习惯在 [start, end] 区间内的打卡日期。"""
    result: dict[int, set[str]] = {habit_id: set() for habit_id in habit_ids}
    if not habit_ids:
        return result
    placeholders = ",".join("?" for _ in habit_ids)
    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT habit_id, day FROM checkins
            WHERE habit_id IN ({placeholders}) AND day BETWEEN ? AND ?
            """,
            (*habit_ids, start.isoformat(), end.isoformat()),
        ).fetchall()
    for row in rows:
        result.setdefault(row["habit_id"], set()).add(row["day"])
    return result


def all_checkin_days(habit_id: int) -> list[str]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT day FROM checkins WHERE habit_id = ? ORDER BY day", (habit_id,)
        ).fetchall()
    return [row["day"] for row in rows]


def checkin_map_for(habit_ids: Sequence[int]) -> dict[int, list[str]]:
    if not habit_ids:
        return {}
    placeholders = ",".join("?" for _ in habit_ids)
    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT habit_id, day FROM checkins
            WHERE habit_id IN ({placeholders}) ORDER BY habit_id, day
            """,
            tuple(habit_ids),
        ).fetchall()
    result: dict[int, list[str]] = {habit_id: [] for habit_id in habit_ids}
    for row in rows:
        result.setdefault(row["habit_id"], []).append(row["day"])
    return result


# -------------------------------------------------------------------- 导出


def export_all() -> dict:
    with connect() as conn:
        habits = [dict(row) for row in conn.execute("SELECT * FROM habits ORDER BY sort_order, id")]
        checkins = [
            dict(row)
            for row in conn.execute("SELECT habit_id, day, created_at FROM checkins ORDER BY habit_id, day")
        ]
    return {"habits": habits, "checkins": checkins}


def import_backup(payload: dict, mode: str = "merge") -> dict:
    """从备份数据导入。

    mode="merge"  ：按习惯名称匹配。同名的只把打卡记录并进去，没有的才新建习惯，
                    不删除任何现有数据，可以反复导入同一份文件。
    mode="replace"：先清空全部习惯与打卡记录，再完整写入备份。

    返回 {habits_created, habits_merged, checkins_added, skipped}。
    """
    habits_in = payload.get("habits")
    checkins_in = payload.get("checkins")
    if not isinstance(habits_in, list) or not isinstance(checkins_in, list):
        raise ValueError("备份文件格式不正确：缺少 habits 或 checkins 列表")

    reference = _dt.date.fromisoformat(today_iso())
    created = merged = added = skipped = 0

    def normalize_day(value: object) -> str | None:
        try:
            day = _dt.date.fromisoformat(str(value))
        except ValueError:
            return None
        # 未来日期直接丢弃，否则会把连续天数算成负数
        return day.isoformat() if day <= reference else None

    def usable_name(item: object) -> str | None:
        """返回清洗后的习惯名；不合法（非对象/为空/超长）返回 None。"""
        if not isinstance(item, dict):
            return None
        name = str(item.get("name") or "").strip()
        if not name or len(name) > MAX_NAME_LEN:
            return None
        return name

    # 备份里有效的习惯 id，用来识别「找不到归属」的打卡记录
    known_source_ids: set[int] = set()
    for item in habits_in:
        if usable_name(item) is None:
            continue
        try:
            known_source_ids.add(int(item["id"]))
        except (KeyError, TypeError, ValueError):
            continue

    # 按「备份里的原习惯 id」归组打卡，方便后面映射到新的 id
    days_by_source: dict[int, set[str]] = {}
    for row in checkins_in:
        if not isinstance(row, dict):
            skipped += 1
            continue
        try:
            source_id = int(row.get("habit_id"))
        except (TypeError, ValueError):
            skipped += 1
            continue
        day = normalize_day(row.get("day"))
        if source_id not in known_source_ids or day is None:
            skipped += 1
            continue
        days_by_source.setdefault(source_id, set()).add(day)

    with connect() as conn:
        if mode == "replace":
            conn.execute("DELETE FROM checkins")
            conn.execute("DELETE FROM habits")
            known: dict[str, int] = {}
            next_order = 1
        else:
            known = {
                row["name"]: row["id"] for row in conn.execute("SELECT id, name FROM habits")
            }
            next_order = conn.execute(
                "SELECT COALESCE(MAX(sort_order), 0) + 1 FROM habits"
            ).fetchone()[0]

        for item in habits_in:
            name = usable_name(item)
            if name is None:
                skipped += 1
                continue

            color = str(item.get("color") or "")
            if not COLOR_RE.match(color):
                color = DEFAULT_COLOR

            habit_id = known.get(name)
            if habit_id is None:
                cursor = conn.execute(
                    """
                    INSERT INTO habits (name, emoji, color, sort_order, archived, created_at, start_day)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        name,
                        str(item.get("emoji") or "")[:4],
                        color,
                        next_order,
                        1 if item.get("archived") else 0,
                        utc_now_iso(),
                        normalize_day(item.get("start_day")) or today_iso(),
                    ),
                )
                habit_id = int(cursor.lastrowid)
                known[name] = habit_id
                next_order += 1
                created += 1
            else:
                merged += 1

            try:
                source_id = int(item.get("id"))
            except (TypeError, ValueError):
                continue

            for day in sorted(days_by_source.get(source_id, ())):
                cursor = conn.execute(
                    "INSERT OR IGNORE INTO checkins (habit_id, day, created_at) VALUES (?, ?, ?)",
                    (habit_id, day, utc_now_iso()),
                )
                if cursor.rowcount:
                    added += 1
                else:
                    skipped += 1

    return {
        "habits_created": created,
        "habits_merged": merged,
        "checkins_added": added,
        "skipped": skipped,
    }
