import { getApiBase, resolveApiUrl } from '@/src/config';
import { clearSession, loadSession, saveSession, type SessionUser } from '@/src/auth/session';

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public body?: unknown,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

let refreshPromise: Promise<string | null> | null = null;

async function refreshAccessToken(): Promise<string | null> {
  if (refreshPromise) return refreshPromise;
  refreshPromise = (async () => {
    const session = await loadSession();
    if (!session?.refreshToken) return null;
    const res = await fetch(`${getApiBase()}/api/v1/auth/mobile/refresh`, {
      method: 'POST',
      headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: session.refreshToken }),
    });
    if (!res.ok) {
      await clearSession();
      return null;
    }
    const body = (await res.json()) as {
      access_token: string;
      refresh_token: string;
      user: SessionUser;
    };
    await saveSession({
      accessToken: body.access_token,
      refreshToken: body.refresh_token,
      user: body.user,
    });
    return body.access_token;
  })().finally(() => {
    refreshPromise = null;
  });
  return refreshPromise;
}

export type ApiFetchOptions = RequestInit & {
  skipAuth?: boolean;
  retryOn401?: boolean;
};

export async function apiFetch<T = unknown>(
  path: string,
  options: ApiFetchOptions = {},
): Promise<T> {
  const { skipAuth = false, retryOn401 = true, headers: initHeaders, ...rest } = options;
  const headers = new Headers(initHeaders);
  headers.set('Accept', 'application/json');
  if (!headers.has('X-Request-Id')) {
    headers.set('X-Request-Id', `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`);
  }

  if (!skipAuth) {
    const session = await loadSession();
    if (session?.accessToken) {
      headers.set('Authorization', `Bearer ${session.accessToken}`);
    }
  }

  const url = resolveApiUrl(path);
  let res = await fetch(url, { ...rest, headers });

  if (res.status === 401 && !skipAuth && retryOn401) {
    const newToken = await refreshAccessToken();
    if (newToken) {
      headers.set('Authorization', `Bearer ${newToken}`);
      res = await fetch(url, { ...rest, headers });
    }
  }

  const text = await res.text();
  let data: unknown = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = text;
    }
  }

  if (!res.ok) {
    const msg =
      typeof data === 'object' && data !== null && 'error' in data
        ? String((data as { error: unknown }).error)
        : res.statusText || 'Request failed';
    throw new ApiError(msg, res.status, data);
  }

  return data as T;
}

export async function downloadWithAuth(
  fileUrl: string,
  localUri: string,
): Promise<void> {
  const FileSystem = await import('expo-file-system/legacy');
  const session = await loadSession();
  if (!session?.accessToken) {
    throw new ApiError('Not signed in', 401);
  }
  const url = resolveApiUrl(fileUrl);
  const result = await FileSystem.downloadAsync(url, localUri, {
    headers: { Authorization: `Bearer ${session.accessToken}` },
  });
  if (result.status < 200 || result.status >= 300) {
    throw new ApiError(`Download failed (${result.status})`, result.status);
  }
}
