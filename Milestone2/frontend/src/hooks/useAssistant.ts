'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import {
  fetchBackendHealth,
  postQuery,
  apiErrorMessage,
  getApiConfigWarning,
  type HealthResponse,
  type QueryResponse,
} from '@/lib/api';
import type { ChatMessage } from '@/types/chat';
import {
  type Conversation,
  generateId,
  titleFromFirstQuery,
  loadConversations,
  saveConversations,
  loadActiveId,
  saveActiveId,
} from '@/lib/chatHistory';

export type { ChatMessage };

export function useAssistant() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthLoading, setHealthLoading] = useState(true);
  const [healthUnreachable, setHealthUnreachable] = useState(false);
  const [hydrated, setHydrated] = useState(false);

  const conversationsRef = useRef(conversations);
  conversationsRef.current = conversations;

  const showWelcome = messages.length === 0;
  const configWarning = getApiConfigWarning();

  useEffect(() => {
    const loaded = loadConversations();
    setConversations(loaded);
    const activeId = loadActiveId();
    if (activeId) {
      const conv = loaded.find((c) => c.id === activeId);
      if (conv) {
        setActiveConversationId(activeId);
        setMessages(conv.messages);
      }
    }
    setHydrated(true);
  }, []);

  const persistConversation = useCallback(
    (id: string, nextMessages: ChatMessage[], title?: string) => {
      const now = new Date().toISOString();
      setConversations((prev) => {
        const existing = prev.find((c) => c.id === id);
        const firstUser = nextMessages.find((m) => m.role === 'user');
        const resolvedTitle =
          title ||
          existing?.title ||
          (firstUser ? titleFromFirstQuery(firstUser.content) : 'New conversation');

        const updated: Conversation = existing
          ? {
              ...existing,
              messages: nextMessages,
              title: resolvedTitle,
              updatedAt: now,
            }
          : {
              id,
              title: resolvedTitle,
              messages: nextMessages,
              createdAt: now,
              updatedAt: now,
            };

        const next = existing
          ? prev.map((c) => (c.id === id ? updated : c))
          : [updated, ...prev];
        saveConversations(next);
        return next;
      });
    },
    []
  );

  const refreshHealth = useCallback(async () => {
    setHealthLoading(true);
    const h = await fetchBackendHealth();
    setHealth(h);
    setHealthUnreachable(h == null);
    setHealthLoading(false);
    return h;
  }, []);

  useEffect(() => {
    void refreshHealth();
    const id = setInterval(() => void refreshHealth(), 20000);
    return () => clearInterval(id);
  }, [refreshHealth]);

  const sendMessage = useCallback(
    async (messageText?: string) => {
      const text = (messageText ?? input).trim();
      if (!text || isLoading) return;

      let convId = activeConversationId;
      if (!convId) {
        convId = generateId();
        setActiveConversationId(convId);
        saveActiveId(convId);
      }

      const userMessage: ChatMessage = { role: 'user', content: text };
      const history = messages.map((m) => ({ role: m.role, content: m.content }));
      const withUser = [...messages, userMessage];

      setMessages(withUser);
      setInput('');
      persistConversation(convId, withUser);
      setIsLoading(true);

      try {
        const data: QueryResponse = await postQuery(text, history);
        const assistantMessage: ChatMessage = {
          role: 'assistant',
          content: data.answer,
          source: data.source,
          source_link: data.source_link,
          last_updated: data.last_updated,
          sources: data.sources,
          status: data.status,
        };
        const complete = [...withUser, assistantMessage];
        setMessages(complete);
        persistConversation(convId, complete);
        void refreshHealth();
      } catch (err) {
        const complete = [
          ...withUser,
          { role: 'assistant' as const, content: apiErrorMessage(err), status: 'error' },
        ];
        setMessages(complete);
        persistConversation(convId, complete);
      } finally {
        setIsLoading(false);
      }
    },
    [input, isLoading, messages, activeConversationId, persistConversation, refreshHealth]
  );

  const newChat = useCallback(() => {
    setActiveConversationId(null);
    saveActiveId(null);
    setMessages([]);
    setInput('');
  }, []);

  const selectConversation = useCallback((id: string) => {
    const conv = conversationsRef.current.find((c) => c.id === id);
    if (!conv) return;
    setActiveConversationId(id);
    saveActiveId(id);
    setMessages(conv.messages);
    setInput('');
  }, []);

  const deleteConversation = useCallback(
    (id: string) => {
      setConversations((prev) => {
        const next = prev.filter((c) => c.id !== id);
        saveConversations(next);
        return next;
      });
      if (activeConversationId === id) {
        setActiveConversationId(null);
        saveActiveId(null);
        setMessages([]);
        setInput('');
      }
    },
    [activeConversationId]
  );

  return {
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
  };
}
