# macOS Branch Handoff

本文档是 `WebUI-dev` 和 macOS 本地测试分支之间的接口冻结说明。

目标只有一个：两边并行开发，但不要互相改坏对方依赖的接口。

当前冻结合同基线：

- `WebUI-dev` 最新已确认基线：`58f5703` (`Upgrade WebUI analytics dashboard`)
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

### 管理认证

以下行为也视为冻结合同：

- 未登录访问 `/admin` 会跳转到 `/login`
- 未登录访问管理 API 返回 `401`
- 认证方式继续使用当前管理员 Cookie

## 5. 冻结的 Agent / macOS 接口

`WebUI-dev` 不要改以下 Agent 侧合同。

### Panel 调 Agent

- `GET /api/v1/status`
- `POST /api/v1/jobs/run`
- `GET /api/v1/results/{run_id}`

### Agent 本地接口

- `POST /api/v1/pair`
- `POST /api/v1/heartbeat`

### Panel 接收 Agent

- `POST /api/v1/agents/pair`
- `POST /api/v1/agents/heartbeat`

### 认证与关键字段

不要改：

- Header: `X-Node-Token`
- `role` 枚举：`client | relay | server`
- `runtime_mode` 枚举：`docker-linux | native-macos | native-windows`

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

## 6. 双方都必须遵守的扩展规则

如果确实需要扩接口，只能按下面规则做：

1. 先更新本 handoff 文档到 `main`
2. 只能新增可选字段，不能改旧字段
3. 尽量新增接口，不要修改旧接口语义
4. 如果是 breaking change，必须新开版本路径，不允许直接覆盖旧 `v1`
5. 两边都要补测试后才能合并

简单说：

- additive change 可以
- breaking change 不允许直接上

## 7. macOS 分支推荐工作方式

建议 macOS 侧只做这些类型的工作：

- `launchd` 启停与开机自启修复
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
launchctl print gui/$(id -u)/com.mc-netprobe.server.agent
tail -n 50 logs/server-agent.launchd.log
curl http://127.0.0.1:9870/api/v1/status
curl -X POST http://127.0.0.1:9870/api/v1/heartbeat
```

如果本地为了调试需要扩展信息：

- 优先放进 `status` 里的附加字段
- 或放进 probe `metadata`
- 但不要移除现有字段

## 9. 合并前检查清单

macOS 分支提交前，至少检查：

1. `agents/service.py` 的既有路由没改名
2. `X-Node-Token` 没改
3. `role` / `runtime_mode` 枚举没改
4. Agent 配置 YAML 字段名没改
5. `bin/install_server_agent_launchd.sh` 仍能用现有参数启动
6. 不包含 `controller/webui.py`、模板、`controller/assets/` 的改动

`WebUI-dev` 提交前，至少检查：

1. 不改 `agents/service.py` 的路由和认证头
2. 不改 Agent CLI 参数名
3. 不改 `config/agent/*.yaml` 的核心字段名
4. 如果新增了 Panel 侧字段，必须保证是可选附加字段

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
