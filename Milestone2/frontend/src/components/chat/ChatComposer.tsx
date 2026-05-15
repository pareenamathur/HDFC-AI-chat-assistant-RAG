'use client';

import { Paperclip, ArrowUp } from 'lucide-react';

const CHIPS = [
  'Expense Ratio?',
  'NAV?',
  'Exit Load?',
  'Top 10 Holdings?',
  'Comparison?',
];

type Props = {
  input: string;
  isLoading: boolean;
  onInputChange: (value: string) => void;
  onSend: () => void;
  onChip: (text: string) => void;
};

export function ChatComposer({ input, isLoading, onInputChange, onSend, onChip }: Props) {
  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      onSend();
    }
  };

  return (
    <div className="shrink-0 border-t border-border bg-background px-4 py-4">
      <div className="mx-auto w-full max-w-chat">
        <div className="chip-scroll mb-3 flex gap-2 overflow-x-auto pb-1">
          {CHIPS.map((chip) => (
            <button
              key={chip}
              type="button"
              disabled={isLoading}
              onClick={() => onChip(chip)}
              className="shrink-0 rounded-full border border-border bg-card px-3 py-1.5 text-xs text-text-secondary transition hover:border-accent hover:text-accent disabled:opacity-50"
            >
              {chip}
            </button>
          ))}
        </div>

        <div className="relative flex items-center rounded-2xl border border-border bg-card pr-2 shadow-card">
          <input
            type="text"
            value={input}
            onChange={(e) => onInputChange(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about HDFC funds, returns, or ratios..."
            disabled={isLoading}
            className="min-w-0 flex-1 bg-transparent py-3.5 pl-4 pr-24 text-body text-text-primary placeholder:text-text-secondary/70 focus:outline-none disabled:opacity-50"
            aria-label="Ask a question"
          />
          <div className="absolute right-2 flex items-center gap-1">
            <button
              type="button"
              disabled
              className="rounded-lg p-2 text-text-secondary opacity-40"
              aria-label="Attach file (not available)"
            >
              <Paperclip className="h-5 w-5" />
            </button>
            <button
              type="button"
              onClick={onSend}
              disabled={isLoading || !input.trim()}
              className="flex h-10 w-10 items-center justify-center rounded-full bg-accent text-background transition hover:bg-success disabled:cursor-not-allowed disabled:opacity-40"
              aria-label="Send message"
            >
              <ArrowUp className="h-5 w-5" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
