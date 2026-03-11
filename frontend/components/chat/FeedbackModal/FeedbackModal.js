'use client';

import { useState } from 'react';
import Modal from '@/components/ui/Modal/Modal';
import Button from '@/components/ui/Button/Button';
import styles from './FeedbackModal.module.css';

export default function FeedbackModal({ isOpen, onClose, onSubmit, loading }) {
  const [rating, setRating] = useState(0);
  const [hovered, setHovered] = useState(0);
  const [comment, setComment] = useState('');

  const handleSubmit = () => {
    if (!rating) return;
    onSubmit({ rating, comment: comment.trim() || null });
  };

  const handleClose = () => {
    setRating(0);
    setHovered(0);
    setComment('');
    onClose();
  };

  return (
    <Modal isOpen={isOpen} onClose={handleClose} title="Rate this response" size="sm">
      <div className={styles.body}>
        <p className={styles.hint}>How well did the answer address your question?</p>

        {/* Star rating */}
        <div className={styles.stars}>
          {[1, 2, 3, 4, 5].map((n) => (
            <button
              key={n}
              className={styles.star}
              aria-label={`Rate ${n} star${n > 1 ? 's' : ''}`}
              onClick={() => setRating(n)}
              onMouseEnter={() => setHovered(n)}
              onMouseLeave={() => setHovered(0)}
            >
              <svg
                width="28"
                height="28"
                viewBox="0 0 24 24"
                fill={n <= (hovered || rating) ? 'currentColor' : 'none'}
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                style={{ color: n <= (hovered || rating) ? 'var(--color-warning)' : 'var(--color-border)' }}
              >
                <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
              </svg>
            </button>
          ))}
        </div>

        {rating > 0 && (
          <p className={styles.ratingLabel}>
            {['', 'Poor', 'Fair', 'Good', 'Very good', 'Excellent'][rating]}
          </p>
        )}

        {/* Optional comment */}
        <textarea
          className={styles.comment}
          placeholder="Optional: add more details about your rating…"
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          maxLength={2000}
          rows={3}
        />

        <div className={styles.actions}>
          <Button variant="ghost" onClick={handleClose} disabled={loading}>
            Cancel
          </Button>
          <Button
            variant="primary"
            onClick={handleSubmit}
            loading={loading}
            disabled={!rating}
          >
            Submit feedback
          </Button>
        </div>
      </div>
    </Modal>
  );
}
