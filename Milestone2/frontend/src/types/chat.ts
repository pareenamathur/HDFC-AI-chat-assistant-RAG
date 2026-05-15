import type { SourceRef } from '@/lib/api';

export type ChatMessage = {
  role: 'user' | 'assistant';
  content: string;
  source?: string;
  source_link?: string;
  last_updated?: string;
  sources?: SourceRef[];
  status?: string;
};
