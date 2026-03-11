'use client';

import { AppProvider } from '@/lib/context/AppContext';
import { Toaster } from 'react-hot-toast';

export default function Providers({ children }) {
  return (
    <AppProvider>
      {children}
      <Toaster
        position="bottom-right"
        gutter={8}
        toastOptions={{
          duration: 4000,
          style: {
            background: 'var(--color-surface)',
            color: 'var(--color-text-primary)',
            border: '1px solid var(--color-border)',
            borderRadius: 'var(--radius-lg)',
            fontSize: '0.875rem',
            boxShadow: 'var(--shadow-lg)',
          },
          success: {
            iconTheme: { primary: 'var(--color-success)', secondary: 'var(--color-surface)' },
          },
          error: {
            iconTheme: { primary: 'var(--color-error)', secondary: 'var(--color-surface)' },
          },
        }}
      />
    </AppProvider>
  );
}
