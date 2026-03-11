'use client';

import { useHealth } from '@/lib/hooks/useHealth';
import HealthCard from '@/components/health/HealthCard/HealthCard';
import ServiceGrid from '@/components/health/ServiceGrid/ServiceGrid';
import Button from '@/components/ui/Button/Button';
import Spinner from '@/components/ui/Spinner/Spinner';
import { formatDate } from '@/lib/utils/format';
import styles from './page.module.css';

export default function HealthPage() {
  const { health, readiness, rootInfo, loading, error, lastChecked, refresh } = useHealth();

  return (
    <div className={styles.page}>
      {/* Header */}
      <div className={styles.header}>
        <div>
          <h2 className={styles.title}>System Health</h2>
          <p className={styles.subtitle}>
            {lastChecked
              ? `Last checked: ${formatDate(lastChecked)}`
              : 'Checking status…'}
          </p>
        </div>
        <Button variant="secondary" size="sm" onClick={refresh} loading={loading}>
          Refresh
        </Button>
      </div>

      {/* Error state */}
      {error && !loading && (
        <div className={styles.errorBanner}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10"/>
            <line x1="12" y1="8" x2="12" y2="12"/>
            <line x1="12" y1="16" x2="12.01" y2="16"/>
          </svg>
          {error.message}
        </div>
      )}

      {/* Loading skeleton */}
      {loading && !health && (
        <div className={styles.loadingState}>
          <Spinner size="lg" />
          <p>Connecting to backend…</p>
        </div>
      )}

      {/* Health overview card */}
      {health && (
        <section className={styles.section}>
          <h3 className={styles.sectionTitle}>Overall Status</h3>
          <HealthCard health={health} rootInfo={rootInfo} />
        </section>
      )}

      {/* Services */}
      {readiness && (
        <section className={styles.section}>
          <h3 className={styles.sectionTitle}>Dependencies</h3>
          <ServiceGrid readiness={readiness} />
        </section>
      )}

      {/* Raw readiness details */}
      {readiness?.details && (
        <section className={styles.section}>
          <h3 className={styles.sectionTitle}>Details</h3>
          <div className={styles.detailsCard}>
            <pre className={styles.pre}>{JSON.stringify(readiness.details, null, 2)}</pre>
          </div>
        </section>
      )}
    </div>
  );
}
