import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { authApi, type AuthResponse, setOnAuthExpired, type User } from "./api";
import {
  clearTokens,
  getRefreshToken,
  getStoredUser,
  setStoredUser,
  setTokens,
} from "./tokenStore";

interface AuthContextValue {
  user: User | null;
  isLoading: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (email: string, password: string, name?: string) => Promise<void>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

async function applyAuthResponse(res: AuthResponse, setUser: (u: User | null) => void) {
  await setTokens(res.access_token, res.refresh_token);
  await setStoredUser(res.user);
  setUser(res.user);
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [storedUser, refreshToken] = await Promise.all([
          getStoredUser(),
          getRefreshToken(),
        ]);
        if (!cancelled && storedUser && refreshToken) {
          setUser(storedUser);
        }
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    setOnAuthExpired(() => {
      clearTokens().then(() => setUser(null));
    });
  }, []);

  const signIn = useCallback(async (email: string, password: string) => {
    const res = await authApi.login(email, password);
    await applyAuthResponse(res, setUser);
  }, []);

  const signUp = useCallback(async (email: string, password: string, name?: string) => {
    const res = await authApi.register(email, password, name);
    await applyAuthResponse(res, setUser);
  }, []);

  const signOut = useCallback(async () => {
    try {
      const refreshToken = await getRefreshToken();
      if (refreshToken) await authApi.logout(refreshToken);
    } catch {
      // Logout is best-effort; clear local state regardless.
    }
    await clearTokens();
    setUser(null);
  }, []);

  const value = useMemo(
    () => ({ user, isLoading, signIn, signUp, signOut }),
    [user, isLoading, signIn, signUp, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}
