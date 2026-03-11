'use client';

import { useState } from 'react';
import toast from 'react-hot-toast';
import clsx from 'clsx';
import { useApp } from '@/lib/context/AppContext';
import { useChat } from '@/lib/hooks/useChat';
import ChatWindow from '@/components/chat/ChatWindow/ChatWindow';
import ChatInput from '@/components/chat/ChatInput/ChatInput';
import SourcePanel from '@/components/chat/SourcePanel/SourcePanel';
import DocumentSelector from '@/components/chat/DocumentSelector/DocumentSelector';
import FeedbackModal from '@/components/chat/FeedbackModal/FeedbackModal';
import Button from '@/components/ui/Button/Button';
import { DEFAULT_TOP_K } from '@/lib/utils/constants';
import { RateLimitError, QuotaError, ServiceUnavailableError } from '@/lib/api/client';
import styles from './page.module.css';

export default function ChatPage() {
  const { userId, selectedDocumentId } = useApp();
  const { messages, isLoading, sendMessage, submitFeedback, clearMessages } = useChat();

  const [input, setInput]           = useState('');
  const [topK, setTopK]             = useState(DEFAULT_TOP_K);
  const [sourcePanelOpen, setSourcePanelOpen] = useState(false);
  const [panelSources, setPanelSources]       = useState([]);

  // Feedback modal state
  const [feedbackOpen, setFeedbackOpen]     = useState(false);
  const [feedbackTarget, setFeedbackTarget] = useState(null);
  const [feedbackLoading, setFeedbackLoading] = useState(false);

  /* ── Send a message ── */
  const handleSend = async () => {
    const query = input.trim();
    if (!query || isLoading) return;
    setInput('');

    try {
      await sendMessage({ query, userId, documentId: selectedDocumentId, topK });
    } catch (err) {
      if (err instanceof RateLimitError) {
        toast.error(
          `Rate limit reached. Try again in ${err.retryAfter}s.`,
          { duration: Math.min(err.retryAfter * 1000, 10000) }
        );
      } else if (err instanceof QuotaError) {
        toast.error('Daily quota exceeded. Resets tomorrow.', { duration: 8000 });
      } else if (err instanceof ServiceUnavailableError) {
        toast.error('Service temporarily unavailable (circuit breaker open).', { duration: 6000 });
      } else {
        toast.error(err.message ?? 'Something went wrong.');
      }
    }
  };

  /* ── View sources ── */
  const handleViewSources = (message) => {
    setPanelSources(message.sources ?? []);
    setSourcePanelOpen(true);
  };

  /* ── Open feedback modal ── */
  const handleRateClick = (message) => {
    setFeedbackTarget(message);
    setFeedbackOpen(true);
  };

  /* ── Submit feedback ── */
  const handleFeedbackSubmit = async ({ rating, comment }) => {
    if (!feedbackTarget) return;
    setFeedbackLoading(true);
    try {
      await submitFeedback({
        messageId: feedbackTarget.id,
        interactionId: feedbackTarget.interaction_id,
        rating,
        comment,
      });
      toast.success('Thanks for your feedback!');
      setFeedbackOpen(false);
      setFeedbackTarget(null);
    } catch {
      toast.error('Failed to submit feedback. Please try again.');
    } finally {
      setFeedbackLoading(false);
    }
  };

  return (
    <div className={styles.layout}>
      {/* Toolbar */}
      <div className={styles.toolbar}>
        <DocumentSelector />
        <div className={styles.toolbarRight}>
          {messages.length > 0 && (
            <Button variant="ghost" size="sm" onClick={clearMessages}>
              Clear chat
            </Button>
          )}
          <button
            className={clsx(styles.sourcesToggle, sourcePanelOpen && styles.sourcesToggleActive)}
            onClick={() => setSourcePanelOpen((o) => !o)}
            title="Toggle sources panel"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/>
              <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>
            </svg>
            Sources
          </button>
        </div>
      </div>

      {/* Main chat + source panel */}
      <div className={styles.body}>
        <div className={styles.chatArea}>
          <ChatWindow
            messages={messages}
            isLoading={isLoading}
            onRateClick={handleRateClick}
            onViewSources={handleViewSources}
          />
          <ChatInput
            value={input}
            onChange={setInput}
            onSend={handleSend}
            isLoading={isLoading}
            topK={topK}
            onTopKChange={setTopK}
            disabled={!userId}
          />
        </div>

        <SourcePanel
          sources={panelSources}
          isOpen={sourcePanelOpen}
          onClose={() => setSourcePanelOpen(false)}
        />
      </div>

      {/* Feedback modal */}
      <FeedbackModal
        isOpen={feedbackOpen}
        onClose={() => { setFeedbackOpen(false); setFeedbackTarget(null); }}
        onSubmit={handleFeedbackSubmit}
        loading={feedbackLoading}
      />
    </div>
  );
}
