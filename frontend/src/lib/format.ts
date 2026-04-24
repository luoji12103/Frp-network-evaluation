import type { AlertRecord, BuildInfo, MetricSeries, NodeRecord, SuggestedAction } from './types';

export function formatDateTime(value: string | null | undefined): string {
  if (!value) {
    return 'N/A';
  }
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

export function formatRelative(value: string | null | undefined): string {
  if (!value) {
    return 'N/A';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  const diffMs = date.getTime() - Date.now();
  const absMs = Math.abs(diffMs);
  const minutes = Math.round(absMs / 60000);
  if (minutes < 1) {
    return 'just now';
  }
  if (minutes < 60) {
    return diffMs >= 0 ? `in ${minutes}m` : `${minutes}m ago`;
  }
  const hours = Math.round(minutes / 60);
  if (hours < 48) {
    return diffMs >= 0 ? `in ${hours}h` : `${hours}h ago`;
  }
  const days = Math.round(hours / 24);
  return diffMs >= 0 ? `in ${days}d` : `${days}d ago`;
}

export function formatNumber(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return 'N/A';
  }
  return new Intl.NumberFormat(undefined, {
    minimumFractionDigits: 0,
    maximumFractionDigits: digits,
  }).format(value);
}

export function formatMetric(value: number | null | undefined, metricName?: string | null, unit?: string | null): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return 'N/A';
  }
  const resolvedUnit = unit ?? metricUnit(metricName);
  return `${formatNumber(value, resolvedUnit === '%' ? 1 : 2)}${resolvedUnit ? ` ${resolvedUnit}` : ''}`;
}

export function metricUnit(metricName?: string | null): string {
  if (!metricName) {
    return '';
  }
  if (metricName.endsWith('_pct')) {
    return '%';
  }
  if (metricName.endsWith('_mbps')) {
    return 'Mbps';
  }
  if (metricName.endsWith('_ms')) {
    return 'ms';
  }
  return '';
}

export function severityTone(value: string | null | undefined): string {
  switch ((value ?? '').toLowerCase()) {
    case 'pass':
    case 'healthy':
    case 'online':
    case 'completed':
    case 'ok':
    case 'info':
      return 'emerald';
    case 'warn':
    case 'warning':
    case 'acknowledged':
    case 'degraded':
    case 'push-only':
    case 'pull-only':
    case 'running':
      return 'amber';
    case 'fail':
    case 'error':
    case 'critical':
    case 'offline':
    case 'failed':
      return 'rose';
    case 'skip':
    case 'disabled':
    case 'unpaired':
      return 'slate';
    default:
      return 'sky';
  }
}

export function statusLabel(value: string | null | undefined): string {
  if (!value) {
    return 'Unknown';
  }
  return value.replaceAll('_', ' ');
}

export function buildLabel(build?: BuildInfo | null): string {
  return build?.display_label || window.panel_build_label || 'unknown build';
}

export function staleSummary(generatedAt: string | null | undefined): string {
  if (!generatedAt) {
    return 'Snapshot time unavailable';
  }
  return `Generated ${formatRelative(generatedAt)} (${formatDateTime(generatedAt)})`;
}

export function alertHeadline(alert: AlertRecord): string {
  return alert.summary || alert.message || `${alert.kind} ${alert.severity}`;
}

export function suggestedActionHref(action: SuggestedAction | null | undefined): string | null {
  if (!action) {
    return null;
  }
  switch (action.kind) {
    case 'open_node':
      return action.target_id ? `/admin/nodes?node=${action.target_id}` : '/admin/nodes';
    case 'open_run':
      return action.run_id ? `/admin/runs?runId=${encodeURIComponent(action.run_id)}` : '/admin/runs';
    case 'open_action':
      return action.action_id ? `/admin/actions?actionId=${action.action_id}` : '/admin/actions';
    case 'open_panel':
      return '/admin';
    default:
      return null;
  }
}

export function suggestedActionLabel(action: SuggestedAction | null | undefined): string {
  return action?.label || 'Open detail';
}

export function resolveNodeTitle(node: NodeRecord): string {
  return `${node.node_name} · ${node.role} · ${node.runtime_mode}`;
}

export function metricSeriesLatest(series: MetricSeries): number | null {
  const point = series.points[series.points.length - 1];
  return point ? point.value : null;
}
