'use client';

import { Trash2 } from 'lucide-react';
import { formatRelativeTime, groupConversations, type Conversation } from '@/lib/chatHistory';

type Props = {
  conversations: Conversation[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
};

export function ChatHistoryList({ conversations, activeId, onSelect, onDelete }: Props) {
  if (conversations.length === 0) {
    return (
      <p className="px-2 py-6 text-center text-xs leading-relaxed text-text-secondary">
        No conversations yet.
        <br />
        Start a new chat to build history.
      </p>
    );
  }

  const groups = groupConversations(conversations);

  return (
    <div className="space-y-3 pb-2">
      {groups.map((group) => (
        <div key={group.label}>
          <p className="sticky top-0 z-10 mb-0.5 bg-sidebar px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-text-secondary/90">
            {group.label}
          </p>
          <ul className="space-y-px">
            {group.items.map((conv) => {
              const active = conv.id === activeId;
              return (
                <li key={conv.id} className="group relative">
                  <button
                    type="button"
                    onClick={() => onSelect(conv.id)}
                    className={[
                      'flex w-full min-w-0 items-center gap-2 rounded-md px-2 py-1.5 text-left transition',
                      active
                        ? 'bg-accent/15 text-text-primary ring-1 ring-accent/35'
                        : 'text-text-primary/85 hover:bg-card',
                    ].join(' ')}
                  >
                    <span className="min-w-0 flex-1 pr-5">
                      <span
                        className={`block truncate text-[13px] leading-tight ${active ? 'font-medium' : ''}`}
                      >
                        {conv.title}
                      </span>
                      <span className="mt-0.5 block truncate text-[10px] text-text-secondary">
                        {formatRelativeTime(conv.updatedAt)}
                      </span>
                    </span>
                  </button>
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      onDelete(conv.id);
                    }}
                    className="absolute right-0.5 top-1/2 -translate-y-1/2 rounded p-1 text-text-secondary opacity-0 transition hover:bg-error/20 hover:text-error group-hover:opacity-100"
                    aria-label={`Delete ${conv.title}`}
                  >
                    <Trash2 className="h-3 w-3" />
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </div>
  );
}
