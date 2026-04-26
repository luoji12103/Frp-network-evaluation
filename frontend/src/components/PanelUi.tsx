import { useMemo, useState, type PropsWithChildren, type ReactNode } from 'react';
import { AlertTriangle, LoaderCircle } from 'lucide-react';
import { Link } from 'react-router-dom';
import { cn } from '../lib/utils';
import { severityTone, suggestedActionHref, suggestedActionLabel } from '../lib/format';
import type { SuggestedAction } from '../lib/types';

export const fieldControlClass =
  'min-h-11 w-full min-w-0 rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-950 outline-none transition placeholder:text-slate-400 focus:border-slate-500 focus:ring-2 focus:ring-slate-200 disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-500';

export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="flex min-w-0 flex-col gap-4 border-b border-slate-200 pb-5 lg:flex-row lg:items-end lg:justify-between">
      <div className="min-w-0 space-y-1">
        <h1 className="break-words text-3xl font-semibold tracking-tight text-slate-950">{title}</h1>
        {description ? <p className="max-w-3xl text-sm text-slate-600">{description}</p> : null}
      </div>
      {actions ? <div className="flex min-w-0 flex-wrap items-center gap-2">{actions}</div> : null}
    </div>
  );
}

export function Surface({ children, className }: PropsWithChildren<{ className?: string }>) {
  return (
    <section className={cn('min-w-0 rounded-2xl border border-slate-200 bg-white shadow-[0_1px_2px_rgba(15,23,42,0.06)]', className)}>
      {children}
    </section>
  );
}

export function SurfaceBody({ children, className }: PropsWithChildren<{ className?: string }>) {
  return <div className={cn('min-w-0 p-4 sm:p-5', className)}>{children}</div>;
}

export function SurfaceTitle({ title, meta }: { title: string; meta?: ReactNode }) {
  return (
    <div className="flex min-w-0 items-start justify-between gap-3">
      <h2 className="min-w-0 break-words text-lg font-semibold text-slate-950">{title}</h2>
      {meta ? <div className="shrink-0 text-xs text-slate-500">{meta}</div> : null}
    </div>
  );
}

export function StatCard({
  label,
  value,
  hint,
}: {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
}) {
  return (
    <Surface>
      <SurfaceBody className="space-y-2 py-4">
        <div className="text-xs uppercase tracking-[0.16em] text-slate-500">{label}</div>
        <div className="break-words text-2xl font-semibold text-slate-950 sm:text-3xl">{value}</div>
        {hint ? <div className="text-sm text-slate-500">{hint}</div> : null}
      </SurfaceBody>
    </Surface>
  );
}

export function ToneBadge({ value, label }: { value?: string | null; label?: string }) {
  const tone = severityTone(value);
  const palette: Record<string, string> = {
    emerald: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
    amber: 'bg-amber-50 text-amber-700 ring-amber-200',
    rose: 'bg-rose-50 text-rose-700 ring-rose-200',
    slate: 'bg-slate-100 text-slate-700 ring-slate-200',
    sky: 'bg-sky-50 text-sky-700 ring-sky-200',
  };
  return (
    <span className={cn('inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium ring-1 ring-inset', palette[tone])}>
      {label || value || 'unknown'}
    </span>
  );
}

export function SmallButton({
  children,
  onClick,
  variant = 'default',
  disabled,
  type = 'button',
}: PropsWithChildren<{
  onClick?: () => void;
  variant?: 'default' | 'secondary' | 'danger';
  disabled?: boolean;
  type?: 'button' | 'submit';
}>) {
  const palette: Record<string, string> = {
    default: 'bg-slate-950 text-white hover:bg-slate-800',
    secondary: 'bg-white text-slate-700 ring-1 ring-slate-200 hover:bg-slate-50',
    danger: 'bg-rose-600 text-white hover:bg-rose-500',
  };
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={cn(
        'inline-flex min-h-11 items-center justify-center rounded-xl px-4 py-2 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-50',
        palette[variant],
      )}
    >
      {children}
    </button>
  );
}

export function KeyValueGrid({ items }: { items: Array<{ label: string; value: ReactNode }> }) {
  return (
    <dl className="grid min-w-0 gap-3 sm:grid-cols-2">
      {items.map((item) => (
        <div key={item.label} className="min-w-0 rounded-xl bg-slate-50 px-4 py-3">
          <dt className="text-xs uppercase tracking-[0.16em] text-slate-500">{item.label}</dt>
          <dd className="mt-1 break-words text-sm text-slate-900">{item.value}</dd>
        </div>
      ))}
    </dl>
  );
}

export function EmptyState({
  title,
  description,
}: {
  title: string;
  description?: string;
}) {
  return (
    <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-5 py-8 text-center">
      <div className="mx-auto mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-white text-slate-400 ring-1 ring-slate-200">
        <AlertTriangle className="h-4 w-4" />
      </div>
      <div className="text-base font-medium text-slate-900">{title}</div>
      {description ? <div className="mt-1 text-sm text-slate-500">{description}</div> : null}
    </div>
  );
}

export function LoadingState({ label }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 text-sm text-slate-500">
      <LoaderCircle className="h-4 w-4 animate-spin" />
      <span>{label || 'Loading…'}</span>
    </div>
  );
}

export function ErrorBanner({
  message,
  action,
}: {
  message: string;
  action?: SuggestedAction | null;
}) {
  const href = suggestedActionHref(action);
  return (
    <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">
      <div>{message}</div>
      {href ? (
        <div className="mt-2">
          <Link className="inline-flex min-h-11 items-center font-medium underline decoration-rose-300 underline-offset-4" to={href}>
            {suggestedActionLabel(action)}
          </Link>
        </div>
      ) : null}
    </div>
  );
}

export function InlineCode({ value }: { value: string | null | undefined }) {
  return (
    <code className="max-w-full break-words rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs text-slate-700">{value || 'N/A'}</code>
  );
}

export function FilterField({
  label,
  children,
}: PropsWithChildren<{
  label: string;
}>) {
  return (
    <label className="min-w-0 space-y-1 text-sm">
      <span className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">{label}</span>
      {children}
    </label>
  );
}

export function JsonBlock({
  value,
  label = 'JSON details',
  defaultExpanded = false,
}: {
  value: unknown;
  label?: string;
  defaultExpanded?: boolean;
}) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const [copied, setCopied] = useState(false);
  const json = useMemo(() => JSON.stringify(value, null, 2), [value]);

  const copyJson = async () => {
    try {
      await navigator.clipboard.writeText(json);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  };

  return (
    <div className="min-w-0 overflow-hidden rounded-2xl border border-slate-200 bg-slate-50">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 px-3 py-2">
        <button
          type="button"
          aria-expanded={expanded}
          onClick={() => setExpanded((current) => !current)}
          className="min-h-11 rounded-lg px-2 text-left text-sm font-medium text-slate-800 hover:bg-white"
        >
          {expanded ? 'Hide' : 'Show'} {label}
        </button>
        <button
          type="button"
          onClick={() => void copyJson()}
          className="min-h-11 rounded-lg px-3 text-sm font-medium text-slate-600 ring-1 ring-slate-200 hover:bg-white"
        >
          {copied ? 'Copied' : 'Copy JSON'}
        </button>
      </div>
      {expanded ? (
        <pre className="max-h-[28rem] min-w-0 overflow-auto whitespace-pre-wrap break-words bg-slate-950 p-4 text-xs leading-6 text-slate-100">
          {json}
        </pre>
      ) : (
        <div className="px-4 py-3 text-sm text-slate-500">Technical JSON is collapsed to keep the operational view focused.</div>
      )}
    </div>
  );
}
