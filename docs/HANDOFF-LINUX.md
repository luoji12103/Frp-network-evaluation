# Linux Handoff

本文档面向当前的 `Panel + Agent` 架构，不再以 SSH 编排为主路径。

## 1. 当前交付形态

当前仓库已经切换为持续监控架构：

- 中央 `Panel`
  - `FastAPI + SQLite`
  - 后台调度
  - 节点配对
  - 历史指标
  - 告警与报告导出
- 节点 `Agent`
  - 常驻 HTTP 服务
  - 本地执行 probe
  - 通过 heartbeat 主动上报
  - 支持 panel 直连下发作业

角色部署约定：

- `relay`: Linux Docker Agent
- `server`: macOS 原生 Agent
- `client`: Windows 原生 Agent

## 2. 仓库内关键入口

- `controller/webui.py`
  中央 Panel 入口。
- `agents/service.py`
  常驻 Agent 服务入口。
- `docker-compose.yml`
  Panel 的 Docker 启动方式。
- `docker/relay-agent.compose.yml`
  Linux relay Agent 的 Docker Compose 模板。
- `bin/install_server_agent_launchd.sh`
  macOS server Agent 安装脚本。
- `bin/install_client_agent.ps1`
  Windows client Agent 安装脚本。
- `bin/start_agent_tmux.sh`
  macOS 原生 Agent 的轻量 fallback。

## 3. Linux 服务器建议迁移内容

建议一起迁移：

- 整个仓库
- `.git/`
- `data/`
  Panel 的 SQLite 数据库和 panel secret
- `config/agent/`
  已配对节点的本地 agent 配置
- `results/`
- `logs/`

不建议迁移：

- `.venv/`
- `.pytest_cache/`
- `__pycache__/`

## 4. Linux 原生开发方式

### 4.1 依赖

Ubuntu / Debian:

```bash
sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-pip iperf3 git
```

Rocky / RHEL / CentOS:

```bash
sudo dnf install -y python3 python3-pip iperf3 git iputils
```

### 4.2 初始化

```bash
cd /path/to/Frp-network-evaluation
bash bin/bootstrap_linux.sh
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
```

### 4.3 测试

```bash
source .venv/bin/activate
python -m pytest -q
```

### 4.4 启动 Panel

```bash
source .venv/bin/activate
bash bin/start_webui.sh
```

默认地址：

```text
http://127.0.0.1:8765
```

页面分工：

- `/`
  公开网络质量看板。
- `/login`
  管理员登录入口。
- `/admin`
  需要登录后访问的管理页面。

远程 Linux 服务器建议通过本地端口转发访问：

```bash
ssh -L 8765:127.0.0.1:8765 <user>@<linux-host>
```

## 5. Linux Docker 方式

### 5.1 Panel

```bash
cd /path/to/Frp-network-evaluation
export MC_NETPROBE_WEBUI_PORT=8765
bash bin/start_webui_docker.sh
```

或者：

```bash
docker compose up --build -d
```

验证：

```bash
docker compose ps
curl http://127.0.0.1:8765/api/v1/public-dashboard
docker compose logs -f panel
```

Panel 的持久化目录：

- `./data -> /app/data`
- `./config/agent -> /app/config/agent`
- `./results -> /app/results`
- `./logs -> /app/logs`

### 5.2 Relay Agent

relay 节点的推荐方式是 Docker Agent：

```bash
PANEL_URL="http://<panel-host>:8765" \
PAIR_CODE="<from-panel>" \
NODE_NAME="relay-1" \
ROLE="relay" \
RUNTIME_MODE="docker-linux" \
AGENT_PORT="9870" \
docker compose -f docker/relay-agent.compose.yml up -d --build
```

验证：

```bash
docker compose -f docker/relay-agent.compose.yml ps
curl http://127.0.0.1:9870/api/v1/status
```

## 6. 配对流程

统一流程：

1. 先启动 Panel。
2. 访问 `/login` 或 `/admin`，使用管理员账号登录。
3. 在管理页面中创建 `client / relay / server` 三个节点卡片。
4. 点击 `生成配对命令`。
5. 在目标机器上执行命令。
6. 等待节点状态从 `unpaired` 变成：
   - `online`
   - `push-only`
   - `heartbeat-degraded`

状态解释：

- `online`
  Push + Pull 都可用。
- `push-only`
  只有 heartbeat 可用，Panel 不可直连该 Agent。
- `heartbeat-degraded`
  Panel 可直连，但 Agent 主动 heartbeat 异常。
- `offline`
  两者都不可用。

## 7. 推荐的 Linux 验证顺序

1. `python -m pytest -q`
2. 原生启动 Panel 并访问 `/`、`/login`、`/api/v1/public-dashboard`
3. Docker 启动 Panel 并确认 `healthy`
4. 在 Linux relay 上用 `docker/relay-agent.compose.yml` 起 Agent
5. 在 macOS server 上执行 `bin/install_server_agent_launchd.sh`
6. 在 Windows client 上执行 `bin/install_client_agent.ps1`
7. 在 Panel 里触发一次 `full` 手动运行
8. 检查 `results/run-*/report.html`

## 8. 已知事项

- 如果没有设置 `MC_NETPROBE_ADMIN_PASSWORD`，Panel 会自动生成管理员密码并写入 `data/admin-password.txt`，默认用户名是 `admin`。
- `iperf3` 缺失时，吞吐相关 probe 会明确失败，但其他 probe 继续执行。
- macOS server 不建议强行使用 Docker Desktop 采集宿主机网络指标；默认改用原生 Agent。
- Windows client 作为正式监控节点仍支持，但推荐通过计划任务常驻，而不是 Docker。
- `main.py` 仍保留给本地调试使用，但不是主部署路径。
