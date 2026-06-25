import { createContext, useContext, useEffect, useMemo, useState } from 'react';

const THEME_STORAGE_KEY = 'cdv-explorer-theme-mode';

const ThemeContext = createContext({
  themeMode: 'system',
  resolvedTheme: 'light',
  setThemeMode: () => {},
  cycleThemeMode: () => {},
});

function getSystemTheme() {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
    return 'light';
  }

  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

function getInitialThemeMode() {
  if (typeof window === 'undefined') {
    return 'system';
  }

  const storedValue = window.localStorage.getItem(THEME_STORAGE_KEY);
  return ['system', 'light', 'dark'].includes(storedValue) ? storedValue : 'system';
}

export function ThemeProvider({ children }) {
  const [themeMode, setThemeMode] = useState(getInitialThemeMode);
  const [systemTheme, setSystemTheme] = useState(getSystemTheme);

  useEffect(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
      return undefined;
    }

    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    const handleChange = (event) => {
      setSystemTheme(event.matches ? 'dark' : 'light');
    };

    handleChange(mediaQuery);
    mediaQuery.addEventListener('change', handleChange);

    return () => mediaQuery.removeEventListener('change', handleChange);
  }, []);

  const resolvedTheme = themeMode === 'system' ? systemTheme : themeMode;

  useEffect(() => {
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(THEME_STORAGE_KEY, themeMode);
    }

    document.documentElement.dataset.theme = resolvedTheme;
    document.documentElement.dataset.themeMode = themeMode;
    document.documentElement.style.colorScheme = resolvedTheme;
  }, [resolvedTheme, themeMode]);

  const value = useMemo(() => ({
    themeMode,
    resolvedTheme,
    setThemeMode,
    cycleThemeMode: () => {
      setThemeMode((currentMode) => {
        if (currentMode === 'system') {
          return 'dark';
        }
        if (currentMode === 'dark') {
          return 'light';
        }
        return 'system';
      });
    },
  }), [resolvedTheme, themeMode]);

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  return useContext(ThemeContext);
}
