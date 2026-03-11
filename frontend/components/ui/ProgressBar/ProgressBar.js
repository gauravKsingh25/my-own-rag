'use client';

import clsx from 'clsx';
import styles from './ProgressBar.module.css';

/** @param {{ value: number, max?: number, variant?: 'primary'|'success'|'error', animated?: boolean }} */
export default function ProgressBar({ value, max = 100, variant = 'primary', animated = false, className }) {
  const pct = max > 0 ? Math.min(Math.max((value / max) * 100, 0), 100) : 0;

  return (
    <div className={clsx(styles.track, className)} role="progressbar" aria-valuenow={value} aria-valuemax={max}>
      <div
        className={clsx(styles.bar, styles[variant], animated && styles.animated)}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}
