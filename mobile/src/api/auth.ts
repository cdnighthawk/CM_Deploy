import { apiFetch } from '@/src/api/client';
import { saveSession, type SessionUser } from '@/src/auth/session';

type LoginResponse = {
  access_token: string;
  refresh_token: string;
  expires_in: number;
  token_type: string;
  user: SessionUser;
};

export async function mobileLogin(email: string, password: string): Promise<SessionUser> {
  const body = await apiFetch<LoginResponse>('/api/v1/auth/mobile/login', {
    method: 'POST',
    skipAuth: true,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: email.trim(), password }),
  });
  await saveSession({
    accessToken: body.access_token,
    refreshToken: body.refresh_token,
    user: body.user,
  });
  return body.user;
}

export async function mobileLogout(): Promise<void> {
  const { loadSession, clearSession } = await import('@/src/auth/session');
  const session = await loadSession();
  if (session?.refreshToken) {
    try {
      await apiFetch('/api/v1/auth/mobile/logout', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: session.refreshToken }),
        retryOn401: false,
      });
    } catch {
      /* revoke best-effort */
    }
  }
  await clearSession();
}
