'use client';

import { WifiOff, AlertTriangle } from 'lucide-react';
import type { HealthResponse } from '@/lib/api';

type Props = {
  health: HealthResponse | null;
  loading: boolean;
};

export function StatusPill({ health, loading }: Props) {
  if (loading) {
    return (
      <div className="flex items-center gap-2 rounded-full border border-border bg-card px-3 py-1.5">
        <span className="h-2 w-2 animate-pulse rounded-full bg-text-secondary" />
        <span className="text-xs text-text-secondary">Checking…</span>
      </div>
    );
  }

  if (!health || health.status !== 'healthy') {
    return (
      <div className="flex items-center gap-2 rounded-full border border-error/40 bg-error-bg px-3 py-1.5">
        <WifiOff className="h-3.5 w-3.5 shrink-0 text-error" />
        <span className="text-xs font-medium text-error">Offline</span>
      </div>
    );
  }

  if (health.degraded) {
    return (
      <div className="flex items-center gap-2 rounded-full border border-warning/40 bg-warning-bg px-3 py-1.5">
        <AlertTriangle className="h-3.5 w-3.5 shrink-0 text-warning" />
        <span className="text-xs font-medium text-warning">Fallback</span>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2 rounded-full border border-border bg-card px-3 py-1.5">
      <span className="relative flex h-2 w-2 shrink-0">
        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-success opacity-60" />
        <span className="relative inline-flex h-2 w-2 rounded-full bg-success" />
      </span>
      <span className="whitespace-nowrap text-xs font-medium text-text-primary">
        System Online
      </span>
    </div>
  );
}
