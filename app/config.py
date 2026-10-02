"""应用配置。

所有配置都可通过环境变量覆盖，方便在 Zeabur 等平台部署。
本地开发时会在项目根目录读取 .env 文件（该文件不会提交到 Git）。
"""

from __future__ import annotations

import os
import secrets
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> None:
    """极简 .env 解析器，只支持 KEY=VALUE 和 # 注释。"""
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv(BASE_DIR / ".env")


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


# ---------------------------------------------------------------- 登录与安全

APP_PASSWORD = os.environ.get("APP_PASSWORD", "").strip()
if not APP_PASSWORD:
    raise RuntimeError(
        "未设置登录口令。请在项目根目录创建 .env 文件（可参考 .env.example），"
        "或设置环境变量 APP_PASSWORD。"
    )

# 未显式配置时随机生成：本地开发每次重启都会让旧登录态失效，生产环境请固定配置。
SESSION_SECRET = os.environ.get("SESSION_SECRET", "").strip() or secrets.token_hex(32)

# 登录有效期，默认 180 天
SESSION_MAX_AGE = int(os.environ.get("SESSION_MAX_AGE", str(180 * 24 * 3600)))

# 只在 HTTPS 下发送登录 Cookie。部署到 Zeabur（HTTPS）后建议设为 1。
COOKIE_SECURE = _env_bool("COOKIE_SECURE", False)

# ------------------------------------------------------------------ 日期时区

# 判断「今天」所用的时区。必须固定，否则晚上打卡会被算到第二天。
APP_TZ = os.environ.get("APP_TZ", "Asia/Shanghai").strip()

# -------------------------------------------------------------------- 存储

DATA_DIR = Path(os.environ.get("DATA_DIR", str(BASE_DIR / "data"))).expanduser()
DB_PATH = Path(os.environ.get("DB_PATH", str(DATA_DIR / "myhabit.db"))).expanduser()

# -------------------------------------------------------------------- 其他

DEV_RELOAD = _env_bool("DEV_RELOAD", False)

# 默认监听 0.0.0.0，这样同一局域网下用手机也能直接打开调试
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8000"))
