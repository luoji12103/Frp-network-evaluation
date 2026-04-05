# 工程 Harness 与 Git 规范文档

## 1. 文档目的

本文件定义 `mc-netprobe` 项目的工程执行约束，确保用 Codex 或人工协作开发时，代码结构、提交粒度、分支模型、验收方式一致，避免“能跑但不可维护”。

---

## 2. 工程目标

工程目标分为四类：

1. 可生成  
   Codex 能在有限轮次内生成可运行骨架。

2. 可验证  
   每个增量提交都能本地验证，不依赖过多手工操作。

3. 可回滚  
   功能拆分成小步提交，出现问题可以明确回滚。

4. 可扩展  
   后续增加 MC status probe、历史对比、图表都不需要推翻第一版结构。

---

## 3. 分支模型

建议使用简化版 Git Flow，但不要引入过重流程。

### 3.1 主分支

- `main`：始终保持可运行、可演示、可打包状态

### 3.2 集成分支

- `develop`：日常集成分支，多个功能完成后合入，再择机合并到 `main`

### 3.3 功能分支

命名建议：

- `feat/bootstrap-project`
- `feat/probe-ping-tcp`
- `feat/probe-iperf3`
- `feat/ssh-orchestrator`
- `feat/report-exporters`
- `feat/load-inflation-scenario`
- `feat/mc-status-probe`

### 3.4 修复分支

- `fix/macos-ping-parser`
- `fix/iperf-timeout-handling`
- `fix/html-report-encoding`

### 3.5 文档分支

- `docs/architecture`
- `docs/harness`
- `docs/prompt-bundle`

---

## 4. 推荐开发节奏

建议按阶段推进，每阶段一个主题分支：

### 阶段 A：项目骨架
分支：`feat/bootstrap-project`

输出：

- 目录结构
- `requirements.txt`
- `README.md`
- `main.py`
- 基础配置加载

### 阶段 B：基础探针
分支：`feat/probe-ping-tcp`

输出：

- `probes/ping.py`
- `probes/tcp_handshake.py`
- `probes/metrics.py`

### 阶段 C：吞吐探针
分支：`feat/probe-iperf3`

输出：

- `probes/throughput.py`
- iperf3 JSON 解析
- 超时与错误处理

### 阶段 D：远程编排
分支：`feat/ssh-orchestrator`

输出：

- `controller/ssh_exec.py`
- `controller/orchestrator.py`
- 远程 agent 调度

### 阶段 E：报告导出
分支：`feat/report-exporters`

输出：

- JSON/CSV/HTML exporter
- 阈值对比与摘要

### 阶段 F：场景化测试
分支：`feat/load-inflation-scenario`

输出：

- 空载/带载测试编排
- 压测 + 延迟观测

### 阶段 G：MC 应用层增强
分支：`feat/mc-status-probe`

输出：

- MC status probe
- 协议级时延指标

---

## 5. Commit 规范

建议使用 Conventional Commits。

### 5.1 格式

`<type>(<scope>): <subject>`

示例：

- `feat(probes): add ping and tcp handshake probes`
- `feat(controller): add ssh-based remote orchestration`
- `fix(throughput): handle iperf3 json parse failure`
- `docs(harness): add branch and commit workflow`
- `refactor(metrics): unify probe result schema`
- `test(exporters): add csv and html snapshot tests`

### 5.2 type 建议

- `feat`：新增功能
- `fix`：修复问题
- `refactor`：重构，不改变外部功能
- `docs`：文档更新
- `test`：测试增加或调整
- `chore`：依赖、脚本、CI、格式化等杂项

### 5.3 提交粒度

每个 commit 只解决一个明确问题。不要把以下内容混在一个提交里：

- 新探针 + 报表重构 + 文档
- agent 重构 + SSH 改造 + 配置改名
- bug 修复 + 格式化全仓库

理想提交粒度示例：

1. `feat(config): add topology and thresholds loaders`
2. `feat(probes): add ping probe with cross-platform parser`
3. `feat(probes): add tcp handshake probe`
4. `feat(exporters): add json exporter`
5. `fix(ping): support macOS stddev parser`

---

## 6. Pull Request 规范

每个 PR 应包含：

1. 变更目的  
2. 影响范围  
3. 手工验证步骤  
4. 结果截图或结果文件说明  
5. 已知限制

PR 模板建议：

```md
## 变更内容
- 
- 

## 原因
- 

## 验证方法
1. 
2. 
3. 

## 结果
- 

## 风险与限制
- 
```

---

## 7. 工程 Harness 约束

这里的 harness 指“约束 Codex 和开发流程的工程护栏”。

### 7.1 结构约束

必须遵守以下目录职责：

- `controller/` 只负责编排，不直接解析所有命令输出细节
- `probes/` 负责所有采样逻辑和命令解析
- `agents/` 只负责接受任务并调用 probes
- `exporters/` 只负责导出，不混入采样逻辑
- `config/` 只放静态配置样例和模板

### 7.2 编码约束

- Python 3.11+
- 默认使用类型注解
- 尽量使用 `dataclass` 或 `pydantic`
- 命令执行必须有超时
- 所有 probe 返回统一的 `ProbeResult`
- 不能把异常静默吞掉，必须写入 `error` 字段

### 7.3 平台约束

第一版至少支持：

- macOS（客户端、Mac mini）
- Ubuntu / Debian（FRP 公网服务器）

解析系统命令输出时必须考虑：

- macOS `ping` 输出中的 `stddev`
- Linux `ping` 输出中的 `mdev`
- `iperf3` 不存在时的错误提示
- SSH 不可达时的清晰失败

### 7.4 配置约束

配置必须外置，禁止将以下信息硬编码：

- 目标 host
- SSH 用户
- 测试端口
- 采样次数
- 吞吐持续时长
- 阈值

### 7.5 输出约束

每次 run 都必须输出：

- 独立目录
- `raw.json`
- `summary.csv`
- `report.html`
- 可选 `logs/`

输出目录命名建议：

`results/run-YYYYMMDD-HHMMSS/`

---

## 8. 最小测试 Harness

### 8.1 单元级验证

建议至少对以下模块做最小测试：

- ping 输出解析
- tcp probe 聚合统计
- iperf3 JSON 解析
- 阈值比较
- html/csv 导出

### 8.2 集成级验证

最少三个验证场景：

#### 场景 1：本地回环
- 在本机启动 iperf3 server
- 本机连接本机
- 验证骨架可运行

#### 场景 2：双机验证
- relay 到 server 测试
- 验证 SSH 调度和远程结果采集

#### 场景 3：完整拓扑验证
- client + relay + server
- 验证总链路与分段链路结果同时输出

### 8.3 回归 Harness

建议保留以下脚本：

- `bin/run_all_local_debug.sh`
- `bin/run_client.sh`
- `bin/run_relay.sh`
- `bin/run_server.sh`

用于快速手工回归。

---

## 9. 推荐里程碑

### M1：骨架可运行
验收：

- 可读 YAML
- 可执行 `main.py`
- 可输出空报告骨架

### M2：基础探针可用
验收：

- ping 和 TCP probe 可运行
- 输出 JSON/CSV

### M3：吞吐探针可用
验收：

- iperf3 forward/reverse 可运行
- 错误处理清晰

### M4：远程编排可用
验收：

- 可通过 SSH 触发 relay 和 server 任务
- 能汇总远程结果

### M5：报告可读
验收：

- HTML 报告能展示所有关键指标
- 有阈值高亮

### M6：带载测试可用
验收：

- 能测空载与带载差异
- 能输出 `load_rtt_inflation_ms`

---

## 10. 建议的 commit 序列

下面给出一个比较稳的提交序列，适合让 Codex 或人工跟着做。

1. `chore(repo): initialize project structure and python tooling`
2. `feat(config): add topology and thresholds yaml loaders`
3. `feat(probes): add shared probe result model and command runner`
4. `feat(probes): add ping probe with linux and macos parsing`
5. `feat(probes): add tcp handshake probe`
6. `feat(probes): add system snapshot probe`
7. `feat(probes): add iperf3 throughput probe`
8. `feat(agents): add server relay client agents with task dispatch`
9. `feat(controller): add ssh execution wrapper`
10. `feat(controller): add orchestrator for baseline path tests`
11. `feat(controller): add throughput and load-inflation scenario`
12. `feat(exporters): add json and csv exporters`
13. `feat(exporters): add html summary report`
14. `docs(readme): document setup and run workflow`
15. `test(parsers): add parser tests for ping and iperf3`

---

## 11. 分支合并策略

建议：

- 功能分支先合入 `develop`
- `develop` 经本地验证后合入 `main`
- `main` 上只保留可发布状态

不要直接在 `main` 上连续堆实验代码，除非只是非常小的文档修正。

---

## 12. Tag 规范

建议使用：

- `v0.1.0`：MVP，具备 ping/tcp/iperf3/system/exporter
- `v0.2.0`：加入带载退化测试
- `v0.3.0`：加入 MC status probe
- `v1.0.0`：整体稳定，完整可用

---

## 13. Release 附件建议

每次版本发布建议附带：

- ZIP 源码包
- 示例配置
- 一份示例结果目录
- README 安装与运行说明

---

## 14. Codex 协作 Harness

给 Codex 的约束应尽量明确，否则它容易写出“能跑但杂乱”的代码。

必须在 prompt 中明确：

1. 目录结构不可随意改变  
2. 所有 probe 返回统一 schema  
3. 所有命令执行必须超时  
4. 所有配置都放到 YAML  
5. 不要引入过重框架  
6. 第一版优先命令式 agent + SSH 调度  
7. 每个阶段只提交一个主题分支  
8. 输出必须包含 JSON/CSV/HTML  

---

## 15. Definition of Done

单个功能分支完成的定义应包括：

- 代码存在
- 本地能跑
- 有最小文档
- 错误处理清晰
- 输出字段符合统一 schema
- 与现有目录职责不冲突

项目完成的定义包括：

- 单命令执行完整测试
- 能同时测总链路和分段链路
- 能输出结构化报告
- 能用结果定位主要瓶颈
- 文档可供他人接手维护

---

## 16. 总结

这份 harness 文档的核心作用，是为 Codex 生成和后续人工接手建立边界条件。  
只要严格遵守：

- 小步提交
- 目录职责清晰
- 配置外置
- 统一结果模型
- 先 MVP 再增强

这个项目就能稳定落地，而不会演变成一组零散脚本。
