// A number for HTML: only a finite number is written, anything else becomes the fallback.
// Year, runtime and rating come from TMDB as numbers, but a restored backup could hold any text.
export function numberText(value, fallback = '') {
  if (value === null || value === undefined || value === '' || typeof value === 'boolean') return fallback;
  const number = Number(value);
  return Number.isFinite(number) ? String(number) : fallback;
}

// A point in time without seconds, e.g. "15 Nov 2026, 23:10".
export function dateTime(seconds) {
  return new Date(seconds * 1000).toLocaleString([], {dateStyle: 'medium', timeStyle: 'short'});
}

// How long ago a point in time was, e.g. "12 min ago", "3 h ago" or "4 days ago" (same words as agoText in
// web/routes.py, so the header reads alike on every page).
export function ago(seconds) {
  const minutes = Math.floor((Date.now() / 1000 - seconds) / 60);
  const hours = Math.floor(minutes / 60);
  return minutes < 1 ? 'just now' : minutes < 60 ? `${minutes} min ago` : hours < 48 ? `${hours} h ago` : `${Math.floor(hours / 24)} days ago`;
}

export function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>'"]/g, char => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    "'": '&#39;',
    '"': '&quot;',
  }[char]));
}

// Up to two letters for a service without a logo: "Arte" -> "A", "YouTube Free" -> "YF".
export const initials = name => String(name || '').replace(/[^\p{L}\p{N} ]/gu, '').split(/\s+/).filter(Boolean)
  .slice(0, 2).map(word => word[0]).join('').toUpperCase() || '?';
