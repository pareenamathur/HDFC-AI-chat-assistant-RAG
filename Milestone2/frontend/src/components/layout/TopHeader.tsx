'use client';

import { Shield, History, HelpCircle, Menu } from 'lucide-react';
import { StatusPill } from '@/components/ui/StatusPill';
import { formatCorpusSubtitle } from '@/lib/format';
import type { HealthResponse } from '@/lib/api';

type Props = {
  health: HealthResponse | null;
  healthLoading: boolean;
  onScrollTop: () => void;
  onMenuOpen?: () => void;
};

export function TopHeader({ health, healthLoading, onScrollTop, onMenuOpen }: Props) {
  return (
    <header className="z-30 flex h-header shrink-0 items-center gap-3 border-b border-border bg-background px-4 lg:px-6">
      {onMenuOpen && (
        <button
          type="button"
          onClick={onMenuOpen}
          className="rounded-lg p-2 text-text-secondary hover:bg-card lg:hidden"
          aria-label="Open menu"
        >
          <Menu className="h-5 w-5" />
        </button>
      )}

      <div className="flex min-w-0 flex-1 items-center gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-accent/30 bg-accent/10">
          <Shield className="h-5 w-5 text-accent" aria-hidden />
        </div>
        <div className="min-w-0">
          <h1 className="truncate text-title-lg text-text-primary">HDFC Assistant</h1>
          <p className="truncate text-xs text-text-secondary">{formatCorpusSubtitle(health)}</p>
        </div>
      </div>

      <div className="hidden max-w-xs flex-1 justify-center px-2 md:flex">
        <p className="truncate rounded-lg border border-warning/30 bg-warning/10 px-3 py-1.5 text-xs text-warning">
          Important: Facts-only assistant
        </p>
      </div>

      <div className="flex shrink-0 items-center gap-2">
        <StatusPill health={health} loading={healthLoading} />
        <button
          type="button"
          onClick={onScrollTop}
          className="hidden rounded-lg p-2 text-text-secondary transition hover:bg-card hover:text-text-primary sm:inline-flex"
          aria-label="Scroll to top"
        >
          <History className="h-4 w-4" />
        </button>
        <a
          href="https://www.hdfcfund.com/"
          target="_blank"
          rel="noopener noreferrer"
          className="rounded-lg p-2 text-text-secondary transition hover:bg-card hover:text-text-primary"
          aria-label="Help"
        >
          <HelpCircle className="h-4 w-4" />
        </a>
      </div>
    </header>
  );
}
