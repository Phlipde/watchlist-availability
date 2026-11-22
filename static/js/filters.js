// Every filter control and the label of its chip, in the order of the chips.
// Genres and services are not single controls; the filter bar makes their chips (filterbar.js).
export const FILTER_CONTROLS = [
  ['film-search', 'Search'], ['cost-filter', 'Cost'], ['runtime-filter', 'Runtime'], ['rating-filter', 'Rating'],
  ['year-from', 'From'], ['year-to', 'To'], ['min-votes', 'Votes'], ['keyword-filter', 'Keyword'],
  ['media-filter', 'Trailer'], ['change-filter', 'Changes'], ['provider-count-filter', 'Services'],
  ['age-filter', 'Age rating'],
  ['language-filter', 'Language'], ['origin-filter', 'Country'], ['show-unavailable', 'Also not available'], ['show-hidden', 'Set aside shown'],
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
export const COST = {all: ['available', 'all'], free: ['Free', 'all'], subscription: ['Paid', 'flatrate'], rent: ['Paid', 'rent']};

// Reads the filter controls into a plain object for filtering.js; genres come from the filter bar.
export function readFilters(doc, favoritesOnly, genres = {include: [], exclude: []}) {
  const value = id => doc.getElementById(id)?.value ?? '';
  // "Year from 2020, to 2000" means the same range as the other way round.
  const years = [Number(value('year-from')) || 0, Number(value('year-to')) || 9999].sort((a, b) => a - b);
  const [availability, kind] = COST[value('cost-filter')] || COST.all;
  const showUnavailable = Boolean(doc.getElementById('show-unavailable')?.checked);
  const [source, minimum] = value('rating-filter').split(':');
  return {
    query: value('film-search').toLowerCase().trim(),
    // Films that are nowhere to stream only show on request, and only without a cost filter.
    availability: availability === 'available' && showUnavailable ? 'all' : availability,
    exclusive: value('provider-count-filter') === 'only1',
    showHidden: Boolean(doc.getElementById('show-hidden')?.checked),
    kind,
    minRating: source === 'tmdb' ? Number(minimum) || 0 : 0,
    minVotes: Number(value('min-votes')) || 0,
    genres,
    keyword: value('keyword-filter') || 'all',
    age: doc.getElementById('age-filter')?.value ?? 'all',
    language: doc.getElementById('language-filter')?.value ?? 'all',
    origin: doc.getElementById('origin-filter')?.value ?? 'all',
    minLetterboxd: source === 'lb' ? Number(minimum) || 0 : 0,
    maxRuntime: Number(value('runtime-filter')) || 0,
    mode: value('match-mode') || 'any',
    yearFrom: years[0],
    yearTo: years[1],
    media: value('media-filter') || 'all',
    change: value('change-filter') || 'all',
    minimumProviders: Number(value('provider-count-filter')) || 0,
    favoriteStatus: value('favorite-status-filter') || 'all',
    sort: value('sort-order'),
    favoritesOnly,
  };
}
