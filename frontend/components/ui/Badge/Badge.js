'use client';

import clsx from 'clsx';
import styles from './Badge.module.css';

/**
 * @param {{ variant?: 'default'|'primary'|'success'|'warning'|'error'|'info'|'ghost', size?: 'sm'|'md' }} props
 */
export default function Badge({ children, variant = 'default', size = 'md', className }) {
  return (
    <span className={clsx(styles.badge, styles[variant], styles[size], className)}>
      {children}
    </span>
  );
}
