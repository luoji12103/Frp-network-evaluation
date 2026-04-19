# 从 0 到上线：mc-netprobe 完整部署与客户端加入教程

这篇教程面向第一次部署 `mc-netprobe` 的同学。你不需要先理解全部源码，只要知道这套系统由一个管理面板和三个节点组成：

- `Panel`：中心控制台，负责登录、配对节点、发起监测、展示结果。
- `client`：玩家或客户端所在机器，通常是 Windows。
- `relay`：FRP 中转或公网入口机器，通常是 Linux Docker。
- `server`：Minecraft 服务端所在机器，本项目当前重点支持 macOS launchd 常驻。

上线成功的标准很朴素：Panel 能打开，三个节点都已配对并在线，发布验收没有失败项，然后手动跑一次 `full` 监测并完成。

## 0. 先准备一张部署表

开始前先把下面这些值填好。后面的命令都用这些占位符。

```text
Panel 地址:        http://<panel-ip-or-domain>:8765
Panel 管理员用户:  admin
Panel 管理员密码:  <your-admin-password>

client 节点名:     client-node
client 地址:       <client-tailnet-ip-or-lan-ip>
client Agent:      http://<client-ip>:9870
client Bridge:     http://<client-ip>:9871

relay 节点名:      relay-node
relay 地址:        <relay-tailnet-ip-or-lan-ip>
relay Agent:       http://<relay-ip>:9870
relay Bridge:      http://<relay-ip>:9871

server 节点名:     server-node
server 地址:       <server-tailnet-ip-or-lan-ip>
server Agent:      http://<server-ip>:9870
server Bridge:     http://<server-ip>:9871
```

如果你用的是 Headscale / Tailscale / ZeroTier 这类虚拟局域网，推荐这里全部填虚拟局域网 IP。这样 Panel 和节点之间的管理流量不会暴露到公网。

## 1. 先理解两个端口

每个节点默认会开两个本地服务：

- `9870`：Agent 端口，Panel 用它下发探测任务，也可以健康检查。
- `9871`：Control Bridge 端口，Panel 用它做受限运维动作，比如同步运行态、查看日志摘录、重启节点 Agent。

如果你想改成更高位端口，可以改启动命令里的 `ListenPort` / `AGENT_PORT` / `--listen-port`。Control Bridge 默认就是 Agent 端口加 1。

安全建议：

- 只允许 Panel 所在内网或虚拟局域网访问这些端口。
- 不要把 `9870/9871` 直接暴露到公网。
- 不要把管理员密码、pair code、node token 写到博客、工单或截图里。

## 2. 在 Panel 机器上部署管理面板

进入仓库目录：

```bash
cd /path/to/Frp-network-evaluation
git rev-parse --short=12 HEAD
```

设置管理员账号密码。第一次上线建议显式设置，不要依赖自动生成密码：

```bash
export MC_NETPROBE_ADMIN_USERNAME=admin
export MC_NETPROBE_ADMIN_PASSWORD='<your-admin-password>'
```

用 Docker 启动 Panel：

```bash
bash bin/start_webui_docker.sh
```

这个脚本会启动两个容器：

- `mc-netprobe-panel`
- `mc-netprobe-panel-control-bridge`

它也会持久化这些目录：

- `data/`：数据库和管理员密码文件
- `config/agent/`：节点 Agent 配置
- `results/`：每次监测导出的结果
- `logs/`：日志目录

如果你是在没有 `.git` 信息的发布包里部署，页面版本可能显示 `unknown`。上线时建议显式传入 build ref：

```bash
MC_NETPROBE_RELEASE_VERSION=1.1.0 \
MC_NETPROBE_BUILD_REF="$(git rev-parse --short=12 HEAD)" \
bash bin/start_webui_docker.sh
```

验证 Panel 是否启动：

```bash
curl -s http://127.0.0.1:8765/api/v1/version | jq
curl -s http://127.0.0.1:8765/api/v1/public-dashboard | jq '.build,.generated_at'
```

浏览器打开：

```text
http://<panel-ip-or-domain>:8765/
```

常用页面：

- `/`：公开看板，不需要登录。
- `/login`：管理员登录。
- `/admin`：管理后台。

页面右上角应该能看到类似：

```text
v1.1.0 · <commit>
```

如果显示 `unknown`，说明这次构建没有带上 commit 标识。功能可能能用，但不建议作为正式上线版本。

## 3. 登录后台并创建三个节点

打开：

```text
http://<panel-ip-or-domain>:8765/login
```

登录后进入 `/admin`。在节点管理区域创建或保存三个节点。

`client` 节点建议这样填：

```text
node_name: client-node
role: client
runtime_mode: native-windows
configured_pull_url: http://<client-ip>:9870
enabled: true
```

`relay` 节点建议这样填：

```text
node_name: relay-node
role: relay
runtime_mode: docker-linux
configured_pull_url: http://<relay-ip>:9870
enabled: true
```

`server` 节点建议这样填：

```text
node_name: server-node
role: server
runtime_mode: native-macos
configured_pull_url: http://<server-ip>:9870
enabled: true
```

说明一下 `configured_pull_url`：

- 这是管理员明确告诉 Panel “去哪里连这个节点”的地址。
- Agent 自己上报的地址只用于诊断，不会覆盖这个配置。
- 如果后台提示 configured / advertised endpoint mismatch，先检查你填的 IP、端口和 Agent 实际监听地址是否一致。

每个节点保存后，点击 `生成配对命令`。Panel 会生成一条主命令和一条 fallback 命令。pair code 有有效期，建议生成后马上去对应机器执行。

## 4. 加入 Linux relay 节点

在 relay 机器上准备 Docker 和 Docker Compose Plugin，然后进入仓库目录：

```bash
cd /path/to/Frp-network-evaluation
```

推荐直接使用后台生成的 relay 配对命令。如果你手动写，命令长这样：

```bash
PANEL_URL="http://<panel-ip-or-domain>:8765" \
PAIR_CODE="<from-panel>" \
NODE_NAME="relay-node" \
ROLE="relay" \
RUNTIME_MODE="docker-linux" \
AGENT_PORT="9870" \
CONTROL_PORT="9871" \
AGENT_ADVERTISE_URL="http://<relay-ip>:9870" \
CONTROL_ADVERTISE_URL="http://<relay-ip>:9871" \
docker compose -f docker/relay-agent.compose.yml up -d --build
```

检查容器：

```bash
docker compose -f docker/relay-agent.compose.yml ps
docker compose -f docker/relay-agent.compose.yml logs --tail=100 relay-agent relay-control-bridge
```

检查健康状态：

```bash
curl -s http://127.0.0.1:9870/api/v1/health | jq
curl -s http://127.0.0.1:9870/api/v1/version | jq
```

如果你在 Panel 机器上检查，可以用 relay 的内网或虚拟局域网 IP：

```bash
curl -s http://<relay-ip>:9870/api/v1/health | jq
curl -s http://<relay-ip>:9870/api/v1/version | jq
```

Control Bridge 端口有 token 保护，直接 curl 可能返回 `401`，这是正常的。Panel 会带节点 token 去访问它。

回到 `/admin`，relay 节点应该从 `unpaired` 变成 `online`、`push-only` 或 `pull-only`。上线前最好是 `online`。

## 5. 加入 macOS server 节点

在 macOS server 机器上进入仓库目录：

```bash
cd /path/to/Frp-network-evaluation
```

准备依赖：

```bash
bash bin/bootstrap_mac.sh
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
```

如果你希望 Agent 只监听虚拟局域网 IP，可以先写一个最小配置。下面例子把 server 绑定到 `<server-ip>`，并改用高位端口 `39870/39871`：

```bash
mkdir -p config/agent
cat > config/agent/server.yaml <<'YAML'
listen_host: <server-ip>
listen_port: 39870
control_port: 39871
YAML
```

此时后台 `server` 节点的 `configured_pull_url` 也要填：

```text
http://<server-ip>:39870
```

如果你使用默认端口，就不需要写上面的配置，直接安装：

```bash
bash bin/install_server_agent_launchd.sh \
  --panel-url "http://<panel-ip-or-domain>:8765" \
  --pair-code "<from-panel>" \
  --node-name "server-node" \
  --role "server" \
  --listen-port 9870
```

如果你用了高位端口，则执行：

```bash
bash bin/install_server_agent_launchd.sh \
  --panel-url "http://<panel-ip-or-domain>:8765" \
  --pair-code "<from-panel>" \
  --node-name "server-node" \
  --role "server" \
  --listen-port 39870
```

安装脚本会创建两个 launchd 服务：

- `com.mc-netprobe.server.agent`
- `com.mc-netprobe.server.control-bridge`

检查 launchd：

```bash
plutil -lint ~/Library/LaunchAgents/com.mc-netprobe.server.agent.plist
plutil -lint ~/Library/LaunchAgents/com.mc-netprobe.server.control-bridge.plist
launchctl print gui/$(id -u)/com.mc-netprobe.server.agent
launchctl print gui/$(id -u)/com.mc-netprobe.server.control-bridge
```

检查日志：

```bash
tail -n 80 ~/Library/Logs/mc-netprobe/server-agent.launchd.log
tail -n 80 ~/Library/Logs/mc-netprobe/server-control-bridge.launchd.log
```

检查 Agent：

```bash
curl -s http://127.0.0.1:9870/api/v1/health | jq
curl -s http://127.0.0.1:9870/api/v1/version | jq
```

如果你用了高位端口：

```bash
curl -s http://<server-ip>:39870/api/v1/health | jq
curl -s http://<server-ip>:39870/api/v1/version | jq
```

回到 `/admin`，server 节点应该显示在线，并且运行态里能看到 supervisor / control bridge 信息。

## 6. 加入 Windows client 节点

在 Windows client 机器上打开 PowerShell，进入仓库目录：

```powershell
cd C:\path\to\Frp-network-evaluation
```

准备依赖：

```powershell
.\bin\bootstrap_windows.ps1
python -m pip install -r requirements-dev.txt
```

推荐直接复制后台生成的 client 配对命令。手动命令长这样：

```powershell
powershell -ExecutionPolicy Bypass -File bin/install_client_agent.ps1 `
  -PanelUrl "http://<panel-ip-or-domain>:8765" `
  -PairCode "<from-panel>" `
  -NodeName "client-node" `
  -Role "client" `
  -ListenPort 9870
```

安装脚本会创建两个计划任务：

- `mc-netprobe-client-agent`
- `mc-netprobe-client-control-bridge`

检查计划任务：

```powershell
Get-ScheduledTask -TaskName mc-netprobe-client-agent
Get-ScheduledTask -TaskName mc-netprobe-client-control-bridge
```

检查本机 Agent：

```powershell
curl http://127.0.0.1:9870/api/v1/health
curl http://127.0.0.1:9870/api/v1/version
```

如果 Windows 防火墙拦截了 Panel 访问，请只对你的内网或虚拟局域网放行 `9870` 和 `9871`，不要开到公网。

回到 `/admin`，client 节点应该显示在线。到这里，三节点接入就完成了。

## 7. 可选：不用封装脚本的手动部署方式

上面的流程优先使用仓库里的 helper 脚本，因为它们会帮你处理目录、配置、日志和持久化服务。真实上线时我仍然推荐用 helper 脚本。

但排障、教学、特殊环境部署时，你可能想知道“脚本背后到底做了什么”。这一节就是手动版。它不引入新接口，只是把脚本拆成更透明的命令。

### 7.1 手动启动 Panel：Native 模式

适合本地开发、临时演示、没有 Docker 的小环境。

```bash
cd /path/to/Frp-network-evaluation
bash bin/bootstrap_linux.sh
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
mkdir -p data config/agent results logs
```

设置管理员账号、版本号和日志文件：

```bash
export MC_NETPROBE_ADMIN_USERNAME=admin
export MC_NETPROBE_ADMIN_PASSWORD='<your-admin-password>'
export MC_NETPROBE_RELEASE_VERSION=1.1.0
export MC_NETPROBE_BUILD_REF="$(git rev-parse --short=12 HEAD)"
export MC_NETPROBE_PANEL_LOG_FILE="$PWD/logs/panel-native.log"
```

启动 Panel：

```bash
python -m controller.webui \
  --host 0.0.0.0 \
  --port 8765 \
  --db-path data/monitor.db \
  >> logs/panel-native.log 2>&1
```

另开一个终端验证：

```bash
curl -s http://127.0.0.1:8765/api/v1/version | jq
curl -s http://127.0.0.1:8765/api/v1/public-dashboard | jq '.build,.generated_at'
```

注意：Native Panel 默认没有 Docker 级强控制。也就是说后台可以看 runtime、暂停或恢复 scheduler、tail 本地日志，但不能像 Docker Panel 那样通过 panel control bridge 可靠地重启自身容器。

### 7.2 手动启动 Panel：Docker 模式但不用 `start_webui_docker.sh`

这个方式等价于把脚本里的环境变量自己写出来。

```bash
cd /path/to/Frp-network-evaluation
mkdir -p data config/agent results logs

export MC_NETPROBE_WEBUI_PORT=8765
export MC_NETPROBE_ADMIN_USERNAME=admin
export MC_NETPROBE_ADMIN_PASSWORD='<your-admin-password>'
export MC_NETPROBE_RELEASE_VERSION=1.1.0
export MC_NETPROBE_BUILD_REF="$(git rev-parse --short=12 HEAD)"

docker compose up --build -d
```

检查：

```bash
docker compose ps
docker compose logs --tail=100 panel panel-control-bridge
curl -s http://127.0.0.1:8765/api/v1/version | jq
```

如果这一步版本仍然显示 `unknown`，说明当前目录没有 git 信息或环境变量没有传进 compose。先确认：

```bash
echo "$MC_NETPROBE_BUILD_REF"
docker compose config | grep MC_NETPROBE_BUILD_REF
```

### 7.3 手动启动 relay：Docker Compose 透明版

relay 本来就是 Docker Compose 部署。这里的“手动”意思是不用后台复制的命令，而是自己把变量填完整。

```bash
cd /path/to/Frp-network-evaluation

export PANEL_URL="http://<panel-ip-or-domain>:8765"
export PAIR_CODE="<from-panel>"
export NODE_NAME="relay-node"
export ROLE="relay"
export RUNTIME_MODE="docker-linux"
export AGENT_PORT=9870
export CONTROL_PORT=9871
export AGENT_ADVERTISE_URL="http://<relay-ip>:9870"
export CONTROL_ADVERTISE_URL="http://<relay-ip>:9871"

docker compose -f docker/relay-agent.compose.yml up -d --build
```

检查：

```bash
docker compose -f docker/relay-agent.compose.yml ps
docker compose -f docker/relay-agent.compose.yml logs --tail=100 relay-agent relay-control-bridge
curl -s http://127.0.0.1:9870/api/v1/health | jq
curl -s http://127.0.0.1:9870/api/v1/version | jq
```

### 7.4 手动部署 macOS server：不用 shell 安装脚本，但仍使用 launchd

这一节相当于手动执行 `bin/install_server_agent_launchd.sh` 的核心步骤。适合你想逐步看清 plist 是怎么生成和加载的情况。

进入仓库：

```bash
cd /path/to/Frp-network-evaluation
bash bin/bootstrap_mac.sh
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
```

准备配置。下面例子使用默认端口 `9870/9871`：

```bash
mkdir -p config/agent "$HOME/Library/LaunchAgents" "$HOME/Library/Logs/mc-netprobe"
cat > config/agent/server.yaml <<'YAML'
listen_host: 0.0.0.0
listen_port: 9870
control_port: 9871
YAML
```

如果你只想监听虚拟局域网 IP，把 `listen_host` 改成 `<server-ip>`。

设置变量：

```bash
export PANEL_URL="http://<panel-ip-or-domain>:8765"
export PAIR_CODE="<from-panel>"
export NODE_NAME="server-node"
export ROLE="server"
export LISTEN_HOST="0.0.0.0"
export LISTEN_PORT=9870
export CONTROL_PORT=9871
export PYTHON_BIN="$(command -v python3)"
export DOMAIN_TARGET="gui/$(id -u)"
```

生成 Agent plist：

```bash
python -m agents.launchd \
  --repo-root "$PWD" \
  --home-dir "$HOME" \
  --python-bin "$PYTHON_BIN" \
  --panel-url "$PANEL_URL" \
  --pair-code "$PAIR_CODE" \
  --node-name "$NODE_NAME" \
  --role "$ROLE" \
  --runtime-mode native-macos \
  --listen-host "$LISTEN_HOST" \
  --listen-port "$LISTEN_PORT" \
  --control-port "$CONTROL_PORT" \
  --config config/agent/server.yaml \
  --label com.mc-netprobe.server.agent
```

生成 Control Bridge plist：

```bash
python -m agents.launchd_control_bridge \
  --repo-root "$PWD" \
  --home-dir "$HOME" \
  --python-bin "$PYTHON_BIN" \
  --bridge-host "$LISTEN_HOST" \
  --bridge-port "$CONTROL_PORT" \
  --agent-config config/agent/server.yaml \
  --agent-label com.mc-netprobe.server.agent \
  --bridge-label com.mc-netprobe.server.control-bridge \
  --bridge-log-path "$HOME/Library/Logs/mc-netprobe/server-control-bridge.launchd.log"
```

校验 plist：

```bash
plutil -lint "$HOME/Library/LaunchAgents/com.mc-netprobe.server.agent.plist"
plutil -lint "$HOME/Library/LaunchAgents/com.mc-netprobe.server.control-bridge.plist"
```

加载并启动：

```bash
launchctl bootout "$DOMAIN_TARGET/com.mc-netprobe.server.agent" >/dev/null 2>&1 || true
launchctl bootout "$DOMAIN_TARGET/com.mc-netprobe.server.control-bridge" >/dev/null 2>&1 || true

launchctl bootstrap "$DOMAIN_TARGET" "$HOME/Library/LaunchAgents/com.mc-netprobe.server.agent.plist"
launchctl bootstrap "$DOMAIN_TARGET" "$HOME/Library/LaunchAgents/com.mc-netprobe.server.control-bridge.plist"

launchctl kickstart -k "$DOMAIN_TARGET/com.mc-netprobe.server.agent"
launchctl kickstart -k "$DOMAIN_TARGET/com.mc-netprobe.server.control-bridge"
```

检查：

```bash
launchctl print "$DOMAIN_TARGET/com.mc-netprobe.server.agent"
launchctl print "$DOMAIN_TARGET/com.mc-netprobe.server.control-bridge"
tail -n 80 "$HOME/Library/Logs/mc-netprobe/server-agent.launchd.log"
tail -n 80 "$HOME/Library/Logs/mc-netprobe/server-control-bridge.launchd.log"
curl -s http://127.0.0.1:9870/api/v1/health | jq
curl -s http://127.0.0.1:9870/api/v1/version | jq
```

如果你只是临时联调，不想写 launchd，也可以直接跑 Agent：

```bash
python -m agents.service \
  --config config/agent/server.yaml \
  --panel-url "http://<panel-ip-or-domain>:8765" \
  --pair-code "<from-panel>" \
  --node-name "server-node" \
  --role server \
  --runtime-mode native-macos \
  --listen-host 0.0.0.0 \
  --listen-port 9870 \
  --control-port 9871
```

但这种临时方式没有可靠 supervisor，后台的 start / stop / restart 运维动作不能完整代表真实上线状态。

### 7.5 手动部署 Windows client：不用 PowerShell 安装脚本

这一节手动注册计划任务，效果接近 `bin/install_client_agent.ps1`。

在 PowerShell 里进入仓库：

```powershell
cd C:\path\to\Frp-network-evaluation
.\bin\bootstrap_windows.ps1
python -m pip install -r requirements-dev.txt
```

设置变量：

```powershell
$panelUrl = "http://<panel-ip-or-domain>:8765"
$pairCode = "<from-panel>"
$nodeName = "client-node"
$role = "client"
$listenPort = 9870
$controlPort = 9871
$repoRoot = (Get-Location).Path
$python = "python"
$configPath = Join-Path $repoRoot "config\agent\client.yaml"
$logDir = Join-Path $repoRoot "logs"
$agentLog = Join-Path $logDir "client-agent.log"
$bridgeLog = Join-Path $logDir "client-control-bridge.log"
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $configPath) | Out-Null
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
```

准备任务参数：

```powershell
$agentArgs = "-m agents.service --config `"$configPath`" --panel-url `"$panelUrl`" --pair-code `"$pairCode`" --node-name `"$nodeName`" --role `"$role`" --runtime-mode native-windows --listen-host 0.0.0.0 --listen-port $listenPort --control-port $controlPort"
$bridgeArgs = "-m controller.control_bridge --mode node --adapter windows-task --host 0.0.0.0 --port $controlPort --agent-config `"$configPath`" --task-name `"mc-netprobe-client-agent`" --log-path `"$agentLog`""
```

注册并启动计划任务：

```powershell
$agentAction = New-ScheduledTaskAction -Execute $python -Argument $agentArgs -WorkingDirectory $repoRoot
$bridgeAction = New-ScheduledTaskAction -Execute $python -Argument $bridgeArgs -WorkingDirectory $repoRoot
$trigger = New-ScheduledTaskTrigger -AtStartup
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)

Register-ScheduledTask -TaskName "mc-netprobe-client-agent" -Action $agentAction -Trigger $trigger -Settings $settings -Description "mc-netprobe persistent client agent" -Force | Out-Null
Register-ScheduledTask -TaskName "mc-netprobe-client-control-bridge" -Action $bridgeAction -Trigger $trigger -Settings $settings -Description "mc-netprobe control bridge for client agent" -Force | Out-Null

Start-ScheduledTask -TaskName "mc-netprobe-client-agent"
Start-ScheduledTask -TaskName "mc-netprobe-client-control-bridge"
```

检查：

```powershell
Get-ScheduledTask -TaskName mc-netprobe-client-agent
Get-ScheduledTask -TaskName mc-netprobe-client-control-bridge
curl http://127.0.0.1:9870/api/v1/health
curl http://127.0.0.1:9870/api/v1/version
```

临时联调也可以不注册计划任务，直接跑：

```powershell
python -m agents.service --config config/agent/client.yaml --panel-url "http://<panel-ip-or-domain>:8765" --pair-code "<from-panel>" --node-name "client-node" --role client --runtime-mode native-windows --listen-host 0.0.0.0 --listen-port 9870 --control-port 9871
```

同样提醒：临时方式没有可靠 supervisor，不适合作为正式上线最终状态。

### 7.6 手动方式什么时候该用，什么时候不该用

适合手动方式的场景：

- 你想学习每一步具体做了什么。
- helper 脚本在某台机器上失败，需要拆开排障。
- 你在临时实验环境里只想快速跑通 Agent。

不适合手动方式的场景：

- 正式上线后需要开机自启。
- 需要后台 start / stop / restart 运维动作完全可用。
- 需要长期稳定记录日志和运行态。

正式上线建议还是回到前面的持久化流程：Panel Docker、relay Docker、macOS launchd、Windows Scheduled Task。

## 8. 做一次发布验收

进入 `/admin` 的管理区域，找到“发布验收”或 release validation 卡片，点击执行。

它会只读检查这些内容：

- Panel `/api/v1/version`
- Panel runtime 和 scheduler
- Panel control bridge
- 每个已启用节点的 `/api/v1/version`
- 每个节点的 `/api/v1/health`
- 每个节点的 token-protected `/api/v1/status`
- 每个节点的 control bridge runtime
- Panel 和 Agent 的 build / protocol 是否一致

验收状态含义：

- `pass`：通过。
- `warn`：可运行但有上线风险，例如 Panel 和 Agent build 不一致。
- `fail`：上线阻塞，例如节点健康检查不通、协议不兼容、control bridge 不可达。
- `skip`：跳过，例如节点禁用或未配对。

初版上线建议达到：

```text
summary.fail == 0
summary.skip == 0
```

最好也让 `warn == 0`。如果只是短期 build mismatch，可以先重部署对应节点或 Panel，让右上角版本和 `/api/v1/version` 都显示同一个 commit。

你也可以用命令检查 public payload：

```bash
curl -s http://<panel-ip-or-domain>:8765/api/v1/version | jq
curl -s http://<panel-ip-or-domain>:8765/api/v1/public-dashboard | jq '.build,.generated_at,.nodes'
```

## 9. 跑一次 full 监测

确认三个节点都不是 `unpaired` 或 `offline` 后，在 `/admin` 点击“手动执行完整监测”。

一次正常的 `full` run 会包含：

- `system`：采集节点 CPU、内存、进程等系统信息。
- `baseline`：跑 ping / TCP 等基础链路探测。
- `capacity`：跑吞吐、负载膨胀等容量类探测。

你要观察这些地方：

- run 状态从 `running` 变成 `completed`。
- run detail 没有残留旧 blocker。
- run events 能看到每个阶段的事件。
- node card 状态和 Operations focus 里的状态一致。
- public dashboard 能展示最新摘要。

完成后，结果会落在：

```text
results/<run-id>/
```

常见文件：

- `raw.json`
- `summary.csv`
- `report.html`

## 10. 上线前最后检查清单

Panel：

```bash
curl -s http://<panel-ip-or-domain>:8765/api/v1/version | jq
curl -s http://<panel-ip-or-domain>:8765/api/v1/public-dashboard | jq '.build,.generated_at'
```

relay：

```bash
curl -s http://<relay-ip>:9870/api/v1/health | jq
curl -s http://<relay-ip>:9870/api/v1/version | jq
```

server：

```bash
curl -s http://<server-ip>:9870/api/v1/health | jq
curl -s http://<server-ip>:9870/api/v1/version | jq
```

client：

```powershell
curl http://<client-ip>:9870/api/v1/health
curl http://<client-ip>:9870/api/v1/version
```

后台页面：

- 三个节点都已配对。
- 三个节点都已启用。
- 三个节点至少能正常 heartbeat。
- 最好三个节点都是 `online`。
- 发布验收没有 `fail`。
- full run 已经完成。
- 页面右上角版本号和 `/api/v1/version` 一致。

## 11. 常见问题

### 页面能打开，但右上角显示 unknown

这通常说明 Docker 构建时没有拿到 git commit。重新部署时显式传入：

```bash
MC_NETPROBE_RELEASE_VERSION=1.1.0 \
MC_NETPROBE_BUILD_REF="$(git rev-parse --short=12 HEAD)" \
bash bin/start_webui_docker.sh
```

### 节点一直 unpaired

优先检查：

- pair code 是否过期。
- 节点机器能否访问 Panel URL。
- `node_name`、`role`、`runtime_mode` 是否和后台节点卡片一致。
- Agent 日志里是否有配对失败信息。

处理方式通常是重新在后台点 `生成配对命令`，然后在节点机器重新执行。

### 节点是 push-only

这表示 Agent 能通过 heartbeat 推送到 Panel，但 Panel 不能直连 Agent。常见原因：

- `configured_pull_url` 填错。
- 防火墙没有放行 Agent 端口。
- Agent 监听在 `127.0.0.1`，Panel 不可能从远端连到。
- tailnet/VLAN IP 写错。

修复后，在后台点 `sync_runtime` 或等下一轮刷新。

### 节点是 pull-only

这表示 Panel 能直连 Agent，但 Agent heartbeat 有问题。常见原因：

- 节点访问不到 Panel URL。
- Panel URL 写错。
- 代理、防火墙或 DNS 阻断了节点到 Panel 的请求。
- 节点 token 或配置文件异常。

优先看节点 Agent 日志。

### control bridge 不可达

Agent 可能在线，但运维控制桥不在线。检查：

- bridge 端口是否放行。
- relay 的 `relay-control-bridge` 容器是否运行。
- macOS 的 `com.mc-netprobe.server.control-bridge` 是否存在。
- Windows 的 `mc-netprobe-client-control-bridge` 计划任务是否运行。

注意：Control Bridge 有认证，手动 curl 返回 `401` 不一定是坏事。Panel 带 token 访问失败才算真的不可达。

### full run 卡在 running

先打开 run detail 和 run events。重点看：

- 当前 blocker 是哪个节点。
- latest queue job 是否 pending / leased / timeout。
- latest probe 是否失败。
- Operations focus 是否给了 CTA。

不要立刻重启所有服务。先按后台提示定位到具体节点，查看对应 Agent 或 Control Bridge 日志。

## 12. 初版上线建议

初版上线窗口里，不建议继续做大功能改动。建议只做这几件事：

- 保持 Panel 和 Agent build 一致。
- 确认三节点都在线。
- 确认 release validation 没有 fail。
- 确认 full run 可以完成。
- 确认 public dashboard 不泄露 endpoint。
- 记录当前 commit、部署时间、Panel URL、三节点 IP、第一次 full run 的 run id。

做到这里，`mc-netprobe` 的第一版完整链路就可以稳定上线了。后续 UI 美化、告警中心、自动修复、多 Panel 灾备，都可以放到下一个版本，不要在上线窗口里把地板拆了重新铺。
