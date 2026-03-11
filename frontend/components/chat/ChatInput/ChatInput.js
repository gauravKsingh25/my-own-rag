'use client';

import { useRef, useEffect, forwardRef } from 'react';
import clsx from 'clsx';
import Button from '@/components/ui/Button/Button';
import styles from './ChatInput.module.css';

const ChatInput = forwardRef(function ChatInput(
  { value, onChange, onSend, isLoading, topK, onTopKChange, disabled },
  ref
) {
  const textareaRef = useRef(null);

  // Auto-grow textarea
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 200) + 'px';
  }, [value]);

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (!isLoading && value.trim()) onSend();
    }
  };

  return (
    <div className={styles.wrap}>
      {/* Top-K control */}
      <div className={styles.controls}>
        <label className={styles.topKLabel} htmlFor="top-k">
          Sources: <strong>{topK}</strong>
        </label>
        <input
          id="top-k"
          type="range"
          min="1"
          max="20"
          step="1"
          value={topK}
          onChange={(e) => onTopKChange(Number(e.target.value))}
          className={styles.slider}
          title={`Retrieve ${topK} source chunks`}
        />
      </div>

      <div className={styles.inputRow}>
        <textarea
          ref={textareaRef}
          className={styles.textarea}
          placeholder="Ask a question about your documents… (Enter to send, Shift+Enter for newline)"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          rows={1}
          disabled={isLoading || disabled}
        />
        <Button
          variant="primary"
          onClick={onSend}
          loading={isLoading}
          disabled={!value.trim() || disabled}
          className={styles.sendBtn}
          aria-label="Send message"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="22" y1="2" x2="11" y2="13"/>
            <polygon points="22 2 15 22 11 13 2 9 22 2"/>
          </svg>
        </Button>
      </div>
    </div>
  );
});

export default ChatInput;
