'use client';

import clsx from 'clsx';
import styles from './SourcePanel.module.css';

function SourceCard({ source, index }) {
  return (
    <div className={styles.sourceCard}>
      <div className={styles.sourceHeader}>
        <span className={styles.sourceNum}>{source.source_number ?? index + 1}</span>
        <div className={styles.sourceMeta}>
          {source.section_title && (
            <p className={styles.sectionTitle}>{source.section_title}</p>
          )}
          <div className={styles.sourceTags}>
            {source.page_number != null && (
              <span className={styles.tag}>p. {source.page_number}</span>
            )}
            <span className={styles.tag}>Score: {source.score?.toFixed(3) ?? '—'}</span>
          </div>
        </div>
      </div>
      <p className={styles.docId} title={source.document_id}>
        Doc: {source.document_id?.slice(0, 16)}…
      </p>
    </div>
  );
}

export default function SourcePanel({ sources, isOpen, onClose }) {
  return (
    <div className={clsx(styles.panel, isOpen && styles.open)}>
      {/* Header */}
      <div className={styles.header}>
        <h3 className={styles.title}>
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/>
            <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>
          </svg>
          Sources ({sources?.length ?? 0})
        </h3>
        <button className={styles.closeBtn} onClick={onClose} aria-label="Close sources panel">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
        </button>
      </div>

      {/* Sources list */}
      <div className={styles.list}>
        {!sources || sources.length === 0 ? (
          <p className={styles.empty}>No sources available.</p>
        ) : (
          sources.map((src, i) => (
            <SourceCard key={src.chunk_id ?? i} source={src} index={i} />
          ))
        )}
      </div>
    </div>
  );
}
