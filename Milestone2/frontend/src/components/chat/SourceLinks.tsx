'use client';

import { ExternalLink, FileText, Globe } from 'lucide-react';
import type { SourceRef } from '@/lib/api';

type Props = {
  sources?: SourceRef[];
  source?: string;
  source_link?: string;
  last_updated?: string;
};

function iconForTitle(title: string) {
  const t = title.toLowerCase();
  if (t.includes('fact') || t.includes('document')) return FileText;
  if (t.includes('groww') || t.includes('fund')) return Globe;
  return ExternalLink;
}

export function SourceLinks({ sources, source, source_link, last_updated }: Props) {
  const items: SourceRef[] = sources?.length
    ? sources
    : source_link
      ? [{ title: source || 'Go to source', url: source_link }]
      : [];

  if (!items.length && !last_updated && !source) return null;

  return (
    <div className="mt-3 flex flex-wrap gap-2">
      {items.map((src, i) => {
        const Icon = iconForTitle(src.title);
        return (
          <a
            key={`${src.url}-${i}`}
            href={src.url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex max-w-full items-center gap-1.5 rounded-full border border-border bg-background px-3 py-1.5 text-xs text-text-secondary transition hover:border-accent hover:text-accent"
          >
            <Icon className="h-3.5 w-3.5 shrink-0" />
            <span className="truncate">{src.title}</span>
          </a>
        );
      })}
      {!items.length && source && (
        <span className="inline-flex items-center gap-1.5 rounded-full border border-border bg-background px-3 py-1.5 text-xs text-text-secondary">
          <FileText className="h-3.5 w-3.5" />
          <span className="truncate">{source}</span>
        </span>
      )}
      {last_updated && (
        <span className="inline-flex items-center gap-1.5 rounded-full border border-border bg-background px-3 py-1.5 text-xs text-text-secondary">
          NAV as of {last_updated}
        </span>
      )}
    </div>
  );
}
