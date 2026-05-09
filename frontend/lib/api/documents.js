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

  return apiFetch('/api/v1/documents/upload', {
    method: 'POST',
    body: formData,
    headers: {
      'X-Authenticated-User-Id': userId,
    },
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

/**
 * Delete a single document and all related backend storage.
 * @param {string} documentId
 * @param {string} userId
 * @returns {Promise<{document_id: string, user_id: string, deleted: boolean, message: string}>}
 */
export async function deleteDocument(documentId, userId) {
  return apiFetch(`/api/v1/documents/${encodeURIComponent(documentId)}`, {
    method: 'DELETE',
    headers: {
      'X-Authenticated-User-Id': userId,
    },
  });
}
