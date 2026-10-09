# 部署到云服务器（VPS）

> 本文讲「租一台云服务器，把应用跑起来，手机随时打开就能用」。
> 本地开发看 [README.md](./README.md)；飞牛 NAS 方案已废弃。

## 先选一条路线

| 路线 | 配置目录 | 访问地址 | 适合 |
| --- | --- | --- | --- |
| **A · 无域名** | [`deploy/ip/`](./deploy/ip/) | `http://<服务器IP>:8000` | 先跑起来，零成本 |
| **B · 有域名** | [`deploy/domain/`](./deploy/domain/) | `https://habit.你的域名.com` | 长期正式使用（自动 HTTPS，推荐） |

- 两条路线**用的是同一个镜像、同一个数据卷**（`myhabit_myhabit-data`），所以**以后可以从 A 无缝升级到 B**，打卡数据不丢。
- A 是 HTTP 明文，登录口令会明文过网；B 是 HTTPS 加密。个人自用 A 可用，但**有条件还是建议上 B**。

---

## 通用步骤（A、B 都要做）

### 1. 买服务器

| 项目 | 选择 |
| --- | --- |
| 地区 | **香港**（免备案）或其他免备案海外地区 |
| 配置 | **1 核 1 GB** 起（2 核 2 GB 很充裕） |
| 系统 | **Ubuntu 22.04 / 24.04** |
| 架构 | 必须 **KVM**（OpenVZ / LXC 装 Docker 会出问题） |

买完记下 **公网 IP** 和 **root 密码**。

### 2. 登录服务器

在你自己的电脑上打开终端：

```bash
ssh root@你的服务器公网IP
```

首次会问 `Are you sure you want to continue connecting?` → 输入 `yes`；
再输入 root 密码（**屏幕上不会显示任何字符，这是正常的**）。

### 3. 安装 Docker

```bash
curl -fsSL https://get.docker.com | sh
docker --version
docker compose version
```

### 4. 拉取代码

```bash
git clone https://github.com/zhedit-lang/myhabit.git /root/myhabit
```

### 5. 放行端口 ⚠️

去服务器的控制台，在**「防火墙 / 安全组」**里放行：

- 路线 A：放行 **8000**
- 路线 B：放行 **80** 和 **443**

> 很多服务商默认只开 22，不放行的话外面永远打不开。

---

## 路线 A：无域名（`http://<IP>:8000`）

### A1. 配置

```bash
cd /root/myhabit/deploy/ip
cp .env.example .env
openssl rand -hex 32      # 复制这串输出，待会儿填进 SESSION_SECRET
nano .env
```

`.env` 里必填两项：

| 变量 | 填什么 |
| --- | --- |
| `APP_PASSWORD` | 你的登录口令 |
| `SESSION_SECRET` | 上一步 `openssl rand -hex 32` 的输出 |

> `SESSION_SECRET` 不设置的话，每次重启都会掉登录。

保存退出 `nano`：`Ctrl+O` → 回车 → `Ctrl+X`。

### A2. 启动

```bash
docker compose up -d
docker compose logs -f myhabit     # 看到日志后 Ctrl+C 退出
```

### A3. 访问

浏览器打开：

```
http://你的服务器公网IP:8000
```

出现登录页 → 输入 `APP_PASSWORD` → 成功。

---

## 路线 B：有域名（自动 HTTPS，推荐）

### B1. 域名解析

去域名服务商添加一条解析：

| 记录类型 | 主机记录 | 记录值 |
| --- | --- | --- |
| `A` | `habit` | 你的服务器公网 IP |

验证：

```bash
dig +short habit.你的域名.com     # 应等于服务器公网 IP
```

> ⚠️ **先解析、后启动**。DNS 没生效时 Caddy 签不了证书（它会自动重试，不用重启）。

### B2. 配置

```bash
cd /root/myhabit/deploy/domain
cp .env.example .env
openssl rand -hex 32
nano .env
```

`.env` 里必填三项：`DOMAIN`、`APP_PASSWORD`、`SESSION_SECRET`。

### B3. 启动

```bash
docker compose up -d
docker compose logs -f caddy       # 看到 certificate obtained successfully 后 Ctrl+C
```

### B4. 验证

浏览器打开 `https://habit.你的域名.com` → 登录页 → 输入口令 → 成功。

---

## 手机加到主屏幕

1. 用 **Safari**（不要用微信内置浏览器，不要用无痕模式）打开访问地址
2. 登录
3. 底部「分享」→ **「添加到主屏幕」**

---

## 以后更新代码

在**自己电脑上**推送：

```bash
git add . && git commit -m "说明改了啥" && git push
```

等 GitHub Actions 构建完（约 30 秒，<https://github.com/zhedit-lang/myhabit/actions>），
再到**服务器上**：

```bash
cd /root/myhabit/deploy/ip        # 或 deploy/domain
docker compose pull myhabit
docker compose up -d
```

---

## 备份与恢复

**最省事**：用应用内的「导出」下载 JSON。

**备份数据库**（两条路线通用，卷名都是 `myhabit_myhabit-data`）：

```bash
docker run --rm -v myhabit_myhabit-data:/data -v "$PWD":/backup alpine \
  tar czf /backup/myhabit-$(date +%F).tar.gz -C /data .
```

**恢复**：用应用内「从备份文件恢复…」导入 JSON，选「覆盖」。

> ⚠️ 删掉卷 `myhabit_myhabit-data` = 删掉全部打卡记录。

---

## 从 A 升级到 B（以后有了域名）

数据不用迁移，因为卷是共用的：

```bash
cd /root/myhabit/deploy/ip
docker compose down                 # 停掉 A
cd ../domain
cp .env.example .env && nano .env   # 填 DOMAIN / APP_PASSWORD / SESSION_SECRET
docker compose up -d                # 起 B（Caddy 自动签证书）
```

> `APP_PASSWORD` 和 `SESSION_SECRET` 填和原来一样即可，登录态不会丢。

---

## 排错

| 现象 | 原因 / 处理 |
| --- | --- |
| 外面打不开 | **防火墙没放行端口**（A 放 8000 / B 放 80、443） |
| 证书申请失败（B） | DNS 没生效、80 端口没放行、`DOMAIN` 写错。改好后 `docker compose restart caddy` |
| `APP_PASSWORD ... is required` | 没建 `.env` 或没填 `APP_PASSWORD` |
| 登录后一刷新就退出 | `SESSION_SECRET` 没固定 |
| `Permission denied` 或 Docker 装不上 | 虚拟化不是 KVM（OpenVZ/LXC） |
| 手机上「今天」不对 | `APP_TZ` 必须是 `Asia/Shanghai` |

**常用命令**：

```bash
docker compose logs -f myhabit    # 应用日志
docker compose ps                 # 容器状态
docker compose down               # 停止（数据保留在卷里）
docker compose up -d              # 启动
```
