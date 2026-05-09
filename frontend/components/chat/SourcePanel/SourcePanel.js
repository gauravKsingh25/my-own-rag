'use client';

import clsx from 'clsx';
import styles from './SourcePanel.module.css';

function formatScore(score) {
  if (typeof score !== 'number' || Number.isNaN(score)) return 'N/A';
  return `${Math.round(score * 100)}%`;
}

function getRelevanceTone(score) {
  if (typeof score !== 'number' || Number.isNaN(score)) return 'Unknown';
  if (score >= 0.85) return 'Very high';
  if (score >= 0.7) return 'High';
  if (score >= 0.5) return 'Medium';
  return 'Low';
}

function compactId(value) {
  if (!value) return 'N/A';
  if (value.length <= 14) return value;
  return `${value.slice(0, 8)}...${value.slice(-4)}`;
}

function SourceCard({ source, index }) {
  const scoreTone = getRelevanceTone(source.score);

  return (
    <div className={styles.sourceCard}>
      <div className={styles.sourceHeader}>
        <span className={styles.sourceNum}>{source.source_number ?? index + 1}</span>
        <div className={styles.sourceMeta}>
          <p className={styles.sectionTitle} title={source.section_title || `Source ${index + 1}`}>
            {source.section_title || `Source ${index + 1}`}
          </p>
          <p className={styles.sectionSubtitle}>Retrieved evidence snippet</p>
        </div>
      </div>

      <div className={styles.details}>
        <div className={styles.detailRow}>
          <span className={styles.detailLabel}>Page</span>
          <span className={styles.detailValue}>
            {source.page_number != null ? source.page_number : 'Not available'}
          </span>
        </div>
        <div className={styles.detailRow}>
          <span className={styles.detailLabel}>Relevance</span>
          <span className={styles.detailValueStrong}>
            {formatScore(source.score)} ({scoreTone})
          </span>
        </div>
        <div className={styles.detailRow}>
          <span className={styles.detailLabel}>Document</span>
          <span className={styles.detailValueMono} title={source.document_id}>
            {compactId(source.document_id)}
          </span>
        </div>
        <div className={styles.detailRow}>
          <span className={styles.detailLabel}>Chunk</span>
          <span className={styles.detailValueMono} title={source.chunk_id}>
            {compactId(source.chunk_id)}
          </span>
        </div>
      </div>
    </div>
  );
}

export default function SourcePanel({ sources, isOpen, onClose }) {
  const totalSources = sources?.length ?? 0;
  const uniqueDocCount = new Set((sources ?? []).map((src) => src.document_id).filter(Boolean)).size;

  return (
    <div className={clsx(styles.panel, isOpen && styles.open)}>
      {/* Header */}
      <div className={styles.header}>
        <div className={styles.headerText}>
          <h3 className={styles.title}>
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/>
              <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>
            </svg>
            Sources ({totalSources})
          </h3>
          <p className={styles.subtitle}>
            {uniqueDocCount} document{uniqueDocCount === 1 ? '' : 's'} referenced
          </p>
        </div>
        <button className={styles.closeBtn} onClick={onClose} aria-label="Close sources panel">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
        </button>
      </div>

      {/* Sources list */}
      <div className={styles.list}>
        {!sources || sources.length === 0 ? (
          <div className={styles.emptyWrap}>
            <p className={styles.empty}>No sources yet</p>
            <p className={styles.emptyHint}>Run a query and open sources on an answer to inspect the evidence.</p>
          </div>
        ) : (
          sources.map((src, i) => (
            <SourceCard key={src.chunk_id ?? i} source={src} index={i} />
          ))
        )}
      </div>
    </div>
  );
}
