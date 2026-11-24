// Every filter control and the label of its chip, in the order of the chips.
// Genres and services are not single controls; the filter bar makes their chips (filterbar.js).
export const FILTER_CONTROLS = [
  ['film-search', 'Search'], ['cost-filter', 'Cost'], ['runtime-filter', 'Runtime'], ['lb-filter', 'Letterboxd'], ['tmdb-filter', 'TMDB'],
  ['year-from', 'From'], ['year-to', 'To'], ['min-votes', 'TMDB votes'], ['keyword-filter', 'Keyword'],
  ['media-filter', 'Trailer'], ['change-filter', 'Changes'], ['provider-count-filter', 'Services'],
  ['age-filter', 'Age rating'],
  ['language-filter', 'Language'], ['origin-filter', 'Country'], ['show-unavailable', 'Also not available'], ['show-hidden', 'Set aside shown'],
  ['where-filter', 'Where'],
];

// A control is set when it differs from its default (data-default), first option, empty value or "unchecked".
export function isFilterSet(input) {
  if (input.type === 'checkbox') return Boolean(input.checked);
  if (input.dataset?.default !== undefined) return input.value !== input.dataset.default;
  if (input.options) return input.value !== input.options[0]?.value;
  return Boolean(input.value);
}

export function clearFilter(input) {
  if (input.type === 'checkbox') input.checked = false;
  else if (input.dataset?.default !== undefined) input.value = input.dataset.default;
  else input.value = input.options ? input.options[0].value : '';
  if (input.dataset) delete input.dataset.pending;
}

// The chips for the set filters: [{id, label, text}].
export function activeFilters(doc) {
  return FILTER_CONTROLS.map(([id, label]) => [doc.getElementById(id), id, label])
    .filter(([input]) => input && isFilterSet(input))
    .map(([input, id, label]) => ({
      id,
      label,
      // Hidden inputs behind a custom control carry their readable value in data-text.
      text: input.type === 'checkbox' ? '' : input.dataset?.text || (input.options ? input.options[input.selectedIndex]?.text ?? input.value : input.value),
    }));
}

export function resetFilters(doc) {
  FILTER_CONTROLS.forEach(([id]) => { const input = doc.getElementById(id); if (input) clearFilter(input); });
}

// Cost (the segmented control) as the sections and offer type filtering.js knows.
// A runtime as people say it: 95 → "95 min", 120 → "2 h", 225 → "3 h 45".
export function durationText(minutes) {
  const total = Math.round(Number(minutes));
  if (!Number.isFinite(total) || total <= 0) return '';
  if (total < 120) return `${total} min`;
  const rest = total % 60;
  return `${Math.floor(total / 60)} h${rest ? ` ${String(rest).padStart(2, '0')}` : ''}`;
}

export const COST = {all: ['available', 'all'], free: ['Free', 'all'], subscription: ['Paid', 'flatrate'], rent: ['Paid', 'rent']};

// ?lb=3.5&tmdb=7; the old ?rating=lb:3.8 (one source) becomes the matching new value.
export function ratingFromParams(params) {
  const number = text => (/^\d+(\.\d+)?$/.test(text || '') ? text : '');
  let lb = number(params.get('lb'));
  let tmdb = number(params.get('tmdb'));
  const old = (params.get('rating') || '').match(/^(lb|tmdb):(\d+(?:\.\d+)?)$/);
  if (old && old[1] === 'lb' && !lb) lb = old[2];
  if (old && old[1] === 'tmdb' && !tmdb) tmdb = old[2];
  return {lb, tmdb};
}

// The trigger's text: "LB 3.5+", "TMDB 7+", "LB 3.5+ · TMDB 7+", with "· 10k+ votes" when set.
export function ratingSummary(lb, tmdb, votesText = '') {
  return [lb ? `LB ${lb}+` : '', tmdb ? `TMDB ${tmdb}+` : '', votesText ? `${votesText} votes` : ''].filter(Boolean).join(' · ');
}

// Reads the filter controls into a plain object for filtering.js; genres come from the filter bar.
export function readFilters(doc, favoritesOnly, genres = {include: [], exclude: []}) {
  const value = id => doc.getElementById(id)?.value ?? '';
  // "Year from 2020, to 2000" means the same range as the other way round.
  const years = [Number(value('year-from')) || 0, Number(value('year-to')) || 9999].sort((a, b) => a - b);
  const [availability, kind] = COST[value('cost-filter')] || COST.all;
  const showUnavailable = Boolean(doc.getElementById('show-unavailable')?.checked);
  return {
    query: value('film-search').toLowerCase().trim(),
    // Films that are nowhere to stream only show on request, and only without a cost filter.
    availability: availability === 'available' && showUnavailable ? 'all' : availability,
    exclusive: value('provider-count-filter') === 'only1',
    showHidden: Boolean(doc.getElementById('show-hidden')?.checked),
    kind,
    minRating: Number(value('tmdb-filter')) || 0,
    minVotes: Number(value('min-votes')) || 0,
    genres,
    keyword: value('keyword-filter') || 'all',
    age: doc.getElementById('age-filter')?.value ?? 'all',
    language: doc.getElementById('language-filter')?.value ?? 'all',
    origin: doc.getElementById('origin-filter')?.value ?? 'all',
    minLetterboxd: Number(value('lb-filter')) || 0,
    maxRuntime: Number(value('runtime-filter')) || 0,
    mode: value('match-mode') || 'any',
    yearFrom: years[0],
    yearTo: years[1],
    where: value('where-filter') || 'all',
    media: value('media-filter') || 'all',
    change: value('change-filter') || 'all',
    minimumProviders: Number(value('provider-count-filter')) || 0,
    favoriteStatus: value('favorite-status-filter') || 'all',
    sort: value('sort-order'),
    favoritesOnly,
  };
}
