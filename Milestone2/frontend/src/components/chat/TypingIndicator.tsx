'use client';

export function TypingIndicator() {
  return (
    <div className="mx-auto flex w-full max-w-chat items-center gap-2 px-4 pb-4">
      <div className="flex gap-1">
        <span className="h-2 w-2 animate-bounce rounded-full bg-accent [animation-delay:0ms]" />
        <span className="h-2 w-2 animate-bounce rounded-full bg-accent [animation-delay:150ms]" />
        <span className="h-2 w-2 animate-bounce rounded-full bg-accent [animation-delay:300ms]" />
      </div>
      <span className="text-sm text-text-secondary">Thinking…</span>
    </div>
  );
}
