'use client';

import { useState, useCallback, useRef, useEffect } from 'react';
import { useApp } from '@/lib/context/AppContext';
import { uploadDocument as uploadDocumentAPI, getDocument } from '@/lib/api/documents';
import { POLL_INTERVAL, PROCESSING_STATUSES } from '@/lib/utils/constants';

export function useDocuments() {
  const { userId, documents, addDocument, updateDocument } = useApp();
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState(null);
  const pollMap = useRef({});

  /** Poll a single document every POLL_INTERVAL until terminal status */
  const startPolling = useCallback(
    (docId) => {
      if (pollMap.current[docId]) return;

      const intervalId = setInterval(async () => {
        try {
          const doc = await getDocument(docId);
          updateDocument(docId, doc);

          if (!PROCESSING_STATUSES.includes(doc.processing_status)) {
            clearInterval(pollMap.current[docId]);
            delete pollMap.current[docId];
          }
        } catch {
          clearInterval(pollMap.current[docId]);
          delete pollMap.current[docId];
        }
      }, POLL_INTERVAL);

      pollMap.current[docId] = intervalId;
    },
    [updateDocument]
  );

  /* Resume polling for any docs that were still in-progress on app load */
  useEffect(() => {
    documents.forEach((doc) => {
      if (PROCESSING_STATUSES.includes(doc.processing_status)) {
        startPolling(doc.id);
      }
    });
    // Cleanup all intervals on unmount
    return () => {
      Object.values(pollMap.current).forEach(clearInterval);
      pollMap.current = {};
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // intentionally runs once on mount only

  const upload = useCallback(
    async (file) => {
      if (!userId) throw new Error('User not initialised');
      setUploading(true);
      setUploadError(null);

      try {
        const result = await uploadDocumentAPI(file, userId);

        // Normalise: upload response uses document_id; GET response uses id
        const docData = {
          id: result.document_id,
          user_id: result.user_id,
          filename: result.filename,
          document_type: result.document_type,
          storage_path: result.storage_path,
          processing_status: result.processing_status,
          created_at: result.created_at,
        };

        addDocument(docData);
        startPolling(result.document_id);
        return result;
      } catch (err) {
        setUploadError(err);
        throw err;
      } finally {
        setUploading(false);
      }
    },
    [userId, addDocument, startPolling]
  );

  return { documents, uploading, uploadError, upload };
}
