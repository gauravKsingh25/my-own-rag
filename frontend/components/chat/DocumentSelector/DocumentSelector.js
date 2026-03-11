'use client';

import clsx from 'clsx';
import { useApp } from '@/lib/context/AppContext';
import styles from './DocumentSelector.module.css';

export default function DocumentSelector() {
  const { completedDocuments, selectedDocumentId, setSelectedDocumentId } = useApp();

  return (
    <div className={styles.wrap}>
      <label className={styles.label} htmlFor="doc-select">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
          <polyline points="14 2 14 8 20 8"/>
        </svg>
        Document
      </label>
      <select
        id="doc-select"
        className={styles.select}
        value={selectedDocumentId ?? ''}
        onChange={(e) => setSelectedDocumentId(e.target.value || null)}
      >
        <option value="">All Documents</option>
        {completedDocuments.map((doc) => (
          <option key={doc.id} value={doc.id}>
            {doc.filename.length > 40 ? doc.filename.slice(0, 40) + '…' : doc.filename}
          </option>
        ))}
      </select>
    </div>
  );
}
