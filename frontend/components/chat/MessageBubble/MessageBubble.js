'use client';

import clsx from 'clsx';
import Badge from '@/components/ui/Badge/Badge';
import { formatDate, formatLatency, formatConfidence, getConfidenceLevel } from '@/lib/utils/format';
import styles from './MessageBubble.module.css';

/** Renders answer text with [Source N] citations highlighted */
function AnswerText({ content }) {
  const parts = content.split(/(\[Source \d+\])/g);
  return (
    <span>
      {parts.map((part, i) => {
        if (/^\[Source \d+\]$/.test(part)) {
          return <span key={i} className={styles.citation}>{part}</span>;
        }
        return part;
      })}
    </span>
  );
}

const CONFIDENCE_VARIANT = {
  'high':     'success',
  'good':     'success',
  'medium':   'warning',
  'low':      'warning',
  'very-low': 'error',
};

export default function MessageBubble({ message, onRateClick, onViewSources }) {
  const isUser      = message.role === 'user';
  const isAssistant = message.role === 'assistant';

  return (
    <div className={clsx(styles.row, isUser ? styles.userRow : styles.assistantRow)}>
      {/* Avatar */}
      <div className={clsx(styles.avatar, isUser ? styles.userAvatar : styles.asstAvatar)}>
        {isUser ? (
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
            <circle cx="12" cy="7" r="4"/>
          </svg>
        ) : (
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>
          </svg>
        )}
      </div>

      {/* Bubble */}
      <div className={styles.bubbleWrap}>
        <div className={clsx(styles.bubble, isUser ? styles.userBubble : styles.asstBubble)}>
          {isUser ? (
            <p className={styles.content}>{message.content}</p>
          ) : (
            <p className={styles.content}>
              <AnswerText content={message.content} />
            </p>
          )}
        </div>

        {/* Assistant meta row */}
        {isAssistant && (
          <div className={styles.metaRow}>
            {message.confidence_score != null && (
              <Badge
                variant={CONFIDENCE_VARIANT[getConfidenceLevel(message.confidence_score)] ?? 'default'}
                size="sm"
                title="Confidence score"
              >
                {formatConfidence(message.confidence_score)} confidence
              </Badge>
            )}

            {message.latency_ms != null && (
              <span className={styles.metaItem}>
                <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
                </svg>
                {formatLatency(message.latency_ms)}
              </span>
            )}

            {message.token_usage?.total_tokens != null && (
              <span className={styles.metaItem}>
                {message.token_usage.total_tokens.toLocaleString()} tokens
              </span>
            )}

            {message.sources?.length > 0 && (
              <button className={styles.actionBtn} onClick={() => onViewSources(message)}>
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/>
                  <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>
                </svg>
                {message.sources.length} sources
              </button>
            )}

            {message.interaction_id && !message.hasFeedback && (
              <button className={styles.actionBtn} onClick={() => onRateClick(message)}>
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
                </svg>
                Rate this
              </button>
            )}

            {message.hasFeedback && (
              <span className={styles.ratedBadge}>
                ★ Rated
              </span>
            )}
          </div>
        )}

        {/* Warnings */}
        {isAssistant && message.warnings?.length > 0 && (
          <div className={styles.warnings}>
            {message.warnings.map((w, i) => (
              <p key={i} className={styles.warningItem}>⚠ {w}</p>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
