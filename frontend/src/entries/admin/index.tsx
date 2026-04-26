import React, { startTransition, useEffect, useMemo, useState } from 'react';
import ReactDOM from 'react-dom/client';
import {
  AlertTriangle,
  ArrowUpRight,
  Bell,
  Calendar,
  LayoutDashboard,
  Menu,
  Play,
  Radar,
  RefreshCw,
  Server,
  Settings,
  Workflow,
  Wrench,
  X,
} from 'lucide-react';
import {
  BrowserRouter,
  Link,
  NavLink,
  Outlet,
  Route,
  Routes,
  useOutletContext,
  useSearchParams,
} from 'react-router-dom';
import '../../index.css';
import { ErrorBanner, EmptyState, FilterField, InlineCode, JsonBlock, KeyValueGrid, LoadingState, PageHeader, SmallButton, StatCard, Surface, SurfaceBody, SurfaceTitle, ToneBadge, fieldControlClass } from '../../components/PanelUi';
import { TimeSeriesChart } from '../../components/TimeSeriesChart';
import { apiErrorDetail, apiGet, apiPost, conflictDetail } from '../../lib/api';
import { staleSummary, alertHeadline, buildLabel, formatDateTime, formatMetric, formatNumber, formatRelative, metricUnit, resolveNodeTitle, statusLabel, suggestedActionHref, suggestedActionLabel } from '../../lib/format';
import { useJsonEditor, useSnapshotResource } from '../../lib/hooks';
import { cn } from '../../lib/utils';
import type {
  ActionCreateResponse,
  AdminOverviewPayload,
  AdminRuntimePayload,
  AlertMutationResponse,
  AlertRecord,
  ConflictDetail,
  ControlActionRecord,
  DashboardSnapshot,
  FilterOptionsPayload,
  MetricSeriesPayload,
  NodeRecord,
  PairCodeResponse,
  PathSummary,
  ReleaseValidationSnapshot,
  RunRecord,
  RunStartResponse,
  ScheduleRecord,
  SuggestedAction,
} from '../../lib/types';

const initialDashboard = (window.__INITIAL_STATE__ as DashboardSnapshot | undefined) ?? {
  topology_id: 0,
  build: undefined,
  generated_at: null,
  settings: {
    topology_name: 'mc-netprobe-monitor',
    services: {},
    thresholds: {},
    scenarios: {},
  },
  schedules: [],
  nodes: [],
  latest_runs: [],
  alerts: [],
  history: {},
};

const navigation = [
  { href: '/admin', label: 'Overview', icon: LayoutDashboard },
  { href: '/admin/nodes', label: 'Nodes', icon: Server },
  { href: '/admin/paths', label: 'Paths', icon: Radar },
  { href: '/admin/runs', label: 'Runs', icon: Workflow },
  { href: '/admin/alerts', label: 'Alerts', icon: Bell },
  { href: '/admin/actions', label: 'Actions', icon: Wrench },
  { href: '/admin/schedules', label: 'Schedules', icon: Calendar },
  { href: '/admin/settings', label: 'Settings', icon: Settings },
];

interface AdminShellContext {
  seed: DashboardSnapshot;
}

function useShell() {
  return useOutletContext<AdminShellContext>();
}

function AdminLayout() {
  const topBadge = buildLabel(initialDashboard.build);
  const [drawerOpen, setDrawerOpen] = useState(false);

  useEffect(() => {
    if (!drawerOpen) {
      return;
    }
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setDrawerOpen(false);
      }
    };
    window.addEventListener('keydown', onKeyDown);
    const originalOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      window.removeEventListener('keydown', onKeyDown);
      document.body.style.overflow = originalOverflow;
    };
  }, [drawerOpen]);

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,_rgba(14,165,233,0.08),_transparent_28%),linear-gradient(180deg,#f8fafc_0%,#eef2ff_100%)] text-slate-900">
      <header className="sticky top-0 z-40 border-b border-slate-200 bg-white/90 px-4 py-3 backdrop-blur lg:hidden">
        <div className="flex min-w-0 items-center justify-between gap-3">
          <div className="min-w-0">
            <div className="text-xs uppercase tracking-[0.24em] text-slate-500">mc-netprobe</div>
            <div className="truncate text-xl font-semibold tracking-tight text-slate-950">Admin Panel</div>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <div data-testid="mobile-build-label">
              <ToneBadge value="info" label={topBadge} />
            </div>
            <button
              type="button"
              aria-controls="admin-mobile-nav"
              aria-expanded={drawerOpen}
              onClick={() => setDrawerOpen(true)}
              className="inline-flex min-h-11 items-center justify-center rounded-xl bg-slate-950 px-3 text-sm font-medium text-white"
            >
              <Menu className="mr-2 h-4 w-4" />
              Menu
            </button>
          </div>
        </div>
      </header>

      {drawerOpen ? (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button
            type="button"
            aria-label="Close navigation menu"
            className="absolute inset-0 bg-slate-950/40"
            onClick={() => setDrawerOpen(false)}
          />
          <aside id="admin-mobile-nav" className="absolute inset-y-0 left-0 flex w-[min(22rem,calc(100vw-2rem))] flex-col overflow-y-auto bg-white p-4 shadow-2xl">
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="text-xs uppercase tracking-[0.24em] text-slate-500">mc-netprobe</div>
                <div className="mt-1 text-2xl font-semibold tracking-tight text-slate-950">Admin Panel</div>
              </div>
              <button
                type="button"
                aria-label="Close navigation menu"
                onClick={() => setDrawerOpen(false)}
                className="inline-flex min-h-11 items-center justify-center rounded-xl px-3 text-slate-700 ring-1 ring-slate-200"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <AdminNavigation onNavigate={() => setDrawerOpen(false)} />
            <TopologySummary />
            <form className="mt-4" method="post" action="/logout">
              <SmallButton type="submit" variant="secondary">Sign out</SmallButton>
            </form>
          </aside>
        </div>
      ) : null}

      <div className="mx-auto flex min-h-screen max-w-[1600px] lg:flex-row">
        <aside className="hidden border-r border-slate-200 bg-white/80 px-4 py-5 backdrop-blur lg:block lg:min-h-screen lg:w-72">
          <div>
            <div className="text-xs uppercase tracking-[0.24em] text-slate-500">mc-netprobe</div>
            <div className="mt-1 text-2xl font-semibold tracking-tight text-slate-950">Admin Panel</div>
          </div>
          <div className="mt-3 flex items-center gap-2">
            <div data-testid="build-label">
              <ToneBadge value="info" label={topBadge} />
            </div>
            <form method="post" action="/logout">
              <SmallButton type="submit" variant="secondary">Sign out</SmallButton>
            </form>
          </div>
          <AdminNavigation />
          <TopologySummary />
        </aside>
        <main className="min-w-0 flex-1 px-4 py-5 lg:px-8 lg:py-6">
          <Outlet context={{ seed: initialDashboard }} />
        </main>
      </div>
    </div>
  );
}

function AdminNavigation({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <nav className="mt-6 grid gap-1">
      {navigation.map((item) => (
        <NavLink
          key={item.href}
          to={item.href}
          end={item.href === '/admin'}
          onClick={onNavigate}
          className={({ isActive }) =>
            cn(
              'flex min-h-11 items-center gap-3 rounded-xl px-4 py-3 text-sm font-medium transition',
              isActive ? 'bg-slate-950 text-white shadow-[0_6px_16px_rgba(15,23,42,0.18)]' : 'text-slate-700 hover:bg-slate-100',
            )
          }
        >
          <item.icon className="h-4 w-4" />
          <span>{item.label}</span>
        </NavLink>
      ))}
    </nav>
  );
}

function TopologySummary() {
  return (
    <div className="mt-8 rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
      <div className="font-medium text-slate-900">{initialDashboard.settings.topology_name}</div>
      <div className="mt-2">Topology ID: <InlineCode value={String(initialDashboard.topology_id)} /></div>
      <div className="mt-2">Boot snapshot: {staleSummary(initialDashboard.generated_at)}</div>
    </div>
  );
}

function SnapshotMeta({
  generatedAt,
  refreshing,
  onRefresh,
}: {
  generatedAt?: string | null;
  refreshing?: boolean;
  onRefresh?: () => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2 text-sm text-slate-500">
      <span>{staleSummary(generatedAt)}</span>
      {onRefresh ? (
        <SmallButton onClick={onRefresh} variant="secondary" disabled={refreshing}>
          <RefreshCw className={cn('mr-2 h-4 w-4', refreshing ? 'animate-spin' : '')} />
          Refresh
        </SmallButton>
      ) : null}
    </div>
  );
}

function SuggestedActionLink({ action }: { action?: SuggestedAction | null }) {
  const href = suggestedActionHref(action);
  if (!action || !href) {
    return null;
  }
  return (
    <Link className="inline-flex min-h-11 items-center gap-1 text-sm font-medium text-sky-700 underline decoration-sky-300 underline-offset-4" to={href}>
      <span>{suggestedActionLabel(action)}</span>
      <ArrowUpRight className="h-3.5 w-3.5" />
    </Link>
  );
}

function DashboardPage() {
  const { seed } = useShell();
  const dashboard = useSnapshotResource(() => apiGet<DashboardSnapshot>('/api/v1/dashboard'), seed, [], { pollMs: 30000 });
  const runtime = useSnapshotResource(() => apiGet<AdminRuntimePayload>('/api/v1/admin/runtime'), null, [], { pollMs: 20000 });
  const overview = useSnapshotResource(() => apiGet<AdminOverviewPayload>('/api/v1/admin/overview?time_range=24h'), null, [], { pollMs: 15000 });
  const releaseValidation = useSnapshotResource(() => apiGet<ReleaseValidationSnapshot>('/api/v1/admin/release-validation'), null, [], { pollMs: 8000 });
  const [panelActionMessage, setPanelActionMessage] = useState<string | null>(null);
  const [panelActionError, setPanelActionError] = useState<ConflictDetail | string | null>(null);

  const submitPanelAction = async (action: string, confirmationToken?: string | null) => {
    try {
      const response = await apiPost<ActionCreateResponse>('/api/v1/admin/panel/actions', {
        action,
        actor: 'admin-webui',
        confirmation_token: confirmationToken ?? undefined,
      });
      if (response.confirmation_required && response.confirmation_token) {
        if (window.confirm(`Confirm panel action: ${action}?`)) {
          await submitPanelAction(action, response.confirmation_token);
        }
        return;
      }
      setPanelActionError(null);
      setPanelActionMessage(response.action ? `Queued panel action #${response.action.id}: ${response.action.action}` : `${action} submitted`);
      void runtime.refresh();
    } catch (error) {
      setPanelActionMessage(null);
      setPanelActionError(conflictDetail(error) || apiErrorDetail(error));
    }
  };

  const startReleaseValidation = async () => {
    try {
      await apiPost<ReleaseValidationSnapshot>('/api/v1/admin/release-validation');
      void releaseValidation.refresh();
    } catch (error) {
      setPanelActionError(apiErrorDetail(error));
    }
  };

  const snapshot = dashboard.data ?? seed;
  const kpis = overview.data?.kpis;
  const attentionItems = runtime.data?.attention.items ?? [];
  const release = releaseValidation.data;
  const panelRuntime = runtime.data?.panel.runtime;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Overview"
        description="Control-plane runtime, operational focus, release validation, and the newest alerts and runs from the existing backend contract."
        actions={<SnapshotMeta generatedAt={runtime.data?.generated_at || snapshot.generated_at} refreshing={dashboard.loading || runtime.loading} onRefresh={() => { void dashboard.refresh(); void runtime.refresh(); void overview.refresh(); }} />}
      />
      {typeof panelActionError === 'string' ? <ErrorBanner message={panelActionError} /> : null}
      {panelActionError && typeof panelActionError === 'object' ? (
        <ErrorBanner message={panelActionError.message || 'Panel action conflicted with an active request'} action={panelActionError.suggested_action} />
      ) : null}
      {panelActionMessage ? (
        <div className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">{panelActionMessage}</div>
      ) : null}

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Total Nodes" value={formatNumber(kpis?.total_nodes ?? snapshot.nodes.length, 0)} hint={`${formatNumber(overview.data?.status_distribution.online ?? 0, 0)} online`} />
        <StatCard label="Online Rate" value={`${formatNumber(kpis?.online_rate_pct ?? 0)}%`} hint={kpis?.last_full_run_status ? `Last full run: ${statusLabel(kpis.last_full_run_status)}` : 'No full run yet'} />
        <StatCard label="Active Alerts" value={formatNumber(kpis?.active_alerts ?? snapshot.alerts.length, 0)} hint={`${formatNumber(kpis?.degraded_nodes ?? 0, 0)} degraded · ${formatNumber(kpis?.offline_nodes ?? 0, 0)} offline`} />
        <StatCard label="Health Score" value={formatNumber(kpis?.health_score ?? 0, 0)} hint={panelRuntime?.details?.operator_summary as string | undefined} />
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.2fr_1fr]">
        <Surface>
          <SurfaceBody className="space-y-4">
            <SurfaceTitle title="Panel Runtime" meta={panelRuntime ? formatDateTime(panelRuntime.checked_at) : undefined} />
            {!runtime.data && runtime.loading ? <LoadingState label="Refreshing panel runtime" /> : null}
            {runtime.data ? (
              <>
                <KeyValueGrid
                  items={[
                    { label: 'State', value: <ToneBadge value={panelRuntime?.state} label={statusLabel(panelRuntime?.state)} /> },
                    { label: 'Deployment', value: String(panelRuntime?.details?.deployment_mode || 'unknown') },
                    { label: 'Control Mode', value: String(panelRuntime?.details?.control_mode || 'unknown') },
                    { label: 'Build Ref', value: <InlineCode value={String(panelRuntime?.details?.panel_build_ref || 'unknown')} /> },
                    { label: 'Scheduler', value: String(panelRuntime?.details?.scheduler_paused ? 'paused' : 'running') },
                    { label: 'PID', value: String(panelRuntime?.details?.pid || 'N/A') },
                  ]}
                />
                <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
                  {['status', 'sync_runtime', 'tail_log', panelRuntime?.details?.scheduler_paused ? 'resume_scheduler' : 'pause_scheduler', 'restart', 'stop']
                    .filter(Boolean)
                    .map((action) => (
                      <SmallButton key={String(action)} onClick={() => void submitPanelAction(String(action))} variant={action === 'stop' ? 'danger' : 'secondary'}>
                        {String(action)}
                      </SmallButton>
                    ))}
                </div>
                {panelRuntime?.details?.operator_recommended_step ? (
                  <div className="rounded-2xl bg-slate-50 px-4 py-3 text-sm text-slate-700">
                    {String(panelRuntime.details.operator_recommended_step)}
                  </div>
                ) : null}
              </>
            ) : null}
          </SurfaceBody>
        </Surface>

        <Surface>
          <SurfaceBody className="space-y-4">
            <SurfaceTitle title="Operations Focus" meta={`${attentionItems.length} active items`} />
            {runtime.loading && !runtime.data ? <LoadingState label="Collecting attention items" /> : null}
            {!attentionItems.length ? <EmptyState title="No attention items" description="Panel and nodes are not reporting actionable warnings right now." /> : null}
            <div className="space-y-3">
              {attentionItems.map((item, index) => (
                <div key={`${item.kind}-${index}`} className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="flex items-center gap-2">
                        <ToneBadge value={item.severity} label={statusLabel(item.severity)} />
                        <div className="font-medium text-slate-900">{item.title}</div>
                      </div>
                      <div className="mt-2 text-sm text-slate-700">{item.summary}</div>
                      {item.recommended_step ? <div className="mt-2 text-sm text-slate-500">{item.recommended_step}</div> : null}
                    </div>
                    <SuggestedActionLink action={item.suggested_action} />
                  </div>
                </div>
              ))}
            </div>
          </SurfaceBody>
        </Surface>
      </div>

      <div className="grid gap-6 xl:grid-cols-[1fr_1fr]">
        <Surface>
          <SurfaceBody className="space-y-4">
            <SurfaceTitle
              title="Release Validation"
              meta={
                <div className="flex items-center gap-2">
                  {release ? <ToneBadge value={release.running ? 'warning' : 'info'} label={release.running ? 'running' : 'snapshot'} /> : null}
                  <SmallButton onClick={() => void startReleaseValidation()} variant="secondary">
                    Run validation
                  </SmallButton>
                </div>
              }
            />
            {!release ? <LoadingState label="Loading validation snapshot" /> : null}
            {release ? (
              <>
                <div className="grid gap-3 md:grid-cols-4">
                  <StatCard label="Pass" value={release.summary.pass} />
                  <StatCard label="Warn" value={release.summary.warn} />
                  <StatCard label="Fail" value={release.summary.fail} />
                  <StatCard label="Skip" value={release.summary.skip} />
                </div>
                <div className="space-y-3">
                  {[release.panel, ...release.nodes.slice(0, 5)].map((item) => (
                    <div key={`${item.target_kind}-${item.target_name}`} className="rounded-2xl border border-slate-200 px-4 py-4">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <div className="flex items-center gap-2">
                            <ToneBadge value={item.status} label={statusLabel(item.status)} />
                            <div className="font-medium text-slate-900">{item.target_name}</div>
                            {item.code ? <InlineCode value={item.code} /> : null}
                          </div>
                          <div className="mt-2 text-sm text-slate-700">{item.summary}</div>
                          {item.recommended_step ? <div className="mt-2 text-sm text-slate-500">{item.recommended_step}</div> : null}
                        </div>
                        <SuggestedActionLink action={item.suggested_action} />
                      </div>
                    </div>
                  ))}
                </div>
              </>
            ) : null}
          </SurfaceBody>
        </Surface>

        <Surface>
          <SurfaceBody className="space-y-4">
            <SurfaceTitle title="Recent Alerts and Runs" meta={staleSummary(snapshot.generated_at)} />
            <div className="grid gap-4">
              <div className="space-y-3">
                <div className="text-sm font-medium text-slate-900">Alerts</div>
                {!snapshot.alerts.length ? <EmptyState title="No alerts" description="Threshold and anomaly alerts will land here." /> : null}
                {snapshot.alerts.slice(0, 5).map((alert) => (
                  <div key={alert.id} className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                    <div className="flex items-center gap-2">
                      <ToneBadge value={alert.severity} label={statusLabel(alert.status)} />
                      <div className="font-medium text-slate-900">{alertHeadline(alert)}</div>
                    </div>
                    <div className="mt-2 text-sm text-slate-500">{formatDateTime(alert.created_at)}</div>
                  </div>
                ))}
              </div>
              <div className="space-y-3">
                <div className="text-sm font-medium text-slate-900">Runs</div>
                {!snapshot.latest_runs.length ? <EmptyState title="No runs yet" description="Manual and scheduled runs will appear here." /> : null}
                {snapshot.latest_runs.slice(0, 5).map((run) => (
                  <div key={run.run_id} className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <div className="font-medium text-slate-900">{run.run_kind}</div>
                        <div className="mt-1 text-sm text-slate-500">{formatDateTime(run.started_at)}</div>
                      </div>
                      <ToneBadge value={run.status} label={statusLabel(run.status)} />
                    </div>
                    <div className="mt-2">
                      <Link className="inline-flex min-h-11 items-center text-sm font-medium text-sky-700 underline decoration-sky-300 underline-offset-4" to={`/admin/runs?runId=${encodeURIComponent(run.run_id)}`}>
                        Open run detail
                      </Link>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </SurfaceBody>
        </Surface>
      </div>
    </div>
  );
}

function NodesPage() {
  const { seed } = useShell();
  const runtime = useSnapshotResource(() => apiGet<AdminRuntimePayload>('/api/v1/admin/runtime'), null, [], { pollMs: 20000 });
  const [searchParams, setSearchParams] = useSearchParams();
  const selectedNodeId = Number(searchParams.get('node') || 0) || null;
  const [pairCode, setPairCode] = useState<PairCodeResponse | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [detailMessage, setDetailMessage] = useState<string | null>(null);
  const [form, setForm] = useState({
    node_name: '',
    role: 'client',
    runtime_mode: 'native-windows',
    configured_pull_url: '',
    enabled: true,
  });
  const nodes = runtime.data?.nodes ?? seed.nodes;
  const detail = useSnapshotResource(
    () => apiGet<NodeRecord>(`/api/v1/nodes/${selectedNodeId}`),
    nodes.find((node) => node.id === selectedNodeId) ?? null,
    [selectedNodeId],
    { enabled: selectedNodeId !== null, pollMs: 8000 },
  );

  const selectedNode = detail.data ?? nodes[0] ?? null;

  useEffect(() => {
    if (!selectedNodeId && nodes[0]) {
      startTransition(() => {
        setSearchParams({ node: String(nodes[0].id) }, { replace: true });
      });
    }
  }, [nodes, selectedNodeId, setSearchParams]);

  const registerNode = async () => {
    try {
      const response = await apiPost<{ ok: boolean; node: NodeRecord }>('/api/v1/nodes', {
        ...form,
        configured_pull_url: form.configured_pull_url || null,
      });
      setDetailError(null);
      setDetailMessage(`Saved node ${response.node.node_name}`);
      await runtime.refresh();
      startTransition(() => {
        setSearchParams({ node: String(response.node.id) });
      });
    } catch (error) {
      setDetailMessage(null);
      setDetailError(apiErrorDetail(error));
    }
  };

  const openPairCode = async (nodeId: number) => {
    try {
      setPairCode(await apiPost<PairCodeResponse>(`/api/v1/nodes/${nodeId}/pair-code`));
    } catch (error) {
      setDetailError(apiErrorDetail(error));
    }
  };

  const submitNodeAction = async (nodeId: number, action: string, confirmationToken?: string | null) => {
    try {
      const response = await apiPost<ActionCreateResponse>(`/api/v1/admin/nodes/${nodeId}/actions`, {
        action,
        actor: 'admin-webui',
        confirmation_token: confirmationToken ?? undefined,
      });
      if (response.confirmation_required && response.confirmation_token) {
        if (window.confirm(`Confirm node action: ${action}?`)) {
          await submitNodeAction(nodeId, action, response.confirmation_token);
        }
        return;
      }
      setDetailError(null);
      setDetailMessage(response.action ? `Queued action #${response.action.id}` : `${action} submitted`);
      void runtime.refresh();
      void detail.refresh();
    } catch (error) {
      const conflict = conflictDetail(error);
      setDetailMessage(null);
      setDetailError(conflict?.message || apiErrorDetail(error));
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Nodes"
        description="Live node runtime, connectivity, pair-code issuance, and lifecycle CTA flow against the current backend contracts."
        actions={<SnapshotMeta generatedAt={runtime.data?.generated_at} refreshing={runtime.loading} onRefresh={() => { void runtime.refresh(); void detail.refresh(); }} />}
      />
      {detailError ? <ErrorBanner message={detailError} /> : null}
      {detailMessage ? <div className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">{detailMessage}</div> : null}
      <div className="grid min-w-0 gap-6 2xl:grid-cols-[1.15fr_0.85fr]">
        <div className="min-w-0 space-y-4">
          <Surface>
            <SurfaceBody className="space-y-4">
              <SurfaceTitle title="Registered Nodes" meta={`${nodes.length} rows`} />
              {!nodes.length ? <EmptyState title="No nodes registered" description="Use the form below to create a node record before issuing a pair code." /> : null}
              <div className="grid gap-3">
                {nodes.map((node) => (
                  <button
                    key={node.id}
                    type="button"
                    onClick={() => setSearchParams({ node: String(node.id) })}
                    className={cn(
                      'min-w-0 rounded-2xl border px-4 py-3 text-left transition',
                      selectedNodeId === node.id ? 'border-slate-950 bg-slate-950 text-white shadow-[0_6px_16px_rgba(15,23,42,0.18)]' : 'border-slate-200 bg-white hover:border-slate-300',
                    )}
                  >
                    <div className="flex min-w-0 items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="break-words font-medium">{resolveNodeTitle(node)}</div>
                        <div className={cn('mt-1 text-sm', selectedNodeId === node.id ? 'text-slate-300' : 'text-slate-500')}>
                          {node.connectivity.summary}
                        </div>
                      </div>
                      <ToneBadge value={node.status} label={statusLabel(node.status)} />
                    </div>
                    <div className={cn('mt-3 flex flex-wrap items-center gap-2 text-xs', selectedNodeId === node.id ? 'text-slate-300' : 'text-slate-500')}>
                      <span>Last seen {formatRelative(node.last_seen_at)}</span>
                      <InlineCode value={node.identity.platform_name as string | undefined} />
                      <InlineCode value={node.identity.protocol_version as string | undefined} />
                    </div>
                  </button>
                ))}
              </div>
            </SurfaceBody>
          </Surface>

          <Surface>
            <SurfaceBody className="space-y-4">
              <SurfaceTitle title="Register or Update Node" />
              <div className="grid gap-3 md:grid-cols-2">
                <label className="space-y-1 text-sm">
                  <span className="text-slate-600">Node Name</span>
                  <input className={fieldControlClass} value={form.node_name} onChange={(event) => setForm((current) => ({ ...current, node_name: event.target.value }))} />
                </label>
                <label className="space-y-1 text-sm">
                  <span className="text-slate-600">Role</span>
                  <select className={fieldControlClass} value={form.role} onChange={(event) => setForm((current) => ({ ...current, role: event.target.value, runtime_mode: event.target.value === 'relay' ? 'docker-linux' : event.target.value === 'server' ? 'native-macos' : 'native-windows' }))}>
                    <option value="client">client</option>
                    <option value="relay">relay</option>
                    <option value="server">server</option>
                  </select>
                </label>
                <label className="space-y-1 text-sm">
                  <span className="text-slate-600">Runtime Mode</span>
                  <select className={fieldControlClass} value={form.runtime_mode} onChange={(event) => setForm((current) => ({ ...current, runtime_mode: event.target.value }))}>
                    <option value="native-windows">native-windows</option>
                    <option value="docker-linux">docker-linux</option>
                    <option value="native-macos">native-macos</option>
                  </select>
                </label>
                <label className="space-y-1 text-sm">
                  <span className="text-slate-600">Configured Pull URL</span>
                  <input className={fieldControlClass} value={form.configured_pull_url} onChange={(event) => setForm((current) => ({ ...current, configured_pull_url: event.target.value }))} />
                </label>
              </div>
              <div className="flex items-center gap-3">
                <SmallButton onClick={() => void registerNode()}>Save node</SmallButton>
                <label className="flex items-center gap-2 text-sm text-slate-600">
                  <input className="h-11 w-11 rounded border-slate-300" checked={form.enabled} type="checkbox" onChange={(event) => setForm((current) => ({ ...current, enabled: event.target.checked }))} />
                  enabled
                </label>
              </div>
            </SurfaceBody>
          </Surface>
        </div>

        <div className="min-w-0 space-y-4">
          <Surface>
            <SurfaceBody className="space-y-4">
              <SurfaceTitle title={selectedNode ? 'Node Detail' : 'Select a node'} meta={selectedNode ? formatDateTime(selectedNode.updated_at) : undefined} />
              {!selectedNode ? <EmptyState title="No node selected" description="Choose a node row to inspect runtime and connectivity details." /> : null}
              {selectedNode ? (
                <>
                  <div className="flex flex-wrap items-center gap-2">
                    <ToneBadge value={selectedNode.status} label={statusLabel(selectedNode.status)} />
                    <InlineCode value={selectedNode.identity.platform_name as string | undefined} />
                    <InlineCode value={selectedNode.identity.agent_version as string | undefined} />
                    <InlineCode value={selectedNode.identity.protocol_version as string | undefined} />
                  </div>
                  <KeyValueGrid
                    items={[
                      { label: 'Connectivity', value: selectedNode.connectivity.summary || 'N/A' },
                      { label: 'Recommended Step', value: selectedNode.connectivity.recommended_step || 'N/A' },
                      { label: 'Configured Pull URL', value: selectedNode.endpoints.configured_pull_url || 'N/A' },
                      { label: 'Advertised Pull URL', value: selectedNode.endpoints.advertised_pull_url || 'N/A' },
                      { label: 'Control Bridge URL', value: selectedNode.endpoints.control_bridge_url || 'N/A' },
                      { label: 'Readonly Reason', value: (selectedNode.runtime.details?.readonly_reason as string | undefined) || 'N/A' },
                    ]}
                  />
                  <div className="grid gap-2 sm:grid-cols-2">
                    <div className="min-w-0 rounded-xl bg-slate-50 px-4 py-3 text-sm text-slate-700">
                      <div className="font-medium text-slate-900">Push</div>
                      <div className="mt-1 break-words">{statusLabel(selectedNode.connectivity.push.state)}</div>
                      {selectedNode.connectivity.push.error ? <div className="mt-1 break-words">{selectedNode.connectivity.push.error}</div> : null}
                    </div>
                    <div className="min-w-0 rounded-xl bg-slate-50 px-4 py-3 text-sm text-slate-700">
                      <div className="font-medium text-slate-900">Pull</div>
                      <div className="mt-1 break-words">{statusLabel(selectedNode.connectivity.pull.state)}</div>
                      {selectedNode.connectivity.pull.error ? <div className="mt-1 break-words">{selectedNode.connectivity.pull.error}</div> : null}
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <SmallButton onClick={() => void openPairCode(selectedNode.id)}>Pair code</SmallButton>
                    {(selectedNode.runtime.details?.available_actions as string[] | undefined)?.map((action) => (
                      <SmallButton key={action} variant={action === 'stop' ? 'danger' : 'secondary'} onClick={() => void submitNodeAction(selectedNode.id, action)}>
                        {action}
                      </SmallButton>
                    ))}
                  </div>
                  <SuggestedActionLink action={selectedNode.runtime.details?.suggested_action as SuggestedAction | undefined} />
                </>
              ) : null}
            </SurfaceBody>
          </Surface>
          {selectedNode ? (
            <Surface>
              <SurfaceBody className="space-y-3">
                <SurfaceTitle title="Raw Runtime Snapshot" />
                <JsonBlock label="runtime JSON" value={{ runtime: selectedNode.runtime, supervisor: selectedNode.supervisor, endpoint_report: selectedNode.endpoint_report, runtime_status: selectedNode.runtime_status }} />
              </SurfaceBody>
            </Surface>
          ) : null}
        </div>
      </div>

      {pairCode ? (
        <div data-testid="pair-code-modal" className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/45 p-4">
          <div className="max-h-[90vh] w-full max-w-3xl overflow-y-auto rounded-2xl bg-white p-5 shadow-2xl">
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="text-xs uppercase tracking-[0.24em] text-slate-500">Pair Code</div>
                <div className="mt-1 text-2xl font-semibold text-slate-950">{pairCode.node_name}</div>
              </div>
              <SmallButton onClick={() => setPairCode(null)} variant="secondary">Close</SmallButton>
            </div>
            <div className="mt-4 grid gap-3 md:grid-cols-2">
              <StatCard label="Pair Code" value={<InlineCode value={pairCode.pair_code} />} hint={`Expires ${formatDateTime(pairCode.expires_at)}`} />
              <StatCard label="Node ID" value={pairCode.node_id} />
            </div>
            <div className="mt-6 space-y-4">
              <div>
                <div className="mb-2 text-sm font-medium text-slate-900">Startup command</div>
                <JsonBlock label="startup command JSON" value={pairCode.startup_command} />
              </div>
              {pairCode.fallback_command ? (
                <div>
                  <div className="mb-2 text-sm font-medium text-slate-900">Fallback command</div>
                  <JsonBlock label="fallback command JSON" value={pairCode.fallback_command} />
                </div>
              ) : null}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function PathsPage() {
  const filters = useSnapshotResource(() => apiGet<FilterOptionsPayload>('/api/v1/admin/filters'), null, [], {});
  const [timeRange, setTimeRange] = useState('24h');
  const [role, setRole] = useState('');
  const [node, setNode] = useState('');
  const [pathLabel, setPathLabel] = useState('');
  const [metricName, setMetricName] = useState('connect_avg_ms');

  const filterQuery = useMemo(() => {
    const params = new URLSearchParams({ time_range: timeRange });
    if (role) params.set('role', role);
    if (node) params.set('node', node);
    if (pathLabel) params.set('path_label', pathLabel);
    return params.toString();
  }, [node, pathLabel, role, timeRange]);

  const pathHealth = useSnapshotResource(
    () => apiGet<{ generated_at?: string; paths: PathSummary[]; trend_groups: Record<string, { series?: import('../../lib/types').MetricSeries[] }> }>(`/api/v1/admin/path-health?${filterQuery}`),
    null,
    [filterQuery],
    {},
  );

  const timeseries = useSnapshotResource(
    () => apiGet<MetricSeriesPayload>(`/api/v1/admin/timeseries?${filterQuery}${metricName ? `&metric_name=${encodeURIComponent(metricName)}` : ''}`),
    null,
    [filterQuery, metricName],
    {},
  );

  const pathRows = pathHealth.data?.paths ?? [];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Paths"
        description="Overview, path-health, and timeseries slices using the admin path-health and timeseries endpoints without invented fields."
        actions={<SnapshotMeta generatedAt={pathHealth.data?.generated_at || timeseries.data?.generated_at} refreshing={pathHealth.loading || timeseries.loading} onRefresh={() => { void pathHealth.refresh(); void timeseries.refresh(); }} />}
      />
      <Surface>
        <SurfaceBody className="space-y-4">
          <SurfaceTitle title="Filters" />
          <div className="grid gap-3 md:grid-cols-5">
            <FilterField label="Time range">
              <select className={fieldControlClass} value={timeRange} onChange={(event) => setTimeRange(event.target.value)}>
                {(filters.data?.time_ranges ?? ['1h', '6h', '24h', '7d', '30d']).map((value) => <option key={value} value={value}>{value}</option>)}
              </select>
            </FilterField>
            <FilterField label="Role">
              <select className={fieldControlClass} value={role} onChange={(event) => setRole(event.target.value)}>
                <option value="">all roles</option>
                {(filters.data?.roles ?? []).map((value) => <option key={value} value={value}>{value}</option>)}
              </select>
            </FilterField>
            <FilterField label="Node">
              <select className={fieldControlClass} value={node} onChange={(event) => setNode(event.target.value)}>
                <option value="">all nodes</option>
                {(filters.data?.nodes ?? []).map((value) => <option key={value.node_name} value={value.node_name}>{value.node_name}</option>)}
              </select>
            </FilterField>
            <FilterField label="Path">
              <select className={fieldControlClass} value={pathLabel} onChange={(event) => setPathLabel(event.target.value)}>
                <option value="">all paths</option>
                {(filters.data?.paths ?? []).map((value) => <option key={value} value={value}>{value}</option>)}
              </select>
            </FilterField>
            <FilterField label="Metric">
              <select className={fieldControlClass} value={metricName} onChange={(event) => setMetricName(event.target.value)}>
                {(filters.data?.metrics ?? ['connect_avg_ms']).map((value) => <option key={value} value={value}>{value}</option>)}
              </select>
            </FilterField>
          </div>
        </SurfaceBody>
      </Surface>

      <div className="grid gap-6 xl:grid-cols-[1fr_1.2fr]">
        <Surface>
          <SurfaceBody className="space-y-4">
            <SurfaceTitle title="Path Health" meta={`${pathRows.length} paths`} />
            {!pathRows.length ? <EmptyState title="No path data" description="Run probes or widen the time-range filter to populate path-health rows." /> : null}
            <div className="space-y-3">
              {pathRows.map((path) => (
                <div key={path.path_label} className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <div className="font-medium text-slate-900">{path.path_label}</div>
                      <div className="mt-1 text-sm text-slate-500">Last capture {formatRelative(path.last_captured_at)}</div>
                    </div>
                    <ToneBadge value={path.status} label={statusLabel(path.status)} />
                  </div>
                  <div className="mt-3 grid gap-2 text-sm text-slate-700 sm:grid-cols-2">
                    {Object.entries(path.latest).slice(0, 4).map(([metric, value]) => (
                      <div key={metric} className="flex min-w-0 items-center justify-between gap-3 rounded-xl bg-white px-3 py-2">
                        <span className="min-w-0 break-words">{metric}</span>
                        <span className="font-medium">{formatMetric(value, metric)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </SurfaceBody>
        </Surface>

        <Surface>
          <SurfaceBody className="space-y-4">
            <SurfaceTitle title="Timeseries" meta={metricName} />
            {!timeseries.data?.series.length ? <EmptyState title="No timeseries series" description="Pick a metric/path slice that exists in the current backend samples." /> : null}
            {timeseries.data?.series.length ? (
              <TimeSeriesChart title={metricName} series={timeseries.data.series} unit={timeseries.data.unit || metricUnit(metricName)} />
            ) : null}
          </SurfaceBody>
        </Surface>
      </div>
    </div>
  );
}

function RunsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [timeRange, setTimeRange] = useState('24h');
  const [runKind, setRunKind] = useState('');
  const [status, setStatus] = useState('');
  const [pathLabel, setPathLabel] = useState('');
  const [runMessage, setRunMessage] = useState<string | null>(null);
  const [runError, setRunError] = useState<ConflictDetail | string | null>(null);

  const query = useMemo(() => {
    const params = new URLSearchParams({ time_range: timeRange });
    if (runKind) params.set('run_kind', runKind);
    if (status) params.set('status', status);
    if (pathLabel) params.set('path_label', pathLabel);
    return params.toString();
  }, [pathLabel, runKind, status, timeRange]);

  const runs = useSnapshotResource(
    () => apiGet<{ generated_at?: string; items: RunRecord[] }>(`/api/v1/admin/runs?${query}`),
    null,
    [query],
    { pollMs: 8000 },
  );

  const selectedRunId = searchParams.get('runId') || runs.data?.items[0]?.run_id || null;
  const detail = useSnapshotResource(
    () => apiGet<RunRecord>(`/api/v1/admin/runs/${selectedRunId}`),
    null,
    [selectedRunId],
    { enabled: Boolean(selectedRunId), pollMs: 3000 },
  );
  const events = useSnapshotResource(
    () => apiGet<{ generated_at?: string; items: Array<Record<string, unknown>> }>(`/api/v1/admin/runs/${selectedRunId}/events`),
    null,
    [selectedRunId],
    { enabled: Boolean(selectedRunId), pollMs: 3000 },
  );

  useEffect(() => {
    if (selectedRunId && searchParams.get('runId') !== selectedRunId) {
      setSearchParams({ runId: selectedRunId });
    }
  }, [searchParams, selectedRunId, setSearchParams]);

  const startManualRun = async (kind: string) => {
    try {
      const response = await apiPost<RunStartResponse>('/api/v1/runs', { run_kind: kind, source: 'admin-webui' });
      setRunError(null);
      setRunMessage(`Started ${response.run_id}`);
      await runs.refresh();
      setSearchParams({ runId: response.run_id });
    } catch (error) {
      setRunMessage(null);
      setRunError(conflictDetail(error) || apiErrorDetail(error));
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Runs"
        description="Manual run triggering, run list filtering, detail payloads, progress summaries, and event timeline from existing admin run endpoints."
        actions={<SnapshotMeta generatedAt={runs.data?.generated_at || detail.data?.generated_at} refreshing={runs.loading || detail.loading} onRefresh={() => { void runs.refresh(); void detail.refresh(); void events.refresh(); }} />}
      />
      {runError && typeof runError === 'string' ? <ErrorBanner message={runError} /> : null}
      {runError && typeof runError === 'object' ? <ErrorBanner message={runError.message || 'A run is already active'} action={runError.suggested_action} /> : null}
      {runMessage ? <div className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">{runMessage}</div> : null}

      <Surface>
        <SurfaceBody className="space-y-4">
          <SurfaceTitle title="Manual Run and Filters" />
          <div className="flex flex-wrap gap-2">
            {['system', 'baseline', 'capacity', 'full'].map((kind) => (
              <SmallButton key={kind} onClick={() => void startManualRun(kind)}>
                <Play className="mr-2 h-4 w-4" />
                {kind}
              </SmallButton>
            ))}
          </div>
          <div className="grid gap-3 md:grid-cols-4">
            <FilterField label="Time range">
              <select className={fieldControlClass} value={timeRange} onChange={(event) => setTimeRange(event.target.value)}>
                {['1h', '6h', '24h', '7d', '30d'].map((value) => <option key={value} value={value}>{value}</option>)}
              </select>
            </FilterField>
            <FilterField label="Run kind">
              <select className={fieldControlClass} value={runKind} onChange={(event) => setRunKind(event.target.value)}>
                <option value="">all kinds</option>
                {['system', 'baseline', 'capacity', 'full'].map((value) => <option key={value} value={value}>{value}</option>)}
              </select>
            </FilterField>
            <FilterField label="Status">
              <select className={fieldControlClass} value={status} onChange={(event) => setStatus(event.target.value)}>
                <option value="">all statuses</option>
                {['running', 'completed', 'failed'].map((value) => <option key={value} value={value}>{value}</option>)}
              </select>
            </FilterField>
            <FilterField label="Path label">
              <input className={fieldControlClass} placeholder="path_label" value={pathLabel} onChange={(event) => setPathLabel(event.target.value)} />
            </FilterField>
          </div>
        </SurfaceBody>
      </Surface>

      <div className="grid min-w-0 gap-6 xl:grid-cols-[0.9fr_1.1fr]">
        <Surface>
          <SurfaceBody className="space-y-4">
            <SurfaceTitle title="Run List" meta={`${runs.data?.items.length ?? 0} items`} />
            {!runs.data?.items.length ? <EmptyState title="No runs in range" description="Start a manual run or expand the time range." /> : null}
            <div className="space-y-3">
              {(runs.data?.items ?? []).map((run) => (
                <button key={run.run_id} type="button" onClick={() => setSearchParams({ runId: run.run_id })} className={cn('w-full min-w-0 rounded-2xl border px-4 py-3 text-left transition', selectedRunId === run.run_id ? 'border-slate-950 bg-slate-950 text-white shadow-[0_6px_16px_rgba(15,23,42,0.18)]' : 'border-slate-200 bg-white hover:border-slate-300')}>
                  <div className="flex min-w-0 items-center justify-between gap-3">
                    <div className="min-w-0">
                      <div className="break-words font-medium">{run.run_kind}</div>
                      <div className={cn('mt-1 text-sm', selectedRunId === run.run_id ? 'text-slate-300' : 'text-slate-500')}>{formatDateTime(run.started_at)}</div>
                    </div>
                    <ToneBadge value={run.status} label={statusLabel(run.status)} />
                  </div>
                  <div className={cn('mt-3 text-sm', selectedRunId === run.run_id ? 'text-slate-300' : 'text-slate-600')}>
                    {run.progress?.headline || run.summary || `findings ${run.findings_count ?? 0}`}
                  </div>
                </button>
              ))}
            </div>
          </SurfaceBody>
        </Surface>

        <div className="min-w-0 space-y-4">
          <Surface>
            <SurfaceBody className="space-y-4">
              <SurfaceTitle title="Run Detail" meta={selectedRunId ? <InlineCode value={selectedRunId} /> : undefined} />
              {!detail.data ? <EmptyState title="No run selected" description="Choose a run from the list to inspect progress, probes, and alerts." /> : null}
              {detail.data ? (
                <>
                  <div className="grid gap-3 md:grid-cols-4">
                    <StatCard label="Status" value={<ToneBadge value={detail.data.status} label={statusLabel(detail.data.status)} />} />
                    <StatCard label="Findings" value={detail.data.findings_count ?? 0} />
                    <StatCard label="Events" value={detail.data.progress?.events_count ?? 0} />
                    <StatCard label="Phase" value={detail.data.progress?.active_phase || 'idle'} />
                  </div>
                  <KeyValueGrid
                    items={[
                      { label: 'Headline', value: detail.data.progress?.headline || 'N/A' },
                      { label: 'Recommended Step', value: detail.data.progress?.recommended_step || 'N/A' },
                      { label: 'Last Failure', value: detail.data.progress?.last_failure_message || 'N/A' },
                      { label: 'Conclusion', value: (detail.data.conclusion ?? []).join(' · ') || 'N/A' },
                    ]}
                  />
                  <div className="grid gap-3 lg:grid-cols-2">
                    <Surface className="border-slate-100">
                      <SurfaceBody className="space-y-3">
                        <SurfaceTitle title="Probes" meta={`${detail.data.probes?.length ?? 0}`} />
                        {!detail.data.probes?.length ? <EmptyState title="No probes recorded" /> : null}
                        {(detail.data.probes ?? []).map((probe, index) => (
                          <div key={`${probe.probe_name || index}`} className="rounded-2xl bg-slate-50 px-4 py-3 text-sm text-slate-700">
                            <div className="font-medium text-slate-900">{String(probe.probe_name || probe.name || 'probe')}</div>
                            <div className="mt-1">{String(probe.path_label || (probe.metadata as Record<string, unknown> | undefined)?.path_label || 'N/A')}</div>
                          </div>
                        ))}
                      </SurfaceBody>
                    </Surface>
                    <Surface className="border-slate-100">
                      <SurfaceBody className="space-y-3">
                        <SurfaceTitle title="Alerts" meta={`${detail.data.alerts?.length ?? 0}`} />
                        {!detail.data.alerts?.length ? <EmptyState title="No alerts for this run" /> : null}
                        {(detail.data.alerts ?? []).map((alert) => (
                          <div key={alert.id} className="rounded-2xl bg-slate-50 px-4 py-3">
                            <div className="flex items-center gap-2">
                              <ToneBadge value={alert.severity} label={statusLabel(alert.status)} />
                              <div className="font-medium text-slate-900">{alertHeadline(alert)}</div>
                            </div>
                          </div>
                        ))}
                      </SurfaceBody>
                    </Surface>
                  </div>
                </>
              ) : null}
            </SurfaceBody>
          </Surface>

          <Surface>
            <SurfaceBody className="space-y-4">
              <SurfaceTitle title="Event Timeline" meta={`${events.data?.items.length ?? 0} events`} />
              {!events.data?.items.length ? <EmptyState title="No timeline events" description="Active and historical event envelopes will render here." /> : null}
              <div className="space-y-3">
                {(events.data?.items ?? []).map((event, index) => (
                  <div key={`${String(event.id ?? index)}`} className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
                    <div className="flex items-center justify-between gap-3">
                      <div className="font-medium text-slate-900">{String(event.event_kind || 'event')}</div>
                      <ToneBadge value={String(event.severity || 'info')} label={statusLabel(String(event.severity || 'info'))} />
                    </div>
                    <div className="mt-2 text-sm text-slate-700">{String(event.summary || event.message || '')}</div>
                    <div className="mt-2 text-sm text-slate-500">{formatDateTime(event.created_at as string | undefined)}</div>
                  </div>
                ))}
              </div>
            </SurfaceBody>
          </Surface>
        </div>
      </div>
    </div>
  );
}

function AlertsPage() {
  const [timeRange, setTimeRange] = useState('24h');
  const [status, setStatus] = useState('');
  const [severity, setSeverity] = useState('');
  const [kind, setKind] = useState('');
  const [pathLabel, setPathLabel] = useState('');
  const [selectedAlertId, setSelectedAlertId] = useState<number | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [silenceTarget, setSilenceTarget] = useState<AlertRecord | null>(null);
  const [silenceHours, setSilenceHours] = useState('12');
  const [silenceReason, setSilenceReason] = useState('');
  const [silenceSubmitting, setSilenceSubmitting] = useState(false);

  const query = useMemo(() => {
    const params = new URLSearchParams({ time_range: timeRange });
    if (status) params.set('status', status);
    if (severity) params.set('severity', severity);
    if (kind) params.set('kind', kind);
    if (pathLabel) params.set('path_label', pathLabel);
    return params.toString();
  }, [kind, pathLabel, severity, status, timeRange]);

  const alerts = useSnapshotResource(
    () => apiGet<{ generated_at?: string; items: AlertRecord[]; summary: Record<string, number> }>(`/api/v1/admin/alerts?${query}`),
    null,
    [query],
    { pollMs: 10000 },
  );
  const selectedAlert = alerts.data?.items.find((item) => item.id === selectedAlertId) ?? alerts.data?.items[0] ?? null;
  const timeseries = useSnapshotResource(
    () => apiGet<MetricSeriesPayload>(`/api/v1/admin/timeseries?time_range=${encodeURIComponent(timeRange)}${selectedAlert?.path_label ? `&path_label=${encodeURIComponent(selectedAlert.path_label)}` : ''}${selectedAlert?.metric_name ? `&metric_name=${encodeURIComponent(selectedAlert.metric_name)}` : ''}`),
    null,
    [selectedAlert?.id, selectedAlert?.metric_name, selectedAlert?.path_label, timeRange],
    { enabled: Boolean(selectedAlert?.metric_name) },
  );

  const acknowledgeAlert = async (alertId: number) => {
    try {
      await apiPost<AlertMutationResponse>(`/api/v1/admin/alerts/${alertId}/ack`, { actor: 'admin-webui' });
      setError(null);
      setMessage(`Alert ${alertId} acknowledged`);
      await alerts.refresh();
      await timeseries.refresh();
    } catch (mutationError) {
      setMessage(null);
      setError(apiErrorDetail(mutationError));
    }
  };

  const openSilenceModal = (alert: AlertRecord) => {
    setSilenceTarget(alert);
    setSilenceHours('12');
    setSilenceReason('');
    setError(null);
    setMessage(null);
  };

  const submitSilence = async () => {
    if (!silenceTarget || !silenceReason.trim()) {
      return;
    }
    setSilenceSubmitting(true);
    try {
      const silencedUntil = new Date(Date.now() + Number(silenceHours) * 60 * 60 * 1000).toISOString();
      await apiPost<AlertMutationResponse>(`/api/v1/admin/alerts/${silenceTarget.id}/silence`, {
        actor: 'admin-webui',
        silenced_until: silencedUntil,
        reason: silenceReason.trim(),
      });
      setError(null);
      setMessage(`Alert ${silenceTarget.id} silenced until ${formatDateTime(silencedUntil)}`);
      setSilenceTarget(null);
      await alerts.refresh();
      await timeseries.refresh();
    } catch (mutationError) {
      setMessage(null);
      setError(apiErrorDetail(mutationError));
    } finally {
      setSilenceSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Alerts"
        description="Alert table, acknowledge/silence flow, and metric timeseries for the selected fingerprint/path slice."
        actions={<SnapshotMeta generatedAt={alerts.data?.generated_at || timeseries.data?.generated_at} refreshing={alerts.loading || timeseries.loading} onRefresh={() => { void alerts.refresh(); void timeseries.refresh(); }} />}
      />
      {error ? <ErrorBanner message={error} /> : null}
      {message ? <div className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">{message}</div> : null}
      <Surface>
        <SurfaceBody className="grid gap-3 md:grid-cols-5">
          <FilterField label="Time range">
            <select className={fieldControlClass} value={timeRange} onChange={(event) => setTimeRange(event.target.value)}>
              {['1h', '6h', '24h', '7d', '30d'].map((value) => <option key={value} value={value}>{value}</option>)}
            </select>
          </FilterField>
          <FilterField label="Status">
            <select className={fieldControlClass} value={status} onChange={(event) => setStatus(event.target.value)}>
              <option value="">all status</option>
              {['open', 'acknowledged', 'resolved'].map((value) => <option key={value} value={value}>{value}</option>)}
            </select>
          </FilterField>
          <FilterField label="Severity">
            <select className={fieldControlClass} value={severity} onChange={(event) => setSeverity(event.target.value)}>
              <option value="">all severity</option>
              {['info', 'warning', 'error'].map((value) => <option key={value} value={value}>{value}</option>)}
            </select>
          </FilterField>
          <FilterField label="Kind">
            <select className={fieldControlClass} value={kind} onChange={(event) => setKind(event.target.value)}>
              <option value="">all kind</option>
              {['threshold', 'anomaly', 'node_status'].map((value) => <option key={value} value={value}>{value}</option>)}
            </select>
          </FilterField>
          <FilterField label="Path label">
            <input className={fieldControlClass} placeholder="path_label" value={pathLabel} onChange={(event) => setPathLabel(event.target.value)} />
          </FilterField>
        </SurfaceBody>
      </Surface>

      <div className="grid min-w-0 gap-6 xl:grid-cols-[1fr_1fr]">
        <Surface>
          <SurfaceBody className="space-y-4">
            <SurfaceTitle title="Alert List" meta={`${alerts.data?.items.length ?? 0} items`} />
            {!alerts.data?.items.length ? <EmptyState title="No alerts match the filter" /> : null}
            <div className="space-y-3">
              {(alerts.data?.items ?? []).map((alert) => (
                <div key={alert.id} className={cn('min-w-0 rounded-2xl border px-4 py-3 transition', selectedAlertId === alert.id ? 'border-slate-950 bg-slate-950 text-white shadow-[0_6px_16px_rgba(15,23,42,0.18)]' : 'border-slate-200 bg-white')}>
                  <button type="button" onClick={() => setSelectedAlertId(alert.id)} className="w-full text-left">
                    <div className="flex min-w-0 items-center justify-between gap-3">
                      <div className="min-w-0">
                        <div className="break-words font-medium">{alertHeadline(alert)}</div>
                        <div className={cn('mt-1 text-sm', selectedAlertId === alert.id ? 'text-slate-300' : 'text-slate-500')}>{formatDateTime(alert.created_at)}</div>
                      </div>
                      <ToneBadge value={alert.severity} label={statusLabel(alert.status)} />
                    </div>
                  </button>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <SmallButton variant="secondary" disabled={Boolean(alert.acknowledged)} onClick={() => void acknowledgeAlert(alert.id)}>
                      {alert.acknowledged ? 'Acknowledged' : 'Acknowledge'}
                    </SmallButton>
                    <SmallButton variant="secondary" disabled={Boolean(alert.is_silenced)} onClick={() => openSilenceModal(alert)}>
                      {alert.is_silenced ? 'Silenced' : 'Silence'}
                    </SmallButton>
                  </div>
                </div>
              ))}
            </div>
          </SurfaceBody>
        </Surface>

        <div className="min-w-0 space-y-4">
          <Surface>
            <SurfaceBody className="space-y-4">
              <SurfaceTitle title="Selected Alert" meta={selectedAlert ? <InlineCode value={String(selectedAlert.id)} /> : undefined} />
              {!selectedAlert ? <EmptyState title="Select an alert" /> : null}
              {selectedAlert ? (
                <>
                  <KeyValueGrid
                    items={[
                      { label: 'Summary', value: alertHeadline(selectedAlert) },
                      { label: 'Path', value: selectedAlert.path_label || 'N/A' },
                      { label: 'Metric', value: selectedAlert.metric_name || 'N/A' },
                      { label: 'Actual / Threshold', value: `${formatMetric(selectedAlert.actual_value, selectedAlert.metric_name)} / ${formatMetric(selectedAlert.threshold_value, selectedAlert.metric_name)}` },
                      { label: 'Acknowledged', value: selectedAlert.acknowledged ? `yes · ${selectedAlert.acknowledged_by || 'unknown'}` : 'no' },
                      { label: 'Silence', value: selectedAlert.silenced_until ? formatDateTime(selectedAlert.silenced_until) : 'not silenced' },
                    ]}
                  />
                  {selectedAlert.path_label && selectedAlert.metric_name && timeseries.data?.series.length ? (
                    <TimeSeriesChart title={selectedAlert.metric_name} series={timeseries.data.series} unit={timeseries.data.unit || metricUnit(selectedAlert.metric_name)} />
                  ) : (
                    <EmptyState title="No linked timeseries" description="This alert does not have a chartable metric/path slice in the current window." />
                  )}
                </>
              ) : null}
            </SurfaceBody>
          </Surface>
        </div>
      </div>
      {silenceTarget ? (
        <div data-testid="silence-modal" className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/45 p-4">
          <form
            className="w-full max-w-lg rounded-2xl bg-white p-5 shadow-2xl"
            onSubmit={(event) => {
              event.preventDefault();
              void submitSilence();
            }}
          >
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="text-xs uppercase tracking-[0.18em] text-slate-500">Confirm silence</div>
                <h2 className="mt-1 break-words text-xl font-semibold text-slate-950">Alert #{silenceTarget.id}</h2>
              </div>
              <SmallButton variant="secondary" onClick={() => setSilenceTarget(null)}>Cancel</SmallButton>
            </div>
            <div className="mt-4 space-y-3">
              <div className="rounded-xl bg-slate-50 px-4 py-3">
                <div className="break-words text-sm font-medium text-slate-950">{alertHeadline(silenceTarget)}</div>
                <div className="mt-2 flex flex-wrap gap-2">
                  <ToneBadge value={silenceTarget.severity} label={statusLabel(silenceTarget.severity)} />
                  <ToneBadge value={silenceTarget.status} label={statusLabel(silenceTarget.status)} />
                </div>
              </div>
              <FilterField label="Duration">
                <select className={fieldControlClass} value={silenceHours} onChange={(event) => setSilenceHours(event.target.value)}>
                  <option value="1">1 hour</option>
                  <option value="6">6 hours</option>
                  <option value="12">12 hours</option>
                  <option value="24">24 hours</option>
                </select>
              </FilterField>
              <FilterField label="Reason">
                <textarea
                  className={cn(fieldControlClass, 'min-h-24 resize-y')}
                  value={silenceReason}
                  onChange={(event) => setSilenceReason(event.target.value)}
                  placeholder="Why is this alert safe to silence?"
                  required
                />
              </FilterField>
            </div>
            <div className="mt-5 flex flex-wrap justify-end gap-2">
              <SmallButton variant="secondary" onClick={() => setSilenceTarget(null)}>Cancel</SmallButton>
              <SmallButton type="submit" variant="danger" disabled={!silenceReason.trim() || silenceSubmitting}>
                Silence alert #{silenceTarget.id}
              </SmallButton>
            </div>
          </form>
        </div>
      ) : null}
    </div>
  );
}

function ActionsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const list = useSnapshotResource(() => apiGet<{ generated_at?: string; items: ControlActionRecord[] }>('/api/v1/admin/actions?limit=100'), null, [], { pollMs: 8000 });
  const actionId = Number(searchParams.get('actionId') || 0) || list.data?.items[0]?.id || null;
  const detail = useSnapshotResource(
    () => apiGet<ControlActionRecord>(`/api/v1/admin/actions/${actionId}`),
    null,
    [actionId],
    { enabled: Boolean(actionId), pollMs: 5000 },
  );

  useEffect(() => {
    if (actionId && searchParams.get('actionId') !== String(actionId)) {
      setSearchParams({ actionId: String(actionId) });
    }
  }, [actionId, searchParams, setSearchParams]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Actions"
        description="Lifecycle action list, action detail, and target snapshot from the existing admin actions endpoints."
        actions={<SnapshotMeta generatedAt={list.data?.generated_at} refreshing={list.loading || detail.loading} onRefresh={() => { void list.refresh(); void detail.refresh(); }} />}
      />
      <div className="grid min-w-0 gap-6 xl:grid-cols-[0.9fr_1.1fr]">
        <Surface>
          <SurfaceBody className="space-y-4">
            <SurfaceTitle title="Action List" meta={`${list.data?.items.length ?? 0} items`} />
            {!list.data?.items.length ? <EmptyState title="No actions yet" description="Queued, running, completed, and failed lifecycle actions will appear here." /> : null}
            <div className="space-y-3">
              {(list.data?.items ?? []).map((action) => (
                <button key={action.id} type="button" onClick={() => setSearchParams({ actionId: String(action.id) })} className={cn('w-full min-w-0 rounded-2xl border px-4 py-3 text-left transition', actionId === action.id ? 'border-slate-950 bg-slate-950 text-white shadow-[0_6px_16px_rgba(15,23,42,0.18)]' : 'border-slate-200 bg-white')}>
                  <div className="flex min-w-0 items-center justify-between gap-3">
                    <div className="min-w-0">
                      <div className="break-words font-medium">{action.target_name || action.target_kind} · {action.action}</div>
                      <div className={cn('mt-1 text-sm', actionId === action.id ? 'text-slate-300' : 'text-slate-500')}>{formatDateTime(action.requested_at)}</div>
                    </div>
                    <ToneBadge value={action.status} label={statusLabel(action.status)} />
                  </div>
                  <div className={cn('mt-2 break-words text-sm', actionId === action.id ? 'text-slate-300' : 'text-slate-600')}>{action.summary || action.result_summary || 'No summary yet'}</div>
                </button>
              ))}
            </div>
          </SurfaceBody>
        </Surface>
        <div className="min-w-0 space-y-4">
          <Surface>
            <SurfaceBody className="space-y-4">
              <SurfaceTitle title="Action Detail" meta={detail.data ? <InlineCode value={String(detail.data.id)} /> : undefined} />
              {!detail.data ? <EmptyState title="Select an action" /> : null}
              {detail.data ? (
                <>
                  <KeyValueGrid
                    items={[
                      { label: 'Target', value: detail.data.target_name || detail.data.target_kind },
                      { label: 'Summary', value: detail.data.summary || detail.data.result_summary || 'N/A' },
                      { label: 'Failure', value: detail.data.failure?.detail ? String(detail.data.failure.detail) : 'N/A' },
                      { label: 'Requested By', value: detail.data.requested_by || 'N/A' },
                      { label: 'Runtime Hint', value: detail.data.target_operator_summary || 'N/A' },
                      { label: 'Recommended Step', value: detail.data.target_operator_recommended_step || 'N/A' },
                    ]}
                  />
                  {detail.data.target_suggested_action ? <SuggestedActionLink action={detail.data.target_suggested_action} /> : null}
                </>
              ) : null}
            </SurfaceBody>
          </Surface>
          {detail.data ? (
            <Surface>
              <SurfaceBody className="space-y-3">
                <SurfaceTitle title="Target Snapshot" />
                <JsonBlock label="target snapshot JSON" value={detail.data.target_snapshot || detail.data.runtime_snapshot || detail.data.response || {}} />
              </SurfaceBody>
            </Surface>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function SchedulesPage() {
  const { seed } = useShell();
  const dashboard = useSnapshotResource(() => apiGet<DashboardSnapshot>('/api/v1/dashboard'), seed, [], { pollMs: 30000 });
  const schedules = dashboard.data?.schedules ?? [];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Schedules"
        description="Current schedule intervals from the backend schedule table. This backend currently exposes schedule visibility but not a dedicated interval mutation endpoint, so the page stays explicit about readonly limits."
        actions={<SnapshotMeta generatedAt={dashboard.data?.generated_at} refreshing={dashboard.loading} onRefresh={() => { void dashboard.refresh(); }} />}
      />
      <Surface>
        <SurfaceBody className="space-y-4">
          <SurfaceTitle title="Schedule Table" meta={`${schedules.length} rows`} />
          {!schedules.length ? <EmptyState title="No schedules found" /> : null}
          <div className="grid gap-4 md:grid-cols-3">
            {schedules.map((schedule: ScheduleRecord) => (
              <Surface key={schedule.id} className="border-slate-100">
                <SurfaceBody className="space-y-3">
                  <div className="flex items-center justify-between gap-3">
                    <div className="font-medium text-slate-900">{schedule.run_kind}</div>
                    <ToneBadge value={schedule.enabled ? 'info' : 'skip'} label={schedule.enabled ? 'enabled' : 'disabled'} />
                  </div>
                  <KeyValueGrid
                    items={[
                      { label: 'Interval', value: `${schedule.interval_sec}s` },
                      { label: 'Next Run', value: formatDateTime(schedule.next_run_at) },
                      { label: 'Updated', value: formatDateTime(schedule.updated_at) },
                    ]}
                  />
                </SurfaceBody>
              </Surface>
            ))}
          </div>
          <div className="rounded-2xl border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-900">
            The existing backend contract currently returns schedules through `GET /api/v1/dashboard`, but does not expose a dedicated schedule interval write API. This page surfaces the data and current limitation instead of inventing a frontend-only mutation path.
          </div>
        </SurfaceBody>
      </Surface>
    </div>
  );
}

function SettingsPage() {
  const { seed } = useShell();
  const dashboard = useSnapshotResource(() => apiGet<DashboardSnapshot>('/api/v1/dashboard'), seed, [], {});
  const settings = dashboard.data?.settings ?? seed.settings;
  const [topologyDraft, setTopologyDraft] = useState(() => ({
    source: settings.topology_name,
    value: settings.topology_name,
  }));
  const [servicesText, setServicesText, parseServices] = useJsonEditor(settings.services);
  const [thresholdsText, setThresholdsText, parseThresholds] = useJsonEditor(settings.thresholds);
  const [scenariosText, setScenariosText, parseScenarios] = useJsonEditor(settings.scenarios);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const topologyName = topologyDraft.source === settings.topology_name ? topologyDraft.value : settings.topology_name;
  const setTopologyName = (value: string) => {
    setTopologyDraft({
      source: settings.topology_name,
      value,
    });
  };

  const saveSettings = async () => {
    const services = parseServices(settings.services);
    const thresholds = parseThresholds(settings.thresholds);
    const scenarios = parseScenarios(settings.scenarios);
    if (!services || !thresholds || !scenarios) {
      setMessage(null);
      setError('Invalid JSON in one of the settings editors');
      return;
    }
    try {
      await apiPost('/api/v1/dashboard', {
        topology_name: topologyName,
        services,
        thresholds,
        scenarios,
      });
      setError(null);
      setMessage('Settings saved');
      await dashboard.refresh();
    } catch (saveError) {
      setMessage(null);
      setError(apiErrorDetail(saveError));
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Settings"
        description="Topology, services, thresholds, and scenarios are edited directly against the backend `PanelSettings` payload shape and submitted through the existing dashboard save endpoint."
        actions={<SnapshotMeta generatedAt={dashboard.data?.generated_at} refreshing={dashboard.loading} onRefresh={() => { void dashboard.refresh(); }} />}
      />
      {error ? <ErrorBanner message={error} /> : null}
      {message ? <div className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">{message}</div> : null}
      <Surface>
        <SurfaceBody className="space-y-4">
          <SurfaceTitle title="Panel Settings" meta={buildLabel(dashboard.data?.build)} />
          <label className="space-y-1 text-sm">
            <span className="text-slate-600">Topology Name</span>
            <input className={fieldControlClass} value={topologyName} onChange={(event) => setTopologyName(event.target.value)} />
          </label>
          <SettingsEditor title="Services" value={servicesText} onChange={setServicesText} />
          <SettingsEditor title="Thresholds" value={thresholdsText} onChange={setThresholdsText} />
          <SettingsEditor title="Scenarios" value={scenariosText} onChange={setScenariosText} />
          <SmallButton onClick={() => void saveSettings()}>Save settings</SmallButton>
        </SurfaceBody>
      </Surface>
    </div>
  );
}

function SettingsEditor({
  title,
  value,
  onChange,
}: {
  title: string;
  value: string;
  onChange: (next: string) => void;
}) {
  return (
    <div className="space-y-2">
      <div className="text-sm font-medium text-slate-900">{title}</div>
      <textarea className="min-h-[240px] w-full min-w-0 rounded-2xl border border-slate-200 bg-slate-950 p-4 font-mono text-sm text-slate-100" value={value} onChange={(event) => onChange(event.target.value)} />
    </div>
  );
}

function PlaceholderRoute({
  title,
  description,
  icon,
}: {
  title: string;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
}) {
  const Icon = icon;
  return (
    <div className="space-y-6">
      <PageHeader title={title} description={description} />
      <Surface>
        <SurfaceBody>
          <div className="flex items-center gap-3 rounded-2xl bg-slate-50 px-5 py-8 text-slate-600">
            <Icon className="h-6 w-6 text-slate-400" />
            <div>This route is intentionally unused.</div>
          </div>
        </SurfaceBody>
      </Surface>
    </div>
  );
}

function AdminApp() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/admin" element={<AdminLayout />}>
          <Route index element={<DashboardPage />} />
          <Route path="nodes" element={<NodesPage />} />
          <Route path="paths" element={<PathsPage />} />
          <Route path="runs" element={<RunsPage />} />
          <Route path="alerts" element={<AlertsPage />} />
          <Route path="actions" element={<ActionsPage />} />
          <Route path="schedules" element={<SchedulesPage />} />
          <Route path="settings" element={<SettingsPage />} />
          <Route path="*" element={<PlaceholderRoute title="Unknown Route" description="The admin SPA fallback is working; this route just is not mapped." icon={AlertTriangle} />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <AdminApp />
  </React.StrictMode>,
);
