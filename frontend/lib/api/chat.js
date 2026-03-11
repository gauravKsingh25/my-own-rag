import { apiFetch } from './client';

/**
 * Send a chat query through the RAG pipeline.
 * @param {{ query: string, userId: string, documentId?: string|null, topK?: number }} params
 * @returns {Promise<ChatResponse>}
 */
export async function sendChat({ query, userId, documentId = null, topK = 5 }) {
  return apiFetch('/api/v1/chat/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      query,
      user_id: userId,
      ...(documentId ? { document_id: documentId } : {}),
      top_k: topK,
    }),
  });
}

/**
 * Submit user feedback for a chat interaction.
 * @param {{ interactionId: string, rating: number, comment?: string|null }} params
 * @returns {Promise<FeedbackResponse>}
 */
export async function submitFeedback({ interactionId, rating, comment = null }) {
  return apiFetch('/api/v1/chat/feedback', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      interaction_id: interactionId,
      rating,
      ...(comment ? { comment } : {}),
    }),
  });
}
