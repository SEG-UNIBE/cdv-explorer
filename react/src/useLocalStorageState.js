import { useState, useEffect, useCallback } from 'react';

function readFromStorage(key, fallback) {
  try {
    const stored = localStorage.getItem(key);
    if (stored !== null) return JSON.parse(stored);
  } catch {
    // ignore parse errors or unavailable storage
  }
  return fallback;
}

export function useLocalStorageState(key, defaultValue) {
  const [value, setValue] = useState(() => readFromStorage(key, defaultValue));

  // Re-read from localStorage when key changes (e.g. navigating between ecosystems)
  useEffect(() => {
    setValue(readFromStorage(key, defaultValue));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  const setPersisted = useCallback((updater) => {
    setValue((current) => {
      const next = typeof updater === 'function' ? updater(current) : updater;
      try {
        localStorage.setItem(key, JSON.stringify(next));
      } catch {
        // ignore write errors (storage full, private mode, etc.)
      }
      return next;
    });
  }, [key]);

  return [value, setPersisted];
}
