import React, { useState } from 'react';
import ReactDOM from 'react-dom/client';
import { ArrowUpRight, Globe2, Shield } from 'lucide-react';
import { BrowserRouter, Link, Route, Routes, useParams } from 'react-router-dom';
import '../../index.css';
import { EmptyState, FilterField, KeyValueGrid, PageHeader, SmallButton, StatCard, Surface, SurfaceBody, SurfaceTitle, ToneBadge, fieldControlClass } from '../../components/PanelUi';
import { TimeSeriesChart } from '../../components/TimeSeriesChart';
import { apiGet } from '../../lib/api';
import { alertHeadline, buildLabel, formatDateTime, formatMetric, formatNumber, formatRelative, staleSummary, statusLabel } from '../../lib/format';
import { useSnapshotResource } from '../../lib/hooks';
import type { MetricSeries, PathSummary, PublicDashboardSnapshot, PublicPathDetail, PublicPathHealthPayload, PublicRoleDetail, PublicTimeseriesPayload } from '../../lib/types';

const initialState = window.__INITIAL_STATE__ as PublicDashboardSnapshot | PublicPathDetail | PublicRoleDetail | undefined;

function PublicLayout() {
  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_right,_rgba(20,184,166,0.12),_transparent_24%),linear-gradient(180deg,#f8fafc_0%,#ecfeff_100%)] text-slate-900">
      <div className="mx-auto max-w-7xl px-4 py-6 lg:px-8">
        <header className="rounded-2xl border border-white/60 bg-white/80 px-5 py-5 shadow-sm shadow-slate-200/70 backdrop-blur">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <div className="text-xs uppercase tracking-[0.24em] text-slate-500">mc-netprobe</div>
              <div className="mt-1 text-3xl font-semibold tracking-tight text-slate-950">Public Panel</div>
              <div className="mt-2 text-sm text-slate-600">Read-only health, path, and role visibility from the current backend privacy contract.</div>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <div data-testid="build-label">
                <ToneBadge value="info" label={buildLabel((initialState as PublicDashboardSnapshot | undefined)?.build)} />
              </div>
              <Link className="inline-flex min-h-11 items-center gap-2 rounded-xl bg-slate-950 px-4 py-2 text-sm font-medium text-white" to="/">
                <Globe2 className="h-4 w-4" />
                Dashboard
              </Link>
              <a className="inline-flex min-h-11 items-center gap-2 rounded-xl bg-white px-4 py-2 text-sm font-medium text-slate-700 ring-1 ring-slate-200" href="/login">
                <Shield className="h-4 w-4" />
                Admin Login
              </a>
            </div>
          </div>
        </header>
        <main className="py-6">
          <Routes>
            <Route path="/" element={<PublicOverviewPage />} />
            <Route path="/public/path/:pathId" element={<PublicPathPage />} />
            <Route path="/public/role/:role" element={<PublicRolePage />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}

function SnapshotMeta({ generatedAt, refreshing, onRefresh }: { generatedAt?: string | null; refreshing?: boolean; onRefresh?: () => void }) {
  return (
    <div className="flex flex-wrap items-center gap-2 text-sm text-slate-500">
      <span>{staleSummary(generatedAt)}</span>
      {onRefresh ? (
        <SmallButton onClick={onRefresh} variant="secondary" disabled={refreshing}>
          {refreshing ? 'Refreshing' : 'Refresh'}
        </SmallButton>
      ) : null}
    </div>
  );
}

function PublicOverviewPage() {
  const seed = (initialState as PublicDashboardSnapshot | undefined) ?? {
    topology_id: 0,
    topology_name: 'mc-netprobe-monitor',
    generated_at: null,
    summary: {
      total_nodes: 0,
      online_nodes: 0,
      degraded_nodes: 0,
      offline_nodes: 0,
      active_alerts: 0,
      online_rate_pct: 0,
      abnormal_nodes: 0,
    },
    nodes: [],
    latest_runs: [],
    alerts: [],
    paths: [],
    history: { trend_groups: {} },
  };
  const dashboard = useSnapshotResource(() => apiGet<PublicDashboardSnapshot>('/api/v1/public-dashboard'), seed, [], { pollMs: 15000 });
  const payload = dashboard.data ?? seed;
  const trendEntries = Object.entries(payload.history.trend_groups ?? {});
  const visibleTrendEntries = trendEntries.filter(([, group]) => (group.series ?? []).length > 0).slice(0, 4);
  const emptyTrendCount = trendEntries.length - visibleTrendEntries.length;

  return (
    <div className="space-y-6">
      <PageHeader
        title={payload.topology_name}
        description="Public-safe topology summary, path health, alerts, and exposed metric groups."
        actions={<SnapshotMeta generatedAt={payload.generated_at} refreshing={dashboard.loading} onRefresh={() => { void dashboard.refresh(); }} />}
      />
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Total Nodes" value={formatNumber(payload.summary.total_nodes, 0)} hint={`${formatNumber(payload.summary.online_nodes, 0)} online`} />
        <StatCard label="Online Rate" value={`${formatNumber(payload.summary.online_rate_pct)}%`} hint={`${formatNumber(payload.summary.abnormal_nodes, 0)} abnormal`} />
        <StatCard label="Active Alerts" value={formatNumber(payload.summary.active_alerts, 0)} hint={`${formatNumber(payload.summary.degraded_nodes, 0)} degraded`} />
        <StatCard label="Privacy Mode" value={payload.privacy_mode || 'role-and-path-only'} hint={payload.time_range || '24h'} />
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.2fr_1fr]">
        <Surface>
          <SurfaceBody className="space-y-4">
            <SurfaceTitle title="Path Health" meta={`${payload.paths.length} public paths`} />
            {!payload.paths.length ? <EmptyState title="No public paths yet" /> : null}
            <div className="space-y-3">
              {payload.paths.map((path: PathSummary) => (
                <div key={path.path_id || path.path_label} className="min-w-0 rounded-2xl border border-slate-200 bg-white px-4 py-3">
                  <div className="flex min-w-0 items-center justify-between gap-3">
                    <div className="min-w-0">
                      <div className="break-words font-medium text-slate-900">{path.path_id || path.path_label}</div>
                      <div className="mt-1 text-sm text-slate-500">Last capture {formatRelative(path.last_captured_at)}</div>
                    </div>
                    <ToneBadge value={path.status} label={statusLabel(path.status)} />
                  </div>
                  <div className="mt-3 grid gap-2 text-sm text-slate-700 sm:grid-cols-2">
                    {Object.entries(path.latest).slice(0, 4).map(([metric, value]) => (
                      <div key={metric} className="flex min-w-0 items-center justify-between gap-3 rounded-xl bg-slate-50 px-3 py-2">
                        <span className="min-w-0 break-words">{metric}</span>
                        <span className="font-medium">{formatMetric(value, metric)}</span>
                      </div>
                    ))}
                  </div>
                  <div className="mt-3">
                    <Link className="inline-flex min-h-11 items-center gap-1 text-sm font-medium text-sky-700 underline decoration-sky-300 underline-offset-4" to={`/public/path/${path.path_id || path.path_label}`}>
                      <span>Open path</span>
                      <ArrowUpRight className="h-3.5 w-3.5" />
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          </SurfaceBody>
        </Surface>

        <Surface>
          <SurfaceBody className="space-y-4">
            <SurfaceTitle title="Alerts and Runs" />
            <div className="space-y-3">
              {!payload.alerts.length ? <EmptyState title="No public alerts" /> : null}
              {payload.alerts.slice(0, 5).map((alert) => (
                <div key={alert.id} className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                  <div className="flex items-center gap-2">
                    <ToneBadge value={alert.severity} label={statusLabel(alert.status)} />
                    <div className="font-medium text-slate-900">{alertHeadline(alert)}</div>
                  </div>
                  <div className="mt-2 text-sm text-slate-500">{formatDateTime(alert.created_at)}</div>
                </div>
              ))}
            </div>
            <div className="space-y-3 pt-2">
              {!payload.latest_runs.length ? <EmptyState title="No public runs" /> : null}
              {payload.latest_runs.slice(0, 5).map((run) => (
                <div key={run.run_id} className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <div className="font-medium text-slate-900">{run.run_kind}</div>
                      <div className="mt-1 text-sm text-slate-500">{formatDateTime(run.started_at)}</div>
                    </div>
                    <ToneBadge value={run.status} label={statusLabel(run.status)} />
                  </div>
                </div>
              ))}
            </div>
          </SurfaceBody>
        </Surface>
      </div>

      {visibleTrendEntries.length ? (
        <div className="grid gap-6 xl:grid-cols-2">
          {visibleTrendEntries.map(([groupName, group]) => (
            <Surface key={groupName}>
              <SurfaceBody className="space-y-4">
                <SurfaceTitle title={groupName} meta={`${(group.series ?? []).length} series`} />
                <TimeSeriesChart title={groupName} series={(group.series ?? []) as MetricSeries[]} />
              </SurfaceBody>
            </Surface>
          ))}
        </div>
      ) : trendEntries.length ? (
        <Surface>
          <SurfaceBody>
            <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 px-4 py-4 text-sm text-slate-600">
              No public metric series are available for the current window across {trendEntries.length} exposed groups.
            </div>
          </SurfaceBody>
        </Surface>
      ) : null}
      {visibleTrendEntries.length && emptyTrendCount > 0 ? (
        <div className="text-sm text-slate-500">{emptyTrendCount} public metric groups have no series in the current window.</div>
      ) : null}
    </div>
  );
}

function PublicPathPage() {
  const { pathId = '' } = useParams();
  const seed = (initialState as PublicPathDetail | undefined) ?? {
    path_id: pathId,
    path_label: pathId,
    status: 'unknown',
    latest: {},
    averages: {},
    open_alerts: 0,
    open_anomalies: 0,
    alerts: [],
    latest_runs: [],
    metric_groups: [],
  };
  const [timeRange, setTimeRange] = useState('24h');
  const [metricGroup, setMetricGroup] = useState(seed.metric_groups[0] || 'latency');
  const detail = useSnapshotResource(
    () => apiGet<PublicPathHealthPayload>(`/api/v1/public/path-health?time_range=${encodeURIComponent(timeRange)}&path_id=${encodeURIComponent(pathId)}`),
    null,
    [pathId, timeRange],
    { pollMs: 15000 },
  );
  const series = useSnapshotResource(
    () => apiGet<PublicTimeseriesPayload>(`/api/v1/public/timeseries?scope_kind=path&scope_id=${encodeURIComponent(pathId)}&metric_group=${encodeURIComponent(metricGroup)}&time_range=${encodeURIComponent(timeRange)}`),
    null,
    [metricGroup, pathId, timeRange],
    { enabled: Boolean(metricGroup) },
  );

  const path = detail.data?.path ?? seed;

  return (
    <div className="space-y-6">
      <PageHeader
        title={path.path_id}
        description="Path-specific health, linked alerts and runs, and the public metric groups allowed by the backend privacy contract."
        actions={<SnapshotMeta generatedAt={detail.data?.generated_at || path.generated_at} refreshing={detail.loading || series.loading} onRefresh={() => { void detail.refresh(); void series.refresh(); }} />}
      />
      <Surface>
        <SurfaceBody className="space-y-4">
          <div className="grid gap-4 md:grid-cols-4">
            <StatCard label="Status" value={<ToneBadge value={path.status} label={statusLabel(path.status)} />} />
            <StatCard label="Open Alerts" value={path.open_alerts} />
            <StatCard label="Open Anomalies" value={path.open_anomalies} />
            <StatCard label="Last Capture" value={path.last_captured_at ? formatRelative(path.last_captured_at) : 'N/A'} />
          </div>
          <KeyValueGrid
            items={[
              { label: 'Roles', value: (path.roles ?? []).join(' · ') || 'N/A' },
              { label: 'Family', value: path.family || 'N/A' },
              { label: 'Time Range', value: detail.data?.time_range || path.time_range || '24h' },
              { label: 'Privacy', value: detail.data?.privacy_mode || path.privacy_mode || 'role-and-path-only' },
            ]}
          />
        </SurfaceBody>
      </Surface>

      <Surface>
        <SurfaceBody className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <FilterField label="Time range">
              <select className={fieldControlClass} value={timeRange} onChange={(event) => setTimeRange(event.target.value)}>
                {['1h', '6h', '24h', '7d', '30d'].map((value) => <option key={value} value={value}>{value}</option>)}
              </select>
            </FilterField>
            <FilterField label="Metric group">
              <select className={fieldControlClass} value={metricGroup} onChange={(event) => setMetricGroup(event.target.value)}>
                {(path.metric_groups ?? ['latency']).map((value) => <option key={value} value={value}>{value}</option>)}
              </select>
            </FilterField>
          </div>
          {series.data?.series.length ? (
            <TimeSeriesChart title={metricGroup} series={series.data.series} />
          ) : (
            <EmptyState title="No public path series" description="This path has not emitted data for the selected metric group and time range." />
          )}
        </SurfaceBody>
      </Surface>

      <div className="grid gap-6 xl:grid-cols-[1fr_1fr]">
        <Surface>
          <SurfaceBody className="space-y-4">
            <SurfaceTitle title="Alerts" meta={`${path.alerts.length} items`} />
            {!path.alerts.length ? <EmptyState title="No alerts on this path" /> : null}
            {path.alerts.map((alert) => (
              <div key={alert.id} className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                <div className="flex items-center gap-2">
                  <ToneBadge value={alert.severity} label={statusLabel(alert.status)} />
                  <div className="font-medium text-slate-900">{alertHeadline(alert)}</div>
                </div>
                <div className="mt-2 text-sm text-slate-500">{formatDateTime(alert.created_at)}</div>
              </div>
            ))}
          </SurfaceBody>
        </Surface>

        <Surface>
          <SurfaceBody className="space-y-4">
            <SurfaceTitle title="Latest Runs" meta={`${path.latest_runs.length} items`} />
            {!path.latest_runs.length ? <EmptyState title="No runs touching this path" /> : null}
            {path.latest_runs.map((run) => (
              <div key={run.run_id} className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="font-medium text-slate-900">{run.run_kind}</div>
                    <div className="mt-1 text-sm text-slate-500">{formatDateTime(run.started_at)}</div>
                  </div>
                  <ToneBadge value={run.status} label={statusLabel(run.status)} />
                </div>
              </div>
            ))}
          </SurfaceBody>
        </Surface>
      </div>
    </div>
  );
}

function PublicRolePage() {
  const { role = '' } = useParams();
  const seed = (initialState as PublicRoleDetail | undefined) ?? {
    role,
    status: 'unknown',
    enabled: false,
    paired: false,
    metric_groups: [],
    paths: [],
    alerts: [],
    latest_runs: [],
  };
  const [timeRange, setTimeRange] = useState('24h');
  const [metricGroup, setMetricGroup] = useState(seed.metric_groups[0] || 'system');
  const series = useSnapshotResource(
    () => apiGet<PublicTimeseriesPayload>(`/api/v1/public/timeseries?scope_kind=role&scope_id=${encodeURIComponent(role)}&metric_group=${encodeURIComponent(metricGroup)}&time_range=${encodeURIComponent(timeRange)}`),
    null,
    [metricGroup, role, timeRange],
    { enabled: Boolean(metricGroup) },
  );

  return (
    <div className="space-y-6">
      <PageHeader
        title={`${role} role`}
        description="Role-scoped health, related paths, alerts, runs, and public metric groups available for this role."
        actions={<SnapshotMeta generatedAt={seed.generated_at || series.data?.generated_at} refreshing={series.loading} onRefresh={() => { void series.refresh(); }} />}
      />
      <Surface>
        <SurfaceBody className="space-y-4">
          <div className="grid gap-4 md:grid-cols-4">
            <StatCard label="Status" value={<ToneBadge value={seed.status} label={statusLabel(seed.status)} />} />
            <StatCard label="Enabled" value={seed.enabled ? 'yes' : 'no'} />
            <StatCard label="Paired" value={seed.paired ? 'yes' : 'no'} />
            <StatCard label="Last Seen" value={seed.last_seen_at ? formatRelative(seed.last_seen_at) : 'N/A'} />
          </div>
          <KeyValueGrid
            items={[
              { label: 'Summary', value: seed.summary || 'N/A' },
              { label: 'Recommended Step', value: seed.recommended_step || 'N/A' },
              { label: 'Privacy', value: seed.privacy_mode || 'role-and-path-only' },
              { label: 'Time Range', value: seed.time_range || '24h' },
            ]}
          />
          <div className="rounded-2xl border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-900">
            The role summary reflects the latest public snapshot loaded with this page. Use the controls below to refresh the visible metric window.
          </div>
        </SurfaceBody>
      </Surface>

      <Surface>
        <SurfaceBody className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <FilterField label="Time range">
              <select className={fieldControlClass} value={timeRange} onChange={(event) => setTimeRange(event.target.value)}>
                {['1h', '6h', '24h', '7d', '30d'].map((value) => <option key={value} value={value}>{value}</option>)}
              </select>
            </FilterField>
            <FilterField label="Metric group">
              <select className={fieldControlClass} value={metricGroup} onChange={(event) => setMetricGroup(event.target.value)}>
                {(seed.metric_groups ?? ['system']).map((value) => <option key={value} value={value}>{value}</option>)}
              </select>
            </FilterField>
          </div>
          {series.data?.series.length ? (
            <TimeSeriesChart title={metricGroup} series={series.data.series} />
          ) : (
            <EmptyState title="No role series" description="This role has not emitted data for the selected public metric group." />
          )}
        </SurfaceBody>
      </Surface>

      <div className="grid gap-6 xl:grid-cols-[1fr_1fr]">
        <Surface>
          <SurfaceBody className="space-y-4">
            <SurfaceTitle title="Paths" meta={`${seed.paths.length} paths`} />
            {!seed.paths.length ? <EmptyState title="No paths for this role" /> : null}
            {seed.paths.map((path) => (
              <div key={path.path_id || path.path_label} className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="font-medium text-slate-900">{path.path_id || path.path_label}</div>
                    <div className="mt-1 text-sm text-slate-500">Open alerts {path.open_alerts}</div>
                  </div>
                  <ToneBadge value={path.status} label={statusLabel(path.status)} />
                </div>
                <div className="mt-2">
                  <Link className="inline-flex min-h-11 items-center gap-1 text-sm font-medium text-sky-700 underline decoration-sky-300 underline-offset-4" to={`/public/path/${path.path_id || path.path_label}`}>
                    <span>Open path</span>
                    <ArrowUpRight className="h-3.5 w-3.5" />
                  </Link>
                </div>
              </div>
            ))}
          </SurfaceBody>
        </Surface>

        <Surface>
          <SurfaceBody className="space-y-4">
            <SurfaceTitle title="Alerts and Runs" meta={`${seed.alerts.length + seed.latest_runs.length} items`} />
            <div className="space-y-3">
              {!seed.alerts.length ? <EmptyState title="No role alerts" /> : null}
              {seed.alerts.map((alert) => (
                <div key={alert.id} className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                  <div className="flex items-center gap-2">
                    <ToneBadge value={alert.severity} label={statusLabel(alert.status)} />
                    <div className="font-medium text-slate-900">{alertHeadline(alert)}</div>
                  </div>
                </div>
              ))}
              {!seed.latest_runs.length ? <EmptyState title="No role runs" /> : null}
              {seed.latest_runs.map((run) => (
                <div key={run.run_id} className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <div className="font-medium text-slate-900">{run.run_kind}</div>
                      <div className="mt-1 text-sm text-slate-500">{formatDateTime(run.started_at)}</div>
                    </div>
                    <ToneBadge value={run.status} label={statusLabel(run.status)} />
                  </div>
                </div>
              ))}
            </div>
          </SurfaceBody>
        </Surface>
      </div>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="*" element={<PublicLayout />} />
      </Routes>
    </BrowserRouter>
  </React.StrictMode>,
);
