# Codex 启动 Prompt

下面是一份建议直接粘贴给 Codex 的启动 prompt。目标是让它一次性生成一个结构正确、边界清晰的 MVP，而不是无约束地输出杂乱代码。

---

## 建议 Prompt

你要为一个名为 `mc-netprobe` 的 Python 3.11 项目生成第一版 MVP。这个项目用于自动化测试 Minecraft 服务器在 FRP 转发架构下的总链路和分段链路质量。

### 一、项目背景

目标拓扑为：

`客户端 -> FRP 公网服务器 -> FRP 隧道 -> Mac mini(MC服务器)`

需要测试四类路径：

1. 总链路：客户端 -> MC 实际公网入口（例如 `play.example.com:25565`）
2. 分段 A：客户端 -> FRP 公网服务器
3. 分段 B：FRP 公网服务器 -> Mac mini
4. 本地对照：Mac mini -> 本地 MC 服务（例如 `127.0.0.1:25565`）

### 二、第一版必须实现的能力

第一版 MVP 必须实现以下功能：

1. YAML 配置加载
2. ping 探测
3. TCP connect 探测
4. iperf3 吞吐探测（forward 和 reverse）
5. 系统快照探测（CPU、内存、load average、网络速率）
6. 通过 SSH 远程执行 relay/server 上的 agent 任务
7. 单次完整 orchestrator 执行
8. 结果导出为 JSON、CSV、HTML
9. 阈值配置与异常高亮
10. 带载情况下的延迟膨胀测试：
   - 对目标跑 iperf3 压测
   - 同时持续采样 MC 端口 TCP connect 时延
   - 输出 `load_rtt_inflation_ms`

### 三、第一版暂不实现

以下能力先不要实现，除非你用很少代码就能优雅支持：

1. 复杂常驻服务框架
2. gRPC / FastAPI / Web UI
3. Prometheus 集成
4. 完整 MC 协议支持
5. 数据库存储
6. 云端部署模板

### 四、硬性结构约束

必须生成如下目录结构，不要擅自改动层级职责：

```text
mc-netprobe/
├── README.md
├── requirements.txt
├── .env.example
├── config/
│   ├── topology.example.yaml
│   ├── thresholds.example.yaml
│   └── scenarios.example.yaml
├── bin/
│   ├── bootstrap_mac.sh
│   ├── bootstrap_linux.sh
│   ├── run_client.sh
│   ├── run_relay.sh
│   ├── run_server.sh
│   └── run_all_local_debug.sh
├── agents/
│   ├── __init__.py
│   ├── agent_client.py
│   ├── agent_relay.py
│   └── agent_server.py
├── controller/
│   ├── __init__.py
│   ├── orchestrator.py
│   ├── ssh_exec.py
│   ├── scenario.py
│   └── scheduler.py
├── probes/
│   ├── __init__.py
│   ├── common.py
│   ├── metrics.py
│   ├── ping.py
│   ├── tcp_handshake.py
│   ├── throughput.py
│   ├── mc_probe.py
│   ├── path_probe.py
│   └── system_probe.py
├── exporters/
│   ├── __init__.py
│   ├── json_exporter.py
│   ├── csv_exporter.py
│   └── html_report.py
├── results/
├── logs/
└── main.py
```

### 五、职责约束

1. `controller/` 只负责编排，不负责复杂命令解析  
2. `probes/` 负责实际探测与命令解析  
3. `agents/` 负责接收任务并调用 probe  
4. `exporters/` 负责导出 JSON、CSV、HTML  
5. 所有结果统一返回同一个 `ProbeResult` schema  
6. 所有外部命令必须有 timeout  
7. 所有异常不能静默吞掉，必须写入 `error` 字段

### 六、平台约束

第一版要支持：

- macOS
- Ubuntu / Debian

注意兼容差异：

- macOS `ping` 的 `stddev`
- Linux `ping` 的 `mdev`
- `iperf3` 缺失时的报错
- SSH 不可达时的错误输出

### 七、配置约束

所有环境信息必须放到 YAML，不允许硬编码：

- host
- SSH 用户与端口
- MC 端口
- iperf3 端口
- 采样次数
- 压测时长
- 告警阈值

请生成：

- `config/topology.example.yaml`
- `config/thresholds.example.yaml`
- `config/scenarios.example.yaml`

### 八、输出约束

每次执行 `main.py` 必须创建一个独立 run 目录，例如：

`results/run-YYYYMMDD-HHMMSS/`

并输出：

- `raw.json`
- `summary.csv`
- `report.html`

### 九、建议实现方式

第一版优先使用：

- Python 3.11
- `asyncio`
- `paramiko` 或系统 ssh
- `psutil`
- `PyYAML`
- `jinja2`

agent 采用“单任务命令式执行”模式，便于通过 SSH 远程触发。例如：

```bash
python -m agents.agent_server --task tcp_probe --host 127.0.0.1 --port 25565
python -m agents.agent_server --task start_iperf_server --port 5201
```

不要在第一版强行引入复杂常驻控制服务。

### 十、带载退化测试要求

必须实现一个场景：

1. 先测空载时对 `mc_public:25565` 的 TCP connect 基线
2. 再对 `iperf_public:5201` 跑 `iperf3 -t 30`
3. 压测同时每 500ms 持续采样 `mc_public:25565` 的 TCP connect
4. 计算：
   - `idle_connect_avg_ms`
   - `loaded_connect_avg_ms`
   - `load_rtt_inflation_ms`
   - `loaded_timeout_pct`

### 十一、代码质量要求

请满足：

- 使用类型注解
- 关键数据结构使用 `dataclass`
- README 写清安装和运行流程
- 所有模块有清晰 docstring
- 尽量避免过度抽象
- 优先正确性、可读性和工程边界清晰

### 十二、交付要求

请直接输出完整文件内容。  
优先给出一个能运行的 MVP，不要为了“设计完美”而省略可执行代码。  
如果某个功能你先用占位实现，也要明确注释并保证接口稳定。  
不要只输出伪代码。

### 十三、开发顺序建议

你在生成代码时请按这个顺序组织内容：

1. requirements 和配置样例
2. ProbeResult schema 与公共命令执行器
3. ping probe
4. tcp handshake probe
5. system probe
6. iperf3 probe
7. agents
8. ssh executor
9. orchestrator
10. exporters
11. main.py
12. README
13. shell scripts

如果篇幅过长，也必须保证先把最小可运行链路打通，不要只写一半框架。

---

## 使用建议

把这份 prompt 粘贴给 Codex 后，建议让它先生成 MVP。  
然后再追加第二轮 prompt：

- 增加 MC status probe
- 增加 html 报表图表
- 增加 parser tests
- 增加历史 run 对比
