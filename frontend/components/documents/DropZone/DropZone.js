'use client';

import { useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import clsx from 'clsx';
import { ACCEPTED_FILE_TYPES, MAX_FILE_SIZE_BYTES } from '@/lib/utils/constants';
import { formatFileSize } from '@/lib/utils/format';
import styles from './DropZone.module.css';

export default function DropZone({ onUpload, uploading }) {
  const onDrop = useCallback(
    (acceptedFiles, rejectedFiles) => {
      if (rejectedFiles.length > 0) return; // errors shown by react-dropzone
      if (acceptedFiles.length > 0) onUpload(acceptedFiles[0]);
    },
    [onUpload]
  );

  const { getRootProps, getInputProps, isDragActive, isDragReject, fileRejections } = useDropzone({
    onDrop,
    accept: ACCEPTED_FILE_TYPES,
    maxSize: MAX_FILE_SIZE_BYTES,
    maxFiles: 1,
    disabled: uploading,
  });

  const firstError = fileRejections?.[0]?.errors?.[0]?.message;

  return (
    <div className={styles.wrapper}>
      <div
        {...getRootProps()}
        className={clsx(
          styles.zone,
          isDragActive && !isDragReject && styles.dragOver,
          isDragReject && styles.dragReject,
          uploading && styles.disabled
        )}
      >
        <input {...getInputProps()} />

        <div className={styles.icon}>
          {uploading ? (
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
              <polyline points="17 8 12 3 7 8"/>
              <line x1="12" y1="3" x2="12" y2="15"/>
            </svg>
          ) : (
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
              <polyline points="17 8 12 3 7 8"/>
              <line x1="12" y1="3" x2="12" y2="15"/>
            </svg>
          )}
        </div>

        {uploading ? (
          <p className={styles.text}>Uploading...</p>
        ) : isDragActive && !isDragReject ? (
          <p className={styles.text}>Drop it here!</p>
        ) : (
          <>
            <p className={styles.text}>
              Drag & drop a file here, or <span className={styles.link}>browse</span>
            </p>
            <p className={styles.hint}>
              PDF, DOCX, PPTX, TXT &nbsp;·&nbsp; Max {formatFileSize(MAX_FILE_SIZE_BYTES)}
            </p>
          </>
        )}
      </div>

      {firstError && <p className={styles.error}>{firstError}</p>}
    </div>
  );
}
