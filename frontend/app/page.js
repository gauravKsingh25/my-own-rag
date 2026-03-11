'use client';

import Link from 'next/link';
import clsx from 'clsx';
import { useApp } from '@/lib/context/AppContext';
import { useHealth } from '@/lib/hooks/useHealth';
import { shortenId } from '@/lib/utils/format';
import styles from './page.module.css';

function StatCard({ icon, label, value, sub, variant }) {
  return (
    <div className={clsx(styles.statCard, variant && styles[variant])}>
      <div className={styles.statIcon}>{icon}</div>
      <div className={styles.statBody}>
        <p className={styles.statValue}>{value}</p>
        <p className={styles.statLabel}>{label}</p>
        {sub && <p className={styles.statSub}>{sub}</p>}
      </div>
    </div>
  );
}

function QuickCard({ href, icon, title, desc, cta }) {
  return (
    <Link href={href} className={styles.quickCard}>
      <div className={styles.quickIcon}>{icon}</div>
      <div className={styles.quickBody}>
        <p className={styles.quickTitle}>{title}</p>
        <p className={styles.quickDesc}>{desc}</p>
      </div>
      <span className={styles.quickCta}>{cta} &rarr;</span>
    </Link>
  );
}

export default function DashboardPage() {
  const { userId, documents, completedDocuments } = useApp();
  const { rootInfo, isHealthy, loading } = useHealth();

  const total     = documents.length;
  const completed = completedDocuments.length;
  const failed    = documents.filter((d) => d.processing_status === 'FAILED').length;

  return (
    <div className={styles.page}>
      <div className={styles.welcome}>
        <h2 className={styles.welcomeTitle}>Welcome back &#x1F44B;</h2>
        {userId && (
          <p className={styles.welcomeSub}>
            Session ID:&nbsp;<code className={styles.uid}>{shortenId(userId)}</code>
          </p>
        )}
      </div>

      <section className={styles.section}>
        <h3 className={styles.sectionTitle}>Overview</h3>
        <div className={styles.statsGrid}>
          <StatCard
            icon={
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                <polyline points="14 2 14 8 20 8"/>
              </svg>
            }
            label="Total Documents"
            value={total}
          />
          <StatCard
            icon={
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="20 6 9 17 4 12"/>
              </svg>
            }
            label="Ready to Chat"
            value={completed}
            variant={completed > 0 ? 'success' : undefined}
          />
          <StatCard
            icon={
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
              </svg>
            }
            label="Backend Status"
            value={loading ? '\u2026' : isHealthy ? 'Healthy' : 'Unavailable'}
            sub={rootInfo?.version ? `v${rootInfo.version}` : undefined}
            variant={loading ? undefined : isHealthy ? 'success' : 'error'}
          />
          <StatCard
            icon={
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10"/>
                <line x1="12" y1="8" x2="12" y2="12"/>
                <line x1="12" y1="16" x2="12.01" y2="16"/>
              </svg>
            }
            label="Failed Documents"
            value={failed}
            variant={failed > 0 ? 'error' : undefined}
          />
        </div>
      </section>

      <section className={styles.section}>
        <h3 className={styles.sectionTitle}>Quick Actions</h3>
        <div className={styles.quickGrid}>
          <QuickCard
            href="/documents"
            icon={
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                <polyline points="17 8 12 3 7 8"/>
                <line x1="12" y1="3" x2="12" y2="15"/>
              </svg>
            }
            title="Upload Document"
            desc="Add a PDF, DOCX, PPTX, or TXT file to your knowledge base"
            cta="Upload"
          />
          <QuickCard
            href="/chat"
            icon={
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
              </svg>
            }
            title="Start Chat"
            desc="Ask questions across all or a specific uploaded document"
            cta="Chat"
          />
          <QuickCard
            href="/health"
            icon={
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
              </svg>
            }
            title="System Health"
            desc="Check backend status, PostgreSQL, and Redis connectivity"
            cta="View"
          />
        </div>
      </section>
    </div>
  );
}

