import { create } from 'zustand';

type Theme = 'dark' | 'light';

interface ThemeState {
  theme: Theme;
  toggleTheme: () => void;
}

export const useThemeStore = create<ThemeState>()((set) => {
  const stored = localStorage.getItem('theme') as Theme | null;
  const initial: Theme = stored || 'dark';
  document.documentElement.setAttribute('data-theme', initial);

  return {
    theme: initial,
    toggleTheme: () => {
      set((state) => {
        const next: Theme = state.theme === 'dark' ? 'light' : 'dark';
        localStorage.setItem('theme', next);
        document.documentElement.setAttribute('data-theme', next);
        return { theme: next };
      });
    },
  };
});
