"""启动入口。

本地开发：  python main.py
生产环境：  python main.py   （自动读取 PORT 环境变量）
"""

from __future__ import annotations

import uvicorn

from app.config import DEV_RELOAD, HOST, PORT

if __name__ == "__main__":
    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=DEV_RELOAD, log_level="info")
