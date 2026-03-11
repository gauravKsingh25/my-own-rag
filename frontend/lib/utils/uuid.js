import { USER_ID_KEY } from './constants';

/**
 * Returns a persistent user ID from localStorage.
 * Creates one with crypto.randomUUID() on first call.
 * Returns null during SSR (no window object).
 */
export function getUserId() {
  if (typeof window === 'undefined') return null;
  let id = localStorage.getItem(USER_ID_KEY);
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem(USER_ID_KEY, id);
  }
  return id;
}
