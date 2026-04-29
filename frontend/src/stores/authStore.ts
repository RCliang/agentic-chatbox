import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import api from '../api/client';
import type { User } from '../types';

interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  fetchMe: () => Promise<void>;
  _hasHydrated: boolean;
  _setHasHydrated: (state: boolean) => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      token: null,
      isAuthenticated: false,
      _hasHydrated: false,
      _setHasHydrated: (state: boolean) => {
        set({ _hasHydrated: state });
      },

      login: async (username: string, password: string) => {
        const res = await api.post('/api/auth/login', { username, password });
        const { access_token } = res.data as { access_token: string };
        localStorage.setItem('token', access_token);
        set({ token: access_token });
        await get().fetchMe();
      },

      logout: () => {
        localStorage.removeItem('token');
        set({ user: null, token: null, isAuthenticated: false });
      },

      fetchMe: async () => {
        try {
          const res = await api.get('/api/auth/me');
          const user = res.data as User;
          set({ user, isAuthenticated: true });
        } catch {
          get().logout();
        }
      },
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({
        token: state.token,
        user: state.user,
        isAuthenticated: state.isAuthenticated,
      }),
      onRehydrateStorage: () => (state) => {
        state?._setHasHydrated(true);
      },
    },
  ),
);
