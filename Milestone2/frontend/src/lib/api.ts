import axios, { AxiosError } from 'axios';

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, '') || 'http://127.0.0.1:8000';

const TIMEOUT_MS = Math.min(
  Math.max(Number(process.env.NEXT_PUBLIC_API_TIMEOUT_MS) || 90000, 15000),
  180000
);

const MAX_RETRIES = 2;

function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}

function shouldRetry(err: unknown): boolean {
  if (!axios.isAxiosError(err)) return false;
  const ax = err as AxiosError;
  const status = ax.response?.status;
  if (status === 503 || status === 502 || status === 429) return true;
  if (!ax.response && ax.code === 'ECONNABORTED') return true;
  return ax.message?.includes('Network Error') ?? false;
}

export type HealthResponse = {
  status: string;
  message?: string;
  ready?: boolean;
  rag_available?: boolean;
  /** True after first successful embedding-backed query (not only Chroma open). */
  rag_ready?: boolean;
  schemes_loaded?: number;
  memory_mb?: number | null;
  model_loaded?: boolean;
  chroma_loaded?: boolean;
  mock_mode?: boolean;
  degraded?: boolean;
};

export async function fetchBackendHealth(): Promise<HealthResponse | null> {
  try {
    const res = await axios.get<HealthResponse>(`${API_BASE_URL}/health`, {
      timeout: 12000,
      validateStatus: (s) => s < 500,
    });
    return res.data;
  } catch {
    return null;
  }
}

export type QueryResponse = {
  answer: string;
  source?: string;
  source_link?: string;
  last_updated?: string;
  status: string;
};

export async function postQuery(
  query: string,
  chatHistory: { role: string; content: string }[]
): Promise<QueryResponse> {
  let lastError: unknown;
  for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
    try {
      const res = await axios.post<QueryResponse>(
        `${API_BASE_URL}/query`,
        { query, chat_history: chatHistory },
        { timeout: TIMEOUT_MS, headers: { 'Content-Type': 'application/json' } }
      );
      return res.data;
    } catch (err) {
      lastError = err;
      if (attempt < MAX_RETRIES && shouldRetry(err)) {
        await sleep(800 * (attempt + 1));
        continue;
      }
      throw err;
    }
  }
  throw lastError;
}

export function apiErrorMessage(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const detail = err.response?.data as { detail?: string } | undefined;
    if (typeof detail?.detail === 'string') return detail.detail;
    if (err.code === 'ECONNABORTED') return 'Request timed out. The backend may be waking up — try again.';
    if (!err.response) return 'Cannot reach the API. Check NEXT_PUBLIC_API_URL and Railway status.';
    return err.response.status === 503
      ? 'Assistant is temporarily unavailable (cold start or overload). Retry in a moment.'
      : 'Something went wrong talking to the server.';
  }
  return 'An unexpected error occurred.';
}
