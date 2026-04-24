import type { PropsWithChildren, ReactNode } from 'react';
import { AlertTriangle, LoaderCircle } from 'lucide-react';
import { Link } from 'react-router-dom';
import { cn } from '../lib/utils';
import { severityTone, suggestedActionHref, suggestedActionLabel } from '../lib/format';
import type { SuggestedAction } from '../lib/types';

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
    <div className="flex flex-col gap-4 border-b border-slate-200 pb-5 lg:flex-row lg:items-end lg:justify-between">
      <div className="space-y-1">
        <h1 className="text-3xl font-semibold tracking-tight text-slate-950">{title}</h1>
        {description ? <p className="max-w-3xl text-sm text-slate-600">{description}</p> : null}
      </div>
      {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
    </div>
  );
}

export function Surface({ children, className }: PropsWithChildren<{ className?: string }>) {
  return (
    <section className={cn('rounded-3xl border border-slate-200 bg-white shadow-sm shadow-slate-200/60', className)}>
      {children}
    </section>
  );
}

export function SurfaceBody({ children, className }: PropsWithChildren<{ className?: string }>) {
  return <div className={cn('p-5', className)}>{children}</div>;
}

export function SurfaceTitle({ title, meta }: { title: string; meta?: ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-3">
      <h2 className="text-lg font-semibold text-slate-950">{title}</h2>
      {meta ? <div className="text-xs text-slate-500">{meta}</div> : null}
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
      <SurfaceBody className="space-y-2">
        <div className="text-xs uppercase tracking-[0.16em] text-slate-500">{label}</div>
        <div className="text-3xl font-semibold text-slate-950">{value}</div>
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
        'inline-flex items-center justify-center rounded-full px-3 py-2 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-50',
        palette[variant],
      )}
    >
      {children}
    </button>
  );
}

export function KeyValueGrid({ items }: { items: Array<{ label: string; value: ReactNode }> }) {
  return (
    <dl className="grid gap-3 sm:grid-cols-2">
      {items.map((item) => (
        <div key={item.label} className="rounded-2xl bg-slate-50 px-4 py-3">
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
    <div className="rounded-3xl border border-dashed border-slate-300 bg-slate-50 px-6 py-12 text-center">
      <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-white text-slate-400 ring-1 ring-slate-200">
        <AlertTriangle className="h-5 w-5" />
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
          <Link className="font-medium underline decoration-rose-300 underline-offset-4" to={href}>
            {suggestedActionLabel(action)}
          </Link>
        </div>
      ) : null}
    </div>
  );
}

export function InlineCode({ value }: { value: string | null | undefined }) {
  return (
    <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs text-slate-700">{value || 'N/A'}</code>
  );
}

export function JsonBlock({ value }: { value: unknown }) {
  return (
    <pre className="overflow-x-auto rounded-2xl bg-slate-950 p-4 text-xs leading-6 text-slate-100">
      {JSON.stringify(value, null, 2)}
    </pre>
  );
}
