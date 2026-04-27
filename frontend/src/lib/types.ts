export type JsonRecord = Record<string, unknown>;

export interface BuildInfo {
  release_version: string;
  build_ref?: string | null;
  display_label: string;
  header_label: string;
}

export interface SnapshotPayload {
  build?: BuildInfo;
  generated_at?: string | null;
}

export interface SuggestedAction {
  kind: string;
  target_kind: string;
  target_id?: number | null;
  run_id?: string | null;
  action_id?: number | null;
  label: string;
  dangerous?: boolean;
}

export interface ConnectivityChannel {
  state: string;
  checked_at?: string | null;
  code?: string | null;
  error?: string | null;
}

export interface RuntimeSummaryRecord {
  state: string;
  checked_at?: string | null;
  last_error?: string | null;
  details?: JsonRecord & {
    available_actions?: string[];
    readonly_reason?: string | null;
    active_action_id?: number | null;
    active_action_summary?: string | null;
    operator_summary?: string | null;
    operator_severity?: string | null;
    operator_recommended_step?: string | null;
    suggested_action?: SuggestedAction | null;
    active_run_id?: string | null;
    active_run_summary?: string | null;
    active_run_severity?: string | null;
  };
}

export interface SupervisorSummaryRecord {
  control_available?: boolean;
  bridge_url?: string | null;
  supervisor_state?: string;
  process_state?: string;
  pid_or_container_id?: string | null;
  log_location?: string | null;
  last_error?: string | null;
  checked_at?: string | null;
}

export interface NodeRecord extends SnapshotPayload {
  id: number;
  topology_id?: number;
  node_name: string;
  role: string;
  runtime_mode: string;
  enabled: boolean;
  paired: boolean;
  status: string;
  configured_pull_url?: string | null;
  advertised_pull_url?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  last_seen_at?: string | null;
  last_heartbeat_at?: string | null;
  token_issued_at?: string | null;
  identity: JsonRecord & {
    node_name?: string;
    role?: string;
    runtime_mode?: string;
    protocol_version?: string;
    platform_name?: string;
    hostname?: string;
    agent_version?: string;
  };
  capabilities: JsonRecord & {
    pull_http?: boolean;
    heartbeat_queue?: boolean;
    result_lookup?: boolean;
  };
  endpoint_report: JsonRecord & {
    listen_host?: string;
    listen_port?: number;
    advertise_url?: string | null;
    control_listen_port?: number | null;
    control_url?: string | null;
  };
  runtime_status: JsonRecord & {
    paired?: boolean;
    started_at?: string;
    last_heartbeat_at?: string | null;
    last_error?: string | null;
    environment?: JsonRecord;
  };
  runtime: RuntimeSummaryRecord;
  supervisor: SupervisorSummaryRecord;
  connectivity: {
    status: string;
    push: ConnectivityChannel;
    pull: ConnectivityChannel;
    endpoint_mismatch?: boolean;
    endpoint_mismatch_detail?: string | null;
    diagnostic_code?: string | null;
    attention_level?: string | null;
    summary?: string | null;
    recommended_step?: string | null;
  };
  endpoints: {
    configured_pull_url?: string | null;
    advertised_pull_url?: string | null;
    effective_pull_url?: string | null;
    control_bridge_url?: string | null;
  };
  active_action?: ControlActionRecord | null;
  run_attention?: {
    run_id?: string | null;
    summary?: string | null;
    severity?: string | null;
    node_id?: number | null;
    recommended_step?: string | null;
    suggested_action?: SuggestedAction | null;
  };
}

export interface ScheduleRecord {
  id: number;
  topology_id?: number;
  run_kind: string;
  interval_sec: number;
  enabled: boolean;
  next_run_at?: string | null;
  updated_at?: string | null;
}

export interface AlertRecord {
  id: number;
  topology_id?: number;
  node_id?: number | null;
  run_id?: string | null;
  kind: string;
  severity: string;
  status: string;
  message?: string;
  summary?: string;
  created_at?: string | null;
  path_label?: string | null;
  path_id?: string | null;
  probe_name?: string | null;
  metric_name?: string | null;
  actual_value?: number | null;
  threshold_value?: number | null;
  fingerprint?: string | null;
  acknowledged?: boolean;
  acknowledged_at?: string | null;
  acknowledged_by?: string | null;
  is_silenced?: boolean;
  silenced_until?: string | null;
  silence_reason?: string | null;
  legacy_unstructured?: boolean;
  roles?: string[];
}

export interface MetricPoint {
  timestamp: string;
  value: number;
}

export interface MetricSeries {
  name: string;
  metric_name: string;
  path_label?: string | null;
  path_id?: string | null;
  probe_name?: string | null;
  unit?: string;
  direction?: string;
  points: MetricPoint[];
  anomalies?: Array<{ id?: number; timestamp?: string | null; value?: number | null; severity?: string | null; message?: string | null }>;
  summary?: JsonRecord;
  stats?: JsonRecord;
  roles?: string[];
}

export interface MetricSeriesPayload extends SnapshotPayload {
  metric_name?: string | null;
  threshold?: number | null;
  direction?: string | null;
  unit?: string | null;
  series: MetricSeries[];
}

export interface TrendGroupRecord {
  metric_names?: string[];
  series?: MetricSeries[];
}

export interface PathSummary {
  path_label: string;
  path_id?: string;
  status: string;
  latest: Record<string, number>;
  averages: Record<string, number>;
  open_alerts: number;
  open_anomalies: number;
  last_captured_at?: string | null;
  roles?: string[];
  family?: string;
}

export interface RunProgressRecord {
  events_count?: number;
  last_event_kind?: string | null;
  last_event_message?: string | null;
  last_event_at?: string | null;
  active_phase?: string | null;
  phase_started_at?: string | null;
  latest_probe?: JsonRecord | null;
  latest_queue_job?: JsonRecord | null;
  current_blocker?: JsonRecord | null;
  headline?: string | null;
  headline_severity?: string | null;
  last_failure_code?: string | null;
  last_failure_message?: string | null;
  last_failure_at?: string | null;
  recommended_step?: string | null;
}

export interface RunRecord extends SnapshotPayload {
  id?: string;
  run_id: string;
  topology_id?: number;
  run_kind: string;
  status: string;
  source?: string;
  started_at?: string | null;
  finished_at?: string | null;
  error?: string | null;
  raw_path?: string | null;
  csv_path?: string | null;
  html_path?: string | null;
  findings_count?: number;
  conclusion?: string[];
  summary?: string | null;
  threshold_findings?: JsonRecord[];
  probes?: JsonRecord[];
  alerts?: AlertRecord[];
  active?: boolean;
  path_ids?: string[];
  roles?: string[];
  progress?: RunProgressRecord;
}

export interface ControlActionRecord extends SnapshotPayload {
  id: number;
  target_kind: string;
  target_id?: number | null;
  action: string;
  status: string;
  confirmation_required?: boolean;
  requested_by?: string;
  requested_at?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
  transport?: string | null;
  result_summary?: string | null;
  error_code?: string | null;
  error_detail?: string | null;
  summary?: string | null;
  severity?: string | null;
  code?: string | null;
  target_name?: string | null;
  is_dangerous?: boolean;
  has_log_excerpt?: boolean;
  has_runtime_snapshot?: boolean;
  active?: boolean;
  request?: JsonRecord;
  response?: JsonRecord;
  log_excerpt?: string[];
  log_location?: string | null;
  runtime_snapshot?: JsonRecord;
  failure?: JsonRecord;
  audit_payload?: JsonRecord;
  target_status?: string | null;
  target_runtime_state?: string | null;
  target_attention_level?: string | null;
  target_operator_summary?: string | null;
  target_operator_severity?: string | null;
  target_operator_recommended_step?: string | null;
  target_suggested_action?: SuggestedAction | null;
  target_active_run_id?: string | null;
  target_active_action_id?: number | null;
  target_snapshot?: JsonRecord;
}

export interface DashboardSnapshot extends SnapshotPayload {
  topology_id: number;
  settings: {
    topology_name: string;
    services: JsonRecord;
    thresholds: JsonRecord;
    scenarios: JsonRecord;
  };
  schedules: ScheduleRecord[];
  nodes: NodeRecord[];
  latest_runs: RunRecord[];
  alerts: AlertRecord[];
  history: JsonRecord;
}

export interface AttentionItem {
  severity: string;
  kind: string;
  title: string;
  summary?: string | null;
  code?: string | null;
  target_kind?: string | null;
  target_id?: number | null;
  target_name?: string | null;
  action_id?: number | null;
  run_id?: string | null;
  suggested_action?: SuggestedAction | null;
  recommended_step?: string | null;
}

export interface AdminRuntimePayload extends SnapshotPayload {
  panel: {
    runtime: RuntimeSummaryRecord;
    supervisor: SupervisorSummaryRecord;
  };
  nodes: NodeRecord[];
  active_run?: RunRecord | null;
  attention: {
    summary: { total: number; error: number; warning: number; info: number };
    items: AttentionItem[];
  };
}

export interface AdminOverviewPayload extends SnapshotPayload {
  kpis: {
    total_nodes: number;
    online_rate_pct: number;
    degraded_nodes: number;
    offline_nodes: number;
    active_alerts: number;
    health_score: number;
    last_full_run_started_at?: string | null;
    last_full_run_status?: string | null;
  };
  status_distribution: Record<string, number>;
  recent_anomalies: AlertRecord[];
  path_health: PathSummary[];
  trend_groups: Record<string, TrendGroupRecord>;
  alert_summary: Record<string, number>;
}

export interface ReleaseValidationItem {
  target_kind: string;
  target_id?: number | null;
  target_name: string;
  role?: string | null;
  status: string;
  code?: string | null;
  summary: string;
  recommended_step?: string | null;
  suggested_action?: SuggestedAction | null;
  checks?: Record<string, { status: string; summary: string; code?: string }>;
  build?: BuildInfo | null;
  connectivity?: JsonRecord | null;
  runtime?: JsonRecord | null;
  supervisor?: JsonRecord | null;
}

export interface ReleaseValidationSnapshot extends SnapshotPayload {
  running: boolean;
  checked_at?: string | null;
  summary: { total: number; pass: number; warn: number; fail: number; skip: number };
  panel: ReleaseValidationItem;
  nodes: ReleaseValidationItem[];
  issues: ReleaseValidationItem[];
}

export interface FilterOptionsPayload extends SnapshotPayload {
  roles: string[];
  nodes: Array<{ role: string; node_name: string }>;
  paths: string[];
  probes: string[];
  metrics: string[];
  run_kinds: string[];
  severities: string[];
  statuses: string[];
  time_ranges: string[];
}

export interface PairCodeResponse {
  node_id: number;
  node_name: string;
  pair_code: string;
  expires_at: string;
  startup_command: string;
  fallback_command?: string | null;
}

export interface ActionCreateResponse {
  ok: boolean;
  queued: boolean;
  confirmation_required: boolean;
  confirmation_token?: string | null;
  action?: ControlActionRecord | null;
}

export interface AlertMutationResponse {
  ok: boolean;
  alert: AlertRecord;
}

export interface RunStartResponse {
  ok: boolean;
  run_id: string;
  status: string;
}

export interface ConflictDetail {
  message?: string;
  recommended_step?: string;
  suggested_action?: SuggestedAction | null;
  active_run?: RunRecord;
  active_action?: ControlActionRecord;
}

export interface PublicDashboardSnapshot extends SnapshotPayload {
  topology_id: number;
  topology_name: string;
  time_range?: string | null;
  privacy_mode?: string | null;
  summary: {
    total_nodes: number;
    online_nodes: number;
    degraded_nodes: number;
    offline_nodes: number;
    active_alerts: number;
    online_rate_pct: number;
    abnormal_nodes: number;
    last_full_run_started_at?: string | null;
    last_full_run_status?: string | null;
  };
  nodes: Array<{
    id: number;
    role: string;
    status: string;
    enabled: boolean;
    paired: boolean;
    last_seen_at?: string | null;
    summary?: string | null;
    recommended_step?: string | null;
    attention_level?: string | null;
    path_ids?: string[];
    connectivity?: { push?: ConnectivityChannel; pull?: ConnectivityChannel };
  }>;
  latest_runs: RunRecord[];
  alerts: AlertRecord[];
  paths: PathSummary[];
  history: {
    time_range_hours?: number;
    trend_groups?: Record<string, TrendGroupRecord>;
  };
}

export interface PublicPathDetail extends SnapshotPayload {
  path_id: string;
  path_label: string;
  roles?: string[];
  family?: string;
  status: string;
  latest: Record<string, number>;
  averages: Record<string, number>;
  open_alerts: number;
  open_anomalies: number;
  last_captured_at?: string | null;
  time_range?: string | null;
  privacy_mode?: string | null;
  alerts: AlertRecord[];
  latest_runs: RunRecord[];
  metric_groups: string[];
}

export interface PublicRoleDetail extends SnapshotPayload {
  role: string;
  status: string;
  enabled: boolean;
  paired: boolean;
  last_seen_at?: string | null;
  summary?: string | null;
  recommended_step?: string | null;
  attention_level?: string | null;
  connectivity?: { push?: ConnectivityChannel; pull?: ConnectivityChannel };
  time_range?: string | null;
  privacy_mode?: string | null;
  paths: PathSummary[];
  alerts: AlertRecord[];
  latest_runs: RunRecord[];
  metric_groups: string[];
}

export interface PublicPathHealthPayload extends SnapshotPayload {
  topology_id: number;
  topology_name: string;
  time_range?: string | null;
  privacy_mode?: string | null;
  paths: PathSummary[];
  path?: PublicPathDetail;
}

export interface PublicTimeseriesPayload extends SnapshotPayload {
  scope_kind: string;
  scope_id: string;
  metric_group: string;
  time_range?: string | null;
  privacy_mode?: string | null;
  series: MetricSeries[];
}

declare global {
  interface Window {
    __INITIAL_STATE__?: DashboardSnapshot | PublicDashboardSnapshot | PublicPathDetail | PublicRoleDetail;
    __PUBLIC_PAGE__?: { kind: 'overview' | 'path' | 'role'; scope_id?: string | null };
    panel_build_label?: string;
    next_path?: string;
    login_error_key_json?: string | null;
  }
}
