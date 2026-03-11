'use client';

import clsx from 'clsx';
import Badge from '@/components/ui/Badge/Badge';
import styles from './HealthCard.module.css';

export default function HealthCard({ health, rootInfo }) {
  const isHealthy = health?.status === 'healthy';

  return (
    <div className={clsx(styles.card, isHealthy ? styles.healthy : styles.unhealthy)}>
      <div className={styles.iconWrap}>
        <span className={clsx(styles.dot, isHealthy ? styles.dotGreen : styles.dotRed)} />
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
        </svg>
      </div>
      <div className={styles.info}>
        <p className={styles.statusLine}>
          Backend is{' '}
          <Badge variant={isHealthy ? 'success' : 'error'}>
            {health?.status ?? '—'}
          </Badge>
        </p>
        <div className={styles.meta}>
          {rootInfo?.version && <span>v{rootInfo.version}</span>}
          {rootInfo?.environment && <span className={styles.env}>{rootInfo.environment}</span>}
        </div>
      </div>
    </div>
  );
}
