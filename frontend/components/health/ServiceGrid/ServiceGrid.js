'use client';

import clsx from 'clsx';
import styles from './ServiceGrid.module.css';

const SERVICE_ICONS = {
  postgresql: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/>
      <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/>
    </svg>
  ),
  redis: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="2" y="2" width="20" height="8" rx="2" ry="2"/>
      <rect x="2" y="14" width="20" height="8" rx="2" ry="2"/>
      <line x1="6" y1="6" x2="6" y2="6"/><line x1="6" y1="18" x2="6" y2="18"/>
    </svg>
  ),
};

function ServiceItem({ name, status }) {
  const isUp = status?.healthy === true || status?.status === 'connected';
  const label = isUp ? 'Connected' : (status?.error ?? 'Unavailable');

  return (
    <div className={clsx(styles.item, isUp ? styles.up : styles.down)}>
      <div className={styles.itemIcon}>{SERVICE_ICONS[name] ?? null}</div>
      <div className={styles.itemInfo}>
        <p className={styles.itemName}>{name.charAt(0).toUpperCase() + name.slice(1)}</p>
        <p className={clsx(styles.itemStatus, isUp ? styles.statusUp : styles.statusDown)}>
          <span className={clsx(styles.statusDot, isUp ? styles.dotUp : styles.dotDown)} />
          {label}
        </p>
      </div>
    </div>
  );
}

export default function ServiceGrid({ readiness }) {
  const services = readiness?.services ?? {};

  if (Object.keys(services).length === 0) {
    return <p className={styles.empty}>No service data available.</p>;
  }

  return (
    <div className={styles.grid}>
      {Object.entries(services).map(([name, status]) => (
        <ServiceItem key={name} name={name} status={status} />
      ))}
    </div>
  );
}
