import type { ChatMessage } from '@/types/chat';

export const STORAGE_KEY = 'hdfc-assistant-conversations';
export const ACTIVE_SESSION_KEY = 'hdfc-assistant-active-id';

export type Conversation = {
  id: string;
  title: string;
  messages: ChatMessage[];
  createdAt: string;
  updatedAt: string;
};

const MAX_CONVERSATIONS = 50;

export function generateId(): string {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return `chat-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

/** Derive a short title from the first user message. */
export function titleFromFirstQuery(text: string): string {
  const cleaned = text.trim().replace(/\s+/g, ' ');
  if (!cleaned) return 'New conversation';
  const max = 48;
  if (cleaned.length <= max) return cleaned;
  return `${cleaned.slice(0, max).trim()}…`;
}

export function formatRelativeTime(iso: string): string {
  const then = new Date(iso).getTime();
  const now = Date.now();
  const diffSec = Math.floor((now - then) / 1000);
  if (diffSec < 60) return 'Just now';
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDay = Math.floor(diffHr / 24);
  if (diffDay === 1) return 'Yesterday';
  if (diffDay < 7) return `${diffDay}d ago`;
  return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

export type HistoryGroup = {
  label: string;
  items: Conversation[];
};

export function groupConversations(conversations: Conversation[]): HistoryGroup[] {
  const now = new Date();
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const startOfYesterday = startOfToday - 86400000;
  const startOfWeek = startOfToday - 6 * 86400000;

  const today: Conversation[] = [];
  const yesterday: Conversation[] = [];
  const thisWeek: Conversation[] = [];
  const older: Conversation[] = [];

  for (const c of conversations) {
    const t = new Date(c.updatedAt).getTime();
    if (t >= startOfToday) today.push(c);
    else if (t >= startOfYesterday) yesterday.push(c);
    else if (t >= startOfWeek) thisWeek.push(c);
    else older.push(c);
  }

  const groups: HistoryGroup[] = [];
  if (today.length) groups.push({ label: 'Today', items: today });
  if (yesterday.length) groups.push({ label: 'Yesterday', items: yesterday });
  if (thisWeek.length) groups.push({ label: 'This week', items: thisWeek });
  if (older.length) groups.push({ label: 'Older', items: older });
  return groups;
}

export function loadConversations(): Conversation[] {
  if (typeof window === 'undefined') return [];
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return [];
    return parsed
      .filter(
        (c): c is Conversation =>
          c != null &&
          typeof c === 'object' &&
          typeof (c as Conversation).id === 'string' &&
          Array.isArray((c as Conversation).messages)
      )
      .map((c) => ({
        id: c.id,
        title: String(c.title || 'Untitled chat'),
        messages: c.messages,
        createdAt: String(c.createdAt || c.updatedAt || new Date().toISOString()),
        updatedAt: String(c.updatedAt || c.createdAt || new Date().toISOString()),
      }))
      .sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime())
      .slice(0, MAX_CONVERSATIONS);
  } catch {
    return [];
  }
}

export function saveConversations(conversations: Conversation[]): void {
  if (typeof window === 'undefined') return;
  const sorted = [...conversations]
    .sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime())
    .slice(0, MAX_CONVERSATIONS);
  localStorage.setItem(STORAGE_KEY, JSON.stringify(sorted));
}

export function loadActiveId(): string | null {
  if (typeof window === 'undefined') return null;
  return sessionStorage.getItem(ACTIVE_SESSION_KEY);
}

export function saveActiveId(id: string | null): void {
  if (typeof window === 'undefined') return;
  if (id) sessionStorage.setItem(ACTIVE_SESSION_KEY, id);
  else sessionStorage.removeItem(ACTIVE_SESSION_KEY);
}
