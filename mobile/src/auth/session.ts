import * as SecureStore from 'expo-secure-store';

const ACCESS_KEY = 'usis_access_token';
const REFRESH_KEY = 'usis_refresh_token';
const USER_KEY = 'usis_user_json';

export type SessionUser = {
  id: string;
  email: string;
  first_name: string | null;
  last_name: string | null;
};

export type SessionTokens = {
  accessToken: string;
  refreshToken: string;
  user: SessionUser;
};

export async function loadSession(): Promise<SessionTokens | null> {
  const accessToken = await SecureStore.getItemAsync(ACCESS_KEY);
  const refreshToken = await SecureStore.getItemAsync(REFRESH_KEY);
  const userJson = await SecureStore.getItemAsync(USER_KEY);
  if (!accessToken || !refreshToken || !userJson) return null;
  try {
    const user = JSON.parse(userJson) as SessionUser;
    return { accessToken, refreshToken, user };
  } catch {
    return null;
  }
}

export async function saveSession(tokens: SessionTokens): Promise<void> {
  await SecureStore.setItemAsync(ACCESS_KEY, tokens.accessToken);
  await SecureStore.setItemAsync(REFRESH_KEY, tokens.refreshToken);
  await SecureStore.setItemAsync(USER_KEY, JSON.stringify(tokens.user));
}

export async function clearSession(): Promise<void> {
  await SecureStore.deleteItemAsync(ACCESS_KEY);
  await SecureStore.deleteItemAsync(REFRESH_KEY);
  await SecureStore.deleteItemAsync(USER_KEY);
}

export function displayName(user: SessionUser): string {
  const parts = [user.first_name, user.last_name].filter(Boolean);
  if (parts.length) return parts.join(' ');
  return user.email;
}
