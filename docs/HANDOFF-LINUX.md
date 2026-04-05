# Linux Handoff

本文档用于把 `mc-netprobe` 从当前 Windows 开发机切换到 Linux 服务器，继续开发、联调和测试。

## 1. 当前状态

当前仓库已经具备以下能力：

- CLI 主入口：`python main.py --topology ... --thresholds ... --scenarios ...`
- 三角色自动化链路测试：`client / relay / server`
- 跨平台 probe：Windows / macOS / Linux `ping` 解析、TCP connect、`iperf3` 吞吐、系统快照
- SSH 编排：通过 `controller/ssh_exec.py` 从控制端联动远端节点
- 导出结果：`raw.json`、`summary.csv`、`report.html`
- 内置 Web UI：配置三台机器并后台发起测试
- Docker 化 Web UI：`docker compose up --build -d`
- 面向小白的角色脚本：
  - `bin/start_server_mac.sh`
  - `bin/start_relay_linux.sh`
  - `bin/start_client_windows.ps1`

## 2. 仓库内关键入口

- `main.py`
  直接执行一次完整测试。
- `controller/webui.py`
  启动内置 Web UI。
- `controller/pipeline.py`
  CLI 和 Web UI 共用的执行管线。
- `docker-compose.yml`
  Docker 一键启动 Web UI。
- `config/topology.example.yaml`
- `config/thresholds.example.yaml`
- `config/scenarios.example.yaml`
  三份基础配置示例。

## 3. 建议迁移内容

切到 Linux 服务器时，建议一并带上：

- 整个仓库
- `.git/`
- `config/webui/`
  如果你希望保留当前 Web UI 上已经填写过的节点配置
- `results/`
  如果你希望保留历史测试产物

不建议迁移：

- `.venv/`
- `.pytest_cache/`
- `__pycache__/`

## 4. Linux 原生开发方式

### 4.1 准备环境

建议 Linux 服务器至少具备：

- `python3.11+`
- `openssh-client`
- `iperf3`
- `git`

如果缺包，可以先按发行版执行：

```bash
sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-pip openssh-client iperf3 git
```

或在 Rocky / RHEL / CentOS 这类系统上执行：

```bash
sudo dnf install -y python3 python3-pip openssh-clients iperf3 git iputils
```

### 4.2 初始化项目

```bash
cd /path/to/Frp-network-evaluation
bash bin/bootstrap_linux.sh
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
```

### 4.3 跑测试和开发校验

```bash
source .venv/bin/activate
python -m pytest -q
python main.py \
  --topology config/topology.example.yaml \
  --thresholds config/thresholds.example.yaml \
  --scenarios config/scenarios.example.yaml
```

说明：

- 当节点配置为 `local: true` 时，控制端现在会自动按当前 Linux 宿主机平台执行本地 probe，不会再误用示例 YAML 里的其他 `os` 值。

### 4.4 启动 Web UI

```bash
source .venv/bin/activate
bash bin/start_webui.sh
```

默认地址：

```text
http://127.0.0.1:8765
```

如果 Linux 服务器是远程机器，通常这样访问：

```bash
ssh -L 8765:127.0.0.1:8765 <user>@<linux-host>
```

然后在本机浏览器打开 `http://127.0.0.1:8765`。

## 5. Linux Docker 方式

### 5.1 前置条件

Linux 服务器需要：

- Docker Engine
- Docker Compose Plugin

典型检查命令：

```bash
docker --version
docker compose version
```

### 5.2 启动

```bash
cd /path/to/Frp-network-evaluation
export MC_NETPROBE_SSH_DIR="$HOME/.ssh"
export MC_NETPROBE_WEBUI_PORT=8765
bash bin/start_webui_docker.sh
```

或直接：

```bash
docker compose up --build -d
```

### 5.3 验证

```bash
docker compose ps
curl http://127.0.0.1:8765/api/state
docker compose logs -f webui
```

### 5.4 Docker 持久化目录

Compose 已经挂载以下目录：

- `./config/webui -> /app/config/webui`
- `./results -> /app/results`
- `./logs -> /app/logs`
- `${MC_NETPROBE_SSH_DIR:-./docker/ssh} -> /home/app/.ssh`

因此：

- Web UI 上填写过的三节点配置会保留
- 每次测试的结果会保留
- 容器可复用宿主机的 SSH key 访问远端节点

## 6. SSH 与三机联动要求

当前控制端可以是 Linux 服务器本机，也可以是 Docker 容器里的 Web UI 进程。无论哪种方式，都需要它能 SSH 到远端节点。

至少确认以下几点：

- Linux 控制端能 SSH 到 `relay`
- Linux 控制端能 SSH 到 `server`
- 如果 `client` 不是本机执行，也要能 SSH 到 `client`
- 远端节点上的 `project_root` 已存在当前仓库副本
- 远端节点上的 `python_bin` 可直接运行

建议先手工验证：

```bash
ssh <user>@<relay-host> "cd <project_root> && <python_bin> --version"
ssh <user>@<server-host> "cd <project_root> && <python_bin> --version"
```

## 7. Web UI 配置建议

Web UI 中应优先填写这些字段：

- `topology.nodes.client`
- `topology.nodes.relay`
- `topology.nodes.server`
- `topology.services.relay_probe`
- `topology.services.mc_public`
- `topology.services.iperf_public`
- `topology.services.mc_local`
- `topology.services.iperf_local`

如果 Linux 服务器本身就是控制端，而不是被测节点，不要把它误填成 `client / relay / server` 之一，除非它本身确实承担那个角色。

## 8. 已验证项

在当前 Windows 开发机上已经完成：

- `python -m pytest -q` 通过
- `python -m controller.webui --help` 可用
- Web UI 本地启动并成功访问 `/api/state`
- `docker compose config` 可正常解析

## 9. 待在 Linux 上补的验证

建议你切到 Linux 后优先做这几项：

1. 原生环境启动 Web UI 并访问 `http://127.0.0.1:8765/api/state`
2. `docker compose up --build -d` 实际构建镜像并确认健康检查通过
3. 用真实 `relay / server / client` 做一次完整测试
4. 检查 `results/run-*/report.html` 是否能反映分段链路和阈值异常

## 10. 已知事项

- `iperf3` 缺失时，吞吐相关 probe 会明确报错，但整次运行不会中断。
- Windows 作为正式 `client` 运行目标已支持，但不作为 Linux 版 handoff 的主开发环境。
- Docker Compose 中的 Web UI 端口已统一为容器内 `8765`，宿主侧可通过 `MC_NETPROBE_WEBUI_PORT` 改映射端口。

## 11. 推荐的 Linux 续开发顺序

1. 先用原生 Python 跑 `pytest`
2. 再原生启动 `controller.webui`
3. 确认 SSH 到三节点都正常
4. 再验证 Docker 方式
5. 最后用真实 MC / FRP / `iperf3` 环境做端到端联调
