'use client';

import { useState, useEffect, useCallback } from 'react';
import { THEME_KEY } from '@/lib/utils/constants';

export function useTheme() {
  const [theme, setTheme] = useState('dark');

  /* Sync with the data-theme attribute that was set by the FOUC-prevention script */
  useEffect(() => {
    const stored = localStorage.getItem(THEME_KEY) || 'dark';
    setTheme(stored);
    document.documentElement.setAttribute('data-theme', stored);
  }, []);

  const toggleTheme = useCallback(() => {
    setTheme((prev) => {
      const next = prev === 'dark' ? 'light' : 'dark';
      localStorage.setItem(THEME_KEY, next);
      document.documentElement.setAttribute('data-theme', next);
      return next;
    });
  }, []);

  return { theme, toggleTheme };
}
