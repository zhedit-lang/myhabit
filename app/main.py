"""FastAPI 应用入口。"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from . import __version__, db
from .api import router as api_router
from .config import APP_TZ, BASE_DIR, COOKIE_SECURE, DB_PATH, SESSION_MAX_AGE, SESSION_SECRET
from .web import router as web_router

# 不需要登录就能访问的路径
PUBLIC_PATHS = {"/login", "/favicon.ico", "/healthz"}
PUBLIC_PREFIXES = ("/static/",)


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init_db()
    print(f"[myhabit] 数据库：{DB_PATH}", flush=True)
    print(f"[myhabit] 时区：{APP_TZ}", flush=True)
    yield


app = FastAPI(
    title="习惯打卡",
    version=__version__,
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


# 注册顺序很重要：guard 先注册 → 处于内层；SessionMiddleware 后注册 → 处于外层。
# 这样 guard 执行时 request.session 已经可用。颠倒顺序会让 guard 直接报错。
@app.middleware("http")
async def require_login(request: Request, call_next):
    path = request.url.path
    if path in PUBLIC_PATHS or path.startswith(PUBLIC_PREFIXES):
        return await call_next(request)
    if request.session.get("auth") is True:
        return await call_next(request)
    if path.startswith("/api/"):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    return RedirectResponse("/login", status_code=303)


app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    max_age=SESSION_MAX_AGE,
    same_site="lax",
    https_only=COOKIE_SECURE,
)

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "app" / "static")), name="static")

app.include_router(web_router)
app.include_router(api_router)


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> RedirectResponse:
    return RedirectResponse("/static/icons/favicon.svg")


@app.get("/healthz", include_in_schema=False)
def healthz() -> dict:
    return {"ok": True, "version": __version__}
