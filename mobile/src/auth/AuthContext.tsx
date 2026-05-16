import { router } from 'expo-router';
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';

import { mobileLogout } from '@/src/api/auth';
import {
  displayName,
  loadSession,
  type SessionTokens,
  type SessionUser,
} from '@/src/auth/session';
import { initDrawingCacheDb } from '@/src/drawings/cache';

type AuthContextValue = {
  ready: boolean;
  user: SessionUser | null;
  signOut: () => Promise<void>;
  refreshSession: () => Promise<void>;
  setUserFromLogin: (user: SessionUser) => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false);
  const [session, setSession] = useState<SessionTokens | null>(null);

  const refreshSession = useCallback(async () => {
    const s = await loadSession();
    setSession(s);
  }, []);

  useEffect(() => {
    (async () => {
      await initDrawingCacheDb();
      await refreshSession();
      setReady(true);
    })();
  }, [refreshSession]);

  const signOut = useCallback(async () => {
    await mobileLogout();
    setSession(null);
    router.replace('/(auth)/login');
  }, []);

  const setUserFromLogin = useCallback((user: SessionUser) => {
    loadSession().then((s) => {
      if (s) setSession(s);
      else setSession(null);
    });
    void user;
  }, []);

  const value = useMemo(
    () => ({
      ready,
      user: session?.user ?? null,
      signOut,
      refreshSession,
      setUserFromLogin,
    }),
    [ready, session, signOut, refreshSession, setUserFromLogin],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}

export { displayName };
