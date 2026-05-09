'use client';

import toast from 'react-hot-toast';
import DropZone from '@/components/documents/DropZone/DropZone';
import DocumentCard from '@/components/documents/DocumentCard/DocumentCard';
import { useDocuments } from '@/lib/hooks/useDocuments';
import { APIError } from '@/lib/api/client';
import styles from './page.module.css';

export default function DocumentsPage() {
  const { documents, uploading, deletingDocIds, upload, remove } = useDocuments();

  const handleUpload = async (file) => {
    try {
      await upload(file);
      toast.success(`"${file.name}" uploaded! Processing started.`);
    } catch (err) {
      const msg = err instanceof APIError ? err.message : 'Upload failed — please try again.';
      toast.error(msg);
    }
  };

  const handleDelete = async (doc) => {
    try {
      await remove(doc.id);
      toast.success(`"${doc.filename}" deleted from all storage.`);
    } catch (err) {
      const msg = err instanceof APIError ? err.message : 'Delete failed — please try again.';
      toast.error(msg);
    }
  };

  return (
    <div className={styles.page}>
      {/* Header */}
      <div className={styles.header}>
        <div>
          <h2 className={styles.title}>Documents</h2>
          <p className={styles.subtitle}>Upload and manage your knowledge base files.</p>
        </div>
        <div className={styles.count}>
          {documents.length} document{documents.length !== 1 && 's'}
        </div>
      </div>

      {/* Drop zone */}
      <DropZone onUpload={handleUpload} uploading={uploading} />

      {/* Document list */}
      {documents.length > 0 && (
        <section className={styles.section}>
          <h3 className={styles.sectionTitle}>Your Documents</h3>
          <div className={styles.grid}>
            {documents.map((doc) => (
              <DocumentCard
                key={doc.id}
                doc={doc}
                onDelete={handleDelete}
                deleting={Boolean(deletingDocIds[doc.id])}
              />
            ))}
          </div>
        </section>
      )}

      {documents.length === 0 && !uploading && (
        <div className={styles.empty}>
          <p>No documents yet. Upload one above to get started.</p>
        </div>
      )}
    </div>
  );
}
