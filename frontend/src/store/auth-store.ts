import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { User, AuthTokens } from "@/types";

interface AuthState {
  user: User | null;
  tokens: AuthTokens | null;
  isAuthenticated: boolean;
}

interface AuthActions {
  setUser: (u: User) => void;
  setTokens: (t: AuthTokens) => void;
  setAuth: (u: User, accessToken: string, refreshToken: string) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState & AuthActions>()(
  persist(
    (set) => ({
      user: null,
      tokens: null,
      isAuthenticated: false,

      setUser: (u) => set({ user: u, isAuthenticated: true }),
      setTokens: (t) => set({ tokens: t }),
      setAuth: (u, accessToken, refreshToken) =>
        set({
          user: u,
          tokens: { access_token: accessToken, refresh_token: refreshToken },
          isAuthenticated: true,
        }),
      logout: () =>
        set({ user: null, tokens: null, isAuthenticated: false }),
    }),
    {
      name: "argus-auth",
      // Only persist user info and auth flag, NOT tokens (tokens handled in memory)
      partialize: (state) => ({ user: state.user, isAuthenticated: state.isAuthenticated }),
    }
  )
);
