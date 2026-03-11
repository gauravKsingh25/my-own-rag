'use client';

import { useEffect, useRef } from 'react';
import MessageBubble from '../MessageBubble/MessageBubble';
import Spinner from '@/components/ui/Spinner/Spinner';
import styles from './ChatWindow.module.css';

export default function ChatWindow({ messages, isLoading, onRateClick, onViewSources }) {
  const bottomRef = useRef(null);

  // Auto-scroll to latest message
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  if (messages.length === 0 && !isLoading) {
    return (
      <div className={styles.empty}>
        <div className={styles.emptyIcon}>
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
          </svg>
        </div>
        <p className={styles.emptyTitle}>Start a conversation</p>
        <p className={styles.emptyHint}>Ask anything about your uploaded documents.</p>
      </div>
    );
  }

  return (
    <div className={styles.window}>
      <div className={styles.messages}>
        {messages.map((msg) => (
          <MessageBubble
            key={msg.id}
            message={msg}
            onRateClick={onRateClick}
            onViewSources={onViewSources}
          />
        ))}

        {isLoading && (
          <div className={styles.typingRow}>
            <div className={styles.typingBubble}>
              <Spinner size="sm" />
              <span>Thinking…</span>
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>
    </div>
  );
}
