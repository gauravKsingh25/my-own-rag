'use client';

import clsx from 'clsx';
import Spinner from '../Spinner/Spinner';
import styles from './Button.module.css';

/**
 * @param {{ variant?: 'primary'|'secondary'|'ghost'|'danger', size?: 'sm'|'md'|'lg', loading?: boolean, fullWidth?: boolean }} props
 */
export default function Button({
  children,
  variant = 'primary',
  size = 'md',
  loading = false,
  disabled = false,
  fullWidth = false,
  type = 'button',
  onClick,
  className,
  ...rest
}) {
  return (
    <button
      type={type}
      disabled={disabled || loading}
      onClick={onClick}
      className={clsx(
        styles.btn,
        styles[variant],
        styles[size],
        fullWidth && styles.fullWidth,
        loading && styles.loading,
        className
      )}
      {...rest}
    >
      {loading && (
        <span className={styles.spinnerWrap}>
          <Spinner size="sm" />
        </span>
      )}
      <span className={clsx(styles.label, loading && styles.hiddenLabel)}>
        {children}
      </span>
    </button>
  );
}
