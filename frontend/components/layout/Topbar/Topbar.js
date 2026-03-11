'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import ThemeToggle from '@/components/ui/ThemeToggle/ThemeToggle';
import { useApp } from '@/lib/context/AppContext';
import { shortenId } from '@/lib/utils/format';
import styles from './Topbar.module.css';

const PAGE_TITLES = {
  '/':          'Dashboard',
  '/documents': 'Documents',
  '/chat':      'Chat',
  '/health':    'System Health',
};

export default function Topbar() {
  const pathname = usePathname();
  const { userId } = useApp();

  const title = Object.entries(PAGE_TITLES)
    .reverse()
    .find(([path]) => (path === '/' ? pathname === '/' : pathname.startsWith(path)))?.[1]
    ?? 'RAG System';

  return (
    <header className={styles.topbar}>
      <div className={styles.left}>
        <h1 className={styles.title}>{title}</h1>
      </div>

      <div className={styles.right}>
        {userId && (
          <div className={styles.userId} title={userId}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
              <circle cx="12" cy="7" r="4"/>
            </svg>
            <span>{shortenId(userId)}</span>
          </div>
        )}
        <ThemeToggle />
      </div>
    </header>
  );
}
