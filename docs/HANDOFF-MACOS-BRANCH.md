# macOS Branch Handoff

本文档是 `WebUI-dev` 和 macOS 本地测试分支之间的接口冻结说明。

目标只有一个：两边并行开发，但不要互相改坏对方依赖的接口。

当前冻结合同基线：

- `main` 已切到新的结构化 `v1` Agent 通信基线：
  - `configured_pull_url` / `advertised_pull_url` / `effective_pull_url`
  - `endpoints` / `connectivity`
  - `identity` / `endpoint` / `capabilities` / `runtime_status`
- `main` 也已经包含独立运维控制面基线：
  - `runtime` / `supervisor`
  - `control_action`
  - admin runtime / actions API
  - host `control bridge`
- 本文档放在 `main`，作为协作约束和 handoff 基准

## 1. 分支职责

### `WebUI-dev`

负责：

- Panel / WebUI
- 公开页、登录页、管理页
- Panel 的统计、告警、历史看板
- 前端静态资源和图表

主要目录：

- `controller/webui.py`
- `controller/panel_store.py`
- `controller/panel_models.py`
- `controller/webui_template.html`
- `controller/public_webui_template.html`
- `controller/login_template.html`
- `controller/assets/`

### macOS 本地测试分支

建议单独建分支，例如：

- `macos-agent-local`

负责：

- macOS 原生 Agent 的本地调试
- `launchd` 安装/重启/自恢复
- macOS control bridge 安装与本地宿主启停
- macOS 上 probe 执行兼容性
- Agent 本地运行稳定性

允许改动的重点目录：

- `agents/`
- `bin/install_server_agent_launchd.sh`
- `bin/start_agent_tmux.sh`
- `config/agent/`
- `tests/test_agent_service.py`
- macOS 相关文档

## 2. macOS 分支禁止修改项

macOS 分支不要修改以下内容，否则很容易把 WebUI / Panel 接口改崩：

- `controller/webui.py`
- `controller/webui_template.html`
- `controller/public_webui_template.html`
- `controller/login_template.html`
- `controller/assets/`
- `controller/panel_store.py` 中对外返回的 JSON 结构
- `controller/panel_models.py` 中与 WebUI / Panel API 相关的请求和响应模型
- `controller/control_bridge.py` 与 `controller/control_bridge_client.py` 的共享协议

尤其不要改这些接口的：

- 路径
- HTTP 方法
- query 参数名
- JSON 字段名
- 字段语义

## 3. WebUI-dev 禁止修改项

`WebUI-dev` 后续开发也不要去改 macOS Agent 侧的稳定接口，尤其不要改：

- `agents/service.py` 对外暴露的 API 路径
- Agent 本地配置字段名
- Agent CLI 参数名
- Panel 与 Agent 之间的认证头
- Agent 返回结果的基础结构

如果 WebUI 需要更多数据：

- 优先新增可选字段
- 不要删除、重命名、重排既有字段
- 不要改已有接口含义

## 4. 冻结的 Panel / WebUI 接口

macOS 分支不要改以下 Panel 侧接口合同。

### 页面路由

- `GET /`
- `GET /login`
- `GET /admin`
- `POST /login`
- `POST /logout`

### 公开接口

- `GET /api/state`
- `GET /api/v1/public-dashboard?time_range=24h|7d|30d`

### 管理接口

- `GET /api/v1/dashboard`
- `POST /api/v1/dashboard`
- `GET /api/v1/history`
- `GET /api/v1/admin/filters`
- `GET /api/v1/admin/overview`
- `GET /api/v1/admin/timeseries`
- `GET /api/v1/admin/path-health`
- `GET /api/v1/admin/runs`
- `GET /api/v1/admin/runs/{run_id}`
- `GET /api/v1/admin/alerts`
- `POST /api/v1/admin/alerts/{alert_id}/ack`
- `POST /api/v1/admin/alerts/{alert_id}/silence`
- `POST /api/v1/nodes`
- `GET /api/v1/nodes/{node_id}`
- `POST /api/v1/nodes/{node_id}/pair-code`
- `POST /api/v1/runs`

当前节点管理字段语义也视为冻结合同：

- `POST /api/v1/nodes` 使用 `configured_pull_url`
- 节点详情 / dashboard 节点对象使用 `endpoints` 与 `connectivity`
- 节点详情 / runtime 视图对象使用 `runtime` 与 `supervisor`
- 不再回到旧的单字段 `agent_url` 语义

当前新增的管理运维接口也视为冻结合同：

- `GET /api/v1/admin/runtime`
- `GET /api/v1/admin/actions`
- `GET /api/v1/admin/actions/{action_id}`
- `POST /api/v1/admin/nodes/{node_id}/actions`
- `POST /api/v1/admin/panel/actions`
- `GET /api/v1/admin/runs/{run_id}/events`

### 管理认证

以下行为也视为冻结合同：

- 未登录访问 `/admin` 会跳转到 `/login`
- 未登录访问管理 API 返回 `401`
- 认证方式继续使用当前管理员 Cookie

## 5. 冻结的 Agent / macOS 接口

`WebUI-dev` 不要改以下 Agent 侧合同。

### Panel 调 Agent

- `GET /api/v1/health`
- `GET /api/v1/status`
- `POST /api/v1/jobs/run`
- `GET /api/v1/results/{run_id}`

### Panel / 宿主控制桥

- `GET /api/v1/control/runtime`
- `POST /api/v1/control/actions`

### Agent 本地接口

- `POST /api/v1/pair`
- `POST /api/v1/heartbeat`

### Panel 接收 Agent

- `POST /api/v1/agents/pair`
- `POST /api/v1/agents/heartbeat`

### 认证与关键字段

不要改：

- Header: `X-Node-Token`
- Panel control bridge header: `X-Control-Token`
- `role` 枚举：`client | relay | server`
- `runtime_mode` 枚举：`docker-linux | native-macos | native-windows`
- `protocol_version` 必填，当前支持值固定为 `1`

不要改结构化通信对象的顶层语义：

- `identity`
- `endpoint`
- `capabilities`
- `runtime_status`
- `completed_jobs`
- `endpoints`
- `connectivity`
- `connectivity.diagnostic_code`
- `connectivity.attention_level`
- `connectivity.summary`
- `connectivity.recommended_step`
- `runtime`
- `supervisor`

不要改 Agent 配置字段名：

- `panel_url`
- `node_name`
- `role`
- `runtime_mode`
- `listen_host`
- `listen_port`
- `advertise_url`
- `node_token`
- `pair_code`

不要改 Agent CLI 参数名：

- `--config`
- `--panel-url`
- `--pair-code`
- `--node-name`
- `--role`
- `--runtime-mode`
- `--listen-host`
- `--listen-port`
- `--advertise-url`
- `--node-token`

不要改 Agent 运行时 endpoint 里的控制桥字段名：

- `control_listen_port`
- `control_url`

不要改节点 / Panel 运行态结构里的关键字段语义：

- `runtime.state`
- `runtime.checked_at`
- `runtime.last_error`
- `runtime.details`
- `runtime.details.available_actions`
- `runtime.details.readonly_reason`
- `runtime.details.active_action_id`
- `runtime.details.active_action_summary`
- `runtime.details.active_run_id`
- `runtime.details.active_run_summary`
- `runtime.details.active_run_severity`
- `supervisor.control_available`
- `supervisor.bridge_url`
- `supervisor.supervisor_state`
- `supervisor.process_state`
- `supervisor.pid_or_container_id`
- `supervisor.log_location`
- `supervisor.last_error`
- `supervisor.checked_at`

## 6. 双方都必须遵守的扩展规则

如果确实需要扩接口，只能按下面规则做：

1. 先更新本 handoff 文档到 `main`
2. 只能在现有结构化对象里新增可选字段，不能改旧字段
3. 不要把结构化对象重新摊平成新的顶层快捷字段
4. 如果是 breaking change，必须先更新本基线并同步测试
5. 两边都要补测试后才能合并

简单说：

- additive change 可以
- 结构化 `v1` 基线不能偷偷改语义
- 运维控制面也只能 additive 扩展，不能改既有字段含义
- 同一目标上的 lifecycle action 固定串行，不能改成堆积排队语义

## 7. macOS 分支推荐工作方式

建议 macOS 侧只做这些类型的工作：

- `launchd` 启停与开机自启修复
- macOS control bridge 的 launchd 持久化、日志与本地调试
- macOS 上 `ping` / `tcp` / `iperf3` / `system_snapshot` 兼容性
- Agent 配对后的本地持久化修复
- 心跳稳定性与后台线程稳定性
- 本机 probe 结果准确性

不建议在 macOS 分支做这些事：

- 改 WebUI 页面
- 改管理接口返回结构
- 改公开页 JSON
- 改告警中心字段
- 改管理页筛选参数名

## 8. macOS 本地测试建议

### 8.1 先准备本地 Python 环境

```bash
bash bin/bootstrap_mac.sh
.venv/bin/pip install -r requirements-dev.txt
```

### 8.2 只测 Agent，不碰 WebUI 接口

```bash
.venv/bin/python -m pytest -q tests/test_control_bridge.py tests/test_control_actions.py
.venv/bin/python -m pytest -q tests/test_launchd.py tests/test_agent_service.py tests/test_quickstart.py
.venv/bin/python -m pytest -q
```

### 8.3 推荐先走 launchd 安装链路

```bash
bash bin/install_server_agent_launchd.sh \
  --panel-url "http://panel-host:8765" \
  --pair-code "<from-panel>" \
  --node-name "server-1" \
  --role "server" \
  --listen-port 9870
```

### 8.4 本地启动 macOS Agent

```bash
.venv/bin/python -m agents.service \
  --config config/agent/server.yaml \
  --node-name server-1 \
  --role server \
  --runtime-mode native-macos \
  --listen-host 0.0.0.0 \
  --listen-port 9870
```

### 8.5 只验证冻结接口和 launchd 安装结果

```bash
plutil -lint ~/Library/LaunchAgents/com.mc-netprobe.server.agent.plist
plutil -lint ~/Library/LaunchAgents/com.mc-netprobe.server.control-bridge.plist
launchctl print gui/$(id -u)/com.mc-netprobe.server.agent
launchctl print gui/$(id -u)/com.mc-netprobe.server.control-bridge
tail -n 50 logs/server-agent.launchd.log
tail -n 50 logs/server-control-bridge.launchd.log
curl http://127.0.0.1:9870/api/v1/health
```

如果本地为了调试需要扩展信息：

- 本地存活检查优先看 `GET /api/v1/health`
- Panel 完整状态检查走带 `X-Node-Token` 的 `GET /api/v1/status`
- 宿主启停与日志检查走 `control bridge`，不要把运维字段重新塞回 probe / heartbeat 面
- action 详情接口会返回规范化字段：`request`、`response`、`log_excerpt`、`log_location`、`runtime_snapshot`、`failure`
- run 详情对象会附带 `progress` 摘要，包含当前阶段、最近事件和事件计数
- `GET /api/v1/admin/runtime` 会附带 `active_run` 和 `attention` 摘要，管理页用它来禁用重复 full run 并展示运行焦点
- active run 的 `progress` 还可以附带 `latest_queue_job`
- 节点 runtime 视图对象可以附带 `run_attention`，把当前 active run 的阻塞点直接贴到对应节点卡片上
- 节点 `connectivity.push` / `connectivity.pull` 里可以附带可选 `code`
- 运行时调试字段优先放进 `runtime_status.environment`
- probe 侧附加信息继续放进 `metadata`
- run `progress` 可以附带 `last_failure_code`、`last_failure_message`、`recommended_step`

## 9. 合并前检查清单

macOS 分支提交前，至少检查：

1. `agents/service.py` 的既有路由没改名
2. `X-Node-Token` 没改
3. `role` / `runtime_mode` 枚举没改
4. `protocol_version=1` 仍然必填且生效
5. Agent 配置 YAML 字段名没改
6. `bin/install_server_agent_launchd.sh` 仍能用现有参数启动
7. 如果包含 `controller/webui.py`、模板、`controller/assets/` 的改动，必须先更新本文档中的冻结合同

`WebUI-dev` 提交前，至少检查：

1. 不改 `agents/service.py` 的路由和认证头
2. 不改 Agent CLI 参数名
3. 不改 `config/agent/*.yaml` 的核心字段名
4. 不改 `control bridge` 既有路由、认证头和 allowlist 动作语义
5. 如果新增了 Panel 侧字段，必须保证是可选附加字段

## 10. 出现冲突时的处理原则

如果两边都需要改同一个接口，不要各自先改。

正确流程：

1. 先在 `main` 更新本 handoff
2. 明确旧接口保留多久
3. 双边分别补兼容实现
4. 两边测试都通过后再合并

当前阶段的默认原则：

- `main` 放协作文档
- `WebUI-dev` 继续只做 WebUI / Panel
- macOS 分支只做 Agent / launchd / 本地兼容
- 双边都不要跨边界改接口
