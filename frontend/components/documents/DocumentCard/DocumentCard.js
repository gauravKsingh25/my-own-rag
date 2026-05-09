'use client';

import { useRouter } from 'next/navigation';
import clsx from 'clsx';
import Badge from '@/components/ui/Badge/Badge';
import Button from '@/components/ui/Button/Button';
import ProcessingStatus from '../ProcessingStatus/ProcessingStatus';
import { formatDate, fileTypeLabel } from '@/lib/utils/format';
import { useApp } from '@/lib/context/AppContext';
import styles from './DocumentCard.module.css';

const STATUS_VARIANT = {
  UPLOADED:   'info',
  PROCESSING: 'warning',
  PARSED:     'warning',
  CHUNKED:    'warning',
  EMBEDDED:   'warning',
  COMPLETED:  'success',
  FAILED:     'error',
};

const TYPE_VARIANT = {
  pdf: 'error', docx: 'info', pptx: 'warning', txt: 'default',
};

export default function DocumentCard({ doc, onDelete, deleting = false }) {
  const router = useRouter();
  const { setSelectedDocumentId } = useApp();
  const isCompleted = doc.processing_status === 'COMPLETED';
  const isFailed    = doc.processing_status === 'FAILED';

  const handleChat = () => {
    setSelectedDocumentId(doc.id);
    router.push('/chat');
  };

  const handleDelete = () => {
    if (!onDelete) return;

    const confirmed = window.confirm(
      `Delete "${doc.filename}"? This permanently removes the file, chunks, and vectors.`
    );

    if (confirmed) {
      onDelete(doc);
    }
  };

  return (
    <div className={clsx(styles.card, isFailed && styles.failed)}>
      {/* Header */}
      <div className={styles.header}>
        <div className={styles.fileIcon}>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
            <polyline points="14 2 14 8 20 8"/>
          </svg>
        </div>
        <div className={styles.badges}>
          <Badge variant={TYPE_VARIANT[doc.document_type] ?? 'default'} size="sm">
            {fileTypeLabel(doc.document_type)}
          </Badge>
        </div>
      </div>

      {/* Body */}
      <div className={styles.body}>
        <p className={styles.filename} title={doc.filename}>{doc.filename}</p>
        <p className={styles.date}>{formatDate(doc.created_at)}</p>
      </div>

      {/* Status */}
      <div className={styles.statusRow}>
        <Badge variant={STATUS_VARIANT[doc.processing_status] ?? 'default'} size="sm">
          {doc.processing_status}
        </Badge>
      </div>

      {/* Progress (only when processing) */}
      {!isCompleted && !isFailed && (
        <ProcessingStatus status={doc.processing_status} />
      )}

      {/* Actions */}
      <div className={styles.actions}>
        {isCompleted && (
          <button className={styles.chatBtn} onClick={handleChat}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
            </svg>
            Chat with this doc
          </button>
        )}

        <Button
          variant="danger"
          size="sm"
          className={styles.deleteBtn}
          onClick={handleDelete}
          loading={deleting}
          disabled={deleting}
        >
          {deleting ? 'Deleting...' : 'Delete'}
        </Button>
      </div>
    </div>
  );
}
