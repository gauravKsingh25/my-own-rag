import { format, formatDistanceToNow } from 'date-fns';

export function formatDate(dateString) {
  if (!dateString) return '—';
  try {
    return format(new Date(dateString), 'MMM d, yyyy · HH:mm');
  } catch {
    return dateString;
  }
}

export function formatRelativeTime(dateString) {
  if (!dateString) return '—';
  try {
    return formatDistanceToNow(new Date(dateString), { addSuffix: true });
  } catch {
    return dateString;
  }
}

export function formatFileSize(bytes) {
  if (!bytes || bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

export function formatLatency(ms) {
  if (ms == null) return '—';
  if (ms < 1000) return `${Math.round(ms)} ms`;
  return `${(ms / 1000).toFixed(1)} s`;
}

export function formatConfidence(score) {
  if (score == null) return '—';
  return `${Math.round(score * 100)}%`;
}

/** Returns a semantic level string used for CSS class variants */
export function getConfidenceLevel(score) {
  if (score >= 0.9) return 'high';
  if (score >= 0.7) return 'good';
  if (score >= 0.5) return 'medium';
  if (score >= 0.3) return 'low';
  return 'very-low';
}

export function shortenId(id) {
  if (!id) return '—';
  return `${id.slice(0, 8)}…`;
}

export function fileTypeLabel(type) {
  const map = { pdf: 'PDF', docx: 'Word', pptx: 'PowerPoint', txt: 'Text' };
  return map[type?.toLowerCase()] ?? type?.toUpperCase() ?? 'Unknown';
}
