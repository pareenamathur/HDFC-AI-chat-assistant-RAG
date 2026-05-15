'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  fetchBackendHealth,
  postQuery,
  apiErrorMessage,
  API_BASE_URL,
  getApiConfigWarning,
  type HealthResponse,
  type QueryResponse,
} from '@/lib/api';

interface SourceRef {
  title: string;
  url: string;
  scheme_name?: string;
  nav_as_of?: string;
}

interface Message {
  role: 'user' | 'assistant';
  content: string;
  source?: string;
  source_link?: string;
  last_updated?: string;
  sources?: SourceRef[];
  status?: string;
}

const STITCH_SUGGESTIONS = [
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

const QUICK_CHIPS = ['Expense ratio?', 'NAV?', 'Exit load?', 'Top 10 holdings?', 'Comparison?'];

function MsIcon({
  name,
  className = '',
  fill = false,
}: {
  name: string;
  className?: string;
  fill?: boolean;
}) {
  return (
    <span
      className={`material-symbols-outlined ${className}`}
      style={
        fill
          ? { fontVariationSettings: "'FILL' 1, 'wght' 400, 'GRAD' 0, 'opsz' 24" }
          : undefined
      }
      aria-hidden
    >
      {name}
    </span>
  );
}

function ApiStatusPill({
  health,
  loading,
}: {
  health: HealthResponse | null;
  loading: boolean;
}) {
  if (loading) {
    return (
      <div className="flex max-w-full items-center gap-xs rounded-full border border-outline bg-surface-container-high px-sm py-xs">
        <span className="relative flex h-2 w-2 shrink-0">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-on-surface-variant opacity-40" />
          <span className="relative inline-flex h-2 w-2 rounded-full bg-on-surface-variant" />
        </span>
        <span className="truncate text-label-md text-on-surface-variant">Checking…</span>
      </div>
    );
  }
  if (!health || health.status !== 'healthy') {
    return (
      <div className="flex max-w-full items-center gap-xs rounded-full border border-error-container bg-surface-container-high px-sm py-xs">
        <MsIcon name="wifi_off" className="shrink-0 text-[16px] text-error" />
        <span className="truncate text-label-md text-error">Unavailable</span>
      </div>
    );
  }
  if (health.degraded) {
    return (
      <div className="flex max-w-full items-center gap-xs rounded-full border border-secondary bg-surface-container-high px-sm py-xs">
        <MsIcon name="error" className="shrink-0 text-[16px] text-secondary" />
        <span className="truncate text-label-md text-on-surface">Fallback</span>
      </div>
    );
  }
  const n = health.schemes_loaded ?? 0;
  const funds = n > 0 ? `${n} funds` : 'live';
  const short =
    health.rag_available && health.rag_ready
      ? `Online · ${funds}`
      : health.rag_available
        ? `Warming · ${funds}`
        : health.index_on_disk
          ? `Index · ${funds}`
          : `Online · ${funds}`;
  const long =
    health.rag_available && health.rag_ready
      ? `System online (${funds})`
      : health.rag_available
        ? `System online (${funds}) · warming`
        : health.index_on_disk
          ? `Index ready (${funds})`
          : `System online (${funds})`;
  return (
    <div className="flex max-w-full items-center gap-xs rounded-full border border-outline bg-surface-container-high px-sm py-xs">
      <span className="relative flex h-2 w-2 shrink-0">
        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary opacity-75" />
        <span className="relative inline-flex h-2 w-2 rounded-full bg-primary" />
      </span>
      <span className="hidden truncate text-label-md text-on-surface sm:inline" title={long}>
        {long}
        {health.mock_mode ? ' · demo LLM' : ''}
      </span>
      <span className="truncate text-label-md text-on-surface sm:hidden" title={long}>
        {short}
        {health.mock_mode ? ' · demo' : ''}
      </span>
    </div>
  );
}

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [showWelcome, setShowWelcome] = useState(true);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthLoading, setHealthLoading] = useState(true);
  const [healthUnreachable, setHealthUnreachable] = useState(false);

  const configWarning = getApiConfigWarning();

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

  const handleSendMessage = async (messageText?: string) => {
    const text = (messageText || input).trim();
    if (!text) return;

    const userMessage: Message = { role: 'user', content: text };
    const history = messages.map((m) => ({
      role: m.role,
      content: m.content,
    }));

    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setShowWelcome(false);
    setIsLoading(true);

    try {
      const data: QueryResponse = await postQuery(text, history);
      const assistantMessage: Message = {
        role: 'assistant',
        content: data.answer,
        source: data.source,
        source_link: data.source_link,
        last_updated: data.last_updated,
        sources: data.sources,
        status: data.status,
      };
      setMessages((prev) => [...prev, assistantMessage]);
      void refreshHealth();
    } catch (err) {
      const assistantMessage: Message = {
        role: 'assistant',
        content: apiErrorMessage(err),
        status: 'error',
      };
      setMessages((prev) => [...prev, assistantMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const newChat = () => {
    setMessages([]);
    setShowWelcome(true);
    setInput('');
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      void handleSendMessage();
    }
  };

  const assistantBubbleClass = (status?: string) => {
    if (status === 'error' || status === 'timeout') {
      return 'border border-error-container bg-[#1A0000] text-on-surface';
    }
    if (status === 'degraded') {
      return 'border border-[#633f00] bg-[#1A1200] text-on-surface';
    }
    return 'border border-outline border-l-[3px] border-l-primary bg-surface text-on-surface shadow-sm';
  };

  return (
    <div className="flex h-dvh max-h-dvh min-h-0 flex-col overflow-hidden bg-background">
      {configWarning && (
        <div className="shrink-0 border-b border-disclaimer/40 bg-disclaimer/15 px-md py-sm text-center text-label-md text-disclaimer">
          {configWarning}
        </div>
      )}

      {!healthLoading && healthUnreachable && (
        <div className="flex shrink-0 flex-wrap items-center justify-center gap-2 border-b border-outline bg-surface-container-high px-md py-sm text-body-md text-on-surface-variant">
          <span>Backend temporarily unavailable — check API URL and CORS.</span>
          <button
            type="button"
            onClick={() => void refreshHealth()}
            className="rounded-full border border-primary px-md py-xs text-label-md font-semibold text-primary transition hover:bg-primary/10"
          >
            Retry health
          </button>
        </div>
      )}

      <div className="shrink-0 border-b border-disclaimer/20 bg-disclaimer/10 py-base text-center">
        <p className="text-label-sm tracking-wide text-disclaimer">
          Important: Facts-only assistant · Not investment advice
        </p>
      </div>

      <header className="flex w-full shrink-0 flex-wrap items-center justify-between gap-y-sm border-b border-outline bg-surface-container-low px-md py-sm">
        <div className="flex min-w-0 max-w-full flex-1 items-center gap-sm">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-primary/20 bg-primary-container/10">
            <MsIcon name="shield" className="text-primary text-[22px]" fill />
          </div>
          <div className="min-w-0 flex-1">
            <h1 className="truncate text-headline-md leading-tight text-primary">HDFC Assistant</h1>
            <p className="truncate text-label-sm tracking-widest text-on-surface-variant">
              CORPUS-BOUND RAG
            </p>
          </div>
        </div>
        <div className="flex w-full min-w-0 shrink-0 items-center justify-end gap-sm sm:w-auto sm:max-w-[55%]">
          <ApiStatusPill health={health} loading={healthLoading} />
          <div className="hidden shrink-0 gap-xs sm:flex">
            <button
              type="button"
              className="rounded-lg p-xs text-on-surface-variant transition hover:bg-surface-container-highest"
              aria-label="Scroll to top"
              onClick={() => document.getElementById('chat-scroll')?.scrollTo({ top: 0, behavior: 'smooth' })}
            >
              <MsIcon name="history" />
            </button>
            <a
              href="https://www.hdfcfund.com/"
              target="_blank"
              rel="noopener noreferrer"
              className="rounded-lg p-xs text-on-surface-variant transition hover:bg-surface-container-highest"
              aria-label="Help"
            >
              <MsIcon name="help_outline" />
            </a>
          </div>
        </div>
      </header>

      <main className="flex min-h-0 flex-1 flex-col overflow-hidden md:flex-row">
        <aside className="hidden w-64 min-w-0 shrink-0 flex-col overflow-y-auto border-r border-outline bg-surface-container-low p-md md:flex">
          <div className="mb-xl space-y-base">
            <button
              type="button"
              onClick={newChat}
              className="flex w-full items-center gap-sm rounded-lg bg-primary-container p-sm text-left text-label-md font-bold text-on-primary-container transition hover:opacity-90"
            >
              <MsIcon name="add_comment" className="shrink-0 text-[20px]" />
              New chat
            </button>
            <nav className="space-y-base pt-md">
              <button
                type="button"
                onClick={() => document.getElementById('chat-scroll')?.scrollTo({ top: 0, behavior: 'smooth' })}
                className="flex w-full items-center gap-sm rounded-lg p-sm text-left text-label-md text-on-surface-variant transition hover:bg-surface-container-highest"
              >
                <MsIcon name="history" className="shrink-0 text-[20px]" />
                History
              </button>
              <button
                type="button"
                onClick={newChat}
                className="flex w-full items-center gap-sm rounded-lg p-sm text-left text-label-md text-on-surface-variant transition hover:bg-surface-container-highest"
              >
                <MsIcon name="trending_up" className="shrink-0 text-[20px]" />
                Market insights
              </button>
              <button
                type="button"
                className="flex w-full cursor-default items-center gap-sm rounded-lg p-sm text-left text-label-md text-on-surface-variant/60"
                aria-disabled
              >
                <MsIcon name="settings" className="shrink-0 text-[20px]" />
                Settings
              </button>
            </nav>
          </div>
          <div className="mt-auto border-t border-outline pt-md">
            <div className="mb-md rounded-xl border border-outline bg-surface-container px-sm py-md">
              <p className="mb-xs text-label-sm font-bold text-primary">Corpus-backed</p>
              <p className="mb-md text-label-md text-on-surface-variant">
                Answers from your deployed index — not live market data.
              </p>
              <a
                href="https://www.hdfcfund.com/"
                target="_blank"
                rel="noopener noreferrer"
                className="block w-full rounded-full bg-primary py-sm text-center text-label-md font-bold text-background transition hover:opacity-90"
              >
                HDFC Fund site
              </a>
            </div>
            <div className="flex flex-col gap-xs">
              <a
                href="https://www.hdfcfund.com/contact-us"
                className="flex items-center gap-sm px-sm py-xs text-label-sm text-on-surface-variant transition hover:text-on-surface"
              >
                <MsIcon name="contact_support" className="shrink-0 text-[18px]" />
                Support
              </a>
              <a
                href="https://www.hdfcfund.com/privacy-policy"
                className="flex items-center gap-sm px-sm py-xs text-label-sm text-on-surface-variant transition hover:text-on-surface"
              >
                <MsIcon name="policy" className="shrink-0 text-[18px]" />
                Privacy
              </a>
            </div>
            <p className="mt-md break-all text-[10px] text-on-surface-variant/70">{API_BASE_URL}</p>
          </div>
        </aside>

        <section className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden pb-[calc(4.5rem+env(safe-area-inset-bottom,0px))] md:pb-0">
          <div
            id="chat-scroll"
            className="custom-scrollbar min-h-0 flex-1 overflow-y-auto overscroll-y-contain px-md py-md md:py-xl"
          >
            <div className="mx-auto w-full max-w-container-max space-y-lg md:space-y-xl">
              {showWelcome && messages.length === 0 && (
                <div className="flex flex-col items-center border-b border-outline/50 py-lg text-center md:py-xl">
                  <div className="mb-md flex h-16 w-16 shrink-0 items-center justify-center rounded-2xl border border-outline bg-surface-container-high md:mb-lg">
                    <MsIcon name="account_balance" className="text-[40px] text-primary" />
                  </div>
                  <h2 className="mb-xs px-2 text-headline-lg text-on-surface">
                    Ask me anything about HDFC Mutual Funds
                  </h2>
                  <p className="mb-lg max-w-md px-2 text-body-md text-on-surface-variant md:mb-xl">
                    Accurate, corpus-driven answers from your indexed FAQ. Facts-only — not personalized advice.
                  </p>
                  <div className="grid w-full grid-cols-1 gap-md md:grid-cols-3">
                    {STITCH_SUGGESTIONS.map((s) => (
                      <button
                        key={s.label}
                        type="button"
                        onClick={() => void handleSendMessage(s.text)}
                        className="rounded-xl border border-outline bg-surface-container-low p-md text-left transition hover:border-primary md:p-lg"
                      >
                        <p className="mb-xs text-label-md font-bold text-primary">{s.label}</p>
                        <p className="break-words text-body-md text-on-surface">&ldquo;{s.text}&rdquo;</p>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              <div className="space-y-md md:space-y-lg">
                {messages.map((message, index) => (
                  <div key={index} className="min-w-0">
                    {message.role === 'user' ? (
                      <div className="flex justify-end">
                        <div className="max-w-[min(100%,32rem)] break-words rounded-2xl rounded-tr-base bg-primary px-md py-sm text-body-md font-medium text-background sm:px-lg">
                          {message.content}
                        </div>
                      </div>
                    ) : (
                      <div className="flex min-w-0 justify-start">
                        <div className="flex min-w-0 max-w-full gap-sm sm:max-w-[min(85%,40rem)] sm:gap-md">
                          <div className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-primary/30 bg-primary-container/10 sm:mt-base">
                            {message.status === 'error' || message.status === 'timeout' ? (
                              <MsIcon name="warning" className="text-[18px] text-error" />
                            ) : message.status === 'degraded' ? (
                              <MsIcon name="block" className="text-[18px] text-secondary" />
                            ) : (
                              <MsIcon name="shield" className="text-[18px] text-primary" fill />
                            )}
                          </div>
                          <div className="min-w-0 flex-1 space-y-sm">
                            <div
                              className={`break-words rounded-2xl rounded-tl-base p-md text-body-lg leading-relaxed sm:p-lg ${assistantBubbleClass(message.status)}`}
                            >
                              <p className="whitespace-pre-wrap break-words">{message.content}</p>
                            </div>
                            {(message.sources?.length ||
                              message.source ||
                              message.source_link ||
                              message.last_updated) &&
                              message.status !== 'error' && (
                                <div className="flex flex-wrap gap-xs">
                                  {(message.sources?.length
                                    ? message.sources
                                    : message.source_link
                                      ? [
                                          {
                                            title: message.source || 'Go to source',
                                            url: message.source_link,
                                          },
                                        ]
                                      : []
                                  ).map((src, i) => (
                                    <a
                                      key={`${src.url}-${i}`}
                                      href={src.url}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className="flex max-w-full items-center gap-xs rounded-full border border-outline bg-surface-container-low px-sm py-xs text-label-md text-on-surface-variant transition hover:border-primary"
                                    >
                                      <MsIcon name="open_in_new" className="shrink-0 text-[14px]" />
                                      <span className="truncate">{src.title || 'Go to source'}</span>
                                    </a>
                                  ))}
                                  {!message.sources?.length && !message.source_link && message.source && (
                                    <span className="flex max-w-full items-center gap-xs rounded-full border border-outline bg-surface-container-low px-sm py-xs text-label-md text-on-surface-variant">
                                      <MsIcon name="article" className="shrink-0 text-[14px]" />
                                      <span className="truncate">{message.source}</span>
                                    </span>
                                  )}
                                  {message.last_updated && (
                                    <span className="flex items-center gap-xs rounded-full border border-outline bg-surface-container-low px-sm py-xs text-label-md text-on-surface-variant">
                                      <MsIcon name="schedule" className="shrink-0 text-[14px]" />
                                      NAV as of {message.last_updated}
                                    </span>
                                  )}
                                </div>
                              )}
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                ))}

                {isLoading && (
                  <div className="flex items-center gap-sm px-1">
                    <div className="flex gap-1">
                      <span className="h-1.5 w-1.5 rounded-full bg-primary opacity-40" />
                      <span className="h-1.5 w-1.5 rounded-full bg-primary opacity-70" />
                      <span className="h-1.5 w-1.5 rounded-full bg-primary" />
                    </div>
                    <span className="text-label-md italic text-on-surface-variant">Thinking…</span>
                  </div>
                )}
              </div>
            </div>
          </div>

          <div className="shrink-0 border-t border-outline bg-surface-container-low p-md pb-[max(0.75rem,env(safe-area-inset-bottom))]">
            <div className="mx-auto w-full max-w-container-max space-y-md">
              <div className="no-scrollbar flex gap-xs overflow-x-auto pb-base">
                {QUICK_CHIPS.map((chip) => (
                  <button
                    key={chip}
                    type="button"
                    onClick={() => void handleSendMessage(chip)}
                    disabled={isLoading}
                    className="shrink-0 rounded-full border border-outline bg-surface-container px-md py-xs text-label-md text-on-surface transition hover:border-primary disabled:opacity-50"
                  >
                    {chip}
                  </button>
                ))}
              </div>
              <div className="relative flex min-w-0 items-center">
                <input
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Ask about HDFC funds, returns, or ratios…"
                  disabled={isLoading}
                  className="min-w-0 w-full rounded-full border border-outline bg-background py-3 pl-4 pr-[7.5rem] text-body-md text-on-surface placeholder:text-on-surface-variant/70 transition focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary disabled:opacity-50 sm:py-lg sm:pl-xl sm:pr-32"
                  aria-label="Ask a question"
                />
                <div className="absolute right-1 flex shrink-0 items-center gap-0 sm:right-xs sm:gap-xs">
                  <button
                    type="button"
                    className="p-2 text-on-surface-variant hover:text-on-surface sm:p-sm"
                    aria-label="Attach (not available)"
                    disabled
                  >
                    <MsIcon name="attach_file" className="opacity-40" />
                  </button>
                  <button
                    type="button"
                    onClick={() => void handleSendMessage()}
                    disabled={isLoading || !input.trim()}
                    className="flex h-11 w-11 items-center justify-center rounded-full bg-primary text-background transition hover:opacity-90 active:scale-95 disabled:cursor-not-allowed disabled:bg-surface-container-highest disabled:opacity-50 sm:h-12 sm:w-12"
                    aria-label="Send"
                  >
                    <MsIcon name="arrow_upward" className="font-bold" />
                  </button>
                </div>
              </div>
              <p className="truncate text-center text-[10px] uppercase tracking-tighter text-on-surface-variant/50">
                API · {API_BASE_URL.replace(/^https?:\/\//, '')}
              </p>
            </div>
          </div>
        </section>
      </main>

      <nav className="fixed bottom-0 left-0 z-40 flex w-full items-center justify-around border-t border-outline bg-surface-container-high py-xs pb-[max(0.25rem,env(safe-area-inset-bottom))] pt-xs px-lg md:hidden">
        <div className="flex flex-col items-center justify-center rounded-full bg-primary-container px-4 py-1 text-on-primary-container">
          <MsIcon name="chat_bubble" fill className="text-[22px]" />
          <span className="text-label-sm">Assistant</span>
        </div>
        <a
          href="https://www.hdfcfund.com/"
          className="flex flex-col items-center justify-center text-on-surface-variant hover:text-primary"
        >
          <MsIcon name="account_balance_wallet" className="text-[22px]" />
          <span className="text-label-sm">Funds</span>
        </a>
        <button
          type="button"
          onClick={newChat}
          className="flex flex-col items-center justify-center text-on-surface-variant hover:text-primary"
        >
          <MsIcon name="search" className="text-[22px]" />
          <span className="text-label-sm">New</span>
        </button>
      </nav>
    </div>
  );
}
