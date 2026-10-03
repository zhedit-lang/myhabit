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

> ⚠️ **关于 iCloud（实测数据）**
>
> 项目放在 iCloud 目录下时，`.venv` 里有约 **2,800 个碎文件（44 MB）**，
> 而你自己写的源码只有 **45 个文件**。iCloud 要同步的文件里 **92% 都是虚拟环境**，
> 而且虚拟环境和绝对路径绑定，同步到另一台 Mac 上也用不了。
>
> 把虚拟环境放到项目外，同步文件数能从 3,060 降到 244：
>
> ```bash
> python3 -m venv ~/.venvs/myhabit
> ~/.venvs/myhabit/bin/python -m pip install -r requirements.txt
> rm -rf .venv
> ```
>
> 之后把下面命令里的 `./.venv/bin/python` 换成 `~/.venvs/myhabit/bin/python`。
>
> **注意：不能直接把 `.venv` 剪切走** —— 里面记录的是绝对路径，挪走就坏了，
> 必须按上面的方式**重新创建**。
>
> 另外，本地虚拟环境只用于在 Mac 上改代码时测试。**线上部署用的是 Docker，跟它无关。**

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
├── .github/workflows/   # 自动构建镜像并推送到 Docker Hub
├── Dockerfile           # 容器镜像定义
├── docker-compose.yml   # 部署到飞牛 NAS 用（模板，需改口令）
└── requirements.txt
```

数据库只有两张表：`habits`（习惯）和 `checkins`（打卡记录，主键为 `习惯 + 日期`）。

---

## 三、代码托管在 GitHub

仓库：<https://github.com/zhedit-lang/myhabit>

`.gitignore` 和 `.dockerignore` 都排除了 `.env` 和 `data/`，
**登录口令和打卡数据永远不会被提交或打进镜像**。

日常改完代码后推送：

```bash
git add .
git commit -m "说明这次改了什么"
git push
```

推送会自动触发镜像构建（见下一节），之后在 NAS 上重新拉取即可生效。

---

## 四、部署到飞牛 NAS

应用最终跑在**飞牛的 Docker** 里。整条链路：

```
Mac 上 git push
   ↓
GitHub Actions 自动构建镜像（.github/workflows/docker-publish.yml）
   ↓
推送到 Docker Hub → zhedit/myhabit:latest
   ↓
飞牛 Docker 拉取镜像 → Compose 启动容器
   ↓
飞牛 FN Connect 暴露成 HTTPS 网址 → iPhone 加到主屏幕
```

> ⚠️ **为什么要绕道 Docker Hub？**
> 因为这台 NAS 所在的网络**连不上任何国外网站** —— `ghcr.io`、Cloudflare、Tailscale 全部不通。
> 但飞牛的 Docker 内置了**国内加速器**，能拉 Docker Hub 的镜像。
> 于是「GitHub 负责构建推送（它在境外出得去）+ NAS 负责拉取（走国内加速器）」这个组合才可行。

### 1. 在 GitHub 配两个密钥

打开 <https://github.com/zhedit-lang/myhabit/settings/secrets/actions> 添加：

| 名称 | 值 |
| --- | --- |
| `DOCKERHUB_USERNAME` | Docker Hub 用户名（`zhedit`） |
| `DOCKERHUB_TOKEN` | Docker Hub Access Token，在 <https://hub.docker.com/settings/security> 生成，权限选 **Read & Write** |

配好之后，每次 push 到 `main` 都会自动重新构建镜像。

### 2. 飞牛上拉取镜像

飞牛 Docker → 左侧 **`本地镜像`** → **`添加镜像`** → **`从 URL 添加`**：

- **镜像**：`zhedit/myhabit:latest`
- **用户 / 密码**：**都留空**（镜像是公开的）

### 3. 用 Compose 创建容器

> ⚠️ 飞牛"简单模式"的**创建容器向导里没有存储挂载和环境变量**。
> 用它会导致：没有 `APP_PASSWORD` 应用**直接启动失败**，没有卷则**重启后数据丢失**。
> 所以**必须走 Compose**。

飞牛 Docker → 左侧 **`Compose`** → 新建项目：

| 字段 | 填什么 |
| --- | --- |
| 项目名称 | `myhabit` |
| 路径 | 随便选一个文件夹（**打卡数据不在这里**） |
| 来源 | 选 **`创建docker-compose.yml`** |
| 创建后立即启动 | 勾上 |

把仓库里 `docker-compose.yml` 的内容粘进去，**改掉 `APP_PASSWORD` 和 `SESSION_SECRET`**。

`SESSION_SECRET` 用这行命令生成，别自己瞎编：

```bash
openssl rand -hex 32
```

### 4. ⚠️ 数据持久化（最关键）

Compose 里已经写好了挂载：

```yaml
volumes:
  - myhabit-data:/data
```

Dockerfile 内置了 `DB_PATH=/data/myhabit.db`，所以 SQLite 文件落在 **Docker 命名卷 `myhabit-data`** 里。
这个卷独立于容器存在，**重新部署/重建容器都不会丢数据**。

**但删掉这个卷就等于删掉全部打卡记录。**
平时备份建议用应用自带的「导出」功能（见第五节），比手动扒卷安全。

### 5. 访问

飞牛 **`容器`** 列表里，`myhabit` 那一行后面有个 **🔗 链接图标**，
点开就是自动生成的网址，形如：

```
https://<容器ID>-0.<你的FNID>.fnos.net/login
```

> ⚠️ **飞牛的"登录门"**：这个网址要求**先在浏览器里登录飞牛账号**才能打开，
> 否则返回「FN Connect 暂无权限访问该服务」（HTTP 403）。
> 这是飞牛为规避备案做的设计，**不是应用出问题**。

### 6. 加到 iPhone 主屏幕

1. 用 iPhone 的 **Safari**（不能用微信内置浏览器）打开 `https://<你的FNID>.fnos.net`，**登录飞牛**
2. 再打开应用的网址，输入 `APP_PASSWORD` 进入
3. 点底部「分享」→ **「添加到主屏幕」**

之后从桌面图标打开就是全屏，和真 App 一样。

> ⚠️ 不要用「无痕模式」，否则登录状态不保存。
> 如果提示飞牛登录过期，先去 `https://<你的FNID>.fnos.net` 重新登录再打开应用。

### 7. 以后怎么更新

```bash
# Mac 上
git add .
git commit -m "改了啥"
git push
```

等 GitHub Actions 跑完（约 30 秒，在 <https://github.com/zhedit-lang/myhabit/actions> 看），
然后到飞牛 Compose 里点 **`重新部署`**（会自动拉取新镜像）。

改口令 / 改时区也一样：编辑 compose 里的环境变量，重新部署即可。

---

## 五、备份与恢复

### 导出

- 统计页右上角「导出」，或习惯页底部的「导出全部数据（JSON）」，会下载一份包含全部习惯与打卡记录的 JSON
- 也可以直接备份数据库文件：`data/myhabit.db`（以及可能存在的 `-wal` / `-shm`），
  在飞牛上就是 Docker 命名卷 `myhabit-data` 里的内容

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
