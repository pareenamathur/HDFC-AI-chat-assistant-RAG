import type { HealthResponse } from '@/lib/api';

export function formatCorpusSubtitle(health: HealthResponse | null): string {
  const raw = health?.nav_as_of_max || health?.corpus_last_updated;
  if (!raw) return 'Corpus-bound RAG';
  const d = new Date(raw.length === 10 ? `${raw}T00:00:00Z` : raw);
  if (Number.isNaN(d.getTime())) return 'Corpus-bound RAG';
  return `Corpus: ${d.toLocaleString('en-US', { month: 'short', year: 'numeric' })}`;
}

/** Split answer text into segments for green highlights (%, ₹, fund-like caps). */
export function splitAnswerHighlights(text: string): { text: string; highlight: boolean }[] {
  const pattern =
    /(\*\*[^*]+\*\*|\d+(?:\.\d+)?%|₹[\d,]+(?:\.\d+)?|\bHDFC[\w\s-]+(?:Fund|ETF|Index)?\b)/gi;
  const parts: { text: string; highlight: boolean }[] = [];
  let last = 0;
  let m: RegExpExecArray | null;
  const re = new RegExp(pattern.source, pattern.flags);
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) {
      parts.push({ text: text.slice(last, m.index), highlight: false });
    }
    let chunk = m[0];
    if (chunk.startsWith('**') && chunk.endsWith('**')) {
      chunk = chunk.slice(2, -2);
    }
    parts.push({ text: chunk, highlight: true });
    last = m.index + m[0].length;
  }
  if (last < text.length) {
    parts.push({ text: text.slice(last), highlight: false });
  }
  return parts.length ? parts : [{ text, highlight: false }];
}
