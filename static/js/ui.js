// A number for HTML: only a finite number is written, anything else becomes the fallback.
// Year, runtime and rating come from TMDB as numbers, but a restored backup could hold any text.
export function numberText(value, fallback = '') {
  if (value === null || value === undefined || value === '' || typeof value === 'boolean') return fallback;
  const number = Number(value);
  return Number.isFinite(number) ? String(number) : fallback;
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
