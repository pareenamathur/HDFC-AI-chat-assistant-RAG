'use client';

import { Building2 } from 'lucide-react';

const SUGGESTIONS = [
  {
    label: 'Performance',
    text: 'Compare HDFC Top 100 vs NIFTY 50 5-year returns',
  },
  {
    label: 'Fees',
    text: 'List expense ratios for all HDFC Hybrid funds',
  },
  {
    label: 'Allocation',
    text: 'What is the equity exposure in HDFC Balanced Advantage?',
  },
];

type Props = {
  onSuggestion: (text: string) => void;
};

export function HeroSection({ onSuggestion }: Props) {
  return (
    <section className="mx-auto w-full max-w-chat px-4 pb-8 pt-6 md:pt-10">
      <div className="flex flex-col items-center text-center">
        <div className="mb-5 flex h-16 w-16 items-center justify-center rounded-2xl border border-border bg-card shadow-card">
          <Building2 className="h-8 w-8 text-accent" />
        </div>
        <h2 className="max-w-xl text-title-xl text-text-primary">
          Ask me anything about HDFC Mutual Funds
        </h2>
        <p className="mt-2 max-w-lg text-body text-text-secondary">
          Accurate, data-driven insights from the indexed corpus.
        </p>
      </div>

      <div className="mt-8 grid grid-cols-1 gap-3 sm:grid-cols-3">
        {SUGGESTIONS.map((s) => (
          <button
            key={s.label}
            type="button"
            onClick={() => onSuggestion(s.text)}
            className="rounded-xl border border-border bg-card p-4 text-left shadow-card transition hover:border-accent/50 hover:shadow-glow"
          >
            <p className="text-sm font-semibold text-accent">{s.label}</p>
            <p className="mt-2 text-sm leading-relaxed text-text-primary">&ldquo;{s.text}&rdquo;</p>
          </button>
        ))}
      </div>
    </section>
  );
}
