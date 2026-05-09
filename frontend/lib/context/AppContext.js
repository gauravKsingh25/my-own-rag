'use client';

import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { getUserId } from '@/lib/utils/uuid';
import { DOCS_STORAGE_PREFIX } from '@/lib/utils/constants';
import { getDocument } from '@/lib/api/documents';

const AppContext = createContext(null);

export function AppProvider({ children }) {
  const [userId, setUserId] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [selectedDocumentId, setSelectedDocumentId] = useState(null);

  /* ── Initialise userId + restore documents from localStorage ── */
  useEffect(() => {
    const id = getUserId();
    setUserId(id);

    const key = `${DOCS_STORAGE_PREFIX}${id}`;
    let stored = [];
    try {
      stored = JSON.parse(localStorage.getItem(key) || '[]');
    } catch { /* ignore */ }

    if (stored.length === 0) return;

    // Fetch each stored document to get the latest status
    Promise.all(
      stored.map((docId) => getDocument(docId).catch(() => null))
    ).then((docs) => {
      setDocuments(docs.filter(Boolean));
    });
  }, []);

  /* ── Persist document IDs whenever the list changes ── */
  const persistDocIds = useCallback((docs, uid) => {
    if (!uid) return;
    const key = `${DOCS_STORAGE_PREFIX}${uid}`;
    localStorage.setItem(key, JSON.stringify(docs.map((d) => d.id)));
  }, []);

  const addDocument = useCallback(
    (doc) => {
      setDocuments((prev) => {
        const next = [doc, ...prev.filter((d) => d.id !== doc.id)];
        persistDocIds(next, userId);
        return next;
      });
    },
    [userId, persistDocIds]
  );

  const updateDocument = useCallback((docId, updates) => {
    setDocuments((prev) =>
      prev.map((d) => (d.id === docId ? { ...d, ...updates } : d))
    );
  }, []);

  const removeDocument = useCallback(
    (docId) => {
      setDocuments((prev) => {
        const next = prev.filter((d) => d.id !== docId);
        persistDocIds(next, userId);
        return next;
      });
    },
    [userId, persistDocIds]
  );

  const completedDocuments = documents.filter(
    (d) => d.processing_status === 'COMPLETED'
  );

  return (
    <AppContext.Provider
      value={{
        userId,
        documents,
        completedDocuments,
        addDocument,
        updateDocument,
        removeDocument,
        selectedDocumentId,
        setSelectedDocumentId,
      }}
    >
      {children}
    </AppContext.Provider>
  );
}

export function useApp() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error('useApp must be used inside <AppProvider>');
  return ctx;
}
