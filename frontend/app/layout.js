import localFont from 'next/font/local';
import './globals.css';
import Providers from './Providers';
import AppShell from '@/components/layout/AppShell/AppShell';

const geistSans = localFont({
  src: './fonts/GeistVF.woff',
  variable: '--font-geist-sans',
  weight: '100 900',
});
const geistMono = localFont({
  src: './fonts/GeistMonoVF.woff',
  variable: '--font-geist-mono',
  weight: '100 900',
});

export const metadata = {
  title: 'RAG System',
  description: 'Retrieval-Augmented Generation — upload documents, ask questions, get cited answers.',
};

/**
 * Inline script that runs before React hydrates.
 * Reads the stored theme from localStorage and sets data-theme on <html>
 * to prevent a flash of the wrong theme (FOUC).
 */
const themeScript = `
  (function() {
    try {
      var t = localStorage.getItem('rag_theme') || 'dark';
      document.documentElement.setAttribute('data-theme', t);
    } catch(e) {}
  })();
`;

export default function RootLayout({ children }) {
  return (
    <html lang="en" data-theme="dark" suppressHydrationWarning>
      <head>
        {/* eslint-disable-next-line react/no-danger */}
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body
        className={`${geistSans.variable} ${geistMono.variable}`}
        suppressHydrationWarning
      >
        <Providers>
          <AppShell>{children}</AppShell>
        </Providers>
      </body>
    </html>
  );
}

