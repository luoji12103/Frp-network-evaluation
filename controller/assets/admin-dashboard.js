(function () {
  const ADMIN_LOCALE_STORAGE_KEY = "mc-netprobe-admin-locale";
  const ADMIN_REFRESH_STORAGE_KEY = "mc-netprobe-admin-refresh-sec";
  const ADMIN_FILTERS_STORAGE_KEY = "mc-netprobe-admin-filters";
  const ADMIN_TAB_STORAGE_KEY = "mc-netprobe-admin-tab";
  const DEFAULT_TIME_RANGES = ["1h", "6h", "24h", "7d", "30d"];
  const FIXED_ROLES = ["client", "relay", "server"];
  const ROLE_RUNTIME = {
    client: "native-windows",
    relay: "docker-linux",
    server: "native-macos",
  };
  const PATH_LABELS = {
    client_to_relay_public: { "zh-CN": "客户端 -> 中继公网", "en-US": "Client -> Relay Public" },
    relay_to_server_backend_mc: { "zh-CN": "中继 -> 服务端后端 MC", "en-US": "Relay -> Server Backend MC" },
    relay_to_server_backend_iperf: { "zh-CN": "中继 -> 服务端后端 iperf", "en-US": "Relay -> Server Backend iperf" },
    server_to_relay_public: { "zh-CN": "服务端 -> 中继公网", "en-US": "Server -> Relay Public" },
    client_to_mc_public: { "zh-CN": "客户端 -> MC 公网", "en-US": "Client -> MC Public" },
    client_to_iperf_public: { "zh-CN": "客户端 -> iperf 公网", "en-US": "Client -> iperf Public" },
    client_to_mc_public_load: { "zh-CN": "客户端 -> MC 公网负载", "en-US": "Client -> MC Public Load" },
    client_system: { "zh-CN": "客户端系统", "en-US": "Client System" },
    relay_system: { "zh-CN": "中继系统", "en-US": "Relay System" },
    server_system: { "zh-CN": "服务端系统", "en-US": "Server System" },
    client_to_relay: { "zh-CN": "客户端 -> 中继公网", "en-US": "Client -> Relay Public" },
    relay_to_server: { "zh-CN": "中继 -> 服务端后端 MC", "en-US": "Relay -> Server Backend MC" },
    server_to_local_mc: { "zh-CN": "服务端 -> 本地 MC", "en-US": "Server -> Local MC" },
    server_iperf_direct: { "zh-CN": "服务端 iperf 直连", "en-US": "Server iperf direct" },
    server_iperf_public: { "zh-CN": "服务端 iperf 公网", "en-US": "Server iperf public" },
  };
  const METRIC_LABELS = {
    packet_loss_pct: { "zh-CN": "丢包", "en-US": "Packet loss" },
    rtt_avg_ms: { "zh-CN": "平均 RTT", "en-US": "RTT avg" },
    rtt_p95_ms: { "zh-CN": "RTT P95", "en-US": "RTT P95" },
    jitter_ms: { "zh-CN": "抖动", "en-US": "Jitter" },
    connect_avg_ms: { "zh-CN": "TCP 平均连接", "en-US": "TCP connect avg" },
    connect_p95_ms: { "zh-CN": "TCP P95", "en-US": "TCP P95" },
    connect_timeout_or_error_pct: { "zh-CN": "TCP 错误", "en-US": "TCP error" },
    throughput_up_mbps: { "zh-CN": "上行吞吐", "en-US": "Up throughput" },
    throughput_down_mbps: { "zh-CN": "下行吞吐", "en-US": "Down throughput" },
    load_rtt_inflation_ms: { "zh-CN": "负载增量", "en-US": "Load inflation" },
    cpu_usage_pct: { "zh-CN": "CPU 使用率", "en-US": "CPU usage" },
    memory_usage_pct: { "zh-CN": "内存使用率", "en-US": "Memory usage" },
  };
  const translations = {
    "zh-CN": {
      pageTitle: "mc-netprobe 企业级网络面板",
      panelOnline: "面板在线",
      language: "语言",
      autoRefresh: "自动刷新",
      refreshOff: "关闭",
      refresh15: "15 秒",
      refresh30: "30 秒",
      refresh60: "60 秒",
      refreshStatusReady: "面板已就绪",
      refreshStatusOk: "已刷新",
      refreshStatusError: "刷新失败",
      heroTitle: "mc-netprobe 企业级网络面板",
      heroDescription: "常驻 Panel 负责角色化网络质量监控、异常检测、趋势分析、告警处理和节点管理，全程不保存 SSH 凭据。",
      publicView: "公开页面",
      saveSettings: "保存全局配置",
      runFull: "手动执行完整监测",
      refreshPanel: "刷新面板",
      logout: "退出登录",
      recentAlertHeadline: "告警脉搏",
      globalFilters: "全局筛选",
      applyFilters: "应用筛选",
      resetFilters: "重置筛选",
      timeRange: "时间范围",
      roles: "角色",
      nodes: "节点",
      paths: "路径",
      probes: "探针",
      metric: "指标",
      runKinds: "运行类型",
      severities: "严重级别",
      alertStatuses: "告警状态",
      onlyAnomalies: "仅异常",
      includeResolved: "包含已恢复",
      pathFocus: "路径聚焦",
      filterSummaryReady: "筛选摘要",
      all: "全部",
      booleanTrue: "是",
      booleanFalse: "否",
      tabOverview: "总览",
      tabPathExplorer: "路径分析",
      tabMetricExplorer: "指标分析",
      tabAlerts: "告警中心",
      tabRuns: "运行记录",
      tabManagement: "管理",
      overviewKpis: "总览 KPI",
      statusDistribution: "状态分布",
      recentAnomalies: "最近异常",
      pathHealthHeat: "路径健康热力图",
      latencyTrend: "延迟趋势",
      lossTrend: "丢包趋势",
      throughputTrend: "吞吐趋势",
      systemTrend: "系统趋势",
      loadTrend: "负载影响",
      pathExplorerHeadline: "路径分析",
      metricExplorerHeadline: "指标分析",
      metricExplorerHint: "单指标、多序列、阈值线和异常点联动，最多同时对比 4 条序列。",
      metricSeriesSummary: "指标序列摘要",
      alertCenter: "告警中心",
      runsHeadline: "运行记录",
      runDetail: "运行详情",
      topologyThresholdsSchedules: "拓扑、阈值与调度",
      serviceEndpoints: "服务端点",
      thresholdsDurations: "阈值与时长",
      pairingConsole: "配对控制台",
      pairingHint: "为 Linux Docker relay、macOS launchd server、Windows 计划任务 client 生成命令。",
      primaryCommand: "主命令",
      fallbackCommand: "兜底命令",
      copy: "复制",
      nodesCaption: "单拓扑 UI，按角色固定部署方式，Agent 持续配对和监控。",
      noData: "暂无数据",
      noAlerts: "暂无符合条件的告警。",
      noRuns: "暂无运行记录。",
      noRunDetail: "请选择一条运行记录查看详情。",
      allPaths: "全部路径",
      loading: "加载中...",
      saveSettingsOk: "全局配置已保存。",
      saveSettingsFailed: "保存全局配置失败",
      runFullOk: "完整监测任务已启动：{value}",
      runFullFailed: "触发完整监测失败",
      saveNodeOk: "{value} 节点已保存。",
      saveNodeFailed: "保存节点失败",
      pairNodeOk: "{value} 配对命令已生成。",
      pairNodeFailed: "生成配对命令失败",
      alertAckOk: "告警已确认。",
      alertAckFailed: "确认告警失败",
      alertSilenceOk: "告警已静默。",
      alertSilenceFailed: "静默告警失败",
      alertHistoryTitle: "同指纹事件历史",
      copied: "已复制到剪贴板。",
      copyFailed: "复制失败，请手动复制。",
      sessionExpired: "登录已失效，请刷新后重新登录。",
      runtimeControl: "运行控制",
      operationsFocus: "运行焦点",
      releaseValidation: "发布验收",
      runValidation: "执行只读验收",
      validationNotRun: "尚未执行发布验收。",
      validationRunning: "发布验收执行中",
      validationLastChecked: "最近验收",
      validationSummary: "验收摘要",
      validationIssues: "验收问题",
      validationNoIssues: "当前验收没有发现警告或失败项。",
      validationChecks: "检查项",
      generatedAt: "生成时间",
      noAttention: "当前没有需要立刻处理的运行问题。",
      activeRunNow: "运行中任务",
      attentionSummary: "待关注事项",
      recommendedStep: "建议动作",
      openRun: "查看运行",
      openNode: "定位节点",
      openPanel: "定位 Panel",
      connectivitySummary: "通信诊断",
      diagnosticCode: "诊断码",
      pushCode: "Push 诊断码",
      pullCode: "Pull 诊断码",
      failureCode: "失败码",
      runBusy: "已有运行中的监测任务",
      actionHistory: "操作历史",
      actionDetail: "动作详情",
      target: "目标",
      result: "结果",
      runEvents: "运行事件",
      currentPhase: "当前阶段",
      lastEvent: "最近事件",
      eventsCount: "事件数",
      latestProbe: "最近探针",
      latestQueueJob: "最近队列任务",
      currentBlocker: "当前阻塞",
      queueStatus: "队列状态",
      leaseState: "租约状态",
      leaseExpiresAt: "租约到期",
      jobId: "任务 ID",
      taskLabel: "任务",
      liveRunHint: "运行仍在进行中，详情会自动刷新。",
      requestPayload: "请求快照",
      responsePayload: "响应快照",
      currentAction: "当前动作",
      viewAction: "查看动作",
      requestedBy: "发起人",
      transport: "执行通道",
      finishedAt: "结束时间",
      failure: "失败原因",
      logExcerpt: "日志摘录",
      runtimeSnapshot: "运行态快照",
      currentTargetSnapshot: "当前目标快照",
      readonlyReason: "只读说明",
      actionBusy: "该目标已有动作执行中",
      start: "启动",
      stop: "停止",
      restart: "重启",
      tailLog: "日志",
      syncRuntime: "同步运行态",
      runtimeState: "运行态",
      supervisorState: "Supervisor",
      processState: "进程状态",
      deploymentMode: "部署模式",
      controlMode: "控制模式",
      controlBridge: "控制桥",
      logLocation: "日志位置",
      schedulerPaused: "调度已暂停",
      schedulerRunning: "调度运行中",
      pauseScheduler: "暂停调度",
      resumeScheduler: "恢复调度",
      nativeMode: "原生",
      dockerBridgeMode: "Docker + 控制桥",
      bridgeManaged: "桥接强控制",
      nativeReadonly: "原生只读观测",
      panelReadonlyHint: "当前为原生只读观测模式，可同步运行态、暂停/恢复调度；若本地日志文件存在，也可查看日志。重启和停止需要配置 panel control bridge。",
      actionQueuedOk: "操作已入队。",
      actionQueuedFailed: "发起操作失败",
      panelTarget: "Panel",
      findings: "发现项",
      actions: "操作",
      severity: "严重级别",
      kind: "类型",
      path: "路径",
      actual: "实际值",
      threshold: "阈值",
      status: "状态",
      runId: "运行 ID",
      runKind: "运行类型",
      startedAt: "开始时间",
      openReport: "打开报告",
      viewDetail: "详情",
      ack: "确认",
      silence: "静默",
      history: "历史",
      duration: "耗时",
      sourceNode: "来源节点",
      saveNode: "保存节点",
      generatePairCommand: "生成配对命令",
      signalOk: "正常",
      signalFail: "失败",
      silenceHoursPrompt: "静默小时数",
      silenceReasonPrompt: "静默原因",
      defaultMaintenanceReason: "维护窗口",
      runtimeMode: "运行方式",
      nodeName: "节点名称",
      configuredPullUrl: "配置 Pull 地址",
      advertisedPullUrl: "Agent 上报地址",
      effectivePullUrl: "当前生效地址",
      pushState: "Push 通道",
      pullState: "Pull 通道",
      endpointMismatch: "地址不一致",
      enabled: "启用",
      paired: "已配对",
      lastSeen: "最近上线",
      recentAlerts: "最近告警",
      pathExplorerHint: "按路径观察 latency / loss / throughput / load 多图联动。",
      probeResults: "探针结果",
      minimum: "最小",
      maximum: "最大",
      field: {
        relayPublicProbeHost: "relay_public_probe 主机",
        relayPublicProbePort: "relay_public_probe 端口",
        mcPublicHost: "mc_public 主机",
        mcPublicPort: "mc_public 端口",
        iperfPublicHost: "iperf_public 主机",
        iperfPublicPort: "iperf_public 端口",
        serverBackendMcHost: "server_backend_mc 主机",
        serverBackendMcPort: "server_backend_mc 端口",
        serverBackendIperfHost: "server_backend_iperf 主机",
        serverBackendIperfPort: "server_backend_iperf 端口",
        pingAvgMax: "Ping 平均延迟上限 ms",
        pingJitterMax: "Ping 抖动上限 ms",
        tcpAvgMax: "TCP 平均连接上限 ms",
        tcpErrorMax: "TCP 错误率上限 %",
        throughputUpMin: "上行吞吐下限 Mbps",
        throughputDownMin: "下行吞吐下限 Mbps",
        loadDeltaMax: "负载增量上限 ms",
        systemCpuMax: "CPU 使用率上限 %",
        throughputDurationSec: "吞吐测试时长 sec",
        loadDurationSec: "负载测试时长 sec",
        tcpAttempts: "TCP 尝试次数",
        systemSampleSec: "系统采样 sec",
      },
      role: { client: "客户端", relay: "中继", server: "服务端" },
      runKindValue: {
        system: "系统",
        baseline: "基线",
        capacity: "容量",
        full: "完整",
      },
      runtime: {
        "docker-linux": "Docker Linux",
        "native-macos": "原生 macOS",
        "native-windows": "原生 Windows",
      },
      severityLabel: {
        info: "信息",
        warning: "警告",
        error: "错误",
      },
      kindLabel: {
        anomaly: "异常",
        threshold: "阈值",
        node_status: "节点状态",
      },
      statusLabel: {
        online: "在线",
        "push-only": "仅 Push",
        "pull-only": "仅 Pull",
        offline: "离线",
        unpaired: "未配对",
        disabled: "已禁用",
        ok: "正常",
        unknown: "未知",
        open: "未恢复",
        acknowledged: "已确认",
        resolved: "已恢复",
        running: "运行中",
        queued: "已排队",
        completed: "完成",
        canceled: "已取消",
        failed: "失败",
        pass: "通过",
        warn: "警告",
        fail: "失败",
        skip: "跳过",
        healthy: "健康",
        degraded: "降级",
        critical: "严重",
      },
    },
    "en-US": {
      pageTitle: "mc-netprobe enterprise panel",
      panelOnline: "Panel online",
      language: "Language",
      autoRefresh: "Auto refresh",
      refreshOff: "Off",
      refresh15: "15 sec",
      refresh30: "30 sec",
      refresh60: "60 sec",
      refreshStatusReady: "Panel ready",
      refreshStatusOk: "Refreshed",
      refreshStatusError: "Refresh failed",
      heroTitle: "mc-netprobe Enterprise Network Panel",
      heroDescription: "Persistent panel for role-aware network quality monitoring, anomaly detection, historical analysis, alert handling, and node management without SSH credential storage.",
      publicView: "Public View",
      saveSettings: "Save Global Settings",
      runFull: "Run Full Monitoring",
      refreshPanel: "Refresh Panel",
      logout: "Logout",
      recentAlertHeadline: "Alert Pulse",
      globalFilters: "Global Filters",
      applyFilters: "Apply Filters",
      resetFilters: "Reset Filters",
      timeRange: "Time Range",
      roles: "Roles",
      nodes: "Nodes",
      paths: "Paths",
      probes: "Probes",
      metric: "Metric",
      runKinds: "Run Kinds",
      severities: "Severities",
      alertStatuses: "Alert Status",
      onlyAnomalies: "Only anomalies",
      includeResolved: "Include resolved",
      pathFocus: "Path focus",
      filterSummaryReady: "Filter summary",
      all: "All",
      booleanTrue: "Yes",
      booleanFalse: "No",
      tabOverview: "Overview",
      tabPathExplorer: "Path Explorer",
      tabMetricExplorer: "Metric Explorer",
      tabAlerts: "Alerts",
      tabRuns: "Runs",
      tabManagement: "Management",
      overviewKpis: "Overview KPIs",
      statusDistribution: "Status Distribution",
      recentAnomalies: "Recent Anomalies",
      pathHealthHeat: "Path Health Heat",
      latencyTrend: "Latency Trend",
      lossTrend: "Loss Trend",
      throughputTrend: "Throughput Trend",
      systemTrend: "System Trend",
      loadTrend: "Load Impact",
      pathExplorerHeadline: "Path Explorer",
      metricExplorerHeadline: "Metric Explorer",
      metricExplorerHint: "One metric, multiple filtered series, threshold lines, and anomaly markers with up to four series at once.",
      metricSeriesSummary: "Metric Series Summary",
      alertCenter: "Alert Center",
      runsHeadline: "Runs",
      runDetail: "Run Detail",
      topologyThresholdsSchedules: "Topology, Thresholds & Schedules",
      serviceEndpoints: "Service Endpoints",
      thresholdsDurations: "Thresholds & Durations",
      pairingConsole: "Pairing Console",
      pairingHint: "Generate commands for Linux Docker relay, macOS launchd server, and Windows scheduled-task client agents.",
      primaryCommand: "Primary Command",
      fallbackCommand: "Fallback Command",
      copy: "Copy",
      nodesCaption: "Single-topology UI, role-specific deployment modes, persistent agent pairing and monitoring.",
      noData: "No data yet",
      noAlerts: "No matching alerts.",
      noRuns: "No runs yet.",
      noRunDetail: "Select a run to inspect its details.",
      allPaths: "All Paths",
      loading: "Loading...",
      saveSettingsOk: "Global settings saved.",
      saveSettingsFailed: "Failed to save global settings",
      runFullOk: "Full monitoring started: {value}",
      runFullFailed: "Failed to start full monitoring",
      saveNodeOk: "{value} node saved.",
      saveNodeFailed: "Failed to save node",
      pairNodeOk: "{value} pairing command generated.",
      pairNodeFailed: "Failed to generate pairing command",
      alertAckOk: "Alert acknowledged.",
      alertAckFailed: "Failed to acknowledge alert",
      alertSilenceOk: "Alert silenced.",
      alertSilenceFailed: "Failed to silence alert",
      alertHistoryTitle: "Fingerprint history",
      copied: "Copied to clipboard.",
      copyFailed: "Copy failed. Please copy manually.",
      sessionExpired: "Session expired. Refresh and log in again.",
      runtimeControl: "Runtime controls",
      operationsFocus: "Operations focus",
      releaseValidation: "Release Validation",
      runValidation: "Run Read-only Validation",
      validationNotRun: "No release validation snapshot is available yet.",
      validationRunning: "Release validation is running",
      validationLastChecked: "Last validation",
      validationSummary: "Validation summary",
      validationIssues: "Validation issues",
      validationNoIssues: "The latest validation did not report warn or fail items.",
      validationChecks: "Checks",
      generatedAt: "Generated",
      noAttention: "Nothing needs immediate runtime attention right now.",
      activeRunNow: "Active run",
      attentionSummary: "Attention items",
      recommendedStep: "Recommended next step",
      openRun: "View run",
      openNode: "Open node",
      openPanel: "Open panel",
      connectivitySummary: "Connectivity diagnostic",
      diagnosticCode: "Diagnostic code",
      pushCode: "Push code",
      pullCode: "Pull code",
      failureCode: "Failure code",
      runBusy: "A monitoring run is already active",
      actionHistory: "Action history",
      actionDetail: "Action detail",
      target: "Target",
      result: "Result",
      runEvents: "Run events",
      currentPhase: "Current phase",
      lastEvent: "Last event",
      eventsCount: "Event count",
      latestProbe: "Latest probe",
      latestQueueJob: "Latest queued job",
      currentBlocker: "Current blocker",
      queueStatus: "Queue status",
      leaseState: "Lease state",
      leaseExpiresAt: "Lease expires at",
      jobId: "Job ID",
      taskLabel: "Task",
      liveRunHint: "This run is still active. Detail will refresh automatically.",
      requestPayload: "Request snapshot",
      responsePayload: "Response snapshot",
      currentAction: "Current action",
      viewAction: "View action",
      requestedBy: "Requested by",
      transport: "Transport",
      finishedAt: "Finished at",
      failure: "Failure",
      logExcerpt: "Log excerpt",
      runtimeSnapshot: "Runtime snapshot",
      currentTargetSnapshot: "Current target snapshot",
      readonlyReason: "Read-only note",
      actionBusy: "Another action is already active for this target",
      start: "Start",
      stop: "Stop",
      restart: "Restart",
      tailLog: "Logs",
      syncRuntime: "Sync runtime",
      runtimeState: "Runtime state",
      supervisorState: "Supervisor",
      processState: "Process state",
      deploymentMode: "Deployment",
      controlMode: "Control mode",
      controlBridge: "Control bridge",
      logLocation: "Log location",
      schedulerPaused: "Scheduler paused",
      schedulerRunning: "Scheduler running",
      pauseScheduler: "Pause scheduler",
      resumeScheduler: "Resume scheduler",
      nativeMode: "Native",
      dockerBridgeMode: "Docker + control bridge",
      bridgeManaged: "Bridge-managed",
      nativeReadonly: "Native read-only",
      panelReadonlyHint: "This panel is running in native read-only mode. You can sync runtime, pause or resume the scheduler, and tail logs when a local log file exists. Restart and stop require a configured panel control bridge.",
      actionQueuedOk: "Action queued.",
      actionQueuedFailed: "Failed to queue action",
      panelTarget: "Panel",
      findings: "Findings",
      actions: "Actions",
      severity: "Severity",
      kind: "Kind",
      path: "Path",
      actual: "Actual",
      threshold: "Threshold",
      status: "Status",
      runId: "Run ID",
      runKind: "Run Kind",
      startedAt: "Started",
      openReport: "Open report",
      viewDetail: "Detail",
      ack: "Acknowledge",
      silence: "Silence",
      history: "History",
      duration: "Duration",
      sourceNode: "Source node",
      saveNode: "Save Node",
      generatePairCommand: "Generate Pair Command",
      signalOk: "OK",
      signalFail: "FAIL",
      silenceHoursPrompt: "Silence hours",
      silenceReasonPrompt: "Silence reason",
      defaultMaintenanceReason: "maintenance",
      runtimeMode: "Runtime Mode",
      nodeName: "Node Name",
      configuredPullUrl: "Configured pull URL",
      advertisedPullUrl: "Advertised pull URL",
      effectivePullUrl: "Effective pull URL",
      pushState: "Push channel",
      pullState: "Pull channel",
      endpointMismatch: "Endpoint mismatch",
      enabled: "Enabled",
      paired: "Paired",
      lastSeen: "Last seen",
      recentAlerts: "Recent Alerts",
      pathExplorerHint: "Explore latency, loss, throughput, and load from the selected path.",
      probeResults: "Probe Results",
      minimum: "Min",
      maximum: "Max",
      field: {
        relayPublicProbeHost: "relay_public_probe host",
        relayPublicProbePort: "relay_public_probe port",
        mcPublicHost: "mc_public host",
        mcPublicPort: "mc_public port",
        iperfPublicHost: "iperf_public host",
        iperfPublicPort: "iperf_public port",
        serverBackendMcHost: "server_backend_mc host",
        serverBackendMcPort: "server_backend_mc port",
        serverBackendIperfHost: "server_backend_iperf host",
        serverBackendIperfPort: "server_backend_iperf port",
        pingAvgMax: "Ping avg max ms",
        pingJitterMax: "Ping jitter max ms",
        tcpAvgMax: "TCP avg max ms",
        tcpErrorMax: "TCP error max %",
        throughputUpMin: "Throughput up min Mbps",
        throughputDownMin: "Throughput down min Mbps",
        loadDeltaMax: "Load delta max ms",
        systemCpuMax: "System CPU max %",
        throughputDurationSec: "Throughput duration sec",
        loadDurationSec: "Load duration sec",
        tcpAttempts: "TCP attempts",
        systemSampleSec: "System sample sec",
      },
      role: { client: "Client", relay: "Relay", server: "Server" },
      runKindValue: {
        system: "System",
        baseline: "Baseline",
        capacity: "Capacity",
        full: "Full",
      },
      runtime: {
        "docker-linux": "Docker Linux",
        "native-macos": "Native macOS",
        "native-windows": "Native Windows",
      },
      severityLabel: {
        info: "Info",
        warning: "Warning",
        error: "Error",
      },
      kindLabel: {
        anomaly: "Anomaly",
        threshold: "Threshold",
        node_status: "Node status",
      },
      statusLabel: {
        online: "Online",
        "push-only": "Push only",
        "pull-only": "Pull only",
        offline: "Offline",
        unpaired: "Unpaired",
        disabled: "Disabled",
        ok: "OK",
        unknown: "Unknown",
        open: "Open",
        acknowledged: "Acknowledged",
        resolved: "Resolved",
        running: "Running",
        queued: "Queued",
        completed: "Completed",
        canceled: "Canceled",
        failed: "Failed",
        pass: "Pass",
        warn: "Warn",
        fail: "Fail",
        skip: "Skip",
        healthy: "Healthy",
        degraded: "Degraded",
        critical: "Critical",
      },
    },
  };

  const state = {
    snapshot: window.__INITIAL_STATE__ || {},
    locale: loadLocale(),
    refreshSec: loadRefreshSec(),
    filtersMeta: null,
    overview: null,
    pathHealth: null,
    metricSeries: null,
    alerts: null,
    runs: null,
    runtimeInfo: null,
    actionHistory: null,
    releaseValidation: null,
    selectedAction: null,
    selectedActionId: null,
    selectedRun: null,
    selectedRunId: null,
    selectedRunEvents: null,
    pendingActionAutoSelectId: null,
    pendingRunAutoSelectId: null,
    activeTab: "overview",
    pairCommands: { primary: "", fallback: "" },
    lastRefreshAt: (window.__INITIAL_STATE__ || {}).generated_at || null,
    lastError: "",
    requestEpochs: {
      snapshot: 0,
      refreshAll: 0,
      actionDetail: 0,
      runDetail: 0,
      releaseValidation: 0,
    },
  };

  const charts = {};
  let refreshTimer = null;
  let actionPollTimer = null;
  let runPollTimer = null;
  let releaseValidationPollTimer = null;

  document.addEventListener("DOMContentLoaded", async () => {
    bindEvents();
    applyLocale();
    hydrateManagement();
    renderHeadlineAlerts();
    await initializeFilters();
    restoreViewState();
    setupAutoRefresh();
    await refreshAll();
    renderPanelStatusMeta();
  });

  function bindEvents() {
    populateRefreshOptions();
    document.getElementById("localeSelect").value = state.locale;
    document.getElementById("autoRefreshSelect").value = String(state.refreshSec);
    document.getElementById("localeSelect").addEventListener("change", async (event) => {
      state.locale = event.target.value;
      safeStorageSet(ADMIN_LOCALE_STORAGE_KEY, state.locale);
      applyLocale();
      rebuildFilterOptions();
      hydrateManagement();
      renderHeadlineAlerts();
      renderAllAnalytics();
    });
    document.getElementById("autoRefreshSelect").addEventListener("change", (event) => {
      state.refreshSec = Number(event.target.value || 0);
      safeStorageSet(ADMIN_REFRESH_STORAGE_KEY, String(state.refreshSec));
      setupAutoRefresh();
      renderPanelStatusMeta();
    });
    document.getElementById("refreshBtn").addEventListener("click", async () => {
      await refreshSnapshot();
      await refreshAll();
    });
    document.getElementById("runReleaseValidationBtn").addEventListener("click", runReleaseValidation);
    document.getElementById("applyFiltersBtn").addEventListener("click", refreshAll);
    document.getElementById("resetFiltersBtn").addEventListener("click", async () => {
      resetFilters();
      await refreshAll();
    });
    document.getElementById("saveSettingsBtn").addEventListener("click", saveSettings);
    document.getElementById("runFullBtn").addEventListener("click", runFullMonitoring);
    document.getElementById("copyPrimaryBtn").addEventListener("click", () => copyText(state.pairCommands.primary));
    document.getElementById("copyFallbackBtn").addEventListener("click", () => copyText(state.pairCommands.fallback));
    document.getElementById("path-focus-select").addEventListener("change", () => renderPathExplorer());
    document.getElementById("tabButtons").addEventListener("click", (event) => {
      const button = event.target.closest("[data-tab]");
      if (!button) {
        return;
      }
      setActiveTab(button.dataset.tab);
    });
    document.getElementById("nodeGrid").addEventListener("click", async (event) => {
      const suggestedButton = event.target.closest("button[data-suggested-kind]");
      if (suggestedButton && await invokeSuggestedActionFromButton(suggestedButton)) {
        return;
      }
      const detailButton = event.target.closest("button[data-action-detail]");
      if (detailButton) {
        await loadActionDetail(Number(detailButton.dataset.actionDetail), { refreshRuntime: false });
        return;
      }
      const button = event.target.closest("button[data-action]");
      if (!button) {
        return;
      }
      const card = button.closest("[data-role]");
      if (!card) {
        return;
      }
      if (button.dataset.action === "save-node") {
        await saveNodeCard(card);
      }
      if (button.dataset.action === "pair-node") {
        await generatePairCode(card);
      }
      if (button.dataset.action === "node-control") {
        await queueNodeAction(card, button.dataset.controlAction);
      }
    });
    document.getElementById("panelRuntimeCard").addEventListener("click", async (event) => {
      const suggestedButton = event.target.closest("button[data-suggested-kind]");
      if (suggestedButton && await invokeSuggestedActionFromButton(suggestedButton)) {
        return;
      }
      const detailButton = event.target.closest("button[data-action-detail]");
      if (detailButton) {
        await loadActionDetail(Number(detailButton.dataset.actionDetail), { refreshRuntime: false });
        return;
      }
      const button = event.target.closest("button[data-panel-action]");
      if (!button) {
        return;
      }
      await queuePanelAction(button.dataset.panelAction);
    });
    document.getElementById("operationsFocus").addEventListener("click", async (event) => {
      const suggestedButton = event.target.closest("button[data-suggested-kind]");
      if (suggestedButton && await invokeSuggestedActionFromButton(suggestedButton)) {
        return;
      }
      const runButton = event.target.closest("button[data-open-run]");
      if (runButton) {
        state.selectedRunId = String(runButton.dataset.openRun);
        setActiveTab("runs");
        await loadSelectedRunDetail(String(runButton.dataset.openRun), { refreshRunsList: true, silent: true }).catch(() => undefined);
        return;
      }
      const detailButton = event.target.closest("button[data-action-detail]");
      if (detailButton) {
        await loadActionDetail(Number(detailButton.dataset.actionDetail), { refreshRuntime: false });
        return;
      }
      const nodeButton = event.target.closest("button[data-focus-node]");
      if (nodeButton) {
        focusNodeCard(nodeButton.dataset.focusNode);
        return;
      }
      const panelButton = event.target.closest("button[data-focus-panel]");
      if (panelButton) {
        focusPanelRuntimeCard();
      }
    });
    document.getElementById("releaseValidationBody").addEventListener("click", async (event) => {
      const suggestedButton = event.target.closest("button[data-suggested-kind]");
      if (suggestedButton && await invokeSuggestedActionFromButton(suggestedButton)) {
        return;
      }
      const nodeButton = event.target.closest("button[data-focus-node]");
      if (nodeButton) {
        focusNodeCard(nodeButton.dataset.focusNode);
        return;
      }
      const panelButton = event.target.closest("button[data-focus-panel]");
      if (panelButton) {
        focusPanelRuntimeCard();
      }
    });
    document.getElementById("actionsTableBody").addEventListener("click", async (event) => {
      const row = event.target.closest("tr[data-action-id]");
      if (!row) {
        return;
      }
      await loadActionDetail(Number(row.dataset.actionId), { refreshRuntime: false });
    });
    document.getElementById("alertsTableBody").addEventListener("click", async (event) => {
      const button = event.target.closest("button[data-alert-action]");
      if (!button) {
        return;
      }
      const alertId = Number(button.dataset.alertId);
      if (!alertId) {
        return;
      }
      if (button.dataset.alertAction === "ack") {
        await acknowledgeAlert(alertId);
      }
      if (button.dataset.alertAction === "silence") {
        await silenceAlert(alertId);
      }
      if (button.dataset.alertAction === "history") {
        await showAlertHistory(button.dataset.fingerprint);
      }
    });
    document.getElementById("runsTableBody").addEventListener("click", async (event) => {
      const row = event.target.closest("[data-run-id]");
      if (!row) {
        return;
      }
      await loadRunDetail(row.dataset.runId);
    });
    document.getElementById("actionDetail").addEventListener("click", async (event) => {
      const suggestedButton = event.target.closest("button[data-suggested-kind]");
      if (suggestedButton && await invokeSuggestedActionFromButton(suggestedButton)) {
        return;
      }
      const runButton = event.target.closest("button[data-open-run]");
      if (runButton) {
        state.selectedRunId = String(runButton.dataset.openRun);
        setActiveTab("runs");
        await loadSelectedRunDetail(String(runButton.dataset.openRun), { refreshRunsList: true, silent: true }).catch(() => undefined);
        return;
      }
      const nodeButton = event.target.closest("button[data-focus-node]");
      if (nodeButton) {
        focusNodeCard(nodeButton.dataset.focusNode);
        return;
      }
      const panelButton = event.target.closest("button[data-focus-panel]");
      if (panelButton) {
        focusPanelRuntimeCard();
      }
    });
    document.getElementById("runDetail").addEventListener("click", async (event) => {
      const suggestedButton = event.target.closest("button[data-suggested-kind]");
      if (suggestedButton && await invokeSuggestedActionFromButton(suggestedButton)) {
        return;
      }
      const nodeButton = event.target.closest("button[data-focus-node]");
      if (nodeButton) {
        focusNodeCard(nodeButton.dataset.focusNode);
      }
    });
    document.getElementById("runEvents").addEventListener("click", async (event) => {
      const suggestedButton = event.target.closest("button[data-suggested-kind]");
      if (suggestedButton && await invokeSuggestedActionFromButton(suggestedButton)) {
        return;
      }
      const nodeButton = event.target.closest("button[data-focus-node]");
      if (nodeButton) {
        focusNodeCard(nodeButton.dataset.focusNode);
      }
    });
    window.addEventListener("resize", () => Object.values(charts).forEach((chart) => chart.resize()));
  }

  async function initializeFilters() {
    state.filtersMeta = await fetchJson("/api/v1/admin/filters");
    const timeRanges = state.filtersMeta?.time_ranges || DEFAULT_TIME_RANGES;
    populateSingleSelect("filter-time-range", timeRanges, "24h");
    populateMultiSelect("filter-roles", state.filtersMeta?.roles || FIXED_ROLES);
    populateMultiSelect("filter-nodes", (state.filtersMeta?.nodes || []).map((item) => item.node_name));
    populateMultiSelect("filter-paths", state.filtersMeta?.paths || []);
    populateMultiSelect("filter-probes", state.filtersMeta?.probes || []);
    populateSingleSelect("filter-metric", state.filtersMeta?.metrics || ["rtt_avg_ms"], "rtt_avg_ms");
    populateMultiSelect("filter-run-kinds", state.filtersMeta?.run_kinds || ["system", "baseline", "capacity", "full"]);
    populateMultiSelect("filter-severities", state.filtersMeta?.severities || ["warning", "error", "info"]);
    populateMultiSelect("filter-alert-statuses", state.filtersMeta?.statuses || ["open", "acknowledged", "resolved"], ["open", "acknowledged"]);
    populateSingleSelect("filter-only-anomalies", ["false", "true"], "false");
    populateSingleSelect("filter-include-resolved", ["false", "true"], "false");
    populateSingleSelect("path-focus-select", ["", ...(state.filtersMeta?.paths || [])], "");
  }

  function restoreViewState() {
    const savedFilters = loadSavedFilters();
    if (savedFilters) {
      setSelectedValue("filter-time-range", savedFilters.timeRange || "24h");
      setSelectedValues("filter-roles", savedFilters.roles || []);
      setSelectedValues("filter-nodes", savedFilters.nodes || []);
      setSelectedValues("filter-paths", savedFilters.paths || []);
      setSelectedValues("filter-probes", savedFilters.probes || []);
      setSelectedValue("filter-metric", savedFilters.metric || "rtt_avg_ms");
      setSelectedValues("filter-run-kinds", savedFilters.runKinds || []);
      setSelectedValues("filter-severities", savedFilters.severities || []);
      setSelectedValues("filter-alert-statuses", savedFilters.alertStatuses || ["open", "acknowledged"]);
      setSelectedValue("filter-only-anomalies", String(Boolean(savedFilters.onlyAnomalies)));
      setSelectedValue("filter-include-resolved", String(Boolean(savedFilters.includeResolved)));
      setSelectedValue("path-focus-select", savedFilters.pathFocus || "");
    }
    const savedTab = safeStorageGet(ADMIN_TAB_STORAGE_KEY);
    if (savedTab && document.querySelector(`[data-tab="${savedTab}"]`)) {
      setActiveTab(savedTab);
    }
  }

  function populateRefreshOptions() {
    document.getElementById("autoRefreshSelect").innerHTML = [
      { value: 0, label: t("refreshOff") },
      { value: 15, label: t("refresh15") },
      { value: 30, label: t("refresh30") },
      { value: 60, label: t("refresh60") },
    ].map((item) => `<option value="${item.value}" ${Number(item.value) === state.refreshSec ? "selected" : ""}>${escapeHtml(item.label)}</option>`).join("");
  }

  function setupAutoRefresh() {
    if (refreshTimer) {
      window.clearInterval(refreshTimer);
      refreshTimer = null;
    }
    if (state.refreshSec > 0) {
      refreshTimer = window.setInterval(() => {
        refreshSnapshot()
          .then(refreshAll)
          .catch(() => undefined);
      }, state.refreshSec * 1000);
    }
  }

  function populateSingleSelect(id, options, selected) {
    const select = document.getElementById(id);
    select.innerHTML = options.map((value) => {
      const label = selectOptionLabel(value);
      return `<option value="${escapeHtml(value)}" ${value === selected ? "selected" : ""}>${escapeHtml(label)}</option>`;
    }).join("");
  }

  function populateMultiSelect(id, options, selected = []) {
    const wanted = new Set(selected);
    const select = document.getElementById(id);
    select.innerHTML = options.map((value) => {
      const label = selectOptionLabel(value);
      return `<option value="${escapeHtml(value)}" ${wanted.has(value) ? "selected" : ""}>${escapeHtml(label)}</option>`;
    }).join("");
  }

  function nextRequestEpoch(key) {
    state.requestEpochs[key] = Number(state.requestEpochs[key] || 0) + 1;
    return state.requestEpochs[key];
  }

  function isLatestRequest(key, epoch) {
    return Number(state.requestEpochs[key] || 0) === Number(epoch);
  }

  function updateLastRefreshAt(...payloads) {
    const generatedAt = payloads
      .map((payload) => payload?.generated_at)
      .find((value) => typeof value === "string" && value);
    if (generatedAt) {
      state.lastRefreshAt = generatedAt;
    }
  }

  function rebuildFilterOptions() {
    if (!state.filtersMeta) {
      return;
    }
    const current = {
      timeRange: selectedValue("filter-time-range"),
      roles: selectedValues("filter-roles"),
      nodes: selectedValues("filter-nodes"),
      paths: selectedValues("filter-paths"),
      probes: selectedValues("filter-probes"),
      metric: selectedValue("filter-metric"),
      runKinds: selectedValues("filter-run-kinds"),
      severities: selectedValues("filter-severities"),
      statuses: selectedValues("filter-alert-statuses"),
      onlyAnomalies: selectedValue("filter-only-anomalies"),
      includeResolved: selectedValue("filter-include-resolved"),
      pathFocus: selectedValue("path-focus-select"),
    };
    populateSingleSelect("filter-time-range", state.filtersMeta.time_ranges || DEFAULT_TIME_RANGES, current.timeRange || "24h");
    populateMultiSelect("filter-roles", state.filtersMeta.roles || FIXED_ROLES, current.roles);
    populateMultiSelect("filter-nodes", (state.filtersMeta.nodes || []).map((item) => item.node_name), current.nodes);
    populateMultiSelect("filter-paths", state.filtersMeta.paths || [], current.paths);
    populateMultiSelect("filter-probes", state.filtersMeta.probes || [], current.probes);
    populateSingleSelect("filter-metric", state.filtersMeta.metrics || ["rtt_avg_ms"], current.metric || "rtt_avg_ms");
    populateMultiSelect("filter-run-kinds", state.filtersMeta.run_kinds || ["system", "baseline", "capacity", "full"], current.runKinds);
    populateMultiSelect("filter-severities", state.filtersMeta.severities || ["warning", "error", "info"], current.severities);
    populateMultiSelect("filter-alert-statuses", state.filtersMeta.statuses || ["open", "acknowledged", "resolved"], current.statuses);
    populateSingleSelect("filter-only-anomalies", ["false", "true"], current.onlyAnomalies || "false");
    populateSingleSelect("filter-include-resolved", ["false", "true"], current.includeResolved || "false");
    populateSingleSelect("path-focus-select", ["", ...(state.filtersMeta.paths || [])], current.pathFocus || "");
  }

  async function refreshSnapshot() {
    const epoch = nextRequestEpoch("snapshot");
    const snapshot = await fetchJson("/api/v1/dashboard");
    if (!isLatestRequest("snapshot", epoch)) {
      return;
    }
    state.snapshot = snapshot;
    updateLastRefreshAt(snapshot);
    hydrateManagement();
    renderHeadlineAlerts();
  }

  async function refreshAll() {
    const epoch = nextRequestEpoch("refreshAll");
    const filters = readFilters();
    const alertStatuses = filters.includeResolved
      ? selectedValues("filter-alert-statuses")
      : (selectedValues("filter-alert-statuses").length ? selectedValues("filter-alert-statuses") : ["open", "acknowledged"]);
    const queryBase = buildQuery({
      time_range: filters.timeRange,
      role: filters.roles,
      node: filters.nodes,
      path_label: filters.paths,
    });
    const metricQuery = buildQuery({
      time_range: filters.timeRange,
      role: filters.roles,
      node: filters.nodes,
      path_label: filters.paths.slice(0, 4),
      probe_name: filters.probes,
      metric_name: filters.metric,
      bucket: "auto",
    });
    const alertsQuery = buildQuery({
      time_range: filters.timeRange,
      severity: filters.severities,
      status: alertStatuses,
      kind: filters.onlyAnomalies ? ["anomaly"] : [],
      path_label: filters.paths,
      metric_name: filters.metric ? [filters.metric] : [],
      anomaly_only: String(filters.onlyAnomalies),
    });
    const runsQuery = buildQuery({
      time_range: filters.timeRange,
      run_kind: filters.runKinds,
      path_label: filters.paths,
      has_findings: filters.onlyAnomalies ? "true" : "",
    });

    try {
      const releaseValidationEpoch = nextRequestEpoch("releaseValidation");
      const [overview, pathHealth, metricSeries, alerts, runs, runtimeInfo, actions, releaseValidation] = await Promise.all([
        fetchJson(`/api/v1/admin/overview?${queryBase.toString()}`),
        fetchJson(`/api/v1/admin/path-health?${queryBase.toString()}`),
        fetchJson(`/api/v1/admin/timeseries?${metricQuery.toString()}`),
        fetchJson(`/api/v1/admin/alerts?${alertsQuery.toString()}`),
        fetchJson(`/api/v1/admin/runs?${runsQuery.toString()}`),
        fetchJson("/api/v1/admin/runtime"),
        fetchJson("/api/v1/admin/actions?limit=40"),
        fetchJson("/api/v1/admin/release-validation"),
      ]);
      if (!isLatestRequest("refreshAll", epoch)) {
        return;
      }
      state.overview = overview;
      state.pathHealth = pathHealth;
      state.metricSeries = metricSeries;
      state.alerts = alerts;
      state.runs = runs;
      state.runtimeInfo = runtimeInfo;
      state.actionHistory = actions;
      if (isLatestRequest("releaseValidation", releaseValidationEpoch)) {
        state.releaseValidation = releaseValidation;
      }
      const selectedActionId = resolveSelectedActionId(actions.items || []);
      state.selectedActionId = selectedActionId;
      if (selectedActionId) {
        const actionDetailEpoch = nextRequestEpoch("actionDetail");
        const detail = await fetchJson(`/api/v1/admin/actions/${encodeURIComponent(selectedActionId)}`).catch((error) => {
          if (error?.payload?.detail === "Action not found") {
            return null;
          }
          throw error;
        });
        if (detail === null) {
          state.selectedActionId = null;
          state.selectedAction = null;
        } else if (isLatestRequest("actionDetail", actionDetailEpoch) && isLatestRequest("refreshAll", epoch)) {
          state.selectedAction = detail;
          state.selectedActionId = Number(detail.id);
          if (state.pendingActionAutoSelectId && Number(state.pendingActionAutoSelectId) === Number(detail.id)) {
            state.pendingActionAutoSelectId = null;
          }
        }
      } else {
        state.selectedAction = null;
      }
      const selectedRunId = resolveSelectedRunId(runs.items || []);
      state.selectedRunId = selectedRunId;
      if (selectedRunId) {
        const runDetailEpoch = nextRequestEpoch("runDetail");
        const [runDetail, runEvents] = await Promise.all([
          fetchJson(`/api/v1/admin/runs/${encodeURIComponent(selectedRunId)}`).catch((error) => {
            if (error?.payload?.detail === "Run not found") {
              return null;
            }
            throw error;
          }),
          fetchJson(`/api/v1/admin/runs/${encodeURIComponent(selectedRunId)}/events`).catch((error) => {
            if (error?.payload?.detail === "Run not found") {
              return { items: [] };
            }
            throw error;
          }),
        ]);
        if (runDetail === null) {
          state.selectedRunId = null;
          state.selectedRun = null;
          state.selectedRunEvents = [];
        } else if (isLatestRequest("runDetail", runDetailEpoch) && isLatestRequest("refreshAll", epoch)) {
          state.selectedRun = runDetail;
          state.selectedRunEvents = runEvents.items || [];
          state.selectedRunId = String(runDetail.run_id);
          if (state.pendingRunAutoSelectId && String(state.pendingRunAutoSelectId) === String(runDetail.run_id)) {
            state.pendingRunAutoSelectId = null;
          }
        }
      } else {
        state.selectedRun = null;
        state.selectedRunEvents = [];
      }
      updateLastRefreshAt(runtimeInfo, overview, releaseValidation, state.snapshot);
      state.lastError = "";
      saveCurrentFilters();
      renderAllAnalytics();
      renderPanelStatusMeta();
      scheduleActionPolling();
      scheduleRunPolling();
      scheduleReleaseValidationPolling();
    } catch (error) {
      if (!isLatestRequest("refreshAll", epoch)) {
        return;
      }
      state.lastError = error.message || String(error);
      renderPanelStatusMeta();
      showMessage(error.message || String(error), "error");
    }
  }

  function resolveSelectedActionId(items) {
    const list = items || [];
    if (!list.length) {
      if (state.selectedActionId && !state.pendingActionAutoSelectId) {
        state.selectedAction = null;
      }
      return null;
    }
    if (state.selectedActionId && list.some((item) => Number(item.id) === Number(state.selectedActionId))) {
      return Number(state.selectedActionId);
    }
    if (state.pendingActionAutoSelectId && list.some((item) => Number(item.id) === Number(state.pendingActionAutoSelectId))) {
      return Number(state.pendingActionAutoSelectId);
    }
    return null;
  }

  function resolveSelectedRunId(items) {
    const list = items || [];
    if (!list.length) {
      return null;
    }
    if (state.selectedRunId && list.some((item) => String(item.run_id) === String(state.selectedRunId))) {
      return String(state.selectedRunId);
    }
    if (state.pendingRunAutoSelectId && list.some((item) => String(item.run_id) === String(state.pendingRunAutoSelectId))) {
      return String(state.pendingRunAutoSelectId);
    }
    return null;
  }

  async function loadActionDetail(actionId, options = {}) {
    if (!actionId) {
      state.selectedAction = null;
      state.selectedActionId = null;
      renderActionDetail();
      renderActionHistory();
      clearActionPolling();
      return null;
    }
    const epoch = nextRequestEpoch("actionDetail");
    const refreshRuntime = options.refreshRuntime !== false;
    const silent = Boolean(options.silent);
    try {
      const requests = [
        fetchJson("/api/v1/admin/actions?limit=40"),
        fetchJson(`/api/v1/admin/actions/${encodeURIComponent(actionId)}`),
      ];
      if (refreshRuntime) {
        requests.push(fetchJson("/api/v1/admin/runtime"));
      }
      const [actions, detail, runtimeInfo] = await Promise.all(requests);
      if (!isLatestRequest("actionDetail", epoch)) {
        return state.selectedAction;
      }
      state.actionHistory = actions;
      state.selectedAction = detail;
      state.selectedActionId = Number(detail.id);
      if (state.pendingActionAutoSelectId && Number(state.pendingActionAutoSelectId) === Number(detail.id)) {
        state.pendingActionAutoSelectId = null;
      }
      if (runtimeInfo) {
        state.runtimeInfo = runtimeInfo;
        updateLastRefreshAt(runtimeInfo);
      }
      renderRuntimeControl();
      renderNodeCards();
      renderReleaseValidation();
      renderActionHistory();
      renderActionDetail();
      scheduleActionPolling();
      return detail;
    } catch (error) {
      if (error?.payload?.detail === "Action not found") {
        if (isLatestRequest("actionDetail", epoch)) {
          state.selectedAction = null;
          state.selectedActionId = null;
          renderActionHistory();
          renderActionDetail();
          clearActionPolling();
        }
        return null;
      }
      if (!silent) {
        showMessage(error.message || String(error), "error");
      }
      throw error;
    }
  }

  function clearActionPolling() {
    if (actionPollTimer) {
      window.clearTimeout(actionPollTimer);
      actionPollTimer = null;
    }
  }

  function scheduleActionPolling() {
    clearActionPolling();
    if (!state.selectedAction || !state.selectedAction.active) {
      return;
    }
    actionPollTimer = window.setTimeout(async () => {
      try {
        await loadActionDetail(Number(state.selectedAction.id), { refreshRuntime: true, silent: true });
      } catch (error) {
        return;
      }
    }, 1500);
  }

  function highlightTargetElement(element) {
    if (!element) {
      return;
    }
    element.classList.add("focused-target");
    element.scrollIntoView({ behavior: "smooth", block: "center" });
    window.setTimeout(() => element.classList.remove("focused-target"), 1800);
  }

  function focusNodeCard(nodeId) {
    if (!nodeId) {
      return;
    }
    setActiveTab("management");
    window.requestAnimationFrame(() => {
      const card = document.querySelector(`#nodeGrid [data-node-id="${escapeSelector(String(nodeId))}"]`);
      highlightTargetElement(card);
    });
  }

  function focusPanelRuntimeCard() {
    setActiveTab("management");
    window.requestAnimationFrame(() => {
      const card = document.querySelector("#panelRuntimeCard .card");
      highlightTargetElement(card);
    });
  }

  function escapeSelector(value) {
    return String(value).replace(/\\/g, "\\\\").replace(/"/g, '\\"');
  }

  function suggestedActionLabel(action) {
    if (!action) {
      return "";
    }
    switch (action.kind) {
      case "open_node":
        return t("openNode");
      case "open_panel":
        return t("openPanel");
      case "open_run":
        return t("openRun");
      case "open_action":
        return t("viewAction");
      case "sync_runtime":
        return t("syncRuntime");
      case "tail_log":
        return t("tailLog");
      default:
        return action.label || t("viewDetail");
    }
  }

  function renderSuggestedActionButton(action, extraStyle = "") {
    if (!action || !action.kind) {
      return "";
    }
    const attrs = [
      `data-suggested-kind="${escapeHtml(String(action.kind))}"`,
      `data-suggested-target-kind="${escapeHtml(String(action.target_kind || ""))}"`,
    ];
    if (action.target_id !== undefined && action.target_id !== null) {
      attrs.push(`data-suggested-target-id="${escapeHtml(String(action.target_id))}"`);
    }
    if (action.run_id) {
      attrs.push(`data-suggested-run-id="${escapeHtml(String(action.run_id))}"`);
    }
    if (action.action_id !== undefined && action.action_id !== null) {
      attrs.push(`data-suggested-action-id="${escapeHtml(String(action.action_id))}"`);
    }
    const className = action.dangerous ? "danger" : "";
    const style = extraStyle ? ` style="${escapeHtml(extraStyle)}"` : "";
    return `<button type="button" class="${escapeHtml(className)}" ${attrs.join(" ")}${style}>${escapeHtml(suggestedActionLabel(action))}</button>`;
  }

  async function invokeSuggestedAction(action) {
    if (!action || !action.kind) {
      return false;
    }
    const kind = action.kind;
    const targetKind = action.target_kind;
    const targetId = action.target_id !== undefined && action.target_id !== null ? Number(action.target_id) : null;
    const runId = action.run_id || null;
    const actionId = action.action_id !== undefined && action.action_id !== null ? Number(action.action_id) : null;
    if (kind === "open_node" && targetId) {
      focusNodeCard(targetId);
      return true;
    }
    if (kind === "open_panel") {
      focusPanelRuntimeCard();
      return true;
    }
    if (kind === "open_run" && runId) {
      state.selectedRunId = String(runId);
      setActiveTab("runs");
      await loadSelectedRunDetail(String(runId), { refreshRunsList: true, silent: true }).catch(() => undefined);
      return true;
    }
    if (kind === "open_action" && actionId) {
      await loadActionDetail(Number(actionId), { refreshRuntime: true, silent: true }).catch(() => undefined);
      return true;
    }
    if (kind === "sync_runtime") {
      if (targetKind === "panel") {
        await queuePanelAction("sync_runtime");
        return true;
      }
      if (targetKind === "node" && targetId) {
        await submitControlAction(`/api/v1/admin/nodes/${targetId}/actions`, "sync_runtime");
        return true;
      }
    }
    if (kind === "tail_log") {
      if (targetKind === "panel") {
        await queuePanelAction("tail_log");
        return true;
      }
      if (targetKind === "node" && targetId) {
        await submitControlAction(`/api/v1/admin/nodes/${targetId}/actions`, "tail_log");
        return true;
      }
    }
    return false;
  }

  async function invokeSuggestedActionFromButton(button) {
    if (!button) {
      return false;
    }
    return invokeSuggestedAction({
      kind: button.dataset.suggestedKind,
      target_kind: button.dataset.suggestedTargetKind,
      target_id: button.dataset.suggestedTargetId ? Number(button.dataset.suggestedTargetId) : null,
      run_id: button.dataset.suggestedRunId || null,
      action_id: button.dataset.suggestedActionId ? Number(button.dataset.suggestedActionId) : null,
    });
  }

  async function loadSelectedRunDetail(runId, options = {}) {
    if (!runId) {
      state.selectedRun = null;
      state.selectedRunId = null;
      state.selectedRunEvents = [];
      renderRuns();
      clearRunPolling();
      return null;
    }
    const epoch = nextRequestEpoch("runDetail");
    const silent = Boolean(options.silent);
    try {
      const requests = [
        fetchJson(`/api/v1/admin/runs/${encodeURIComponent(runId)}`),
        fetchJson(`/api/v1/admin/runs/${encodeURIComponent(runId)}/events`),
      ];
      if (options.refreshRunsList !== false) {
        requests.unshift(fetchJson(`/api/v1/admin/runs?${buildRunsQuery().toString()}`));
      }
      const responses = await Promise.all(requests);
      if (!isLatestRequest("runDetail", epoch)) {
        return state.selectedRun;
      }
      if (options.refreshRunsList !== false) {
        state.runs = responses[0];
        state.selectedRun = responses[1];
        state.selectedRunEvents = responses[2].items || [];
      } else {
        state.selectedRun = responses[0];
        state.selectedRunEvents = responses[1].items || [];
      }
      state.selectedRunId = String(runId);
      if (state.pendingRunAutoSelectId && String(state.pendingRunAutoSelectId) === String(runId)) {
        state.pendingRunAutoSelectId = null;
      }
      renderRuns();
      scheduleRunPolling();
      return state.selectedRun;
    } catch (error) {
      if (error?.payload?.detail === "Run not found") {
        if (isLatestRequest("runDetail", epoch)) {
          state.selectedRun = null;
          state.selectedRunId = null;
          state.selectedRunEvents = [];
          renderRuns();
          clearRunPolling();
        }
        return null;
      }
      if (!silent) {
        showMessage(error.message || String(error), "error");
      }
      throw error;
    }
  }

  function clearRunPolling() {
    if (runPollTimer) {
      window.clearTimeout(runPollTimer);
      runPollTimer = null;
    }
  }

  function scheduleRunPolling() {
    clearRunPolling();
    if (!state.selectedRun || state.selectedRun.status !== "running") {
      return;
    }
    runPollTimer = window.setTimeout(async () => {
      try {
        await loadSelectedRunDetail(String(state.selectedRun.run_id), { refreshRunsList: true, silent: true });
      } catch (error) {
        return;
      }
    }, 1500);
  }

  function renderPanelStatusMeta() {
    const target = document.getElementById("panelStatusMeta");
    const refreshLabel = state.refreshSec > 0 ? `${state.refreshSec}s` : t("refreshOff");
    const base = state.lastRefreshAt
      ? `${t("refreshStatusOk")} · ${formatTimestamp(state.lastRefreshAt)}`
      : t("refreshStatusReady");
    const extras = [];
    const activeRun = state.runtimeInfo?.active_run;
    const attentionSummary = state.runtimeInfo?.attention?.summary || {};
    if (activeRun?.run_id) {
      extras.push(`${t("activeRunNow")}: ${activeRun.run_id}`);
    }
    if ((attentionSummary.total || 0) > 0) {
      extras.push(`${t("attentionSummary")}: ${attentionSummary.total}`);
    }
    const statusText = state.lastError
      ? `${t("refreshStatusError")}: ${state.lastError} · ${t("autoRefresh")}: ${refreshLabel}`
      : `${base} · ${t("autoRefresh")}: ${refreshLabel}`;
    target.textContent = extras.length ? `${statusText} · ${extras.join(" · ")}` : statusText;
  }

  function renderAllAnalytics() {
    renderOverview();
    renderPathExplorer();
    renderMetricExplorer();
    renderAlerts();
    renderRuns();
    renderRunLauncherState();
    renderRuntimeControl();
    renderOperationsFocus();
    renderReleaseValidation();
    renderActionHistory();
    renderActionDetail();
    renderFiltersSummary();
  }

  function clearReleaseValidationPolling() {
    if (releaseValidationPollTimer) {
      window.clearTimeout(releaseValidationPollTimer);
      releaseValidationPollTimer = null;
    }
  }

  function scheduleReleaseValidationPolling() {
    clearReleaseValidationPolling();
    if (!state.releaseValidation?.running) {
      return;
    }
    releaseValidationPollTimer = window.setTimeout(async () => {
      try {
        await loadReleaseValidation({ silent: true });
      } catch (error) {
        return;
      }
    }, 1500);
  }

  function renderHeadlineAlerts() {
    const alerts = state.snapshot?.alerts || [];
    const root = document.getElementById("headlineAlerts");
    document.getElementById("topologyCaption").textContent = state.snapshot?.settings?.topology_name || "";
    if (!alerts.length) {
      root.innerHTML = `<div class="empty">${escapeHtml(t("noAlerts"))}</div>`;
      return;
    }
    root.innerHTML = alerts.slice(0, 4).map((alert) => `
      <div class="card">
        <div class="section-head">
          <strong>${escapeHtml(kindLabel(alert.kind))}</strong>
          <span class="status-pill ${escapeHtml(alert.severity || alert.status)}">${escapeHtml(severityLabel(alert.severity || alert.status))}</span>
        </div>
        <p>${escapeHtml(alert.message || "")}</p>
        <div class="muted">${escapeHtml(formatTimestamp(alert.created_at))}</div>
      </div>
    `).join("");
  }

  function renderOverview() {
    const overview = state.overview;
    if (!overview) {
      return;
    }
    const kpis = overview.kpis || {};
    const items = [
      { label: "healthScore", value: kpis.health_score ?? 0, meta: "" },
      { label: "onlineRate", value: `${Number(kpis.online_rate_pct || 0).toFixed(1)}%`, meta: "" },
      { label: "activeAlerts", value: kpis.active_alerts ?? 0, meta: "" },
      { label: "lastFullRun", value: statusLabel(kpis.last_full_run_status || ""), meta: formatTimestamp(kpis.last_full_run_started_at) },
    ];
    document.getElementById("overviewKpis").innerHTML = items.map((item) => `
      <div class="card">
        <div class="muted">${escapeHtml(kpiLabel(item.label))}</div>
        <div class="kpi-value">${escapeHtml(String(item.value || t("noData")))}</div>
        <div class="muted">${escapeHtml(item.meta || "")}</div>
      </div>
    `).join("");

    const anomalies = overview.recent_anomalies || [];
    document.getElementById("overviewAnomalies").innerHTML = anomalies.length ? anomalies.map((alert) => `
      <div class="card">
        <div class="section-head">
          <strong>${escapeHtml(pathLabel(alert.path_label))}</strong>
          <span class="status-pill ${escapeHtml(alert.severity || "warning")}">${escapeHtml(severityLabel(alert.severity || "warning"))}</span>
        </div>
        <p>${escapeHtml(alert.message || "")}</p>
        <div class="muted">${escapeHtml(formatTimestamp(alert.created_at))}</div>
      </div>
    `).join("") : `<div class="empty">${escapeHtml(t("noAlerts"))}</div>`;

    const pathHealth = overview.path_health || [];
    document.getElementById("overviewPathGrid").innerHTML = pathHealth.length ? pathHealth.map((item) => `
      <div class="card">
        <div class="section-head">
          <h3>${escapeHtml(pathLabel(item.path_label))}</h3>
          <span class="status-pill ${escapeHtml(item.status)}">${escapeHtml(statusLabel(item.status))}</span>
        </div>
        <div class="muted">${escapeHtml(summarizeMetrics(item.latest || {}))}</div>
        <div class="muted">${escapeHtml(t("recentAlerts"))}: ${item.open_alerts || 0}</div>
      </div>
    `).join("") : `<div class="empty">${escapeHtml(t("noData"))}</div>`;

    renderPieChart("statusChart", overview.status_distribution || {});
    renderGroupChart("overviewLatencyChart", overview.trend_groups?.latency, t("latencyTrend"));
    renderGroupChart("overviewLossChart", overview.trend_groups?.loss, t("lossTrend"));
    renderGroupChart("overviewThroughputChart", overview.trend_groups?.throughput, t("throughputTrend"));
    renderGroupChart("overviewSystemChart", overview.trend_groups?.system, t("systemTrend"));
  }

  function renderPathExplorer() {
    const pathHealth = state.pathHealth;
    if (!pathHealth) {
      return;
    }
    const focus = document.getElementById("path-focus-select").value;
    const paths = focus ? (pathHealth.paths || []).filter((item) => item.path_label === focus) : (pathHealth.paths || []);
    document.getElementById("pathExplorerCaption").textContent = focus ? pathLabel(focus) : t("pathExplorerHint");
    document.getElementById("pathSummaryCards").innerHTML = paths.length ? paths.map((item) => `
      <div class="card">
        <div class="section-head">
          <h3>${escapeHtml(pathLabel(item.path_label))}</h3>
          <span class="status-pill ${escapeHtml(item.status)}">${escapeHtml(statusLabel(item.status))}</span>
        </div>
        <div class="muted">${escapeHtml(summarizeMetrics(item.latest || {}))}</div>
        <div class="muted">${escapeHtml(formatTimestamp(item.last_captured_at))}</div>
      </div>
    `).join("") : `<div class="empty">${escapeHtml(t("noData"))}</div>`;

    renderMetricResponseChart("pathLatencyChart", pathHealth.trend_groups?.latency, t("latencyTrend"));
    renderMetricResponseChart("pathLossChart", pathHealth.trend_groups?.loss, t("lossTrend"));
    renderMetricResponseChart("pathThroughputChart", combineMetricResponses([
      pathHealth.trend_groups?.throughput_down,
      pathHealth.trend_groups?.throughput_up,
    ]), t("throughputTrend"));
    renderMetricResponseChart("pathLoadChart", pathHealth.trend_groups?.load, t("loadTrend"));
  }

  function renderMetricExplorer() {
    if (!state.metricSeries) {
      return;
    }
    document.getElementById("metricExplorerCaption").textContent = metricLabel(state.metricSeries.metric_name || "");
    renderMetricResponseChart("metricExplorerChart", state.metricSeries, t("metricExplorerHeadline"));
    const series = (state.metricSeries.series || []).slice(0, 4);
    document.getElementById("metricSeriesSummary").innerHTML = series.length ? series.map((item) => `
      <div class="card">
        <h3>${escapeHtml(pathLabel(item.path_label || item.name))}</h3>
        <div class="muted">${escapeHtml(metricLabel(state.metricSeries.metric_name || ""))}</div>
        <div class="kpi-value">${escapeHtml(formatMetricValue(state.metricSeries.metric_name || "", item.summary?.latest))}</div>
        <div class="muted">${escapeHtml(t("minimum"))} ${escapeHtml(formatMetricValue(state.metricSeries.metric_name || "", item.summary?.min))} | ${escapeHtml(t("maximum"))} ${escapeHtml(formatMetricValue(state.metricSeries.metric_name || "", item.summary?.max))}</div>
      </div>
    `).join("") : `<div class="empty">${escapeHtml(t("noData"))}</div>`;
  }

  function renderAlerts() {
    const root = document.getElementById("alertSummaryCards");
    const body = document.getElementById("alertsTableBody");
    const payload = state.alerts || { summary: {}, items: [] };
    const summary = payload.summary || {};
    root.innerHTML = [
      { label: "open", value: summary.open || 0 },
      { label: "acknowledged", value: summary.acknowledged || 0 },
      { label: "resolved", value: summary.resolved || 0 },
      { label: "silenced", value: summary.silenced || 0 },
    ].map((item) => `
      <div class="card">
        <div class="muted">${escapeHtml(statusLabel(item.label))}</div>
        <div class="kpi-value">${escapeHtml(String(item.value))}</div>
      </div>
    `).join("");

    if (!(payload.items || []).length) {
      body.innerHTML = `<tr><td colspan="8"><div class="empty">${escapeHtml(t("noAlerts"))}</div></td></tr>`;
      return;
    }
    body.innerHTML = payload.items.map((alert) => `
      <tr>
        <td><span class="status-pill ${escapeHtml(alert.severity || "")}">${escapeHtml(severityLabel(alert.severity || ""))}</span></td>
        <td>${escapeHtml(kindLabel(alert.kind))}</td>
        <td>${escapeHtml(pathLabel(alert.path_label || ""))}</td>
        <td>${escapeHtml(metricLabel(alert.metric_name || ""))}</td>
        <td>${escapeHtml(formatMetricValue(alert.metric_name || "", alert.actual_value))}</td>
        <td>${escapeHtml(formatMetricValue(alert.metric_name || "", alert.threshold_value))}</td>
        <td><span class="status-pill ${escapeHtml(alert.status || "")}">${escapeHtml(statusLabel(alert.status || ""))}</span></td>
        <td>
          <div class="node-actions">
            <button type="button" data-alert-action="ack" data-alert-id="${alert.id}">${escapeHtml(t("ack"))}</button>
            <button type="button" data-alert-action="silence" data-alert-id="${alert.id}">${escapeHtml(t("silence"))}</button>
            <button type="button" data-alert-action="history" data-alert-id="${alert.id}" data-fingerprint="${escapeHtml(alert.fingerprint || "")}">${escapeHtml(t("history"))}</button>
          </div>
        </td>
      </tr>
    `).join("");
  }

  function renderRuns() {
    const body = document.getElementById("runsTableBody");
    const items = state.runs?.items || [];
    if (!items.length) {
      body.innerHTML = `<tr><td colspan="6"><div class="empty">${escapeHtml(t("noRuns"))}</div></td></tr>`;
      document.getElementById("runDetail").innerHTML = `<div class="empty">${escapeHtml(t("noRunDetail"))}</div>`;
      document.getElementById("runEvents").innerHTML = `<div class="empty">${escapeHtml(t("noData"))}</div>`;
      return;
    }
    body.innerHTML = items.map((run) => `
      <tr class="interactive-row ${String(run.run_id) === String(state.selectedRunId || "") ? "selected" : ""}" data-run-id="${escapeHtml(run.run_id)}">
        <td>${escapeHtml(run.run_id)}</td>
        <td>${escapeHtml(runKindLabel(run.run_kind || ""))}</td>
        <td><span class="status-pill ${escapeHtml(run.status || "")}">${escapeHtml(statusLabel(run.status || ""))}</span></td>
        <td>${escapeHtml(formatTimestamp(run.started_at))}</td>
        <td>${run.findings_count || 0}</td>
        <td>
          ${run.progress?.headline_severity ? `<span class="status-pill ${escapeHtml(run.progress.headline_severity)}">${escapeHtml(severityLabel(run.progress.headline_severity))}</span> ` : ""}
          ${escapeHtml(run.progress?.headline || run.progress?.active_phase || run.progress?.last_event_kind || t("viewDetail"))}
        </td>
      </tr>
    `).join("");
    renderRunDetail();
  }

  async function loadRunDetail(runId) {
    return loadSelectedRunDetail(runId, { refreshRunsList: true });
  }

  function renderRunDetail() {
    const payload = state.selectedRun;
    const findings = payload?.threshold_findings || [];
    const probes = payload?.probes || [];
    const progress = payload?.progress || {};
    const latestQueueJob = progress.latest_queue_job || {};
    const currentBlocker = progress.current_blocker || {};
    const latestProbe = progress.latest_probe || {};
    const blockerSuggestedAction = currentBlocker.suggested_action || null;
    const focusNodeId = currentBlocker.node_id || latestQueueJob.node_id || latestProbe.node_id || null;
    const links = [];
    if (!payload) {
      document.getElementById("runDetail").innerHTML = `<div class="empty">${escapeHtml(t("noRunDetail"))}</div>`;
      document.getElementById("runEvents").innerHTML = `<div class="empty">${escapeHtml(t("noData"))}</div>`;
      return;
    }
    if (payload.html_path) {
      links.push(`<a href="${escapeHtml(resultPathToHref(payload.html_path))}" target="_blank" rel="noreferrer">${escapeHtml(t("openReport"))}</a>`);
    }
    document.getElementById("runDetail").innerHTML = `
      <div class="card">
        <div class="section-head">
          <strong>${escapeHtml(payload.run_id)}</strong>
          <span class="status-pill ${escapeHtml(payload.status || "")}">${escapeHtml(statusLabel(payload.status || ""))}</span>
        </div>
        <div class="muted">${escapeHtml(formatTimestamp(payload.started_at))}</div>
        <div class="muted">${escapeHtml(t("runKind"))}: ${escapeHtml(runKindLabel(payload.run_kind || ""))}</div>
        <div class="muted">${escapeHtml(t("findings"))}: ${findings.length}</div>
        <div class="muted">${escapeHtml(t("eventsCount"))}: ${escapeHtml(String(progress.events_count || 0))}</div>
        <div class="muted">${escapeHtml(t("currentPhase"))}: ${escapeHtml(progress.active_phase || t("noData"))}</div>
        <div class="muted">${escapeHtml(t("lastEvent"))}: ${escapeHtml(progress.last_event_message || progress.last_event_kind || t("noData"))}</div>
        ${progress.headline ? `<div class="muted">${escapeHtml(t("result"))}: ${progress.headline_severity ? `<span class="status-pill ${escapeHtml(progress.headline_severity)}">${escapeHtml(severityLabel(progress.headline_severity))}</span> ` : ""}${escapeHtml(progress.headline)}</div>` : ""}
        <div class="muted">${escapeHtml(t("latestProbe"))}: ${escapeHtml(latestProbe.task || latestProbe.path_label || t("noData"))}</div>
        ${currentBlocker.summary ? `<div class="muted">${escapeHtml(t("currentBlocker"))}: ${escapeHtml(currentBlocker.summary)}</div>` : ""}
        ${latestQueueJob.job_id ? `
          <div class="muted">${escapeHtml(t("latestQueueJob"))}: ${escapeHtml([
            latestQueueJob.task || t("noData"),
            latestQueueJob.node_name || "",
            latestQueueJob.status || latestQueueJob.event_kind || "",
          ].filter(Boolean).join(" | "))}${latestQueueJob.node_id ? ` <button type="button" data-focus-node="${escapeHtml(String(latestQueueJob.node_id))}">${escapeHtml(t("openNode"))}</button>` : ""}</div>
          <div class="muted">${escapeHtml(t("jobId"))}: ${escapeHtml(String(latestQueueJob.job_id))}</div>
          ${latestQueueJob.lease_state ? `<div class="muted">${escapeHtml(t("leaseState"))}: ${escapeHtml(latestQueueJob.lease_state)}</div>` : ""}
          ${latestQueueJob.lease_expires_at ? `<div class="muted">${escapeHtml(t("leaseExpiresAt"))}: ${escapeHtml(formatTimestamp(latestQueueJob.lease_expires_at))}</div>` : ""}
        ` : ""}
        ${progress.last_failure_code ? `<div class="muted">${escapeHtml(t("failureCode"))}: ${escapeHtml(progress.last_failure_code)}</div>` : ""}
        ${progress.last_failure_message ? `<div class="muted">${escapeHtml(t("failure"))}: ${escapeHtml(progress.last_failure_message)}</div>` : ""}
        ${!blockerSuggestedAction && progress.recommended_step ? `<div class="muted">${escapeHtml(t("recommendedStep"))}: ${escapeHtml(progress.recommended_step)}</div>` : ""}
        <div class="muted">${links.join(" | ") || escapeHtml(t("noData"))}</div>
        ${blockerSuggestedAction ? `<div class="node-actions" style="margin-top: 10px;">${renderSuggestedActionButton(blockerSuggestedAction)}</div>` : focusNodeId ? `<div class="node-actions" style="margin-top: 10px;"><button type="button" data-focus-node="${escapeHtml(String(focusNodeId))}">${escapeHtml(t("openNode"))}</button></div>` : ""}
        ${payload.status === "running" ? `<div class="muted">${escapeHtml(t("liveRunHint"))}</div>` : ""}
      </div>
      <div class="card">
        <h3>${escapeHtml(t("findings"))}</h3>
        ${findings.length ? findings.map((item) => `<div class="muted">${escapeHtml(pathLabel(item.path_label || ""))} | ${escapeHtml(metricLabel(item.metric || ""))} | ${escapeHtml(String(item.actual))} / ${escapeHtml(String(item.threshold))}</div>`).join("") : `<div class="empty">${escapeHtml(t("noData"))}</div>`}
      </div>
      <div class="card">
        <h3>${escapeHtml(t("probeResults"))}</h3>
        ${probes.length ? probes.map((probe) => `
          <div style="margin-bottom: 12px;">
            <strong>${escapeHtml(pathLabel(probe.path_label || probe.probe_name || ""))}</strong>
            <div class="muted">${escapeHtml(probe.probe_name)} | ${escapeHtml(probe.node_name || "")}</div>
            <div class="muted">${escapeHtml(summarizeMetrics(probe.metrics || {}))}</div>
          </div>
        `).join("") : `<div class="empty">${escapeHtml(t("noData"))}</div>`}
      </div>
    `;
    document.getElementById("runEvents").innerHTML = state.selectedRunEvents.length
      ? `<div class="card">${state.selectedRunEvents.map((item) => `
          <div style="margin-bottom: 10px;">
            <strong>${escapeHtml(item.event_kind)}</strong>
            ${item.severity ? `<span class="status-pill ${escapeHtml(item.severity)}" style="margin-left: 8px;">${escapeHtml(severityLabel(item.severity))}</span>` : ""}
            <div class="muted">${escapeHtml(formatTimestamp(item.created_at))}</div>
            <div class="muted">${escapeHtml(item.message || "")}</div>
            ${item.summary ? `<div class="muted">${escapeHtml(item.summary)}</div>` : ""}
            ${item.code ? `<div class="muted">${escapeHtml(t("failureCode"))}: ${escapeHtml(item.code)}</div>` : ""}
            ${item.node_id ? `<div class="node-actions" style="margin-top: 8px;"><button type="button" data-focus-node="${escapeHtml(String(item.node_id))}">${escapeHtml(t("openNode"))}</button></div>` : ""}
          </div>
        `).join("")}</div>`
      : `<div class="empty">${escapeHtml(t("noData"))}</div>`;
  }

  function renderRunLauncherState() {
    const button = document.getElementById("runFullBtn");
    if (!button) {
      return;
    }
    const activeRun = state.runtimeInfo?.active_run;
    button.disabled = Boolean(activeRun?.run_id);
    button.title = activeRun?.run_id ? `${t("runBusy")}: ${activeRun.run_id}` : "";
  }

  function hydrateManagement() {
    fillSettingsInputs();
    renderNodeCards();
    renderScheduleMeta();
  }

  function renderRuntimeControl() {
    const panel = state.runtimeInfo?.panel || {};
    const runtime = panel.runtime || {};
    const supervisor = panel.supervisor || {};
    const details = runtime.details || {};
    const operatorSummary = details.operator_summary || "";
    const operatorSeverity = details.operator_severity || "";
    const operatorRecommendedStep = details.operator_recommended_step || "";
    const suggestedAction = details.suggested_action || null;
    const availableActions = new Set(details.available_actions || []);
    const activeActionId = details.active_action_id || null;
    const activeActionSummary = details.active_action_summary || "";
    const paused = Boolean(details.scheduler_paused);
    const logLocation = supervisor.log_location || details.log_location;
    const buttons = [];
    if (availableActions.has("sync_runtime")) {
      buttons.push(`<button type="button" data-panel-action="sync_runtime" ${activeActionId ? "disabled" : ""}>${escapeHtml(t("syncRuntime"))}</button>`);
    }
    if (availableActions.has("tail_log")) {
      buttons.push(`<button type="button" data-panel-action="tail_log" ${activeActionId ? "disabled" : ""}>${escapeHtml(t("tailLog"))}</button>`);
    }
    buttons.push(
      `<button type="button" data-panel-action="${paused ? "resume_scheduler" : "pause_scheduler"}" ${activeActionId ? "disabled" : ""}>${escapeHtml(paused ? t("resumeScheduler") : t("pauseScheduler"))}</button>`,
    );
    if (availableActions.has("restart")) {
      buttons.push(`<button type="button" data-panel-action="restart" class="danger" ${activeActionId ? "disabled" : ""}>${escapeHtml(t("restart"))}</button>`);
    }
    if (availableActions.has("stop")) {
      buttons.push(`<button type="button" data-panel-action="stop" class="danger" ${activeActionId ? "disabled" : ""}>${escapeHtml(t("stop"))}</button>`);
    }
    const root = document.getElementById("panelRuntimeCard");
    if (!root) {
      return;
    }
    root.innerHTML = `
      <div class="card">
        <div class="section-head">
          <strong>${escapeHtml(t("panelTarget"))}</strong>
          <span class="status-pill ${escapeHtml(runtime.state || "unknown")}">${escapeHtml(statusLabel(runtime.state || "unknown"))}</span>
        </div>
        <div class="muted">${escapeHtml(t("runtimeState"))}: ${escapeHtml(statusLabel(runtime.state || "unknown"))}</div>
        <div class="muted">${escapeHtml(t("supervisorState"))}: ${escapeHtml(supervisor.supervisor_state || t("noData"))}</div>
        <div class="muted">${escapeHtml(t("processState"))}: ${escapeHtml(supervisor.process_state || t("noData"))}</div>
        <div class="muted">${escapeHtml(t("deploymentMode"))}: ${escapeHtml(panelDeploymentModeLabel(details.deployment_mode))}</div>
        <div class="muted">${escapeHtml(t("controlMode"))}: ${escapeHtml(panelControlModeLabel(details.control_mode))}</div>
        <div class="muted">${escapeHtml(t("controlBridge"))}: ${escapeHtml(supervisor.bridge_url || t("noData"))}</div>
        <div class="muted">${escapeHtml(t("logLocation"))}: ${escapeHtml(logLocation || t("noData"))}</div>
        <div class="muted">${escapeHtml(paused ? t("schedulerPaused") : t("schedulerRunning"))}</div>
        <div class="muted">${escapeHtml(formatTimestamp(details.last_loop_at || runtime.checked_at))}</div>
        ${operatorSummary ? `<div class="muted">${escapeHtml(t("result"))}: ${operatorSeverity ? `<span class="status-pill ${escapeHtml(operatorSeverity)}">${escapeHtml(severityLabel(operatorSeverity))}</span> ` : ""}${escapeHtml(operatorSummary)}</div>` : ""}
        ${!suggestedAction && operatorRecommendedStep ? `<div class="muted">${escapeHtml(t("recommendedStep"))}: ${escapeHtml(operatorRecommendedStep)}</div>` : ""}
        ${details.readonly_reason ? `<div class="muted">${escapeHtml(t("readonlyReason"))}: ${escapeHtml(details.readonly_reason)}</div>` : ""}
        ${activeActionId ? `<div class="muted">${escapeHtml(t("currentAction"))}: ${escapeHtml(activeActionSummary || t("actionBusy"))}${suggestedAction?.kind === "open_action" ? "" : ` <button type="button" data-action-detail="${escapeHtml(String(activeActionId))}">${escapeHtml(t("viewAction"))}</button>`}</div>` : ""}
        ${!supervisor.control_available && details.control_mode === "native-readonly" ? `<div class="muted">${escapeHtml(t("panelReadonlyHint"))}</div>` : ""}
        <div class="node-actions" style="margin-top: 12px;">
          ${suggestedAction ? renderSuggestedActionButton(suggestedAction) : ""}
          ${buttons.join("")}
        </div>
      </div>
    `;
  }

  function renderOperationsFocus() {
    const root = document.getElementById("operationsFocus");
    if (!root) {
      return;
    }
    const attention = state.runtimeInfo?.attention || {};
    const items = attention.items || [];
    const summary = attention.summary || {};
    if (!items.length) {
      root.innerHTML = `<div class="empty">${escapeHtml(t("noAttention"))}</div>`;
      return;
    }
      root.innerHTML = `
      <div class="muted">${escapeHtml(t("attentionSummary"))}: ${escapeHtml(String(summary.total || items.length))}</div>
      ${items.map((item) => {
        const buttons = [];
        if (item.suggested_action) {
          buttons.push(renderSuggestedActionButton(item.suggested_action));
        } else if (item.target_kind === "node" && item.target_id) {
          buttons.push(`<button type="button" data-focus-node="${escapeHtml(String(item.target_id))}">${escapeHtml(t("openNode"))}</button>`);
        }
        if (!item.suggested_action && item.target_kind === "panel") {
          buttons.push(`<button type="button" data-focus-panel="panel">${escapeHtml(t("openPanel"))}</button>`);
        }
        if (!item.suggested_action && item.run_id) {
          buttons.push(`<button type="button" data-open-run="${escapeHtml(String(item.run_id))}">${escapeHtml(t("openRun"))}</button>`);
        }
        if (!item.suggested_action && item.action_id) {
          buttons.push(`<button type="button" data-action-detail="${escapeHtml(String(item.action_id))}">${escapeHtml(t("viewAction"))}</button>`);
        }
        return `
        <div class="card" style="margin-top: 12px;">
          <div class="section-head">
            <strong>${escapeHtml(item.title || t("noData"))}</strong>
            <span class="status-pill ${escapeHtml(item.severity || "info")}">${escapeHtml(severityLabel(item.severity || "info"))}</span>
          </div>
          <div class="muted">${escapeHtml(item.summary || t("noData"))}</div>
          ${item.code ? `<div class="muted">${escapeHtml(t("diagnosticCode"))}: ${escapeHtml(item.code)}</div>` : ""}
          ${!item.suggested_action && item.recommended_step ? `<div class="muted">${escapeHtml(t("recommendedStep"))}: ${escapeHtml(item.recommended_step)}</div>` : ""}
          ${buttons.length ? `<div class="node-actions" style="margin-top: 10px;">${buttons.join("")}</div>` : ""}
        </div>
      `;
      }).join("")}
    `;
  }

  async function loadReleaseValidation(options = {}) {
    const epoch = nextRequestEpoch("releaseValidation");
    const silent = Boolean(options.silent);
    try {
      const payload = await fetchJson("/api/v1/admin/release-validation");
      if (!isLatestRequest("releaseValidation", epoch)) {
        return state.releaseValidation;
      }
      state.releaseValidation = payload;
      updateLastRefreshAt(payload);
      renderReleaseValidation();
      scheduleReleaseValidationPolling();
      return payload;
    } catch (error) {
      if (!silent) {
        showMessage(error.message || String(error), "error");
      }
      throw error;
    }
  }

  async function runReleaseValidation() {
    const epoch = nextRequestEpoch("releaseValidation");
    try {
      const payload = await fetchJson("/api/v1/admin/release-validation", { method: "POST" });
      if (!isLatestRequest("releaseValidation", epoch)) {
        return;
      }
      state.releaseValidation = payload;
      updateLastRefreshAt(payload);
      renderReleaseValidation();
      scheduleReleaseValidationPolling();
      showMessage(payload.running ? t("validationRunning") : t("validationLastChecked"), "ok");
    } catch (error) {
      showMessage(error.message || String(error), "error");
    }
  }

  function renderReleaseValidation() {
    const meta = document.getElementById("releaseValidationMeta");
    const root = document.getElementById("releaseValidationBody");
    if (!meta || !root) {
      return;
    }
    const payload = state.releaseValidation;
    if (!payload) {
      meta.textContent = t("validationNotRun");
      root.innerHTML = `<div class="empty">${escapeHtml(t("validationNotRun"))}</div>`;
      clearReleaseValidationPolling();
      return;
    }
    const summary = payload.summary || {};
    const issues = payload.issues || [];
    const nodes = payload.nodes || [];
    const counts = [
      `${t("validationSummary")}: ${summary.total || 0}`,
      `pass ${summary.pass || 0}`,
      `warn ${summary.warn || 0}`,
      `fail ${summary.fail || 0}`,
      `skip ${summary.skip || 0}`,
    ];
    if (payload.generated_at) {
      counts.unshift(`${t("generatedAt")}: ${formatTimestamp(payload.generated_at)}`);
    }
    if (payload.checked_at) {
      counts.unshift(`${t("validationLastChecked")}: ${formatTimestamp(payload.checked_at)}`);
    }
    if (payload.running) {
      counts.unshift(t("validationRunning"));
    }
    meta.textContent = counts.join(" · ");
    root.innerHTML = `
      <div class="grid-four">
        ${[
          { label: "pass", value: summary.pass || 0 },
          { label: "warn", value: summary.warn || 0 },
          { label: "fail", value: summary.fail || 0 },
          { label: "skip", value: summary.skip || 0 },
        ].map((item) => `
          <div class="card">
            <div class="muted">${escapeHtml(statusLabel(item.label))}</div>
            <div class="kpi-value">${escapeHtml(String(item.value))}</div>
          </div>
        `).join("")}
      </div>
      <div class="management-grid" style="margin-top: 16px;">
        <div class="card">
          <h3>${escapeHtml(t("panelTarget"))}</h3>
          ${renderReleaseValidationItem(payload.panel || null)}
        </div>
        <div class="card">
          <h3>${escapeHtml(t("validationIssues"))}</h3>
          ${issues.length ? issues.map((item) => renderReleaseValidationIssue(item)).join("") : `<div class="empty">${escapeHtml(t("validationNoIssues"))}</div>`}
        </div>
      </div>
      <div class="list" style="margin-top: 16px;">
        <h3>${escapeHtml(t("nodes"))}</h3>
        ${nodes.length ? nodes.map((item) => renderReleaseValidationItem(item)).join("") : `<div class="empty">${escapeHtml(t("noData"))}</div>`}
      </div>
    `;
  }

  function renderReleaseValidationIssue(item) {
    const buttons = [];
    if (item?.suggested_action) {
      buttons.push(renderSuggestedActionButton(item.suggested_action));
    } else if (item?.target_kind === "node" && item?.target_id) {
      buttons.push(`<button type="button" data-focus-node="${escapeHtml(String(item.target_id))}">${escapeHtml(t("openNode"))}</button>`);
    } else if (item?.target_kind === "panel") {
      buttons.push(`<button type="button" data-focus-panel="panel">${escapeHtml(t("openPanel"))}</button>`);
    }
    return `
      <div class="card" style="margin-top: 12px;">
        <div class="section-head">
          <strong>${escapeHtml(item?.target_name || t("noData"))}</strong>
          <span class="status-pill ${escapeHtml(item?.status || "skip")}">${escapeHtml(statusLabel(item?.status || "skip"))}</span>
        </div>
        <div class="muted">${escapeHtml(item?.summary || t("noData"))}</div>
        ${item?.code ? `<div class="muted">${escapeHtml(t("diagnosticCode"))}: ${escapeHtml(item.code)}</div>` : ""}
        ${!item?.suggested_action && item?.recommended_step ? `<div class="muted">${escapeHtml(t("recommendedStep"))}: ${escapeHtml(item.recommended_step)}</div>` : ""}
        ${buttons.length ? `<div class="node-actions" style="margin-top: 10px;">${buttons.join("")}</div>` : ""}
      </div>
    `;
  }

  function renderReleaseValidationItem(item) {
    if (!item) {
      return `<div class="empty">${escapeHtml(t("noData"))}</div>`;
    }
    const buttons = [];
    if (item.suggested_action) {
      buttons.push(renderSuggestedActionButton(item.suggested_action));
    } else if (item.target_kind === "node" && item.target_id) {
      buttons.push(`<button type="button" data-focus-node="${escapeHtml(String(item.target_id))}">${escapeHtml(t("openNode"))}</button>`);
    } else if (item.target_kind === "panel") {
      buttons.push(`<button type="button" data-focus-panel="panel">${escapeHtml(t("openPanel"))}</button>`);
    }
    const checks = Object.entries(item.checks || {});
    return `
      <div class="card" style="margin-top: 12px;">
        <div class="section-head">
          <strong>${escapeHtml(item.target_name || t("noData"))}</strong>
          <span class="status-pill ${escapeHtml(item.status || "skip")}">${escapeHtml(statusLabel(item.status || "skip"))}</span>
        </div>
        ${item.role ? `<div class="muted">${escapeHtml(roleLabel(item.role))}</div>` : ""}
        <div class="muted">${escapeHtml(item.summary || t("noData"))}</div>
        ${item.build?.display_label ? `<div class="muted">Build: ${escapeHtml(item.build.display_label)}</div>` : ""}
        ${item.code ? `<div class="muted">${escapeHtml(t("diagnosticCode"))}: ${escapeHtml(item.code)}</div>` : ""}
        ${!item.suggested_action && item.recommended_step ? `<div class="muted">${escapeHtml(t("recommendedStep"))}: ${escapeHtml(item.recommended_step)}</div>` : ""}
        ${checks.length ? `
          <div style="margin-top: 10px;">
            <strong>${escapeHtml(t("validationChecks"))}</strong>
            ${checks.map(([name, check]) => `
              <div class="muted">
                <span class="status-pill ${escapeHtml(check.status || "skip")}">${escapeHtml(statusLabel(check.status || "skip"))}</span>
                ${escapeHtml(name)}: ${escapeHtml(check.summary || t("noData"))}
              </div>
            `).join("")}
          </div>
        ` : ""}
        ${buttons.length ? `<div class="node-actions" style="margin-top: 10px;">${buttons.join("")}</div>` : ""}
      </div>
    `;
  }

  function renderActionHistory() {
    const body = document.getElementById("actionsTableBody");
    const items = state.actionHistory?.items || [];
    if (!body) {
      return;
    }
    if (!items.length) {
      body.innerHTML = `<tr><td colspan="5"><div class="empty">${escapeHtml(t("noData"))}</div></td></tr>`;
      return;
    }
    body.innerHTML = items.map((item) => {
      const targetSuggestedAction = item.target_suggested_action || null;
      const actionButtons = [];
      if (targetSuggestedAction) {
        actionButtons.push(renderSuggestedActionButton(targetSuggestedAction));
      }
      return `
        <tr class="interactive-row ${Number(item.id) === Number(state.selectedActionId || 0) ? "selected" : ""}" data-action-id="${escapeHtml(String(item.id))}">
          <td>
            <div>${escapeHtml(item.target_kind === "panel" ? t("panelTarget") : (item.target_name || String(item.target_id || "")))}</div>
            ${(item.target_status || item.target_runtime_state) ? `<div class="muted">${item.target_status ? `<span class="status-pill ${escapeHtml(item.target_attention_level || item.target_status)}">${escapeHtml(statusLabel(item.target_status))}</span>` : ""}${item.target_runtime_state ? ` <span class="status-pill ${escapeHtml(item.target_runtime_state)}">${escapeHtml(statusLabel(item.target_runtime_state))}</span>` : ""}</div>` : ""}
          </td>
          <td>${escapeHtml(item.action || "")}</td>
          <td><span class="status-pill ${escapeHtml(item.status || "")}">${escapeHtml(statusLabel(item.status || ""))}</span></td>
          <td>${escapeHtml(formatTimestamp(item.started_at || item.requested_at))}</td>
          <td>
            ${item.severity ? `<span class="status-pill ${escapeHtml(item.severity)}">${escapeHtml(severityLabel(item.severity))}</span> ` : ""}${escapeHtml(item.summary || t("noData"))}
            ${item.target_operator_summary ? `<div class="muted">${escapeHtml(item.target_operator_summary)}</div>` : ""}
            ${!targetSuggestedAction && item.target_operator_recommended_step ? `<div class="muted">${escapeHtml(t("recommendedStep"))}: ${escapeHtml(item.target_operator_recommended_step)}</div>` : ""}
            ${actionButtons.length ? `<div class="node-actions" style="margin-top: 8px;">${actionButtons.join("")}</div>` : ""}
          </td>
        </tr>
      `;
    }).join("");
  }

  function renderActionDetail() {
    const root = document.getElementById("actionDetail");
    if (!root) {
      return;
    }
    const action = state.selectedAction;
    if (!action) {
      root.innerHTML = `<div class="empty">${escapeHtml(t("noData"))}</div>`;
      return;
    }
    const runtimeSnapshot = action.runtime_snapshot || {};
    const runtime = runtimeSnapshot.runtime || {};
    const supervisor = runtimeSnapshot.supervisor || {};
    const failure = action.failure || {};
    const logExcerpt = action.log_excerpt || [];
    const targetSnapshot = action.target_snapshot || {};
    const targetRuntime = targetSnapshot.runtime || {};
    const targetRuntimeDetails = targetRuntime.details || {};
    const targetSupervisor = targetSnapshot.supervisor || {};
    const targetConnectivity = targetSnapshot.connectivity || {};
    const targetSuggestedAction = targetRuntimeDetails.suggested_action || targetSnapshot.suggested_action || null;
    const targetButtons = [];
    if (targetSuggestedAction) {
      targetButtons.push(renderSuggestedActionButton(targetSuggestedAction));
    } else if (targetSnapshot.target_kind === "node" && targetSnapshot.target_id) {
      targetButtons.push(`<button type="button" data-focus-node="${escapeHtml(String(targetSnapshot.target_id))}">${escapeHtml(t("openNode"))}</button>`);
    }
    if (!targetSuggestedAction && targetSnapshot.target_kind === "panel") {
      targetButtons.push(`<button type="button" data-focus-panel="panel">${escapeHtml(t("openPanel"))}</button>`);
    }
    if (!targetSuggestedAction && targetSnapshot.active_run_id) {
      targetButtons.push(`<button type="button" data-open-run="${escapeHtml(String(targetSnapshot.active_run_id))}">${escapeHtml(t("openRun"))}</button>`);
    }
    root.innerHTML = `
      <div class="card detail-stack">
        <div class="section-head">
          <strong>${escapeHtml(action.target_kind === "panel" ? t("panelTarget") : (action.target_name || String(action.target_id || "")))}</strong>
          <span class="status-pill ${escapeHtml(action.status || "")}">${escapeHtml(statusLabel(action.status || ""))}</span>
        </div>
        <div class="muted">${escapeHtml(t("actions"))}: ${escapeHtml(action.action || "")}</div>
        <div class="muted">${escapeHtml(t("requestedBy"))}: ${escapeHtml(action.requested_by || t("noData"))}</div>
        <div class="muted">${escapeHtml(t("startedAt"))}: ${escapeHtml(formatTimestamp(action.started_at || action.requested_at))}</div>
        <div class="muted">${escapeHtml(t("finishedAt"))}: ${escapeHtml(formatTimestamp(action.finished_at))}</div>
        <div class="muted">${escapeHtml(t("transport"))}: ${escapeHtml(action.transport || t("noData"))}</div>
        <div class="muted">${escapeHtml(t("result"))}: ${action.severity ? `<span class="status-pill ${escapeHtml(action.severity)}">${escapeHtml(severityLabel(action.severity))}</span> ` : ""}${escapeHtml(action.summary || t("noData"))}</div>
        ${(action.code || failure.code || failure.detail) ? `<div class="muted">${escapeHtml(t("failure"))}: ${escapeHtml([action.code || failure.code, failure.detail].filter(Boolean).join(" | "))}</div>` : ""}
        <div class="muted">${escapeHtml(t("logLocation"))}: ${escapeHtml(action.log_location || t("noData"))}</div>
        <div>
          <h3>${escapeHtml(t("currentTargetSnapshot"))}</h3>
          <div class="muted">${escapeHtml(t("target"))}: ${escapeHtml(targetSnapshot.target_kind === "panel" ? t("panelTarget") : (targetSnapshot.target_name || t("noData")))}</div>
          <div class="muted">${escapeHtml(t("status"))}: ${escapeHtml(statusLabel(targetSnapshot.status || "unknown"))}</div>
          <div class="muted">${escapeHtml(t("runtimeState"))}: ${escapeHtml(statusLabel(targetRuntime.state || "unknown"))}</div>
          <div class="muted">${escapeHtml(t("supervisorState"))}: ${escapeHtml(targetSupervisor.supervisor_state || t("noData"))}</div>
          ${targetConnectivity.summary ? `<div class="muted">${escapeHtml(t("connectivitySummary"))}: ${escapeHtml(targetConnectivity.summary)}</div>` : ""}
          ${targetConnectivity.diagnostic_code ? `<div class="muted">${escapeHtml(t("diagnosticCode"))}: ${escapeHtml(targetConnectivity.diagnostic_code)}</div>` : ""}
          ${targetRuntimeDetails.operator_summary || targetSnapshot.operator_summary ? `<div class="muted">${escapeHtml(t("result"))}: ${(targetRuntimeDetails.operator_severity || targetSnapshot.operator_severity) ? `<span class="status-pill ${escapeHtml(targetRuntimeDetails.operator_severity || targetSnapshot.operator_severity)}">${escapeHtml(severityLabel(targetRuntimeDetails.operator_severity || targetSnapshot.operator_severity))}</span> ` : ""}${escapeHtml(targetRuntimeDetails.operator_summary || targetSnapshot.operator_summary)}</div>` : ""}
          ${!targetSuggestedAction && (targetRuntimeDetails.operator_recommended_step || targetSnapshot.operator_recommended_step) ? `<div class="muted">${escapeHtml(t("recommendedStep"))}: ${escapeHtml(targetRuntimeDetails.operator_recommended_step || targetSnapshot.operator_recommended_step)}</div>` : ""}
          ${targetButtons.length ? `<div class="node-actions" style="margin-top: 10px;">${targetButtons.join("")}</div>` : ""}
        </div>
        <div>
          <h3>${escapeHtml(t("logExcerpt"))}</h3>
          ${logExcerpt.length ? `<div class="command-box">${escapeHtml(logExcerpt.join("\n"))}</div>` : `<div class="empty">${escapeHtml(t("noData"))}</div>`}
        </div>
        <div>
          <h3>${escapeHtml(t("requestPayload"))}</h3>
          ${Object.keys(action.request || {}).length ? `<div class="command-box">${escapeHtml(formatJson(action.request))}</div>` : `<div class="empty">${escapeHtml(t("noData"))}</div>`}
        </div>
        <div>
          <h3>${escapeHtml(t("responsePayload"))}</h3>
          ${Object.keys(action.response || {}).length ? `<div class="command-box">${escapeHtml(formatJson(action.response))}</div>` : `<div class="empty">${escapeHtml(t("noData"))}</div>`}
        </div>
        <div>
          <h3>${escapeHtml(t("runtimeSnapshot"))}</h3>
          <div class="muted">${escapeHtml(t("runtimeState"))}: ${escapeHtml(statusLabel(runtime.state || "unknown"))}</div>
          <div class="muted">${escapeHtml(t("supervisorState"))}: ${escapeHtml(supervisor.supervisor_state || t("noData"))}</div>
          <div class="muted">${escapeHtml(t("processState"))}: ${escapeHtml(supervisor.process_state || t("noData"))}</div>
          <div class="muted">${escapeHtml(t("logLocation"))}: ${escapeHtml(supervisor.log_location || action.log_location || t("noData"))}</div>
        </div>
      </div>
    `;
  }

  function fillSettingsInputs() {
    const settings = state.snapshot?.settings || {};
    const services = settings.services || {};
    const thresholds = settings.thresholds || {};
    const scenarios = settings.scenarios || {};
    setValue("relay_public_probe_host", services.relay_public_probe?.host || "");
    setValue("relay_public_probe_port", services.relay_public_probe?.port ?? 22);
    setValue("mc_public_host", services.mc_public?.host || "");
    setValue("mc_public_port", services.mc_public?.port ?? 25565);
    setValue("iperf_public_host", services.iperf_public?.host || "");
    setValue("iperf_public_port", services.iperf_public?.port ?? 5201);
    setValue("server_backend_mc_host", services.server_backend_mc?.host || "");
    setValue("server_backend_mc_port", services.server_backend_mc?.port ?? 25565);
    setValue("server_backend_iperf_host", services.server_backend_iperf?.host || "");
    setValue("server_backend_iperf_port", services.server_backend_iperf?.port ?? 5201);
    setValue("ping_rtt_avg_max", thresholds.ping?.rtt_avg_ms_max ?? 120);
    setValue("ping_jitter_max", thresholds.ping?.jitter_ms_max ?? 20);
    setValue("tcp_connect_avg_max", thresholds.tcp?.connect_avg_ms_max ?? 150);
    setValue("tcp_timeout_error_max", thresholds.tcp?.timeout_or_error_pct_max ?? 10);
    setValue("throughput_up_min", thresholds.throughput?.throughput_up_mbps_min ?? 5);
    setValue("throughput_down_min", thresholds.throughput?.throughput_down_mbps_min ?? 5);
    setValue("load_delta_max", thresholds.load_inflation?.load_rtt_inflation_ms_max ?? 80);
    setValue("system_cpu_max", thresholds.system?.cpu_usage_pct_max ?? 90);
    setValue("throughput_duration_sec", scenarios.throughput?.duration_sec ?? 10);
    setValue("load_duration_sec", scenarios.load_inflation?.duration_sec ?? 10);
    setValue("tcp_attempts", scenarios.tcp?.attempts ?? 6);
    setValue("system_sample_sec", scenarios.system?.sample_interval_sec ?? 1);
  }

  function renderScheduleMeta() {
    const schedules = state.snapshot?.schedules || [];
    document.getElementById("scheduleMeta").innerHTML = schedules.map((item) => `
      <span>${escapeHtml(runKindLabel(item.run_kind || ""))}: ${escapeHtml(String(item.interval_sec))}s</span>
    `).join(" | ");
  }

  function renderNodeCards() {
    const nodes = state.runtimeInfo?.nodes || state.snapshot?.nodes || [];
    const root = document.getElementById("nodeGrid");
    root.innerHTML = FIXED_ROLES.map((role) => {
      const node = nodes.find((item) => item.role === role) || {};
      const endpoints = node.endpoints || {};
      const connectivity = node.connectivity || {};
      const push = connectivity.push || {};
      const pull = connectivity.pull || {};
      const runtime = node.runtime || {};
      const supervisor = node.supervisor || {};
      const runtimeDetails = runtime.details || {};
      const runAttention = node.run_attention || null;
      const operatorSummary = runtimeDetails.operator_summary || "";
      const operatorSeverity = runtimeDetails.operator_severity || "";
      const operatorRecommendedStep = runtimeDetails.operator_recommended_step || "";
      const suggestedAction = runtimeDetails.suggested_action || null;
      const availableActions = new Set(runtimeDetails.available_actions || []);
      const activeActionId = runtimeDetails.active_action_id || null;
      const activeActionSummary = runtimeDetails.active_action_summary || "";
      const readonlyReason = runtimeDetails.readonly_reason || "";
      const connectivitySummary = connectivity.summary || "";
      const diagnosticCode = connectivity.diagnostic_code || "";
      const controlButtons = [];
      if (availableActions.has("sync_runtime")) {
        controlButtons.push(`<button type="button" data-action="node-control" data-control-action="sync_runtime" ${activeActionId ? "disabled" : ""}>${escapeHtml(t("syncRuntime"))}</button>`);
      }
      if (availableActions.has("tail_log")) {
        controlButtons.push(`<button type="button" data-action="node-control" data-control-action="tail_log" ${activeActionId ? "disabled" : ""}>${escapeHtml(t("tailLog"))}</button>`);
      }
      if (availableActions.has("start")) {
        controlButtons.push(`<button type="button" data-action="node-control" data-control-action="start" ${activeActionId ? "disabled" : ""}>${escapeHtml(t("start"))}</button>`);
      }
      if (availableActions.has("restart")) {
        controlButtons.push(`<button type="button" data-action="node-control" data-control-action="restart" class="danger" ${activeActionId ? "disabled" : ""}>${escapeHtml(t("restart"))}</button>`);
      }
      if (availableActions.has("stop")) {
        controlButtons.push(`<button type="button" data-action="node-control" data-control-action="stop" class="danger" ${activeActionId ? "disabled" : ""}>${escapeHtml(t("stop"))}</button>`);
      }
      return `
        <div class="card" data-role="${escapeHtml(role)}" data-node-id="${escapeHtml(node.id || "")}">
          <div class="section-head">
            <h3>${escapeHtml(roleLabel(role))}</h3>
            <span class="status-pill ${escapeHtml(node.status || "unpaired")}">${escapeHtml(statusLabel(node.status || "unpaired"))}</span>
          </div>
          <label><span>${escapeHtml(t("nodeName"))}</span><input data-field="node_name" type="text" value="${escapeHtml(node.node_name || `${role}-node`)}"></label>
          <label><span>${escapeHtml(t("runtimeMode"))}</span><select data-field="runtime_mode">
            ${Object.keys(translations[state.locale].runtime).map((mode) => `<option value="${escapeHtml(mode)}" ${((node.runtime_mode || ROLE_RUNTIME[role]) === mode) ? "selected" : ""}>${escapeHtml(runtimeLabel(mode))}</option>`).join("")}
          </select></label>
          <label><span>${escapeHtml(t("configuredPullUrl"))}</span><input data-field="configured_pull_url" type="text" value="${escapeHtml(endpoints.configured_pull_url || "")}"></label>
          <label><span>${escapeHtml(t("enabled"))}</span><select data-field="enabled"><option value="true" ${node.enabled !== false ? "selected" : ""}>${escapeHtml(booleanLabel(true))}</option><option value="false" ${node.enabled === false ? "selected" : ""}>${escapeHtml(booleanLabel(false))}</option></select></label>
          <div class="muted">${escapeHtml(t("paired"))}: ${escapeHtml(booleanLabel(Boolean(node.paired)))}</div>
          <div class="muted">${escapeHtml(t("lastSeen"))}: ${escapeHtml(formatTimestamp(node.last_seen_at))}</div>
          <div class="muted">${escapeHtml(t("advertisedPullUrl"))}: ${escapeHtml(endpoints.advertised_pull_url || t("noData"))}</div>
          <div class="muted">${escapeHtml(t("effectivePullUrl"))}: ${escapeHtml(endpoints.effective_pull_url || t("noData"))}</div>
          <div class="muted">${escapeHtml(t("runtimeState"))}: ${escapeHtml(statusLabel(runtime.state || "unknown"))}</div>
          <div class="muted">${escapeHtml(t("supervisorState"))}: ${escapeHtml(supervisor.supervisor_state || t("noData"))}</div>
          <div class="muted">${escapeHtml(t("processState"))}: ${escapeHtml(supervisor.process_state || t("noData"))}</div>
          <div class="muted">${escapeHtml(t("pushState"))}: ${escapeHtml(statusLabel(push.state || "unknown"))}</div>
          ${push.code ? `<div class="muted">${escapeHtml(t("pushCode"))}: ${escapeHtml(push.code)}</div>` : ""}
          <div class="muted">${escapeHtml(t("pullState"))}: ${escapeHtml(statusLabel(pull.state || "unknown"))}</div>
          ${pull.code ? `<div class="muted">${escapeHtml(t("pullCode"))}: ${escapeHtml(pull.code)}</div>` : ""}
          ${diagnosticCode ? `<div class="muted">${escapeHtml(t("diagnosticCode"))}: ${escapeHtml(diagnosticCode)}</div>` : ""}
          ${connectivitySummary ? `<div class="muted">${escapeHtml(t("connectivitySummary"))}: ${escapeHtml(connectivitySummary)}</div>` : ""}
          ${operatorSummary ? `<div class="muted">${escapeHtml(t("result"))}: ${operatorSeverity ? `<span class="status-pill ${escapeHtml(operatorSeverity)}">${escapeHtml(severityLabel(operatorSeverity))}</span> ` : ""}${escapeHtml(operatorSummary)}</div>` : ""}
          ${!suggestedAction && operatorRecommendedStep ? `<div class="muted">${escapeHtml(t("recommendedStep"))}: ${escapeHtml(operatorRecommendedStep)}</div>` : ""}
          ${runAttention?.run_id ? `<div class="muted">${escapeHtml(t("activeRunNow"))}: ${runAttention.severity ? `<span class="status-pill ${escapeHtml(runAttention.severity)}">${escapeHtml(severityLabel(runAttention.severity))}</span> ` : ""}${escapeHtml(runAttention.summary || runAttention.run_id)} <button type="button" data-open-run="${escapeHtml(String(runAttention.run_id))}">${escapeHtml(t("openRun"))}</button></div>` : ""}
          ${readonlyReason ? `<div class="muted">${escapeHtml(t("readonlyReason"))}: ${escapeHtml(readonlyReason)}</div>` : ""}
          ${activeActionId ? `<div class="muted">${escapeHtml(t("currentAction"))}: ${escapeHtml(activeActionSummary || t("actionBusy"))}${suggestedAction?.kind === "open_action" ? "" : ` <button type="button" data-action-detail="${escapeHtml(String(activeActionId))}">${escapeHtml(t("viewAction"))}</button>`}</div>` : ""}
          ${connectivity.endpoint_mismatch ? `<div class="muted">${escapeHtml(t("endpointMismatch"))}: ${escapeHtml(connectivity.endpoint_mismatch_detail || "")}</div>` : ""}
          <div class="node-actions">
            ${suggestedAction ? renderSuggestedActionButton(suggestedAction) : ""}
            <button type="button" data-action="save-node" class="primary">${escapeHtml(t("saveNode"))}</button>
            <button type="button" data-action="pair-node">${escapeHtml(t("generatePairCommand"))}</button>
            ${controlButtons.join("")}
          </div>
        </div>
      `;
    }).join("");
  }

  async function saveSettings() {
    try {
      const payload = collectSettingsPayload();
      await fetchJson("/api/v1/dashboard", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      await refreshSnapshot();
      showMessage(t("saveSettingsOk"), "ok");
    } catch (error) {
      showMessage(`${t("saveSettingsFailed")}: ${error.message || error}`, "error");
    }
  }

  async function runFullMonitoring() {
    try {
      const payload = await fetchJson("/api/v1/runs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ run_kind: "full", source: "admin-ui" }),
      });
      state.pendingRunAutoSelectId = String(payload.run_id);
      state.selectedRunId = String(payload.run_id);
      showMessage(tWithValue("runFullOk", payload.run_id), "ok");
      setActiveTab("runs");
      await refreshAll();
    } catch (error) {
      const conflictAction = error.detailPayload?.suggested_action;
      if (conflictAction) {
        await invokeSuggestedAction(conflictAction).catch(() => undefined);
      } else {
        const activeRun = error.detailPayload?.active_run;
        if (activeRun?.run_id) {
          state.selectedRunId = String(activeRun.run_id);
          setActiveTab("runs");
          await loadSelectedRunDetail(String(activeRun.run_id), { refreshRunsList: true, silent: true }).catch(() => undefined);
        }
      }
      showMessage(`${t("runFullFailed")}: ${error.message || error}`, "error");
    }
  }

  async function saveNodeCard(card) {
    const role = card.dataset.role;
    const nodeId = card.dataset.nodeId ? Number(card.dataset.nodeId) : null;
    const payload = {
      id: Number.isFinite(nodeId) && nodeId > 0 ? nodeId : null,
      node_name: card.querySelector('[data-field="node_name"]').value.trim(),
      role,
      runtime_mode: card.querySelector('[data-field="runtime_mode"]').value,
      configured_pull_url: card.querySelector('[data-field="configured_pull_url"]').value.trim() || null,
      enabled: card.querySelector('[data-field="enabled"]').value === "true",
    };
    try {
      const response = await fetchJson("/api/v1/nodes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      await refreshSnapshot();
      showMessage(tWithValue("saveNodeOk", roleLabel(role)), "ok");
      return response.node;
    } catch (error) {
      showMessage(`${t("saveNodeFailed")}: ${error.message || error}`, "error");
      return null;
    }
  }

  async function generatePairCode(card) {
    const role = card.dataset.role;
    let nodeId = card.dataset.nodeId ? Number(card.dataset.nodeId) : null;
    if (!nodeId) {
      const saved = await saveNodeCard(card);
      nodeId = saved?.id ? Number(saved.id) : null;
    }
    if (!nodeId) {
      showMessage(t("pairNodeFailed"), "error");
      return;
    }
    try {
      const payload = await fetchJson(`/api/v1/nodes/${nodeId}/pair-code`, { method: "POST" });
      state.pairCommands.primary = payload.startup_command || "";
      state.pairCommands.fallback = payload.fallback_command || "";
      document.getElementById("pairPrimaryBox").textContent = state.pairCommands.primary || t("noData");
      document.getElementById("pairFallbackBox").textContent = state.pairCommands.fallback || t("noData");
      showMessage(tWithValue("pairNodeOk", roleLabel(role)), "ok");
    } catch (error) {
      showMessage(`${t("pairNodeFailed")}: ${error.message || error}`, "error");
    }
  }

  async function queueNodeAction(card, actionName) {
    const nodeId = card.dataset.nodeId ? Number(card.dataset.nodeId) : null;
    if (!nodeId) {
      showMessage(t("actionQueuedFailed"), "error");
      return;
    }
    await submitControlAction(`/api/v1/admin/nodes/${nodeId}/actions`, actionName);
  }

  async function queuePanelAction(actionName) {
    await submitControlAction("/api/v1/admin/panel/actions", actionName);
  }

  async function submitControlAction(url, actionName) {
    const payload = { action: actionName, actor: "admin-ui", tail_lines: actionName === "tail_log" ? 40 : undefined };
    try {
      let response = await fetchJson(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (response.confirmation_required) {
        const confirmed = window.confirm(`${t("actions")}: ${actionName}`);
        if (!confirmed) {
          return;
        }
        response = await fetchJson(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ ...payload, confirmation_token: response.confirmation_token }),
        });
      }
      showMessage(t("actionQueuedOk"), "ok");
      if (response.action?.id) {
        state.pendingActionAutoSelectId = Number(response.action.id);
        await loadActionDetail(Number(response.action.id), { refreshRuntime: true });
      } else {
        await delay(500);
        await refreshAll();
      }
    } catch (error) {
      const conflictAction = error.detailPayload?.suggested_action;
      if (conflictAction) {
        await invokeSuggestedAction(conflictAction).catch(() => undefined);
      } else {
        const activeAction = error.detailPayload?.active_action;
        if (activeAction?.id) {
          await loadActionDetail(Number(activeAction.id), { refreshRuntime: true, silent: true }).catch(() => undefined);
        }
      }
      showMessage(`${t("actionQueuedFailed")}: ${error.message || error}`, "error");
    }
  }

  async function acknowledgeAlert(alertId) {
    try {
      await fetchJson(`/api/v1/admin/alerts/${alertId}/ack`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ actor: "admin-ui" }),
      });
      showMessage(t("alertAckOk"), "ok");
      await refreshAll();
    } catch (error) {
      showMessage(`${t("alertAckFailed")}: ${error.message || error}`, "error");
    }
  }

  async function silenceAlert(alertId) {
    const hoursText = window.prompt(t("silenceHoursPrompt"), "24");
    if (!hoursText) {
      return;
    }
    const hours = Number(hoursText);
    if (!Number.isFinite(hours) || hours <= 0) {
      return;
    }
    const reason = window.prompt(t("silenceReasonPrompt"), t("defaultMaintenanceReason"));
    const silencedUntil = new Date(Date.now() + hours * 3600 * 1000).toISOString();
    try {
      await fetchJson(`/api/v1/admin/alerts/${alertId}/silence`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ silenced_until: silencedUntil, reason: reason || "", actor: "admin-ui" }),
      });
      showMessage(t("alertSilenceOk"), "ok");
      await refreshAll();
    } catch (error) {
      showMessage(`${t("alertSilenceFailed")}: ${error.message || error}`, "error");
    }
  }

  async function showAlertHistory(fingerprint) {
    if (!fingerprint) {
      return;
    }
    const query = buildQuery({
      time_range: selectedValue("filter-time-range") || "24h",
      fingerprint: [fingerprint],
    });
    const payload = await fetchJson(`/api/v1/admin/alerts?${query.toString()}`);
    const lines = (payload.items || []).slice(0, 8).map((item) => `${formatTimestamp(item.created_at)} | ${kindLabel(item.kind)} | ${item.message}`);
    showMessage(`${t("alertHistoryTitle")}\n${lines.join("\n")}`, "warn");
  }

  function renderFiltersSummary() {
    const target = document.getElementById("filtersSummary");
    if (!target) {
      return;
    }
    const filters = readFilters();
    const parts = [
      `${t("timeRange")}: ${filters.timeRange || "24h"}`,
      `${t("roles")}: ${formatFilterCount(filters.roles)}`,
      `${t("nodes")}: ${formatFilterCount(filters.nodes)}`,
      `${t("paths")}: ${formatFilterCount(filters.paths)}`,
      `${t("probes")}: ${formatFilterCount(filters.probes)}`,
      `${t("metric")}: ${metricLabel(filters.metric || "")}`,
      `${t("tabAlerts")}: ${(state.alerts?.items || []).length}`,
      `${t("tabRuns")}: ${(state.runs?.items || []).length}`,
    ];
    target.textContent = parts.join(" · ") || t("filterSummaryReady");
  }

  function renderPieChart(elementId, distribution) {
    const chart = ensureChart(elementId);
    chart.setOption({
      animation: false,
      tooltip: { trigger: "item" },
      legend: { bottom: 0 },
      series: [{
        type: "pie",
        radius: ["40%", "68%"],
        data: Object.entries(distribution || {}).map(([name, value]) => ({ name: statusLabel(name), value })),
        label: { formatter: "{b}: {c}" },
      }],
    });
  }

  function renderGroupChart(elementId, group, title) {
    const series = (group?.series || []).slice(0, 4);
    renderSeriesChart(elementId, series, null, title);
  }

  function renderMetricResponseChart(elementId, payload, title) {
    const series = (payload?.series || []).slice(0, 4);
    renderSeriesChart(elementId, series, payload?.threshold, title || metricLabel(payload?.metric_name || ""));
  }

  function renderSeriesChart(elementId, seriesItems, threshold, title) {
    const chart = ensureChart(elementId);
    chart.setOption({
      animation: false,
      tooltip: { trigger: "axis" },
      legend: { top: 0 },
      grid: { left: 54, right: 24, top: 48, bottom: 56 },
      dataZoom: [{ type: "inside" }, { type: "slider", bottom: 10, height: 18 }],
      xAxis: { type: "time" },
      yAxis: { type: "value" },
      title: { text: title, left: "center", textStyle: { fontSize: 14, fontWeight: 600 } },
      series: seriesItems.map((series) => ({
        name: pathLabel(series.path_label || series.name),
        type: "line",
        showSymbol: false,
        smooth: false,
        emphasis: { focus: "series" },
        data: (series.points || []).map((point) => [point.timestamp, point.value]),
        markLine: threshold !== null && threshold !== undefined ? {
          symbol: "none",
          lineStyle: { type: "dashed" },
          data: [{ yAxis: threshold, name: "threshold" }],
        } : undefined,
        markPoint: {
          symbolSize: 28,
          data: (series.anomalies || []).slice(0, 40).map((item) => ({
            name: "anomaly",
            coord: [item.timestamp, item.value],
            value: item.value,
          })),
        },
      })),
    });
  }

  function ensureChart(elementId) {
    if (!charts[elementId]) {
      charts[elementId] = echarts.init(document.getElementById(elementId));
    }
    return charts[elementId];
  }

  function collectSettingsPayload() {
    const current = JSON.parse(JSON.stringify(state.snapshot?.settings || {}));
    current.services = current.services || {};
    current.thresholds = current.thresholds || {};
    current.scenarios = current.scenarios || {};
    current.services.relay_public_probe = { host: valueOf("relay_public_probe_host"), port: numberOf("relay_public_probe_port") };
    current.services.mc_public = { host: valueOf("mc_public_host"), port: numberOf("mc_public_port") };
    current.services.iperf_public = { host: valueOf("iperf_public_host"), port: numberOf("iperf_public_port") };
    current.services.server_backend_mc = { host: valueOf("server_backend_mc_host"), port: numberOf("server_backend_mc_port") };
    current.services.server_backend_iperf = { host: valueOf("server_backend_iperf_host"), port: numberOf("server_backend_iperf_port") };
    current.thresholds.ping = { ...(current.thresholds.ping || {}), rtt_avg_ms_max: numberOf("ping_rtt_avg_max"), jitter_ms_max: numberOf("ping_jitter_max") };
    current.thresholds.tcp = { ...(current.thresholds.tcp || {}), connect_avg_ms_max: numberOf("tcp_connect_avg_max"), timeout_or_error_pct_max: numberOf("tcp_timeout_error_max") };
    current.thresholds.throughput = { ...(current.thresholds.throughput || {}), throughput_up_mbps_min: numberOf("throughput_up_min"), throughput_down_mbps_min: numberOf("throughput_down_min") };
    current.thresholds.load_inflation = { ...(current.thresholds.load_inflation || {}), load_rtt_inflation_ms_max: numberOf("load_delta_max") };
    current.thresholds.system = { ...(current.thresholds.system || {}), cpu_usage_pct_max: numberOf("system_cpu_max") };
    current.scenarios.throughput = { ...(current.scenarios.throughput || {}), duration_sec: numberOf("throughput_duration_sec") };
    current.scenarios.load_inflation = { ...(current.scenarios.load_inflation || {}), duration_sec: numberOf("load_duration_sec") };
    current.scenarios.tcp = { ...(current.scenarios.tcp || {}), attempts: numberOf("tcp_attempts") };
    current.scenarios.system = { ...(current.scenarios.system || {}), sample_interval_sec: numberOf("system_sample_sec") };
    return current;
  }

  function readFilters() {
    return {
      timeRange: selectedValue("filter-time-range") || "24h",
      roles: selectedValues("filter-roles"),
      nodes: selectedValues("filter-nodes"),
      paths: selectedValues("filter-paths"),
      probes: selectedValues("filter-probes"),
      metric: selectedValue("filter-metric"),
      runKinds: selectedValues("filter-run-kinds"),
      severities: selectedValues("filter-severities"),
      onlyAnomalies: selectedValue("filter-only-anomalies") === "true",
      includeResolved: selectedValue("filter-include-resolved") === "true",
    };
  }

  function buildRunsQuery() {
    const filters = readFilters();
    return buildQuery({
      time_range: filters.timeRange,
      run_kind: filters.runKinds,
      path_label: filters.paths,
      has_findings: filters.onlyAnomalies ? "true" : "",
    });
  }

  function resetFilters() {
    populateSingleSelect("filter-time-range", state.filtersMeta?.time_ranges || DEFAULT_TIME_RANGES, "24h");
    populateMultiSelect("filter-roles", state.filtersMeta?.roles || FIXED_ROLES);
    populateMultiSelect("filter-nodes", (state.filtersMeta?.nodes || []).map((item) => item.node_name));
    populateMultiSelect("filter-paths", state.filtersMeta?.paths || []);
    populateMultiSelect("filter-probes", state.filtersMeta?.probes || []);
    populateSingleSelect("filter-metric", state.filtersMeta?.metrics || ["rtt_avg_ms"], "rtt_avg_ms");
    populateMultiSelect("filter-run-kinds", state.filtersMeta?.run_kinds || ["system", "baseline", "capacity", "full"]);
    populateMultiSelect("filter-severities", state.filtersMeta?.severities || ["warning", "error", "info"]);
    populateMultiSelect("filter-alert-statuses", state.filtersMeta?.statuses || ["open", "acknowledged", "resolved"], ["open", "acknowledged"]);
    populateSingleSelect("filter-only-anomalies", ["false", "true"], "false");
    populateSingleSelect("filter-include-resolved", ["false", "true"], "false");
    populateSingleSelect("path-focus-select", ["", ...(state.filtersMeta?.paths || [])], "");
    saveCurrentFilters();
  }

  function setActiveTab(tabName) {
    state.activeTab = tabName;
    safeStorageSet(ADMIN_TAB_STORAGE_KEY, tabName);
    document.querySelectorAll(".tab-button").forEach((button) => {
      button.classList.toggle("active", button.dataset.tab === tabName);
    });
    document.querySelectorAll(".tab-section").forEach((section) => {
      section.classList.toggle("hidden", section.id !== `tab-${tabName}`);
    });
    Object.values(charts).forEach((chart) => chart.resize());
  }

  function applyLocale() {
    document.documentElement.lang = state.locale;
    document.title = t("pageTitle");
    populateRefreshOptions();
    document.querySelectorAll("[data-i18n]").forEach((node) => {
      node.textContent = t(node.dataset.i18n);
    });
    renderPanelStatusMeta();
    renderFiltersSummary();
  }

  async function fetchJson(url, options = {}) {
    const response = await fetch(url, {
      credentials: "same-origin",
      ...options,
    });
    if (response.status === 401) {
      showMessage(t("sessionExpired"), "error");
      throw new Error(t("sessionExpired"));
    }
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = payload.detail;
      const message = typeof detail === "string"
        ? detail
        : detail?.message || payload.message || response.statusText || "Request failed";
      const error = new Error(message);
      error.payload = payload;
      error.detailPayload = detail;
      throw error;
    }
    return payload;
  }

  function buildQuery(mapping) {
    const query = new URLSearchParams();
    Object.entries(mapping || {}).forEach(([key, value]) => {
      if (Array.isArray(value)) {
        if (value.length) {
          query.set(key, value.join(","));
        }
        return;
      }
      if (value !== undefined && value !== null && value !== "") {
        query.set(key, value);
      }
    });
    return query;
  }

  function combineMetricResponses(items) {
    const valid = items.filter(Boolean);
    if (!valid.length) {
      return null;
    }
    return {
      metric_name: valid[0].metric_name,
      threshold: null,
      series: valid.flatMap((item) => item.series || []),
    };
  }

  function selectedValues(id) {
    return Array.from(document.getElementById(id).selectedOptions || []).map((item) => item.value).filter(Boolean);
  }

  function selectedValue(id) {
    return document.getElementById(id).value;
  }

  function setSelectedValue(id, value) {
    const element = document.getElementById(id);
    if (element) {
      element.value = value ?? "";
    }
  }

  function setSelectedValues(id, values) {
    const wanted = new Set(values || []);
    Array.from(document.getElementById(id).options || []).forEach((option) => {
      option.selected = wanted.has(option.value);
    });
  }

  function setValue(id, value) {
    const element = document.getElementById(id);
    if (element) {
      element.value = value ?? "";
    }
  }

  function valueOf(id) {
    return document.getElementById(id).value;
  }

  function numberOf(id) {
    return Number(document.getElementById(id).value || 0);
  }

  function delay(ms) {
    return new Promise((resolve) => window.setTimeout(resolve, ms));
  }

  function showMessage(message, level) {
    const box = document.getElementById("messageBox");
    box.textContent = message;
    box.className = `message show ${level || "ok"}`;
  }

  async function copyText(value) {
    try {
      await navigator.clipboard.writeText(value || "");
      showMessage(t("copied"), "ok");
    } catch (error) {
      showMessage(t("copyFailed"), "warn");
    }
  }

  function selectOptionLabel(value) {
    if (value === "") {
      return t("allPaths");
    }
    if (value === "true" || value === "false") {
      return booleanLabel(value === "true");
    }
    return pathLabel(value) !== value ? pathLabel(value)
      : runtimeLabel(value) !== value ? runtimeLabel(value)
      : roleLabel(value) !== value ? roleLabel(value)
      : runKindLabel(value) !== value ? runKindLabel(value)
      : metricLabel(value) !== value ? metricLabel(value)
      : severityLabel(value) !== value ? severityLabel(value)
      : statusLabel(value) !== value ? statusLabel(value)
      : value;
  }

  function roleLabel(role) {
    return translations[state.locale].role[role] || role;
  }

  function runtimeLabel(mode) {
    return translations[state.locale].runtime[mode] || mode;
  }

  function panelDeploymentModeLabel(mode) {
    const labels = {
      native: t("nativeMode"),
      "docker-bridge": t("dockerBridgeMode"),
    };
    return labels[mode] || mode || t("noData");
  }

  function panelControlModeLabel(mode) {
    const labels = {
      "bridge-managed": t("bridgeManaged"),
      "native-readonly": t("nativeReadonly"),
    };
    return labels[mode] || mode || t("noData");
  }

  function runKindLabel(runKind) {
    return translations[state.locale].runKindValue[runKind] || runKind;
  }

  function severityLabel(level) {
    return translations[state.locale].severityLabel[level] || statusLabel(level) || level;
  }

  function kindLabel(kind) {
    return translations[state.locale].kindLabel[kind] || kind || t("noData");
  }

  function statusLabel(status) {
    return translations[state.locale].statusLabel[status] || status || t("noData");
  }

  function pathLabel(path) {
    return PATH_LABELS[path]?.[state.locale] || path || t("noData");
  }

  function metricLabel(metric) {
    return METRIC_LABELS[metric]?.[state.locale] || metric || t("noData");
  }

  function booleanLabel(value) {
    return value ? t("booleanTrue") : t("booleanFalse");
  }

  function signalLabel(value) {
    return value ? t("signalOk") : t("signalFail");
  }

  function kpiLabel(key) {
    const labels = {
      healthScore: state.locale === "zh-CN" ? "健康评分" : "Health Score",
      onlineRate: state.locale === "zh-CN" ? "在线率" : "Online Rate",
      activeAlerts: state.locale === "zh-CN" ? "活跃告警" : "Active Alerts",
      lastFullRun: state.locale === "zh-CN" ? "最近完整运行" : "Last Full Run",
    };
    return labels[key] || key;
  }

  function summarizeMetrics(metrics) {
    const parts = [];
    Object.entries(metrics || {}).slice(0, 4).forEach(([name, value]) => {
      parts.push(`${metricLabel(name)} ${formatMetricValue(name, value)}`);
    });
    return parts.join(" | ") || t("noData");
  }

  function formatJson(value) {
    try {
      return JSON.stringify(value, null, 2);
    } catch (error) {
      return String(value);
    }
  }

  function formatMetricValue(metricName, value) {
    if (value === null || value === undefined || value === "") {
      return t("noData");
    }
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) {
      return String(value);
    }
    if ((metricName || "").endsWith("_pct")) {
      return `${numeric.toFixed(1)}%`;
    }
    if ((metricName || "").endsWith("_mbps")) {
      return `${numeric.toFixed(1)} Mbps`;
    }
    if ((metricName || "").endsWith("_ms")) {
      return `${numeric.toFixed(1)} ms`;
    }
    if ((metricName || "").endsWith("_sec")) {
      return `${numeric.toFixed(1)} sec`;
    }
    return numeric.toFixed(2);
  }

  function formatTimestamp(value) {
    if (!value) {
      return t("noData");
    }
    try {
      return new Date(value).toLocaleString(state.locale === "zh-CN" ? "zh-CN" : "en-US", {
        hour12: false,
      });
    } catch (error) {
      return value;
    }
  }

  function resultPathToHref(path) {
    if (!path) {
      return "#";
    }
    const normalized = String(path).replace(/\\/g, "/");
    if (normalized.startsWith("results/")) {
      return `/results/${normalized.slice("results/".length)}`;
    }
    if (normalized.startsWith("/results/")) {
      return normalized;
    }
    return `/results/${normalized.replace(/^\/+/, "")}`;
  }

  function t(key) {
    return key.split(".").reduce((value, segment) => (value && value[segment] !== undefined ? value[segment] : undefined), translations[state.locale]) || key;
  }

  function tWithValue(key, value) {
    return t(key).replace("{value}", value);
  }

  function loadLocale() {
    const value = safeStorageGet(ADMIN_LOCALE_STORAGE_KEY);
    if (translations[value]) {
      return value;
    }
    return detectBrowserLocale();
  }

  function loadRefreshSec() {
    const value = Number(safeStorageGet(ADMIN_REFRESH_STORAGE_KEY) || 30);
    return Number.isFinite(value) && [0, 15, 30, 60].includes(value) ? value : 30;
  }

  function loadSavedFilters() {
    try {
      const raw = safeStorageGet(ADMIN_FILTERS_STORAGE_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch (error) {
      return null;
    }
  }

  function saveCurrentFilters() {
    safeStorageSet(ADMIN_FILTERS_STORAGE_KEY, JSON.stringify({
      timeRange: selectedValue("filter-time-range"),
      roles: selectedValues("filter-roles"),
      nodes: selectedValues("filter-nodes"),
      paths: selectedValues("filter-paths"),
      probes: selectedValues("filter-probes"),
      metric: selectedValue("filter-metric"),
      runKinds: selectedValues("filter-run-kinds"),
      severities: selectedValues("filter-severities"),
      alertStatuses: selectedValues("filter-alert-statuses"),
      onlyAnomalies: selectedValue("filter-only-anomalies") === "true",
      includeResolved: selectedValue("filter-include-resolved") === "true",
      pathFocus: selectedValue("path-focus-select"),
    }));
  }

  function detectBrowserLocale() {
    const languages = Array.isArray(navigator.languages) && navigator.languages.length ? navigator.languages : [navigator.language || ""];
    return languages.some((value) => String(value).toLowerCase().startsWith("zh")) ? "zh-CN" : "en-US";
  }

  function safeStorageGet(key) {
    try {
      return window.localStorage.getItem(key);
    } catch (error) {
      return null;
    }
  }

  function safeStorageSet(key, value) {
    try {
      window.localStorage.setItem(key, value);
    } catch (error) {
      return;
    }
  }

  function formatFilterCount(values) {
    return values && values.length ? String(values.length) : t("all");
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }
})();
