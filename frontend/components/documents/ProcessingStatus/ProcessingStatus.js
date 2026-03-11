'use client';

import ProgressBar from '@/components/ui/ProgressBar/ProgressBar';
import { STATUS_PROGRESS, PROCESSING_STATUSES } from '@/lib/utils/constants';
import styles from './ProcessingStatus.module.css';

const STATUS_LABELS = {
  UPLOADED:   'Queued for processing',
  PROCESSING: 'Processing document…',
  PARSED:     'Text extracted',
  CHUNKED:    'Split into chunks',
  EMBEDDED:   'Generating embeddings',
  COMPLETED:  'Ready',
  FAILED:     'Processing failed',
};

export default function ProcessingStatus({ status }) {
  const progress = STATUS_PROGRESS[status] ?? 0;
  const isProcessing = PROCESSING_STATUSES.includes(status);
  const isFailed = status === 'FAILED';
  const variant = isFailed ? 'error' : (status === 'COMPLETED' ? 'success' : 'primary');

  return (
    <div className={styles.wrap}>
      <ProgressBar value={progress} animated={isProcessing} variant={variant} />
      <p className={styles.label}>{STATUS_LABELS[status] ?? status}</p>
    </div>
  );
}
