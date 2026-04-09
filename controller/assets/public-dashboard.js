(function () {
  const PUBLIC_LOCALE_STORAGE_KEY = "mc-netprobe-public-locale";
  const PUBLIC_TIME_RANGE_STORAGE_KEY = "mc-netprobe-public-time-range";
  const PUBLIC_REFRESH_STORAGE_KEY = "mc-netprobe-public-refresh-sec";
  const state = {
    data: window.__INITIAL_STATE__ || {},
    locale: loadLocale(),
    timeRange: loadTimeRange(),
    refreshSec: loadRefreshSec(),
    lastRefreshAt: (window.__INITIAL_STATE__ || {}).generated_at || null,
    lastError: "",
    requestEpoch: 0,
  };

  const charts = {};
  let refreshTimer = null;
  const translations = {
    "zh-CN": {
      pageTitle: "mc-netprobe 公开网络看板",
      boardBadge: "公开网络质量大盘",
      language: "语言",
      timeRange: "时间范围",
      heroTitle: "mc-netprobe 网络质量总览",
      heroDescription: "公开查看网络质量、角色健康、近期异常与监测趋势。内部地址、管理操作和敏感配置保持在管理员后台内。",
      adminLogin: "管理员登录",
      refreshBoard: "刷新看板",
      openLatestReport: "打开最新报告",
      topSummary: "执行摘要",
      roleHealth: "角色健康",
      roleHealthHint: "仅公开角色级状态，不暴露后端地址",
      pathSummary: "路径摘要",
      pathSummaryHint: "聚焦延迟、丢包、抖动、吞吐与活跃告警",
      latencyTrend: "延迟趋势",
      jitterTrend: "抖动趋势",
      lossTrend: "丢包趋势",
      throughputTrend: "吞吐趋势",
      recentAnomalies: "最近异常",
      recentAnomaliesHint: "仅展示阈值和离群事件",
      recentRuns: "最近运行",
      totalNodes: "节点总数",
      onlineRate: "在线率",
      abnormalNodes: "异常节点",
      activeAlerts: "活跃告警",
      lastFullRun: "最近完整运行",
      findings: "发现项",
      push: "Push",
      pull: "Pull",
      signalOk: "正常",
      signalFail: "失败",
      noData: "暂无数据",
      noAlerts: "暂无异常事件。",
      noRuns: "暂无运行记录。",
      alerts: "告警",
      anomalies: "异常",
      avg: "平均",
      latest: "最新",
      path: "路径",
      lastCaptured: "最近采样",
      lastSeen: "最近上线",
      reportUnavailable: "暂无报告",
      updatedAt: "更新时间",
      autoRefresh: "自动刷新",
      refreshOff: "关闭",
      refresh15: "15 秒",
      refresh30: "30 秒",
      refresh60: "60 秒",
      refreshStatusReady: "页面已就绪",
      refreshStatusOk: "已刷新",
      refreshStatusError: "刷新失败",
      kpiUnitPct: "%",
      runKind: {
        system: "系统",
        baseline: "基线",
        capacity: "容量",
        full: "完整",
      },
      role: { client: "客户端", relay: "中继", server: "服务端" },
      status: {
        online: "在线",
        "push-only": "仅 Push",
        "pull-only": "仅 Pull",
        offline: "离线",
        unpaired: "未配对",
        disabled: "已禁用",
        healthy: "健康",
        degraded: "降级",
        critical: "严重",
        ok: "正常",
        unknown: "未知",
        running: "运行中",
        completed: "完成",
        failed: "失败",
        open: "未恢复",
        acknowledged: "已确认",
        resolved: "已恢复",
      },
      kind: {
        anomaly: "异常",
        threshold: "阈值",
        node_status: "节点状态",
      },
    },
    "en-US": {
      pageTitle: "mc-netprobe public board",
      boardBadge: "Public network quality board",
      language: "Language",
      timeRange: "Time range",
      heroTitle: "mc-netprobe Network Quality",
      heroDescription: "Public visibility into network quality, role health, recent anomalies, and monitoring trends. Internal addresses, management actions, and sensitive configuration stay behind admin access.",
      adminLogin: "Admin Login",
      refreshBoard: "Refresh Board",
      openLatestReport: "Open latest report",
      topSummary: "Executive Summary",
      roleHealth: "Role Health",
      roleHealthHint: "Role-level visibility without exposing backend endpoints",
      pathSummary: "Path Summary",
      pathSummaryHint: "Focused on latency, loss, jitter, throughput, and active alerts",
      latencyTrend: "Latency Trend",
      jitterTrend: "Jitter Trend",
      lossTrend: "Loss Trend",
      throughputTrend: "Throughput Trend",
      recentAnomalies: "Recent Anomalies",
      recentAnomaliesHint: "Threshold and outlier events only",
      recentRuns: "Recent Runs",
      totalNodes: "Total Nodes",
      onlineRate: "Online Rate",
      abnormalNodes: "Abnormal Nodes",
      activeAlerts: "Active Alerts",
      lastFullRun: "Last Full Run",
      findings: "Findings",
      push: "Push",
      pull: "Pull",
      signalOk: "OK",
      signalFail: "FAIL",
      noData: "No data yet",
      noAlerts: "No recent anomaly events.",
      noRuns: "No runs yet.",
      alerts: "Alerts",
      anomalies: "Anomalies",
      avg: "Average",
      latest: "Latest",
      path: "Path",
      lastCaptured: "Last captured",
      lastSeen: "Last seen",
      reportUnavailable: "No report",
      updatedAt: "Updated",
      autoRefresh: "Auto refresh",
      refreshOff: "Off",
      refresh15: "15 sec",
      refresh30: "30 sec",
      refresh60: "60 sec",
      refreshStatusReady: "Ready",
      refreshStatusOk: "Refreshed",
      refreshStatusError: "Refresh failed",
      kpiUnitPct: "%",
      runKind: {
        system: "System",
        baseline: "Baseline",
        capacity: "Capacity",
        full: "Full",
      },
      role: { client: "Client", relay: "Relay", server: "Server" },
      status: {
        online: "Online",
        "push-only": "Push only",
        "pull-only": "Pull only",
        offline: "Offline",
        unpaired: "Unpaired",
        disabled: "Disabled",
        healthy: "Healthy",
        degraded: "Degraded",
        critical: "Critical",
        ok: "OK",
        unknown: "Unknown",
        running: "Running",
        completed: "Completed",
        failed: "Failed",
        open: "Open",
        acknowledged: "Acknowledged",
        resolved: "Resolved",
      },
      kind: {
        anomaly: "Anomaly",
        threshold: "Threshold",
        node_status: "Node status",
      },
    },
  };

  const PATH_LABELS = {
    client_to_relay: { "zh-CN": "客户端 -> 中继", "en-US": "Client -> Relay" },
    relay_to_server: { "zh-CN": "中继 -> 服务端", "en-US": "Relay -> Server" },
    client_to_mc_public: { "zh-CN": "客户端 -> MC 公网", "en-US": "Client -> MC Public" },
    client_to_iperf_public: { "zh-CN": "客户端 -> iperf 公网", "en-US": "Client -> iperf Public" },
    client_to_mc_public_load: { "zh-CN": "客户端 -> MC 公网负载", "en-US": "Client -> MC Public Load" },
    client_system: { "zh-CN": "客户端系统", "en-US": "Client System" },
    relay_system: { "zh-CN": "中继系统", "en-US": "Relay System" },
    server_system: { "zh-CN": "服务端系统", "en-US": "Server System" },
  };

  const METRIC_LABELS = {
    rtt_avg_ms: { "zh-CN": "平均 RTT", "en-US": "RTT avg" },
    connect_avg_ms: { "zh-CN": "TCP 平均连接", "en-US": "TCP connect avg" },
    jitter_ms: { "zh-CN": "抖动", "en-US": "Jitter" },
    packet_loss_pct: { "zh-CN": "丢包", "en-US": "Packet loss" },
    connect_timeout_or_error_pct: { "zh-CN": "TCP 错误", "en-US": "TCP error" },
    throughput_down_mbps: { "zh-CN": "下行吞吐", "en-US": "Down throughput" },
    throughput_up_mbps: { "zh-CN": "上行吞吐", "en-US": "Up throughput" },
    load_rtt_inflation_ms: { "zh-CN": "负载增量", "en-US": "Load inflation" },
    cpu_usage_pct: { "zh-CN": "CPU 使用率", "en-US": "CPU usage" },
  };

  document.addEventListener("DOMContentLoaded", () => {
    bindEvents();
    applyLocale();
    restoreControls();
    setupAutoRefresh();
    render();
    renderStatusMeta();
  });

  function bindEvents() {
    document.getElementById("localeSelect").addEventListener("change", (event) => {
      state.locale = event.target.value;
      safeStorageSet(PUBLIC_LOCALE_STORAGE_KEY, state.locale);
      applyLocale();
      render();
    });
    document.getElementById("timeRangeSelect").addEventListener("change", async (event) => {
      state.timeRange = event.target.value;
      safeStorageSet(PUBLIC_TIME_RANGE_STORAGE_KEY, state.timeRange);
      await refreshData();
    });
    document.getElementById("autoRefreshSelect").addEventListener("change", (event) => {
      state.refreshSec = Number(event.target.value || 0);
      safeStorageSet(PUBLIC_REFRESH_STORAGE_KEY, String(state.refreshSec));
      setupAutoRefresh();
      renderStatusMeta();
    });
    document.getElementById("refreshBtn").addEventListener("click", refreshData);
    window.addEventListener("resize", () => Object.values(charts).forEach((chart) => chart.resize()));
  }

  function restoreControls() {
    populateRefreshOptions();
    document.getElementById("localeSelect").value = state.locale;
    document.getElementById("timeRangeSelect").value = state.timeRange;
    document.getElementById("autoRefreshSelect").value = String(state.refreshSec);
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
        refreshData().catch(() => undefined);
      }, state.refreshSec * 1000);
    }
  }

  async function refreshData() {
    const epoch = ++state.requestEpoch;
    const response = await fetch(`/api/v1/public-dashboard?time_range=${encodeURIComponent(state.timeRange)}`, {
      credentials: "same-origin",
    });
    if (!response.ok) {
      if (epoch !== state.requestEpoch) {
        return;
      }
      state.lastError = `${t("refreshStatusError")}: ${response.status}`;
      renderStatusMeta();
      return;
    }
    const payload = await response.json();
    if (epoch !== state.requestEpoch) {
      return;
    }
    state.data = payload;
    state.lastRefreshAt = payload.generated_at || state.lastRefreshAt;
    state.lastError = "";
    render();
  }

  function applyLocale() {
    document.documentElement.lang = state.locale;
    document.title = t("pageTitle");
    populateRefreshOptions();
    document.querySelectorAll("[data-i18n]").forEach((node) => {
      node.textContent = t(node.dataset.i18n);
    });
    renderStatusMeta();
  }

  function render() {
    document.getElementById("topologyName").textContent = state.data.topology_name || "";
    document.getElementById("lastUpdated").textContent = `${t("updatedAt")}: ${formatTimestamp(state.data.generated_at || state.lastRefreshAt)}`;
    renderLatestReport();
    renderKpis();
    renderRoles();
    renderPaths();
    renderAlerts();
    renderRuns();
    renderCharts();
    renderStatusMeta();
  }

  function renderStatusMeta() {
    const status = document.getElementById("boardStatusMeta");
    const refreshLabel = state.refreshSec > 0 ? `${state.refreshSec}s` : t("refreshOff");
    const effectiveTimestamp = state.data.generated_at || state.lastRefreshAt;
    const base = effectiveTimestamp
      ? `${t("refreshStatusOk")} · ${t("updatedAt")}: ${formatTimestamp(effectiveTimestamp)}`
      : t("refreshStatusReady");
    const suffix = `${t("timeRange")}: ${state.timeRange} · ${t("autoRefresh")}: ${refreshLabel}`;
    status.textContent = state.lastError ? `${state.lastError} · ${suffix}` : `${base} · ${suffix}`;
  }

  function renderLatestReport() {
    const latestRun = (state.data.latest_runs || []).find((run) => run.html_path);
    const link = document.getElementById("latestReportLink");
    if (!latestRun || !latestRun.html_path) {
      link.textContent = t("reportUnavailable");
      link.removeAttribute("href");
      return;
    }
    link.textContent = t("openLatestReport");
    link.href = resultPathToHref(latestRun.html_path);
  }

  function renderKpis() {
    const summary = state.data.summary || {};
    const items = [
      { label: t("totalNodes"), value: summary.total_nodes ?? 0, meta: `${summary.online_nodes ?? 0}/${summary.total_nodes ?? 0}` },
      { label: t("onlineRate"), value: formatNumber(summary.online_rate_pct, "%"), meta: `${summary.online_nodes ?? 0}` },
      { label: t("abnormalNodes"), value: summary.abnormal_nodes ?? 0, meta: `${summary.degraded_nodes ?? 0} / ${summary.offline_nodes ?? 0}` },
      { label: t("activeAlerts"), value: summary.active_alerts ?? 0, meta: "" },
      { label: t("lastFullRun"), value: summary.last_full_run_status ? statusLabel(summary.last_full_run_status) : t("noData"), meta: formatTimestamp(summary.last_full_run_started_at) },
    ];
    document.getElementById("kpiGrid").innerHTML = items.map((item) => `
      <div class="card">
        <div class="muted">${escapeHtml(item.label)}</div>
        <div class="kpi-value">${escapeHtml(String(item.value))}</div>
        <div class="metric-meta">${escapeHtml(item.meta || "")}</div>
      </div>
    `).join("");
  }

  function renderRoles() {
    const roles = ["client", "relay", "server"];
    const nodes = state.data.nodes || [];
    const html = roles.map((role) => {
      const node = nodes.find((item) => item.role === role);
      if (!node) {
        return `
          <div class="card">
            <h3>${escapeHtml(roleLabel(role))}</h3>
            <div class="empty">${escapeHtml(t("noData"))}</div>
          </div>
        `;
      }
      return `
        <div class="card">
          <div class="section-head">
            <h3>${escapeHtml(roleLabel(role))}</h3>
            <span class="status-pill ${escapeHtml(node.status)}">${escapeHtml(statusLabel(node.status))}</span>
          </div>
          <div class="metric-meta">${escapeHtml(node.node_name)}</div>
          <div class="metric-meta">${escapeHtml(t("lastSeen"))}: ${escapeHtml(formatTimestamp(node.last_seen_at))}</div>
          <div class="metric-meta">${escapeHtml(t("push"))}: ${escapeHtml(statusLabel(node.connectivity?.push?.state || "unknown"))} | ${escapeHtml(t("pull"))}: ${escapeHtml(statusLabel(node.connectivity?.pull?.state || "unknown"))}</div>
        </div>
      `;
    }).join("");
    document.getElementById("roleGrid").innerHTML = html;
  }

  function renderPaths() {
    const paths = state.data.paths || [];
    const html = paths.map((item) => {
      const latest = item.latest || {};
      return `
        <div class="card">
          <div class="section-head">
            <h3>${escapeHtml(pathLabel(item.path_label))}</h3>
            <span class="status-pill ${escapeHtml(item.status)}">${escapeHtml(statusLabel(item.status))}</span>
          </div>
          <div class="metric-meta">${escapeHtml(metricSummary(latest))}</div>
          <div class="metric-meta">${escapeHtml(t("alerts"))}: ${item.open_alerts || 0} | ${escapeHtml(t("anomalies"))}: ${item.open_anomalies || 0}</div>
          <div class="metric-meta">${escapeHtml(t("lastCaptured"))}: ${escapeHtml(formatTimestamp(item.last_captured_at))}</div>
        </div>
      `;
    }).join("");
    document.getElementById("pathGrid").innerHTML = html || `<div class="empty">${escapeHtml(t("noData"))}</div>`;
  }

  function renderAlerts() {
    const alerts = (state.data.alerts || []).filter((item) => item.kind === "anomaly" || item.kind === "threshold").slice(0, 8);
    const root = document.getElementById("alertsList");
    if (!alerts.length) {
      root.innerHTML = `<div class="empty">${escapeHtml(t("noAlerts"))}</div>`;
      return;
    }
    root.innerHTML = alerts.map((alert) => `
      <div class="list-item">
        <div class="section-head">
          <strong>${escapeHtml(kindLabel(alert.kind))}</strong>
          <span class="status-pill ${escapeHtml(alert.severity || alert.status)}">${escapeHtml(statusLabel(alert.status || alert.severity))}</span>
        </div>
        <div class="metric-meta">${escapeHtml(pathLabel(alert.path_label || ""))}</div>
        <p>${escapeHtml(alert.message || "")}</p>
        <div class="metric-meta">${escapeHtml(formatTimestamp(alert.created_at))}</div>
      </div>
    `).join("");
  }

  function renderRuns() {
    const runs = state.data.latest_runs || [];
    const root = document.getElementById("runsList");
    if (!runs.length) {
      root.innerHTML = `<div class="empty">${escapeHtml(t("noRuns"))}</div>`;
      return;
    }
    root.innerHTML = runs.slice(0, 8).map((run) => `
      <div class="list-item">
        <div class="section-head">
          <strong>${escapeHtml(runKindLabel(run.run_kind || ""))}</strong>
          <span class="status-pill ${escapeHtml(run.status || "")}">${escapeHtml(statusLabel(run.status || ""))}</span>
        </div>
        <div class="metric-meta">${escapeHtml(formatTimestamp(run.started_at))}</div>
        <div class="metric-meta">${escapeHtml(t("findings"))}: ${run.findings_count || 0}</div>
        ${run.html_path ? `<a href="${escapeHtml(resultPathToHref(run.html_path))}" target="_blank" rel="noreferrer">${escapeHtml(t("openLatestReport"))}</a>` : ""}
      </div>
    `).join("");
  }

  function renderCharts() {
    const groups = state.data.history?.trend_groups || {};
    renderSeriesChart("latencyChart", groups.latency, t("latencyTrend"));
    renderSeriesChart("jitterChart", groups.jitter, t("jitterTrend"));
    renderSeriesChart("lossChart", groups.loss, t("lossTrend"));
    renderSeriesChart("throughputChart", groups.throughput, t("throughputTrend"));
  }

  function renderSeriesChart(elementId, group, title) {
    const root = document.getElementById(elementId);
    if (!charts[elementId]) {
      charts[elementId] = echarts.init(root);
    }
    const seriesItems = (group?.series || []).slice(0, 4);
    charts[elementId].setOption({
      animation: false,
      tooltip: { trigger: "axis" },
      legend: { top: 0 },
      grid: { left: 54, right: 24, top: 48, bottom: 52 },
      dataZoom: [{ type: "inside" }, { type: "slider", height: 18, bottom: 10 }],
      xAxis: { type: "time" },
      yAxis: { type: "value" },
      series: seriesItems.map((series) => ({
        name: pathLabel(series.path_label || series.name),
        type: "line",
        showSymbol: false,
        smooth: false,
        emphasis: { focus: "series" },
        data: (series.points || []).map((point) => [point.timestamp, point.value]),
        markPoint: {
          symbolSize: 28,
          data: (series.anomalies || []).slice(0, 40).map((item) => ({
            name: "anomaly",
            coord: [item.timestamp, item.value],
            value: item.value,
          })),
        },
      })),
      title: { text: title, left: "center", textStyle: { fontSize: 14, fontWeight: 600 } },
    });
  }

  function metricSummary(latest) {
    const parts = [];
    Object.entries(latest || {}).slice(0, 4).forEach(([metricName, value]) => {
      parts.push(`${metricLabel(metricName)} ${formatMetricValue(metricName, value)}`);
    });
    return parts.join(" | ") || t("noData");
  }

  function formatMetricValue(metricName, value) {
    if (value === null || value === undefined || Number.isNaN(Number(value))) {
      return t("noData");
    }
    const numeric = Number(value);
    if (metricName.endsWith("_pct")) {
      return `${numeric.toFixed(1)}%`;
    }
    if (metricName.endsWith("_mbps")) {
      return `${numeric.toFixed(1)} Mbps`;
    }
    if (metricName.endsWith("_ms")) {
      return `${numeric.toFixed(1)} ms`;
    }
    return numeric.toFixed(2);
  }

  function pathLabel(path) {
    return PATH_LABELS[path]?.[state.locale] || path || t("noData");
  }

  function metricLabel(metricName) {
    return METRIC_LABELS[metricName]?.[state.locale] || metricName;
  }

  function roleLabel(role) {
    return translations[state.locale].role[role] || role;
  }

  function runKindLabel(runKind) {
    return translations[state.locale].runKind[runKind] || runKind;
  }

  function statusLabel(status) {
    return translations[state.locale].status[status] || status || t("noData");
  }

  function kindLabel(kind) {
    return translations[state.locale].kind[kind] || kind || t("noData");
  }

  function signalLabel(value) {
    return value ? t("signalOk") : t("signalFail");
  }

  function inferTimeRange(payload) {
    const hours = payload?.history?.time_range_hours || 24;
    if (hours >= 24 * 30) {
      return "30d";
    }
    if (hours >= 24 * 7) {
      return "7d";
    }
    return "24h";
  }

  function loadLocale() {
    const value = safeStorageGet(PUBLIC_LOCALE_STORAGE_KEY);
    if (translations[value]) {
      return value;
    }
    return detectBrowserLocale();
  }

  function loadRefreshSec() {
    const value = Number(safeStorageGet(PUBLIC_REFRESH_STORAGE_KEY) || 30);
    return Number.isFinite(value) && [0, 15, 30, 60].includes(value) ? value : 30;
  }

  function loadTimeRange() {
    const value = safeStorageGet(PUBLIC_TIME_RANGE_STORAGE_KEY);
    return ["24h", "7d", "30d"].includes(value || "") ? value : inferTimeRange(window.__INITIAL_STATE__);
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

  function formatNumber(value, suffix) {
    if (value === null || value === undefined || value === "") {
      return t("noData");
    }
    return `${Number(value).toFixed(1)}${suffix || ""}`;
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

  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }
})();
