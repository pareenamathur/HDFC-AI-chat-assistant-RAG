'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  Send,
  Bot,
  User,
  ExternalLink,
  Clock,
  MessageSquare,
  Menu,
  Loader2,
  WifiOff,
  Wifi,
  AlertCircle,
} from 'lucide-react';
import {
  fetchBackendHealth,
  postQuery,
  apiErrorMessage,
  API_BASE_URL,
  type HealthResponse,
  type QueryResponse,
} from '@/lib/api';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  source?: string;
  source_link?: string;
  last_updated?: string;
}

const SUGGESTED_QUESTIONS = [
  'What is the expense ratio of HDFC Balanced Advantage Fund?',
  'What is the exit load for HDFC Flexi Cap Fund?',
  'How does NAV work for mutual funds?',
];

function ApiStatusPill({
  health,
  loading,
}: {
  health: HealthResponse | null;
  loading: boolean;
}) {
  if (loading) {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full border border-hdfc-border bg-hdfc-elevated px-3 py-1 text-xs font-medium text-gray-300">
        <Loader2 className="h-3.5 w-3.5 animate-spin text-teal-400" />
        Checking API…
      </span>
    );
  }
  if (!health || health.status !== 'healthy') {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full border border-red-500/40 bg-red-950/50 px-3 py-1 text-xs font-medium text-red-200">
        <WifiOff className="h-3.5 w-3.5" />
        API offline
      </span>
    );
  }
  if (health.degraded) {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full border border-amber-500/40 bg-amber-950/40 px-3 py-1 text-xs font-medium text-amber-100">
        <AlertCircle className="h-3.5 w-3.5" />
        Fallback mode — no RAG
      </span>
    );
  }
  if (health.rag_available) {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full border border-teal-500/40 bg-teal-950/40 px-3 py-1 text-xs font-medium text-teal-200">
        <Wifi className="h-3.5 w-3.5" />
        {health.mock_mode ? 'RAG online · demo LLM' : 'RAG online'}
      </span>
    );
  }
  if (health.mock_mode) {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full border border-teal-500/40 bg-teal-950/40 px-3 py-1 text-xs font-medium text-teal-200">
        <Wifi className="h-3.5 w-3.5" />
        Online · demo LLM
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-slate-600 bg-hdfc-elevated px-3 py-1 text-xs font-medium text-gray-300">
      <Wifi className="h-3.5 w-3.5" />
      API online
    </span>
  );
}

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [showWelcome, setShowWelcome] = useState(true);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthLoading, setHealthLoading] = useState(true);

  const refreshHealth = useCallback(async () => {
    const h = await fetchBackendHealth();
    setHealth(h);
    setHealthLoading(false);
    return h;
  }, []);

  useEffect(() => {
    refreshHealth();
    const id = setInterval(refreshHealth, 20000);
    return () => clearInterval(id);
  }, [refreshHealth]);

  const handleSendMessage = async (messageText?: string) => {
    const text = messageText || input.trim();
    if (!text) return;

    const userMessage: Message = { role: 'user', content: text };
    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setShowWelcome(false);
    setIsLoading(true);

    try {
      const history = messages.map((m) => ({
        role: m.role,
        content: m.content,
      }));
      const data: QueryResponse = await postQuery(text, history);

      const assistantMessage: Message = {
        role: 'assistant',
        content: data.answer,
        source: data.source,
        source_link: data.source_link,
        last_updated: data.last_updated,
      };
      setMessages((prev) => [...prev, assistantMessage]);
      void refreshHealth();
    } catch (err) {
      const assistantMessage: Message = {
        role: 'assistant',
        content: apiErrorMessage(err),
      };
      setMessages((prev) => [...prev, assistantMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleClearChat = () => {
    setMessages([]);
    setShowWelcome(true);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      void handleSendMessage();
    }
  };

  return (
    <div className="flex min-h-screen bg-hdfc-bg">
      <aside
        className={`${
          sidebarOpen ? 'w-64' : 'w-0'
        } shrink-0 overflow-hidden border-r border-hdfc-border bg-hdfc-surface transition-all duration-300`}
      >
        <div className="flex h-full min-w-[16rem] flex-col">
          <div className="border-b border-hdfc-border p-4">
            <h1 className="text-lg font-semibold tracking-tight text-white">
              HDFC MF Assistant
            </h1>
            <p className="mt-1 text-xs text-gray-400">Facts only · Not advice</p>
          </div>
          <div className="flex flex-1 flex-col gap-3 p-4">
            <button
              type="button"
              onClick={() => {
                setMessages([]);
                setShowWelcome(true);
                setInput('');
              }}
              className="flex w-full items-center justify-center gap-2 rounded-lg bg-teal-600 px-4 py-2.5 text-sm font-medium text-white shadow-card transition hover:bg-teal-500"
            >
              New chat
            </button>
            <button
              type="button"
              onClick={handleClearChat}
              className="rounded-lg border border-hdfc-border px-4 py-2 text-sm text-gray-300 transition hover:bg-hdfc-elevated"
            >
              Clear conversation
            </button>
          </div>
          <div className="border-t border-hdfc-border p-4 text-xs text-gray-500">
            <p className="font-mono text-[10px] break-all text-gray-600">
              {API_BASE_URL}
            </p>
          </div>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-hdfc-border bg-hdfc-surface/80 px-4 py-3 backdrop-blur">
          <button
            type="button"
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="rounded-lg p-2 text-gray-400 hover:bg-hdfc-elevated hover:text-white"
            aria-label="Toggle sidebar"
          >
            <Menu size={20} />
          </button>
          <div className="flex flex-col items-center gap-1 sm:flex-row sm:gap-3">
            <h2 className="text-sm font-semibold text-white sm:text-base">
              Mutual fund information
            </h2>
            <ApiStatusPill health={health} loading={healthLoading} />
          </div>
          <div className="w-10" />
        </header>

        <main className="custom-scrollbar flex flex-1 flex-col overflow-hidden">
          <div className="flex-1 overflow-y-auto p-4 md:p-8">
            {showWelcome && messages.length === 0 ? (
              <div className="mx-auto max-w-3xl text-center">
                <div className="mb-10 pt-4">
                  <Bot className="mx-auto mb-6 h-14 w-14 text-teal-400" />
                  <h1 className="mb-3 text-3xl font-bold tracking-tight text-white md:text-4xl">
                    HDFC Mutual Fund Assistant
                  </h1>
                  <p className="text-gray-400">
                    Ask factual questions about HDFC schemes — answers use your indexed corpus.
                  </p>
                </div>

                <div className="mb-10 rounded-lg border border-amber-500/30 bg-amber-950/30 px-4 py-3 text-left text-sm text-amber-100/90">
                  <strong className="text-amber-200">Disclaimer:</strong> Informational only.
                  Not investment advice. Consult a qualified advisor before investing.
                </div>

                <div className="mb-6 text-left">
                  <h3 className="mb-4 text-sm font-semibold uppercase tracking-wide text-gray-500">
                    Suggested questions
                  </h3>
                  <div className="grid gap-3 sm:grid-cols-2">
                    {SUGGESTED_QUESTIONS.map((question, index) => (
                      <button
                        key={index}
                        type="button"
                        onClick={() => void handleSendMessage(question)}
                        className="rounded-xl border border-hdfc-border bg-hdfc-elevated p-4 text-left text-sm text-gray-200 shadow-card transition hover:border-teal-500/50 hover:bg-hdfc-surface"
                      >
                        {question}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              <div className="mx-auto max-w-3xl space-y-6">
                {messages.map((message, index) => (
                  <div
                    key={index}
                    className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
                  >
                    <div
                      className={`max-w-[90%] sm:max-w-2xl ${
                        message.role === 'user' ? 'order-2' : 'order-1'
                      }`}
                    >
                      <div
                        className={`flex items-start gap-3 ${
                          message.role === 'user' ? 'flex-row-reverse' : ''
                        }`}
                      >
                        <div
                          className={`mt-0.5 shrink-0 rounded-full p-2 ${
                            message.role === 'user'
                              ? 'bg-teal-600/30 text-teal-300'
                              : 'bg-hdfc-elevated text-gray-400'
                          }`}
                        >
                          {message.role === 'user' ? (
                            <User size={16} />
                          ) : (
                            <Bot size={16} />
                          )}
                        </div>
                        <div
                          className={`rounded-2xl px-4 py-3 text-[15px] leading-relaxed ${
                            message.role === 'user'
                              ? 'bg-teal-700/40 text-white ring-1 ring-teal-500/30'
                              : 'bg-hdfc-elevated text-gray-100 ring-1 ring-white/5'
                          }`}
                        >
                          <p className="whitespace-pre-wrap">{message.content}</p>
                        </div>
                      </div>

                      {message.role === 'assistant' &&
                        (message.source || message.source_link || message.last_updated) && (
                          <div className="mt-2 ml-11 rounded-lg border border-hdfc-border bg-hdfc-surface/80 px-3 py-2 text-xs text-gray-400">
                            <div className="flex flex-wrap items-center gap-4">
                              {message.source_link ? (
                                <a
                                  href={message.source_link}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="inline-flex items-center gap-1 text-teal-400 hover:text-teal-300"
                                >
                                  <ExternalLink size={12} />
                                  {message.source || 'Source'}
                                </a>
                              ) : message.source ? (
                                <span className="inline-flex items-center gap-1">
                                  <MessageSquare size={12} />
                                  {message.source}
                                </span>
                              ) : null}
                              {message.last_updated && (
                                <span className="inline-flex items-center gap-1 text-gray-500">
                                  <Clock size={12} />
                                  {message.last_updated}
                                </span>
                              )}
                            </div>
                          </div>
                        )}
                    </div>
                  </div>
                ))}

                {isLoading && (
                  <div className="flex justify-start">
                    <div className="ml-11 flex items-center gap-2 rounded-2xl bg-hdfc-elevated px-4 py-3 ring-1 ring-white/5">
                      <Loader2 className="h-5 w-5 animate-spin text-teal-400" />
                      <span className="text-sm text-gray-400">Thinking…</span>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>

          <div className="border-t border-hdfc-border bg-hdfc-surface p-4">
            <div className="mx-auto flex max-w-3xl gap-3">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={
                  health?.status === 'healthy'
                    ? 'Ask about HDFC mutual funds…'
                    : 'Waiting for API… you can still type'
                }
                className="min-w-0 flex-1 rounded-xl border border-hdfc-border bg-hdfc-bg px-4 py-3 text-[15px] text-gray-100 placeholder:text-gray-600 focus:border-teal-500/50 focus:outline-none focus:ring-2 focus:ring-teal-500/20 disabled:opacity-50"
                disabled={isLoading}
                aria-label="Message input"
              />
              <button
                type="button"
                onClick={() => void handleSendMessage()}
                disabled={isLoading || !input.trim()}
                className="flex shrink-0 items-center gap-2 rounded-xl bg-teal-600 px-5 py-3 text-sm font-semibold text-white shadow-card transition hover:bg-teal-500 disabled:cursor-not-allowed disabled:bg-gray-700 disabled:text-gray-500"
              >
                <Send size={18} />
                Send
              </button>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
