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

export function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>'"]/g, char => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    "'": '&#39;',
    '"': '&quot;',
  }[char]));
}
