// Pure filtering over the film data. No DOM access, so it can be tested with `node --test`.

export const SECTION_KINDS = {
  Free: ['free', 'ads'],
  Paid: ['flatrate', 'rent'],
};
export const SECTIONS = Object.keys(SECTION_KINDS);

// The server sends `key` (the TMDB id); older saved scans only have title and year.
export function filmKey(film) {
  return film.key ?? `${film.title}|${film.year}`;
}

// Providers of a film that have an offer belonging to the section.
export function sectionProviders(film, section) {
  const sectionKinds = SECTION_KINDS[section];
  return Object.entries(film.providers || {})
    .filter(([, kinds]) => kinds.some(kind => sectionKinds.includes(kind)))
    .map(([name]) => name);
}

// Offer types the selected providers have for this film.
export function selectedKinds(film, selected) {
  const kinds = new Set();
  Object.entries(film.providers || {}).forEach(([provider, providerKinds]) => {
    if (selected.has(provider)) providerKinds.forEach(kind => kinds.add(kind));
  });
  return [...kinds];
}

// Stored availability changes of a film, limited to the selected providers.
export function selectedChanges(film, selected) {
  const changes = film.provider_changes || {};
  return {
    added: (changes.added || []).filter(provider => selected.has(provider)),
    removed: (changes.removed || []).filter(provider => selected.has(provider)),
  };
}

export function changeTypes(film, selected) {
  const changes = selectedChanges(film, selected);
  return Object.keys(changes).filter(change => changes[change].length);
}

function runtimeMatches(runtime, minutes) {
  return runtime === 'all'
    || (runtime === 'short' && minutes > 0 && minutes < 90)
    || (runtime === 'medium' && minutes >= 90 && minutes <= 120)
    || (runtime === 'long' && minutes > 120);
}

// Filters that apply the same way to available and unavailable films.
function commonMatches(film, filters, context) {
  const key = filmKey(film);
  const year = Number(film.year) || 0;
  const favoriteMatch = !filters.favoritesOnly || (
    context.favorites.has(key)
    && (filters.favoriteStatus === 'all' || context.favorites.get(key)?.status === filters.favoriteStatus)
  );
  return favoriteMatch
    && [film.title, film.director, ...(film.cast || []), ...(film.keywords || [])]
      .filter(Boolean)
      .some(value => String(value).toLowerCase().includes(filters.query))
    && (filters.genre === 'all' || (film.genres || []).includes(filters.genre))
    && (filters.keyword === 'all' || (film.keywords || []).includes(filters.keyword))
    // The server decides this with the rule of the costs page (watchlist_app/costs.py).
    && (!filters.exclusive || film.only_on_my_services === true)
    && runtimeMatches(filters.runtime, Number(film.runtime) || 0)
    && (filters.media === 'all' || (filters.media === 'trailer' && Boolean(film.trailer_url)))
    && (filters.change === 'all' || changeTypes(film, context.selected).includes(filters.change))
    && Object.keys(film.providers || {}).filter(provider => context.selected.has(provider)).length >= filters.minimumProviders
    && (Number(film.rating) || 0) >= filters.minRating
    && (Number(film.vote_count) || 0) >= filters.minVotes
    && year >= filters.yearFrom
    && year <= filters.yearTo;
}

// Should the film get a card in this section ("Free" or "Paid")?
export function matchesSection(film, section, filters, context) {
  const providers = sectionProviders(film, section);
  if (!providers.length) return false;
  const selected = context.selected;
  const providerMatch = filters.mode === 'all'
    ? selected.size > 0 && [...selected].every(provider => providers.includes(provider))
    : providers.some(provider => selected.has(provider));
  // "No longer available" also shows films that just left every selected provider.
  const leftSelected = filters.change === 'removed' && selectedChanges(film, selected).removed.length > 0;
  if (!providerMatch && !leftSelected) return false;
  if (!['all', 'available', section].includes(filters.availability)) return false;
  if (filters.kind !== 'all') {
    // The offer type must come from a selected provider and belong to this section.
    if (!SECTION_KINDS[section].includes(filters.kind)) return false;
    if (!selectedKinds(film, selected).includes(filters.kind)) return false;
  }
  return commonMatches(film, filters, context);
}

export function matchesUnavailable(film, filters, context) {
  if (!['all', 'unavailable'].includes(filters.availability)) return false;
  if (filters.kind !== 'all') return false;
  return commonMatches(film, filters, context);
}

export function sortFilms(films, order) {
  const byTitle = (a, b) => String(a.title).toLowerCase().localeCompare(String(b.title).toLowerCase());
  const compare = {
    'year-desc': (a, b) => (Number(b.year) || 0) - (Number(a.year) || 0),
    'year-asc': (a, b) => (Number(a.year) || 0) - (Number(b.year) || 0),
    rating: (a, b) => (Number(b.rating) || 0) - (Number(a.rating) || 0),
    popularity: (a, b) => (Number(b.popularity) || 0) - (Number(a.popularity) || 0),
    votes: (a, b) => (Number(b.vote_count) || 0) - (Number(a.vote_count) || 0),
  }[order];
  return [...films].sort((a, b) => (compare ? compare(a, b) : 0) || byTitle(a, b));
}

// Returns what to show: films per section, matching unavailable films and the visible count.
export function filterFilms(films, unavailable, filters, context) {
  const sections = {};
  const visibleKeys = new Set();
  SECTIONS.forEach(section => {
    sections[section] = sortFilms(films.filter(film => matchesSection(film, section, filters, context)), filters.sort);
    sections[section].forEach(film => visibleKeys.add(filmKey(film)));
  });
  const unavailableMatches = sortFilms(unavailable.filter(film => matchesUnavailable(film, filters, context)), filters.sort);
  return {sections, unavailable: unavailableMatches, visibleCount: visibleKeys.size};
}

// Evening mode: the three best-rated films that fit the time and genre and run on an own service.
export function eveningSuggestions(films, {maximum, genre, subscriptions}) {
  return films
    .filter(film => (!maximum || (film.runtime > 0 && film.runtime <= maximum))
      && (genre === 'all' || (film.genres || []).includes(genre))
      && Object.entries(film.providers || {}).some(([provider, kinds]) =>
        subscriptions.has(provider) && kinds.some(kind => ['free', 'ads', 'flatrate'].includes(kind))))
    .sort((a, b) => (Number(b.rating) || 0) - (Number(a.rating) || 0) || String(a.title).localeCompare(String(b.title)))
    .slice(0, 3);
}
