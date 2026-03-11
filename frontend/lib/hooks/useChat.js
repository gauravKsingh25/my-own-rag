'use client';

import { useState, useCallback } from 'react';
import { sendChat as sendChatAPI, submitFeedback as submitFeedbackAPI } from '@/lib/api/chat';

export function useChat() {
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  const sendMessage = useCallback(
    async ({ query, userId, documentId, topK }) => {
      setError(null);

      // Optimistically append the user message
      const userMsg = {
        id: crypto.randomUUID(),
        role: 'user',
        content: query,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, userMsg]);
      setIsLoading(true);

      try {
        const res = await sendChatAPI({ query, userId, documentId, topK });

        const assistantMsg = {
          id: crypto.randomUUID(),
          role: 'assistant',
          content: res.answer,
          timestamp: new Date(),
          interaction_id: res.interaction_id,
          citations: res.citations ?? [],
          confidence_score: res.confidence_score,
          sources: res.sources ?? [],
          token_usage: res.token_usage,
          latency_ms: res.latency_ms,
          warnings: res.warnings ?? [],
          hasFeedback: false,
        };

        setMessages((prev) => [...prev, assistantMsg]);
        return assistantMsg;
      } catch (err) {
        setError(err);
        throw err;
      } finally {
        setIsLoading(false);
      }
    },
    []
  );

  const submitFeedback = useCallback(async ({ messageId, interactionId, rating, comment }) => {
    await submitFeedbackAPI({ interactionId, rating, comment });
    setMessages((prev) =>
      prev.map((m) => (m.id === messageId ? { ...m, hasFeedback: true } : m))
    );
  }, []);

  const clearMessages = useCallback(() => {
    setMessages([]);
    setError(null);
  }, []);

  return { messages, isLoading, error, sendMessage, submitFeedback, clearMessages };
}
