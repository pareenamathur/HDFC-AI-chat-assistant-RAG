'use client';

import { Bot, AlertCircle } from 'lucide-react';
import { SourceLinks } from '@/components/chat/SourceLinks';
import { splitAnswerHighlights } from '@/lib/format';
import type { ChatMessage } from '@/types/chat';

type Props = {
  messages: ChatMessage[];
};

function AssistantContent({ content }: { content: string }) {
  const parts = splitAnswerHighlights(content);
  return (
    <p className="whitespace-pre-wrap break-words text-body leading-relaxed">
      {parts.map((p, i) =>
        p.highlight ? (
          <span key={i} className="font-semibold text-accent">
            {p.text}
          </span>
        ) : (
          <span key={i}>{p.text}</span>
        )
      )}
    </p>
  );
}

function bubbleClass(status?: string) {
  if (status === 'error' || status === 'timeout') {
    return 'border-error/40 bg-error-bg';
  }
  if (status === 'degraded') {
    return 'border-warning/40 bg-warning-bg';
  }
  return 'border-accent/30 bg-card';
}

export function MessageList({ messages }: Props) {
  return (
    <div className="mx-auto w-full max-w-chat space-y-6 px-4 py-6">
      {messages.map((message, index) =>
        message.role === 'user' ? (
          <div key={index} className="flex justify-end">
            <div className="max-w-[70%] rounded-2xl rounded-br-md bg-accent px-4 py-3 text-body text-background shadow-card">
              <p className="whitespace-pre-wrap break-words">{message.content}</p>
            </div>
          </div>
        ) : (
          <div key={index} className="flex justify-start gap-3">
            <div className="mt-1 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-accent/30 bg-accent/10">
              {message.status === 'error' ? (
                <AlertCircle className="h-4 w-4 text-error" />
              ) : (
                <Bot className="h-4 w-4 text-accent" />
              )}
            </div>
            <div className="min-w-0 max-w-[85%] sm:max-w-[75%]">
              <div
                className={`rounded-2xl rounded-tl-md border px-4 py-3 shadow-card ${bubbleClass(message.status)}`}
              >
                <AssistantContent content={message.content} />
              </div>
              {message.status !== 'error' && (
                <SourceLinks
                  sources={message.sources}
                  source={message.source}
                  source_link={message.source_link}
                  last_updated={message.last_updated}
                />
              )}
            </div>
          </div>
        )
      )}
    </div>
  );
}
