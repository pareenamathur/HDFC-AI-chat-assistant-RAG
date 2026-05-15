'use client';

import { Plus, TrendingUp, X, LifeBuoy, Shield, MessageSquareText } from 'lucide-react';
import { ChatHistoryList } from '@/components/sidebar/ChatHistoryList';
import type { Conversation } from '@/lib/chatHistory';

type Props = {
  open: boolean;
  onClose: () => void;
  onNewChat: () => void;
  conversations: Conversation[];
  activeConversationId: string | null;
  onSelectConversation: (id: string) => void;
  onDeleteConversation: (id: string) => void;
  hydrated: boolean;
};

export function Sidebar({
  open,
  onClose,
  onNewChat,
  conversations,
  activeConversationId,
  onSelectConversation,
  onDeleteConversation,
  hydrated,
}: Props) {
  return (
    <>
      {open && (
        <button
          type="button"
          className="fixed inset-0 z-40 bg-black/60 lg:hidden"
          aria-label="Close sidebar"
          onClick={onClose}
        />
      )}

      <aside
        className={[
          'fixed bottom-0 left-0 top-16 z-50 flex h-[calc(100dvh-4rem)] w-sidebar flex-col border-r border-border bg-sidebar transition-transform duration-200',
          'lg:static lg:z-0 lg:h-full lg:min-h-0 lg:translate-x-0',
          open ? 'translate-x-0' : '-translate-x-full lg:translate-x-0',
        ].join(' ')}
      >
        {/* Mobile drawer header */}
        <div className="flex shrink-0 items-center justify-between border-b border-border px-3 py-2.5 lg:hidden">
          <span className="text-sm font-semibold text-text-primary">Menu</span>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1.5 text-text-secondary hover:bg-card"
            aria-label="Close menu"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* TOP: brand + new chat */}
        <div className="shrink-0 space-y-3 border-b border-border px-3 py-3">
          <div className="hidden items-center gap-2 lg:flex">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-accent/30 bg-accent/10">
              <Shield className="h-4 w-4 text-accent" />
            </div>
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold text-text-primary">HDFC Assistant</p>
              <p className="text-[10px] text-text-secondary">Mutual fund Q&amp;A</p>
            </div>
          </div>

          <button
            type="button"
            onClick={() => {
              onNewChat();
              onClose();
            }}
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-accent px-3 py-2.5 text-sm font-semibold text-background transition hover:bg-success active:scale-[0.98]"
          >
            <Plus className="h-4 w-4" />
            New chat
          </button>
        </div>

        {/* MIDDLE: recent chats — primary, flex-grow scroll */}
        <section className="flex min-h-0 flex-1 flex-col overflow-hidden px-2 py-2">
          <div className="mb-1.5 flex shrink-0 items-center justify-between px-1">
            <h2 className="text-[11px] font-semibold uppercase tracking-wider text-text-secondary">
              Recent chats
            </h2>
            {hydrated && conversations.length > 0 && (
              <span className="text-[10px] text-text-secondary/80">{conversations.length}</span>
            )}
          </div>

          <div className="sidebar-history-scroll min-h-0 flex-1 overflow-y-auto overscroll-contain px-0.5">
            {hydrated ? (
              <ChatHistoryList
                conversations={conversations}
                activeId={activeConversationId}
                onSelect={(id) => {
                  onSelectConversation(id);
                  onClose();
                }}
                onDelete={onDeleteConversation}
              />
            ) : (
              <p className="px-2 py-4 text-xs text-text-secondary">Loading history…</p>
            )}
          </div>
        </section>

        {/* BOTTOM: compact links + premium */}
        <footer className="shrink-0 border-t border-border px-3 py-2">
          <nav className="space-y-0.5">
            <button
              type="button"
              onClick={() => {
                onNewChat();
                onClose();
              }}
              className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-xs text-text-secondary transition hover:bg-card hover:text-text-primary"
            >
              <TrendingUp className="h-3.5 w-3.5 shrink-0" />
              Market insights
            </button>
            <a
              href="https://www.hdfcfund.com/contact-us"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 rounded-md px-2 py-1.5 text-xs text-text-secondary transition hover:bg-card hover:text-text-primary"
            >
              <LifeBuoy className="h-3.5 w-3.5 shrink-0" />
              Support
            </a>
            <a
              href="https://www.hdfcfund.com/privacy-policy"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 rounded-md px-2 py-1.5 text-xs text-text-secondary transition hover:bg-card hover:text-text-primary"
            >
              <Shield className="h-3.5 w-3.5 shrink-0" />
              Privacy
            </a>
          </nav>

          <div className="mt-2 flex items-center gap-2 rounded-lg border border-border/80 bg-card/50 px-2 py-1.5">
            <MessageSquareText className="h-3.5 w-3.5 shrink-0 text-accent" />
            <div className="min-w-0 flex-1">
              <p className="truncate text-[10px] font-medium text-text-primary">Premium</p>
              <p className="truncate text-[9px] text-text-secondary">Advanced analytics soon</p>
            </div>
          </div>
        </footer>
      </aside>
    </>
  );
}
