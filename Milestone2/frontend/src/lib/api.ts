import axios, { AxiosError, AxiosInstance } from 'axios';

/**
 * Normalize public API base URL (no trailing slash, no duplicate slashes).
 * Reads only NEXT_PUBLIC_* (inlined at build time on Vercel).
 */
function normalizeApiBaseUrl(raw: string | undefined): string {
  const v = (raw ?? '').trim();
  if (!v) return 'http://127.0.0.1:8000';
  try {
    const u = new URL(v.startsWith('http') ? v : `https://${v}`);
    u.pathname = u.pathname.replace(/\/+$/, '') || '';
    return u.toString().replace(/\/$/, '');
  } catch {
    return v.replace(/\/+$/, '') || 'http://127.0.0.1:8000';
  }
}

export const API_BASE_URL = normalizeApiBaseUrl(process.env.NEXT_PUBLIC_API_URL);

/** True when NEXT_PUBLIC_API_URL was set at build time (Vercel env). */
export const API_URL_CONFIGURED = Boolean(
  typeof process.env.NEXT_PUBLIC_API_URL === 'string' &&
    process.env.NEXT_PUBLIC_API_URL.trim().length > 0
);

const TIMEOUT_MS = Math.min(
  Math.max(Number(process.env.NEXT_PUBLIC_API_TIMEOUT_MS) || 90000, 15000),
  180000
);

const MAX_RETRIES = 2;

const IS_DEV = process.env.NODE_ENV === 'development';

function logApi(tag: string, detail: Record<string, unknown> = {}) {
  if (IS_DEV) {
    console.info(`[HDFC API] ${tag}`, { base: API_BASE_URL, ...detail });
  }
}

function logApiWarn(tag: string, detail: Record<string, unknown> = {}) {
  console.warn(`[HDFC API] ${tag}`, { base: API_BASE_URL, ...detail });
}

/** User-facing hint when production build likely still points at localhost. */
export function getApiConfigWarning(): string | null {
  if (process.env.NODE_ENV !== 'production') return null;
  if (API_URL_CONFIGURED) return null;
  return 'NEXT_PUBLIC_API_URL is not set for this production build. Add your Railway HTTPS URL in Vercel → Environment Variables, then redeploy.';
}

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

function formatFastApiDetail(data: unknown): string | null {
  if (data == null) return null;
  if (typeof data === 'string') return data;
  const d = data as { detail?: unknown };
  if (typeof d.detail === 'string') return d.detail;
  if (Array.isArray(d.detail)) {
    const parts = d.detail
      .map((x) => {
        if (typeof x === 'string') return x;
        if (x && typeof x === 'object' && 'msg' in x) return String((x as { msg: unknown }).msg);
        return JSON.stringify(x);
      })
      .filter(Boolean);
    if (parts.length) return parts.join(' ');
  }
  return null;
}

const client: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    Accept: 'application/json',
    'Content-Type': 'application/json',
  },
  timeout: TIMEOUT_MS,
  withCredentials: false,
  validateStatus: (s) => s >= 200 && s < 300,
});

if (typeof window !== 'undefined') {
  logApi('client ready', { configured: API_URL_CONFIGURED });
}

export type HealthResponse = {
  status: string;
  message?: string;
  ready?: boolean;
  rag_available?: boolean;
  rag_ready?: boolean;
  schemes_loaded?: number;
  memory_mb?: number | null;
  model_loaded?: boolean;
  chroma_loaded?: boolean;
  mock_mode?: boolean;
  degraded?: boolean;
  index_on_disk?: boolean;
  /** Backend build (e.g. 2.2.11); use to confirm deploy matches Git. */
  api_version?: string;
  /** Last POST /query terminal status on this worker, or null if none yet. */
  last_query_status?: string | null;
};

export async function fetchBackendHealth(): Promise<HealthResponse | null> {
  const url = '/health';
  logApi('GET /health start', { url });
  try {
    const res = await client.get<HealthResponse>(url, { timeout: 12000 });
    logApi('GET /health ok', { status: res.status });
    const data = res.data;
    if (!data || typeof data !== 'object') {
      logApiWarn('GET /health invalid JSON shape');
      return null;
    }
    return data;
  } catch (err) {
    if (axios.isAxiosError(err)) {
      const ax = err as AxiosError;
      logApiWarn('GET /health failed', {
        status: ax.response?.status,
        code: ax.code,
        message: ax.message,
      });
    } else {
      logApiWarn('GET /health failed', { err: String(err) });
    }
    return null;
  }
}

export type SourceRef = {
  title: string;
  url: string;
  scheme_name?: string;
  nav_as_of?: string;
};

export type QueryResponse = {
  answer: string;
  source?: string;
  source_link?: string;
  last_updated?: string;
  sources?: SourceRef[];
  status: string;
};

function normalizeQueryResponse(data: unknown): QueryResponse {
  if (!data || typeof data !== 'object') {
    return { answer: 'Empty response from server.', status: 'error' };
  }
  const d = data as Partial<QueryResponse> & { sources?: unknown };
  const answer =
    typeof d.answer === 'string' && d.answer.trim() ? d.answer : 'No answer field in response.';
  const sources: SourceRef[] = Array.isArray(d.sources)
    ? d.sources
        .filter((s): s is Record<string, unknown> => s != null && typeof s === 'object')
        .map((s) => ({
          title: String(s.title || s.scheme_name || 'Source'),
          url: String(s.url || ''),
          scheme_name: s.scheme_name != null ? String(s.scheme_name) : undefined,
          nav_as_of: s.nav_as_of != null ? String(s.nav_as_of) : undefined,
        }))
        .filter((s) => s.url.startsWith('http'))
    : [];
  return {
    answer,
    source: d.source,
    source_link: d.source_link,
    last_updated: d.last_updated,
    sources,
    status: typeof d.status === 'string' ? d.status : 'ok',
  };
}

export async function postQuery(
  query: string,
  chatHistory: { role: string; content: string }[]
): Promise<QueryResponse> {
  const url = '/query';
  let lastError: unknown;
  for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
    try {
      logApi('POST /query start', { attempt, url });
      const res = await client.post<QueryResponse>(
        url,
        { query, chat_history: chatHistory },
        { timeout: TIMEOUT_MS }
      );
      logApi('POST /query ok', { status: res.status });
      return normalizeQueryResponse(res.data);
    } catch (err) {
      lastError = err;
      if (axios.isAxiosError(err)) {
        const ax = err as AxiosError;
        logApiWarn('POST /query error', {
          attempt,
          status: ax.response?.status,
          code: ax.code,
        });
      }
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
  if (!axios.isAxiosError(err)) {
    return 'An unexpected error occurred.';
  }
  const ax = err as AxiosError;
  const status = ax.response?.status;
  const detail = formatFastApiDetail(ax.response?.data);

  if (detail) return detail;

  if (ax.code === 'ECONNABORTED') {
    return 'Request timed out. The backend may be waking up — try again in a moment.';
  }

  if (!ax.response) {
    const isLocal =
      API_BASE_URL.includes('127.0.0.1') ||
      API_BASE_URL.includes('localhost');
    if (isLocal && process.env.NODE_ENV === 'production') {
      return 'Backend temporarily unavailable: this build is still using the default localhost API URL. Set NEXT_PUBLIC_API_URL to your Railway HTTPS URL in Vercel and redeploy.';
    }
    if (isLocal) {
      return `Cannot reach the API at ${API_BASE_URL}. Start the backend (uvicorn on port 8000) and ensure NEXT_PUBLIC_API_URL in frontend/.env.local matches.`;
    }
    return 'Backend temporarily unavailable (network or CORS). Set Vercel NEXT_PUBLIC_API_URL to your Railway HTTPS URL. On Railway use CORS_ALLOW_ORIGINS=* (default) or your exact Vercel origin.';
  }

  if (status === 503 || status === 502) {
    return 'Assistant is temporarily unavailable (cold start or overload). Retry in a moment.';
  }
  if (status === 404) {
    return 'API path not found (404). Check that the backend exposes POST /query and GET /health.';
  }
  if (status === 405) {
    return 'Method not allowed — the server rejected this request. Verify POST /query on the FastAPI app.';
  }
  if (status === 401 || status === 403) {
    return 'Request was rejected (auth/CORS). Check CORS_ALLOW_ORIGINS on Railway matches your Vercel domain.';
  }
  if (status != null && status >= 500) {
    return 'Server error from the API. Check Railway logs and try again.';
  }

  return 'Something went wrong talking to the server.';
}
