import { useEffect, useState } from 'react';

const STORAGE_KEY = 'researchmind-theme';
const systemTheme = window.matchMedia?.('(prefers-color-scheme: dark)');
let preference;
try {
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored === 'light' || stored === 'dark') preference = stored;
} catch {
  // A blocked storage policy should not prevent theme selection.
}

function currentTheme() {
  return preference || (systemTheme?.matches ? 'dark' : 'light');
}

// Apply before React mounts, without remounting or updating the application.
document.documentElement.dataset.theme = currentTheme();

export default function ThemeToggle() {
  const [theme, setTheme] = useState(currentTheme);

  useEffect(() => {
    function syncTheme() {
      const next = currentTheme();
      document.documentElement.dataset.theme = next;
      setTheme(next);
    }
    syncTheme();
    systemTheme?.addEventListener?.('change', syncTheme);
    return () => systemTheme?.removeEventListener?.('change', syncTheme);
  }, []);

  function toggleTheme() {
    const next = theme === 'dark' ? 'light' : 'dark';
    preference = next;
    document.documentElement.dataset.theme = next;
    setTheme(next);
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // Keep the selection for this session when persistence is unavailable.
    }
  }

  const label = `Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`;
  return (
    <button type="button" className="theme-toggle" onClick={toggleTheme}
      aria-label={label} title={label}>
      <span aria-hidden="true">{theme === 'dark' ? '\u263e' : '\u2600'}</span>
      {theme === 'dark' ? 'Dark' : 'Light'}
    </button>
  );
}
