import { apiFetch } from './client';

/**
 * Upload a file document.
 * @param {File} file
 * @param {string} userId
 * @returns {Promise<DocumentUploadResponse>}
 */
export async function uploadDocument(file, userId) {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('user_id', userId);

  return apiFetch('/api/v1/documents/upload', {
    method: 'POST',
    body: formData,
    // Do NOT set Content-Type — browser sets it with boundary automatically
  });
}

/**
 * Fetch a single document by ID.
 * @param {string} documentId
 * @returns {Promise<DocumentResponse>}
 */
export async function getDocument(documentId) {
  return apiFetch(`/api/v1/documents/${encodeURIComponent(documentId)}`);
}
