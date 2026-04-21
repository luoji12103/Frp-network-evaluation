(function () {
  const PUBLIC_LOCALE_STORAGE_KEY = "mc-netprobe-public-locale";
  const PUBLIC_TIME_RANGE_STORAGE_KEY = "mc-netprobe-public-time-range";
  const PUBLIC_REFRESH_STORAGE_KEY = "mc-netprobe-public-refresh-sec";
  const DETAIL_METRIC_GROUPS = {
    path: ["latency", "loss", "jitter", "throughput", "load"],
    role: ["latency", "loss", "jitter", "throughput", "load", "system"],
  };
  const PAGE = window.__PUBLIC_PAGE__ || { kind: "overview", scope_id: null };
  const INITIAL_STATE = window.__INITIAL_STATE__ || {};
  const charts = {};
  let refreshTimer = null;

  const state = {
    page: PAGE,
    overview: PAGE.kind === "overview" ? INITIAL_STATE : null,
    detail: PAGE.kind === "overview" ? null : INITIAL_STATE,
    locale: loadLocale(),
    timeRange: loadTimeRange(INITIAL_STATE),
    refreshSec: loadRefreshSec(),
    requestEpoch: 0,
    lastRefreshAt: INITIAL_STATE.generated_at || null,
    lastError: "",
  };

  const translations = {
    "zh-CN": {
      pageTitle: "MC公开网络质量",
      boardBadge: "公开网络质量",
      language: "语言",
      timeRange: "时间范围",
      autoRefresh: "自动刷新",
      refreshOff: "关闭",
      refresh15: "15 秒",
      refresh30: "30 秒",
      refresh60: "60 秒",
      heroTitle: "MC网络质量监测",
      heroDescription: "公开查看网络质量、角色健康、近期异常与监测趋势。内部地址、管理操作和敏感配置保持在管理员后台内。",
      pathHeroTitle: "公开路径详情",
      pathHeroDescription: "查看单条公开链路的延迟、丢包、抖动、吞吐、负载与相关异常。",
      roleHeroTitle: "公开角色详情",
      roleHeroDescription: "查看角色健康、相关链路趋势、系统摘要与近期公开运行。",
      adminLogin: "管理员登录",
      backToOverview: "返回总览",
      refreshBoard: "刷新看板",
      openLatestReport: "打开最新报告",
      reportUnavailable: "暂无报告",
      topSummary: "执行摘要",
      detailSummary: "详情摘要",
      roleHealth: "角色健康",
      roleHealthHint: "仅公开角色级状态，不暴露后端地址",
      pathSummary: "路径摘要",
      pathSummaryHint: "聚焦延迟、丢包、抖动、吞吐与活跃告警",
      relatedPaths: "相关路径",
      relatedPathsHint: "仅公开路径级状态与指标",
      latencyTrend: "延迟趋势",
      jitterTrend: "抖动趋势",
      lossTrend: "丢包趋势",
      throughputTrend: "吞吐趋势",
      loadTrend: "负载趋势",
      systemTrend: "系统趋势",
      recentAnomalies: "最近异常",
      recentAnomaliesHint: "仅展示阈值和离群事件",
      recentRuns: "最近运行",
      totalNodes: "节点总数",
      onlineRate: "在线率",
      abnormalNodes: "异常节点",
      activeAlerts: "活跃告警",
      lastFullRun: "最近完整运行",
      findings: "发现项",
      lastSeen: "最近上线",
      lastCaptured: "最近采样",
      push: "Push",
      pull: "Pull",
      latest: "最新",
      average: "均值",
      peak: "峰值",
      p95: "P95",
      anomalies: "异常",
      compare: "对比",
      noData: "暂无数据",
      noAlerts: "暂无异常事件。",
      noRuns: "暂无运行记录。",
      updatedAt: "更新时间",
      refreshStatusReady: "页面已就绪",
      refreshStatusOk: "已刷新",
      refreshStatusError: "刷新失败",
      path: "路径",
      alerts: "告警",
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
        pass: "通过",
        warn: "警告",
        fail: "失败",
        skip: "跳过",
      },
      role: { client: "客户端", relay: "中继", server: "服务端" },
      runKind: { system: "系统", baseline: "基线", capacity: "容量", full: "完整" },
      kind: { anomaly: "异常", threshold: "阈值", node_status: "节点状态" },
    },
    "en-US": {
      pageTitle: "MC Public Network Quality",
      boardBadge: "Public Network Quality",
      language: "Language",
      timeRange: "Time range",
      autoRefresh: "Auto refresh",
      refreshOff: "Off",
      refresh15: "15 sec",
      refresh30: "30 sec",
      refresh60: "60 sec",
      heroTitle: "MC Network Quality Monitoring",
      heroDescription: "Public visibility into network quality, role health, recent anomalies, and monitoring trends. Internal addresses, management actions, and sensitive configuration stay behind admin access.",
      pathHeroTitle: "Public path detail",
      pathHeroDescription: "Inspect one public path across latency, loss, jitter, throughput, load, and related anomalies.",
      roleHeroTitle: "Public role detail",
      roleHeroDescription: "Inspect role health, related path trends, system summary, and recent public runs.",
      adminLogin: "Admin Login",
      backToOverview: "Back to overview",
      refreshBoard: "Refresh Board",
      openLatestReport: "Open latest report",
      reportUnavailable: "No report",
      topSummary: "Executive Summary",
      detailSummary: "Detail Summary",
      roleHealth: "Role Health",
      roleHealthHint: "Role-level visibility without exposing backend endpoints",
      pathSummary: "Path Summary",
      pathSummaryHint: "Focused on latency, loss, jitter, throughput, and active alerts",
      relatedPaths: "Related Paths",
      relatedPathsHint: "Public path-level status and metrics only",
      latencyTrend: "Latency Trend",
      jitterTrend: "Jitter Trend",
      lossTrend: "Loss Trend",
      throughputTrend: "Throughput Trend",
      loadTrend: "Load Trend",
      systemTrend: "System Trend",
      recentAnomalies: "Recent Anomalies",
      recentAnomaliesHint: "Threshold and outlier events only",
      recentRuns: "Recent Runs",
      totalNodes: "Total Nodes",
      onlineRate: "Online Rate",
      abnormalNodes: "Abnormal Nodes",
      activeAlerts: "Active Alerts",
      lastFullRun: "Last Full Run",
      findings: "Findings",
      lastSeen: "Last seen",
      lastCaptured: "Last captured",
      push: "Push",
      pull: "Pull",
      latest: "Latest",
      average: "Average",
      peak: "Peak",
      p95: "P95",
      anomalies: "Anomalies",
      compare: "Compare",
      noData: "No data yet",
      noAlerts: "No recent anomaly events.",
      noRuns: "No runs yet.",
      updatedAt: "Updated",
      refreshStatusReady: "Ready",
      refreshStatusOk: "Refreshed",
      refreshStatusError: "Refresh failed",
      path: "Path",
      alerts: "Alerts",
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
        pass: "Pass",
        warn: "Warn",
        fail: "Fail",
        skip: "Skip",
      },
      role: { client: "Client", relay: "Relay", server: "Server" },
      runKind: { system: "System", baseline: "Baseline", capacity: "Capacity", full: "Full" },
      kind: { anomaly: "Anomaly", threshold: "Threshold", node_status: "Node status" },
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
    rtt_p95_ms: { "zh-CN": "RTT P95", "en-US": "RTT P95" },
    connect_avg_ms: { "zh-CN": "TCP 平均连接", "en-US": "TCP connect avg" },
    connect_timeout_or_error_pct: { "zh-CN": "TCP 错误", "en-US": "TCP error" },
    jitter_ms: { "zh-CN": "抖动", "en-US": "Jitter" },
    packet_loss_pct: { "zh-CN": "丢包", "en-US": "Packet loss" },
    throughput_down_mbps: { "zh-CN": "下行吞吐", "en-US": "Down throughput" },
    throughput_up_mbps: { "zh-CN": "上行吞吐", "en-US": "Up throughput" },
    load_rtt_inflation_ms: { "zh-CN": "负载增量", "en-US": "Load inflation" },
    cpu_usage_pct: { "zh-CN": "CPU 使用率", "en-US": "CPU usage" },
    memory_usage_pct: { "zh-CN": "内存使用率", "en-US": "Memory usage" },
  };

  document.addEventListener("DOMContentLoaded", async () => {
    bindEvents();
    applyLocale();
    restoreControls();
    setupAutoRefresh();
    render();
    if (state.page.kind !== "overview" || state.timeRange !== inferTimeRange(INITIAL_STATE)) {
      await refreshData();
    }
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
    document.getElementById("homeLink").classList.toggle("hidden", state.page.kind === "overview");
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
    try {
      if (state.page.kind === "overview") {
        const payload = await fetchJson(`/api/v1/public-dashboard?time_range=${encodeURIComponent(state.timeRange)}`);
        if (epoch !== state.requestEpoch) return;
        state.overview = payload;
        state.lastRefreshAt = payload.generated_at || state.lastRefreshAt;
      } else if (state.page.kind === "path") {
        const scopeId = state.page.scope_id;
        const requests = [
          fetchJson(`/api/v1/public-dashboard?time_range=${encodeURIComponent(state.timeRange)}`),
          fetchJson(`/api/v1/public/path-health?time_range=${encodeURIComponent(state.timeRange)}&path_id=${encodeURIComponent(scopeId)}`),
          ...DETAIL_METRIC_GROUPS.path.map((group) => fetchJson(`/api/v1/public/timeseries?scope_kind=path&scope_id=${encodeURIComponent(scopeId)}&metric_group=${encodeURIComponent(group)}&time_range=${encodeURIComponent(state.timeRange)}`)),
        ];
        const [overview, pathPayload, ...timeseries] = await Promise.all(requests);
        if (epoch !== state.requestEpoch) return;
        state.overview = overview;
        state.detail = buildPathDetailState(pathPayload.path || {}, overview, timeseries);
        state.lastRefreshAt = overview.generated_at || state.lastRefreshAt;
      } else if (state.page.kind === "role") {
        const scopeId = state.page.scope_id;
        const requests = [
          fetchJson(`/api/v1/public-dashboard?time_range=${encodeURIComponent(state.timeRange)}`),
          ...DETAIL_METRIC_GROUPS.role.map((group) => fetchJson(`/api/v1/public/timeseries?scope_kind=role&scope_id=${encodeURIComponent(scopeId)}&metric_group=${encodeURIComponent(group)}&time_range=${encodeURIComponent(state.timeRange)}`)),
        ];
        const [overview, ...timeseries] = await Promise.all(requests);
        if (epoch !== state.requestEpoch) return;
        state.overview = overview;
        state.detail = buildRoleDetailState(scopeId, overview, timeseries);
        state.lastRefreshAt = overview.generated_at || state.lastRefreshAt;
      }
      state.lastError = "";
      render();
    } catch (error) {
      if (epoch !== state.requestEpoch) return;
      state.lastError = `${t("refreshStatusError")}: ${(error && error.message) || error}`;
      renderStatusMeta();
    }
  }

  function buildPathDetailState(pathPayload, overview, timeseriesResponses) {
    const pathId = pathPayload.path_id || state.page.scope_id;
    return {
      ...pathPayload,
      path_id: pathId,
      alerts: filterAlertsByPath(overview.alerts || [], pathId),
      latest_runs: filterRunsByPath(overview.latest_runs || [], pathId),
      related_paths: (overview.paths || []).filter((item) => item.path_id === pathId),
      charts: groupTimeseriesResponses(timeseriesResponses),
    };
  }

  function buildRoleDetailState(role, overview, timeseriesResponses) {
    const node = (overview.nodes || []).find((item) => item.role === role) || {};
    return {
      ...node,
      role,
      paths: (overview.paths || []).filter((item) => (item.roles || []).includes(role)),
      alerts: filterAlertsByRole(overview.alerts || [], role),
      latest_runs: filterRunsByRole(overview.latest_runs || [], role),
      charts: groupTimeseriesResponses(timeseriesResponses),
    };
  }

  function groupTimeseriesResponses(responses) {
    const grouped = {};
    (responses || []).forEach((payload) => {
      if (payload && payload.metric_group) {
        grouped[payload.metric_group] = payload;
      }
    });
    return grouped;
  }

  function fetchJson(url) {
    return fetch(url, { credentials: "same-origin" }).then(async (response) => {
      if (!response.ok) {
        const text = await response.text();
        throw new Error(text || `HTTP ${response.status}`);
      }
      return response.json();
    });
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
    if (state.page.kind === "overview") {
      renderOverview();
    } else {
      renderDetail();
    }
    renderStatusMeta();
  }

  function renderOverview() {
    const overview = state.overview || INITIAL_STATE || {};
    document.getElementById("overviewView").classList.remove("hidden");
    document.getElementById("detailView").classList.add("hidden");
    document.getElementById("heroTitle").textContent = t("heroTitle");
    document.getElementById("heroDescription").textContent = t("heroDescription");
    document.getElementById("summaryTitle").textContent = t("topSummary");
    document.getElementById("topologyName").textContent = overview.topology_name || "";
    document.getElementById("lastUpdated").textContent = `${t("updatedAt")}: ${formatTimestamp(overview.generated_at || state.lastRefreshAt)}`;
    renderLatestReport(overview.latest_runs || []);
    renderKpis(overview);
    renderRoles(overview.nodes || []);
    renderPaths(overview.paths || []);
    renderAlerts("alertsList", overview.alerts || []);
    renderRuns("runsList", overview.latest_runs || []);
    renderGroupChart("latencyChart", overview.history?.trend_groups?.latency, t("latencyTrend"));
    renderGroupChart("jitterChart", overview.history?.trend_groups?.jitter, t("jitterTrend"));
    renderGroupChart("lossChart", overview.history?.trend_groups?.loss, t("lossTrend"));
    renderGroupChart("throughputChart", overview.history?.trend_groups?.throughput, t("throughputTrend"));
    renderGroupChart("loadChart", overview.history?.trend_groups?.load, t("loadTrend"));
    renderGroupChart("systemChart", overview.history?.trend_groups?.system, t("systemTrend"));
  }

  function renderDetail() {
    const detail = state.detail || INITIAL_STATE || {};
    document.getElementById("overviewView").classList.add("hidden");
    document.getElementById("detailView").classList.remove("hidden");
    if (state.page.kind === "path") {
      document.getElementById("heroTitle").textContent = `${t("pathHeroTitle")} · ${pathLabel(detail.path_id || state.page.scope_id)}`;
      document.getElementById("heroDescription").textContent = t("pathHeroDescription");
      document.getElementById("detailTitle").textContent = pathLabel(detail.path_id || state.page.scope_id);
      document.getElementById("detailSubtitle").textContent = statusLabel(detail.status || "unknown");
      document.getElementById("summaryTitle").textContent = t("detailSummary");
      document.getElementById("topologyName").textContent = `${t("path")}: ${pathLabel(detail.path_id || state.page.scope_id)}`;
      renderLatestReport(detail.latest_runs || []);
      renderDetailMetricSummary(flattenDetailSeries(detail.charts));
      renderDetailPaths(detail.related_paths || []);
      renderAlerts("detailAlertsList", detail.alerts || []);
      renderRuns("detailRunsList", detail.latest_runs || []);
      document.getElementById("detailAlertsHint").textContent = pathLabel(detail.path_id || state.page.scope_id);
      document.getElementById("detailRunsHint").textContent = pathLabel(detail.path_id || state.page.scope_id);
      renderDetailCharts(detail.charts || {});
    } else {
      const role = detail.role || state.page.scope_id;
      document.getElementById("heroTitle").textContent = `${t("roleHeroTitle")} · ${roleLabel(role)}`;
      document.getElementById("heroDescription").textContent = t("roleHeroDescription");
      document.getElementById("detailTitle").textContent = roleLabel(role);
      document.getElementById("detailSubtitle").textContent = detail.summary || statusLabel(detail.status || "unknown");
      document.getElementById("summaryTitle").textContent = t("detailSummary");
      document.getElementById("topologyName").textContent = `${t("roleHealth")}: ${roleLabel(role)}`;
      renderLatestReport(detail.latest_runs || []);
      renderRoleDetailSummary(detail);
      renderDetailPaths(detail.paths || []);
      renderAlerts("detailAlertsList", detail.alerts || []);
      renderRuns("detailRunsList", detail.latest_runs || []);
      document.getElementById("detailAlertsHint").textContent = roleLabel(role);
      document.getElementById("detailRunsHint").textContent = roleLabel(role);
      renderDetailCharts(detail.charts || {});
    }
  }

  function renderLatestReport(runs) {
    const latestRun = (runs || []).find((run) => run.html_path);
    const link = document.getElementById("latestReportLink");
    if (!latestRun || !latestRun.html_path) {
      link.textContent = t("reportUnavailable");
      link.removeAttribute("href");
      return;
    }
    link.textContent = t("openLatestReport");
    link.href = resultPathToHref(latestRun.html_path);
  }

  function renderKpis(overview) {
    const summary = overview.summary || {};
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

  function renderRoles(nodes) {
    const roles = ["client", "relay", "server"];
    const html = roles.map((role) => {
      const node = (nodes || []).find((item) => item.role === role);
      if (!node) {
        return `
          <div class="card">
            <h3>${escapeHtml(roleLabel(role))}</h3>
            <div class="empty">${escapeHtml(t("noData"))}</div>
          </div>
        `;
      }
      return `
        <a class="card card-link" href="${escapeHtml(roleHref(role))}">
          <div class="section-head">
            <h3>${escapeHtml(roleLabel(role))}</h3>
            <span class="status-pill ${escapeHtml(node.status)}">${escapeHtml(statusLabel(node.status))}</span>
          </div>
          <div class="metric-meta">${escapeHtml(node.summary || t("noData"))}</div>
          <div class="metric-meta">${escapeHtml(t("lastSeen"))}: ${escapeHtml(formatTimestamp(node.last_seen_at))}</div>
          <div class="metric-meta">${escapeHtml(t("push"))}: ${escapeHtml(statusLabel(node.connectivity?.push?.state || "unknown"))} | ${escapeHtml(t("pull"))}: ${escapeHtml(statusLabel(node.connectivity?.pull?.state || "unknown"))}</div>
        </a>
      `;
    }).join("");
    document.getElementById("roleGrid").innerHTML = html;
  }

  function renderPaths(paths) {
    const html = (paths || []).map((item) => `
      <a class="card card-link" href="${escapeHtml(pathHref(item.path_id))}">
        <div class="section-head">
          <h3>${escapeHtml(pathLabel(item.path_id))}</h3>
          <span class="status-pill ${escapeHtml(item.status)}">${escapeHtml(statusLabel(item.status))}</span>
        </div>
        <div class="metric-meta">${escapeHtml(metricSummary(item.latest || {}))}</div>
        <div class="metric-meta">${escapeHtml(t("alerts"))}: ${item.open_alerts || 0} | ${escapeHtml(t("anomalies"))}: ${item.open_anomalies || 0}</div>
        <div class="metric-meta">${escapeHtml(t("lastCaptured"))}: ${escapeHtml(formatTimestamp(item.last_captured_at))}</div>
      </a>
    `).join("");
    document.getElementById("pathGrid").innerHTML = html || `<div class="empty">${escapeHtml(t("noData"))}</div>`;
  }

  function renderDetailMetricSummary(seriesItems) {
    const cards = (seriesItems || []).slice(0, 8).map((series) => {
      const stats = series.stats || {};
      const compare = stats.compare || {};
      return `
        <div class="card">
          <div class="muted">${escapeHtml(detailSeriesLabel(series))}</div>
          <div class="kpi-value">${escapeHtml(formatMetricValue(series.metric_name, stats.latest))}</div>
          <div class="metric-meta">${escapeHtml(t("average"))}: ${escapeHtml(formatMetricValue(series.metric_name, stats.average))}</div>
          <div class="metric-meta">${escapeHtml(t("peak"))}: ${escapeHtml(formatMetricValue(series.metric_name, stats.peak))} | ${escapeHtml(t("p95"))}: ${escapeHtml(formatMetricValue(series.metric_name, stats.p95))}</div>
          <div class="metric-meta">${escapeHtml(t("anomalies"))}: ${escapeHtml(String(stats.anomaly_count ?? 0))} | ${escapeHtml(t("compare"))}: ${escapeHtml(compareText(series.metric_name, compare))}</div>
        </div>
      `;
    });
    document.getElementById("detailSummaryGrid").innerHTML = cards.join("") || `<div class="empty">${escapeHtml(t("noData"))}</div>`;
  }

  function renderRoleDetailSummary(detail) {
    const items = [
      { label: roleLabel(detail.role || state.page.scope_id), value: statusLabel(detail.status || "unknown"), meta: detail.summary || "" },
      { label: t("lastSeen"), value: formatTimestamp(detail.last_seen_at), meta: "" },
      { label: t("push"), value: statusLabel(detail.connectivity?.push?.state || "unknown"), meta: "" },
      { label: t("pull"), value: statusLabel(detail.connectivity?.pull?.state || "unknown"), meta: "" },
      { label: t("alerts"), value: detail.alerts?.length || 0, meta: detail.recommended_step || "" },
      { label: t("pathSummary"), value: detail.paths?.length || 0, meta: "" },
    ];
    document.getElementById("detailSummaryGrid").innerHTML = items.map((item) => `
      <div class="card">
        <div class="muted">${escapeHtml(item.label)}</div>
        <div class="kpi-value">${escapeHtml(String(item.value || t("noData")))}</div>
        <div class="metric-meta">${escapeHtml(item.meta || "")}</div>
      </div>
    `).join("");
  }

  function renderDetailPaths(paths) {
    const html = (paths || []).map((item) => `
      <a class="card card-link" href="${escapeHtml(pathHref(item.path_id))}">
        <div class="section-head">
          <h3>${escapeHtml(pathLabel(item.path_id))}</h3>
          <span class="status-pill ${escapeHtml(item.status)}">${escapeHtml(statusLabel(item.status))}</span>
        </div>
        <div class="metric-meta">${escapeHtml(metricSummary(item.latest || {}))}</div>
        <div class="metric-meta">${escapeHtml(t("alerts"))}: ${item.open_alerts || 0} | ${escapeHtml(t("anomalies"))}: ${item.open_anomalies || 0}</div>
      </a>
    `).join("");
    document.getElementById("detailPathGrid").innerHTML = html || `<div class="empty">${escapeHtml(t("noData"))}</div>`;
  }

  function renderAlerts(rootId, alerts) {
    const root = document.getElementById(rootId);
    const filtered = (alerts || []).slice(0, 8);
    if (!filtered.length) {
      root.innerHTML = `<div class="empty">${escapeHtml(t("noAlerts"))}</div>`;
      return;
    }
    root.innerHTML = filtered.map((alert) => {
      const href = publicAlertHref(alert);
      const body = `
        <div class="section-head">
          <strong>${escapeHtml(kindLabel(alert.kind))}</strong>
          <span class="status-pill ${escapeHtml(alert.severity || alert.status)}">${escapeHtml(statusLabel(alert.status || alert.severity))}</span>
        </div>
        <div class="metric-meta">${escapeHtml(alert.path_id ? pathLabel(alert.path_id) : (alert.roles || []).map(roleLabel).join(" / "))}</div>
        <p>${escapeHtml(alert.summary || "")}</p>
        <div class="metric-meta">${escapeHtml(formatTimestamp(alert.created_at))}</div>
      `;
      if (!href) {
        return `<div class="list-item">${body}</div>`;
      }
      return `<a class="list-item card-link" href="${escapeHtml(href)}">${body}</a>`;
    }).join("");
  }

  function renderRuns(rootId, runs) {
    const root = document.getElementById(rootId);
    const items = (runs || []).slice(0, 8);
    if (!items.length) {
      root.innerHTML = `<div class="empty">${escapeHtml(t("noRuns"))}</div>`;
      return;
    }
    root.innerHTML = items.map((run) => {
      const href = publicRunHref(run);
      const body = `
        <div class="section-head">
          <strong>${escapeHtml(runKindLabel(run.run_kind || ""))}</strong>
          <span class="status-pill ${escapeHtml(run.status || "")}">${escapeHtml(statusLabel(run.status || ""))}</span>
        </div>
        <div class="metric-meta">${escapeHtml(formatTimestamp(run.started_at))}</div>
        <div class="metric-meta">${escapeHtml(t("findings"))}: ${run.findings_count || 0}</div>
        <div class="metric-meta">${escapeHtml(run.summary || "")}</div>
      `;
      if (!href) {
        return `<div class="list-item">${body}</div>`;
      }
      return `<a class="list-item card-link" href="${escapeHtml(href)}">${body}</a>`;
    }).join("");
  }

  function renderDetailCharts(chartGroups) {
    const root = document.getElementById("detailCharts");
    const entries = Object.entries(chartGroups || {}).filter(([, payload]) => (payload?.series || []).length);
    if (!entries.length) {
      root.innerHTML = `<div class="panel"><div class="empty">${escapeHtml(t("noData"))}</div></div>`;
      return;
    }
    root.innerHTML = entries.map(([group]) => `
      <div class="panel">
        <h2>${escapeHtml(groupTitle(group))}</h2>
        <div id="detailChart-${escapeHtml(group)}" class="chart"></div>
      </div>
    `).join("");
    entries.forEach(([group, payload]) => renderGroupChart(`detailChart-${group}`, payload, groupTitle(group)));
  }

  function renderGroupChart(elementId, group, title) {
    const root = document.getElementById(elementId);
    if (!root) return;
    if (!charts[elementId]) {
      charts[elementId] = echarts.init(root);
    }
    const seriesItems = (group?.series || []).slice(0, 12);
    charts[elementId].setOption({
      animation: false,
      tooltip: { trigger: "axis" },
      legend: { top: 0 },
      grid: { left: 54, right: 24, top: 48, bottom: 52 },
      dataZoom: [{ type: "inside" }, { type: "slider", height: 18, bottom: 10 }],
      xAxis: { type: "time" },
      yAxis: { type: "value" },
      series: seriesItems.map((series) => ({
        name: detailSeriesLabel(series),
        type: "line",
        showSymbol: false,
        smooth: false,
        emphasis: { focus: "series" },
        data: (series.points || []).map((point) => [point.timestamp, point.value]),
        markPoint: {
          symbolSize: 24,
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

  function renderStatusMeta() {
    const status = document.getElementById("boardStatusMeta");
    const effectivePayload = state.page.kind === "overview" ? state.overview : state.detail;
    const effectiveTimestamp = effectivePayload?.generated_at || state.lastRefreshAt;
    const refreshLabel = state.refreshSec > 0 ? `${state.refreshSec}s` : t("refreshOff");
    const base = effectiveTimestamp
      ? `${t("refreshStatusOk")} · ${t("updatedAt")}: ${formatTimestamp(effectiveTimestamp)}`
      : t("refreshStatusReady");
    const suffix = `${t("timeRange")}: ${state.timeRange} · ${t("autoRefresh")}: ${refreshLabel}`;
    status.textContent = state.lastError ? `${state.lastError} · ${suffix}` : `${base} · ${suffix}`;
  }

  function flattenDetailSeries(chartGroups) {
    return Object.values(chartGroups || {}).flatMap((payload) => payload?.series || []);
  }

  function filterAlertsByPath(alerts, pathId) {
    return (alerts || []).filter((item) => item.path_id === pathId).slice(0, 8);
  }

  function filterAlertsByRole(alerts, role) {
    return (alerts || []).filter((item) => (item.roles || []).includes(role)).slice(0, 8);
  }

  function filterRunsByPath(runs, pathId) {
    return (runs || []).filter((item) => (item.path_ids || []).includes(pathId)).slice(0, 8);
  }

  function filterRunsByRole(runs, role) {
    return (runs || []).filter((item) => (item.roles || []).includes(role)).slice(0, 8);
  }

  function publicAlertHref(alert) {
    if (alert.path_id) {
      return pathHref(alert.path_id);
    }
    if ((alert.roles || [])[0]) {
      return roleHref(alert.roles[0]);
    }
    return "";
  }

  function publicRunHref(run) {
    if ((run.path_ids || [])[0]) {
      return pathHref(run.path_ids[0]);
    }
    if ((run.roles || [])[0]) {
      return roleHref(run.roles[0]);
    }
    return "";
  }

  function groupTitle(group) {
    const mapping = {
      latency: t("latencyTrend"),
      jitter: t("jitterTrend"),
      loss: t("lossTrend"),
      throughput: t("throughputTrend"),
      load: t("loadTrend"),
      system: t("systemTrend"),
    };
    return mapping[group] || group;
  }

  function detailSeriesLabel(series) {
    const metric = metricLabel(series.metric_name);
    if (series.path_id && state.page.kind === "role") {
      return `${pathLabel(series.path_id)} · ${metric}`;
    }
    return metric;
  }

  function metricSummary(latest) {
    const parts = [];
    Object.entries(latest || {}).slice(0, 4).forEach(([metricName, value]) => {
      parts.push(`${metricLabel(metricName)} ${formatMetricValue(metricName, value)}`);
    });
    return parts.join(" | ") || t("noData");
  }

  function compareText(metricName, compare) {
    const vsAverage = formatMetricDelta(metricName, compare?.vs_average);
    const vsPeak = formatMetricDelta(metricName, compare?.vs_peak);
    return `${vsAverage} / ${vsPeak}`;
  }

  function formatMetricDelta(metricName, value) {
    if (value === null || value === undefined || Number.isNaN(Number(value))) {
      return t("noData");
    }
    const numeric = Number(value);
    const sign = numeric > 0 ? "+" : "";
    return `${sign}${formatMetricValue(metricName, numeric)}`;
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

  function pathHref(pathId) {
    return `/public/path/${encodeURIComponent(pathId)}`;
  }

  function roleHref(role) {
    return `/public/role/${encodeURIComponent(role)}`;
  }

  function pathLabel(pathId) {
    return PATH_LABELS[pathId]?.[state.locale] || pathId || t("noData");
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

  function inferTimeRange(payload) {
    if (payload?.time_range && ["24h", "7d", "30d"].includes(payload.time_range)) {
      return payload.time_range;
    }
    const hours = payload?.history?.time_range_hours || 24;
    if (hours >= 24 * 30) return "30d";
    if (hours >= 24 * 7) return "7d";
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

  function loadTimeRange(payload) {
    const value = safeStorageGet(PUBLIC_TIME_RANGE_STORAGE_KEY);
    return ["24h", "7d", "30d"].includes(value || "") ? value : inferTimeRange(payload);
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
      return new Date(value).toLocaleString(state.locale === "zh-CN" ? "zh-CN" : "en-US", { hour12: false });
    } catch (error) {
      return value;
    }
  }

  function resultPathToHref(path) {
    if (!path) return "#";
    const normalized = String(path).replace(/\\/g, "/");
    if (normalized.startsWith("results/")) {
      return `/results/${normalized.slice("results/".length)}`;
    }
    if (normalized.startsWith("/results/")) {
      return normalized;
    }
    return `/results/${normalized}`;
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/\"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function t(key) {
    return translations[state.locale][key] || key;
  }
})();
