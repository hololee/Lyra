/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useLayoutEffect, useMemo, useState, type ReactNode } from 'react';

type Theme = 'light' | 'dark';

interface ThemeContextType {
  theme: Theme;
  setTheme: (theme: Theme) => void;
  toggleTheme: () => void;
}

const STORAGE_KEY = 'lyra.theme';
const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

function readStoredTheme(): Theme | null {
  if (typeof window === 'undefined') return null;
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    return stored === 'light' || stored === 'dark' ? stored : null;
  } catch {
    return null;
  }
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>(() => readStoredTheme() ?? 'dark');

  useLayoutEffect(() => {
    if (typeof document !== 'undefined') {
      document.documentElement.classList.toggle('theme-dark', theme === 'dark');
    }
    if (typeof window !== 'undefined') {
      try {
        window.localStorage.setItem(STORAGE_KEY, theme);
      } catch {
        // Ignore storage write errors
      }
    }
  }, [theme]);

  const value = useMemo<ThemeContextType>(() => ({
    theme,
    setTheme,
    toggleTheme: () => setTheme((prev) => (prev === 'dark' ? 'light' : 'dark')),
  }), [theme]);

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error('useTheme must be used within a ThemeProvider');
  }
  return context;
}

export type { Theme };
