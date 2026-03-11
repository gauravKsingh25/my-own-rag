export const POLL_INTERVAL = 5000;
export const HEALTH_REFRESH_INTERVAL = 30000;

export const DOCUMENT_STATUSES = {
  UPLOADED:   'UPLOADED',
  PROCESSING: 'PROCESSING',
  PARSED:     'PARSED',
  CHUNKED:    'CHUNKED',
  EMBEDDED:   'EMBEDDED',
  COMPLETED:  'COMPLETED',
  FAILED:     'FAILED',
};

/** Statuses that mean the backend is still working on the document */
export const PROCESSING_STATUSES = [
  'UPLOADED',
  'PROCESSING',
  'PARSED',
  'CHUNKED',
  'EMBEDDED',
];

/** Progress % per status step (for the progress bar) */
export const STATUS_PROGRESS = {
  UPLOADED:   14,
  PROCESSING: 28,
  PARSED:     43,
  CHUNKED:    57,
  EMBEDDED:   71,
  COMPLETED:  100,
  FAILED:     0,
};

export const ACCEPTED_FILE_TYPES = {
  'application/pdf':  ['.pdf'],
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
  'application/vnd.openxmlformats-officedocument.presentationml.presentation': ['.pptx'],
  'text/plain': ['.txt'],
};

export const MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024; // 25 MB

export const DEFAULT_TOP_K = 5;
export const MIN_TOP_K = 1;
export const MAX_TOP_K = 20;

export const DOCS_STORAGE_PREFIX = 'rag_docs_';
export const USER_ID_KEY = 'rag_user_id';
export const THEME_KEY = 'rag_theme';
