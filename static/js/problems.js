// What a failed scan says in plain words: who is not answering and what the user can do. Pure, tested with node.
export function scanProblem(message) {
  const text = String(message || '').toLowerCase();
  if (/tmdb[^.]*(401|key|api)/.test(text) || /key[^.]*tmdb/.test(text) || text.includes('tmdb_api_key')) {
    return {text: 'TMDB does not accept the API key.', action: 'Check the key in Settings.', link: '/settings#tmdb'};
  }
  if (text.includes('letterboxd') || text.includes('watchlist') || text.includes('private')) {
    return {text: 'Letterboxd is not responding, or the watchlist is not public.', action: 'Try again in a few minutes.', link: null};
  }
  if (text.includes('tmdb') || /request failed|timed out|timeout|connection/.test(text)) {
    return {text: 'TMDB is not responding.', action: 'Try again in a few minutes.', link: null};
  }
  return {text: 'The scan failed.', action: 'The reason is on the data page.', link: '/settings/data'};
}
