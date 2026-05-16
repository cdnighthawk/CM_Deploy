import Constants from 'expo-constants';

const extra = Constants.expoConfig?.extra as { apiBase?: string } | undefined;

/** Flask API origin without trailing slash. */
export function getApiBase(): string {
  const fromEnv = process.env.EXPO_PUBLIC_API_BASE?.trim();
  if (fromEnv) return fromEnv.replace(/\/$/, '');
  const fromExtra = extra?.apiBase?.trim();
  if (fromExtra) return fromExtra.replace(/\/$/, '');
  return 'http://127.0.0.1:5000';
}

export function resolveApiUrl(path: string): string {
  const base = getApiBase();
  if (path.startsWith('http://') || path.startsWith('https://')) return path;
  const p = path.startsWith('/') ? path : `/${path}`;
  return `${base}${p}`;
}
