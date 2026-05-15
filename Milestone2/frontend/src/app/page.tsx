'use client';

import { useState, useRef, useCallback, useEffect } from 'react';
import { TopHeader } from '@/components/layout/TopHeader';
import { Sidebar } from '@/components/layout/Sidebar';
import { HeroSection } from '@/components/welcome/HeroSection';
import { MessageList } from '@/components/chat/MessageList';
import { ChatComposer } from '@/components/chat/ChatComposer';
import { TypingIndicator } from '@/components/chat/TypingIndicator';
import { useAssistant } from '@/hooks/useAssistant';

export default function Home() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  const {
    messages,
    input,
    setInput,
    isLoading,
    sendMessage,
    newChat,
    selectConversation,
    deleteConversation,
    conversations,
    activeConversationId,
    hydrated,
    showWelcome,
    health,
    healthLoading,
    healthUnreachable,
    refreshHealth,
    configWarning,
  } = useAssistant();

  const scrollToTop = useCallback(() => {
    scrollRef.current?.scrollTo({ top: 0, behavior: 'smooth' });
  }, []);

  useEffect(() => {
    if (!scrollRef.current) return;
    scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages, isLoading, activeConversationId]);

  return (
    <div className="flex h-dvh max-h-dvh flex-col overflow-hidden bg-background">
      {configWarning && (
        <div className="shrink-0 border-b border-warning/30 bg-warning/10 px-4 py-2 text-center text-xs text-warning">
          {configWarning}
        </div>
      )}

      {!healthLoading && healthUnreachable && (
        <div className="flex shrink-0 flex-wrap items-center justify-center gap-2 border-b border-border bg-card px-4 py-2 text-xs text-text-secondary">
          <span>Backend temporarily unavailable — check API URL and CORS.</span>
          <button
            type="button"
            onClick={() => void refreshHealth()}
            className="rounded-full border border-accent px-3 py-1 text-xs font-medium text-accent hover:bg-accent/10"
          >
            Retry
          </button>
        </div>
      )}

      <TopHeader
        health={health}
        healthLoading={healthLoading}
        onScrollTop={scrollToTop}
        onMenuOpen={() => setSidebarOpen(true)}
      />

      <div className="flex min-h-0 flex-1">
        <Sidebar
          open={sidebarOpen}
          onClose={() => setSidebarOpen(false)}
          onNewChat={newChat}
          conversations={conversations}
          activeConversationId={activeConversationId}
          onSelectConversation={selectConversation}
          onDeleteConversation={deleteConversation}
          hydrated={hydrated}
        />

        <main className="flex min-h-0 min-w-0 flex-1 flex-col bg-background">
          <div
            ref={scrollRef}
            className="scrollbar-thin min-h-0 flex-1 overflow-y-auto overscroll-y-contain"
          >
            {showWelcome && <HeroSection onSuggestion={(t) => void sendMessage(t)} />}
            {messages.length > 0 && <MessageList messages={messages} />}
            {isLoading && <TypingIndicator />}
          </div>

          <ChatComposer
            input={input}
            isLoading={isLoading}
            onInputChange={setInput}
            onSend={() => void sendMessage()}
            onChip={(t) => void sendMessage(t)}
          />
        </main>
      </div>
    </div>
  );
}
