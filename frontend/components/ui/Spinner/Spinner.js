'use client';

import clsx from 'clsx';
import styles from './Spinner.module.css';

/** @param {{ size?: 'sm'|'md'|'lg', className?: string }} */
export default function Spinner({ size = 'md', className }) {
  return (
    <span
      className={clsx(styles.spinner, styles[size], className)}
      role="status"
      aria-label="Loading"
    />
  );
}
