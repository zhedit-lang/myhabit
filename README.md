# 习惯打卡 · myhabit

一个给自己用的习惯打卡网页应用，界面按 iPhone 屏幕设计，可以「添加到主屏幕」当成 App 用。

- **每日打卡**：自定义习惯名称、emoji、颜色，点一下即打卡，再点一下取消
- **补打卡**：可以补记、修改、取消过去任意一天的记录
- **统计**：已打卡天数、当前连续天数、历史最长连续、近 30 天完成率
- **日历色块**：周视图（每个习惯一行色块，可直接点选）/ 月视图（整月热力图）
- **数据存服务端**：SQLite 文件，不依赖第三方服务

技术栈：Python **FastAPI** + **SQLite** + Jinja2 服务端渲染 + 原生 CSS/JS（无前端构建步骤）。

---

## 一、本地运行

```bash
# 1. 创建虚拟环境（VS Code 已自动创建，若已存在可跳过）
python3 -m venv .venv

# 2. 安装依赖
./.venv/bin/python -m pip install -r requirements.txt

# 3. 创建配置文件并修改口令
cp .env.example .env
#    编辑 .env，把 APP_PASSWORD 改成你自己的口令

# 4. 启动
./.venv/bin/python main.py
```

打开 <http://127.0.0.1:8000>，输入 `.env` 里的 `APP_PASSWORD` 即可。

> 在 VS Code 里打开项目后，终端会自动激活 `.venv`，直接敲 `python main.py` 也可以。

> 服务器默认监听 `0.0.0.0`，所以同一个 Wi-Fi 下用手机访问
> `http://<你 Mac 的局域网 IP>:8000` 也能直接调试。

> ⚠️ 项目放在 iCloud 目录下，而 `.venv` 里有上万个碎文件，iCloud 会持续同步它们。
> 如果觉得卡或者想避免同步问题，可以把虚拟环境放到项目外：
> `python3 -m venv ~/.venvs/myhabit`，之后把下面的 `./.venv/bin/python` 换成
> `~/.venvs/myhabit/bin/python` 即可。

### 环境变量

| 变量 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `APP_PASSWORD` | ✅ | 无 | 登录口令，未设置会直接启动失败 |
| `SESSION_SECRET` | 建议 | 随机生成 | 登录 Cookie 的签名密钥。**不设置的话每次重启都会掉登录** |
| `APP_TZ` | | `Asia/Shanghai` | 判断「今天」用的时区，必须固定，否则晚上打卡会算到第二天 |
| `DB_PATH` | | `<项目>/data/myhabit.db` | SQLite 文件位置 |
| `DATA_DIR` | | `<项目>/data` | 数据库目录（`DB_PATH` 优先） |
| `COOKIE_SECURE` | | `0` | 部署到 HTTPS 后建议设为 `1` |
| `SESSION_MAX_AGE` | | `15552000` | 登录有效期（秒），默认 180 天 |
| `PORT` | | `8000` | 监听端口 |

---

## 二、项目结构

```
myhabit/
├── app/
│   ├── main.py          # FastAPI 入口、登录拦截中间件
│   ├── config.py        # 配置（读取环境变量与 .env）
│   ├── db.py            # SQLite 建表与增删改查
│   ├── dates.py         # 时区与日期计算（周/月网格）
│   ├── stats.py         # 连续天数、完成率
│   ├── validators.py    # 输入清洗校验、配色板
│   ├── web.py           # HTML 页面路由
│   ├── api.py           # /api/checkin 打卡接口
│   ├── templates/       # Jinja2 模板
│   └── static/          # CSS / JS / 图标
├── tools/make_icons.py  # 重新生成 App 图标
├── main.py              # 启动入口
├── .venv/               # 虚拟环境（不提交）
├── Dockerfile           # 部署用（Zeabur 会自动识别）
└── requirements.txt
```

数据库只有两张表：`habits`（习惯）和 `checkins`（打卡记录，主键为 `习惯 + 日期`）。

---

## 三、部署到 GitHub

```bash
cd myhabit

git init
git add .
git commit -m "feat: 习惯打卡应用"

# 先在 GitHub 上建一个空仓库（不要勾选 README），然后：
git remote add origin git@github.com:<你的用户名>/myhabit.git
git branch -M main
git push -u origin main
```

`.gitignore` 已经排除了 `.env` 和 `data/`，口令和打卡数据不会被推上去。
推送前可以用 `git status` 确认一下。

---

## 四、部署到 Zeabur

### 1. 创建项目

Zeabur 控制台 → **Create Project** → **Deploy from GitHub** → 选择 `myhabit` 仓库。
Zeabur 会检测到 `Dockerfile` 并自动用它构建。

### 2. ⚠️ 挂载持久化卷（最关键的一步）

SQLite 数据放在容器文件系统里，**重新部署就会丢**。必须挂一个卷：

1. 进入项目 → 你的服务 → **Volumes**（存储 / 卷）
2. 新增一个卷，挂载路径填 **`/data`**
3. 确认容器内环境变量 `DB_PATH=/data/myhabit.db`（Dockerfile 已内置）

没挂卷的话，容器一重启数据就没了。

### 3. 设置环境变量

服务 → **Variables**，添加：

| 变量 | 值 |
| --- | --- |
| `APP_PASSWORD` | 你的登录口令 |
| `SESSION_SECRET` | 一串长随机字符串（例如 `openssl rand -hex 32` 的输出） |
| `APP_TZ` | `Asia/Shanghai` |
| `COOKIE_SECURE` | `1` |

### 4. 绑定域名

服务 → **Networking** → 生成一个 `*.zeabur.app` 域名，或绑定自己的域名。
Zeabur 自动配好 HTTPS。

### 5. 加到 iPhone 主屏幕

用 **Safari** 打开上面的网址 → 登录 → 点底部「分享」→ **添加到主屏幕**。
之后从主屏幕图标打开就是全屏，没有浏览器地址栏，用起来和 App 一样。

> 注意：不要用「无痕模式」打开，Safari 在无痕模式下不会保存登录状态。
> 另外如果长期不访问，登录可能会过期，重新输入口令即可。

---

## 五、备份与恢复

### 导出

- 统计页右上角「导出」，或习惯页底部的「导出全部数据（JSON）」，会下载一份包含全部习惯与打卡记录的 JSON
- 也可以直接备份数据库文件：`data/myhabit.db`（以及可能存在的 `-wal` / `-shm`），
  在 Zeabur 上就是从 `/data` 卷里取

### 恢复

习惯页底部 →「从备份文件恢复…」→ 选择 JSON → 选导入方式：

| 方式 | 行为 | 什么时候用 |
| --- | --- | --- |
| **合并** | 按习惯名称匹配：同名的只把打卡记录并进去，没有的才新建习惯，不删任何现有数据 | 把旧备份补回来。同一份文件重复导入也不会产生重复记录 |
| **覆盖** | 先清空全部习惯与打卡记录，再用备份完全替换 | 换服务器，或想回到某个时间点的状态 |

覆盖导入前会**自动**把当前数据存一份到 `data/backups/before-import-<时间>.json`，
最多保留最近 20 份，所以误操作了还能找回来。

导入时会丢弃无效数据：格式错误的日期、未来的日期、颜色值不合法的习惯（改用默认蓝色）、
超过 40 字的习惯名。这些都会在结果提示里显示「跳过 N 条」。

---

## 六、重新生成图标

```bash
./.venv/bin/python tools/make_icons.py
```

脚本用标准库直接写 PNG，不依赖 Pillow。要改配色或对勾形状，编辑
`tools/make_icons.py` 顶部的 `BG` / `CHECK_POINTS` / `JOBS` 即可。
