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

// Missing values always go last, whatever the direction.
const last = value => (value === null || value === undefined || Number.isNaN(value) ? -Infinity : value);
const ratingPerHour = film => (Number(film.rating) && Number(film.runtime) > 0 ? Number(film.rating) / (Number(film.runtime) / 60) : null);

// context.subscriptions (the user's own services) is only needed for "own-services".
export function sortFilms(films, order, context = {}) {
  const byTitle = (a, b) => String(a.title).toLowerCase().localeCompare(String(b.title).toLowerCase());
  const own = film => Object.keys(film.providers || {}).filter(provider => context.subscriptions?.has(provider)).length;
  const compare = {
    'rating-per-hour': (a, b) => last(ratingPerHour(b)) - last(ratingPerHour(a)),
    // Position 0 is the film added last, so the highest position has waited longest.
    'watchlist-oldest': (a, b) => last(b.watchlist_position) - last(a.watchlist_position),
    'own-services': (a, b) => own(b) - own(a),
    // Films of one series stand together, oldest first; films without a series follow by title.
    series: (a, b) => (a.collection ? 0 : 1) - (b.collection ? 0 : 1)
      || String(a.collection || '').localeCompare(String(b.collection || ''))
      || (a.collection ? (Number(a.year) || 0) - (Number(b.year) || 0) : 0),
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
    sections[section] = sortFilms(films.filter(film => matchesSection(film, section, filters, context)), filters.sort, context);
    sections[section].forEach(film => visibleKeys.add(filmKey(film)));
  });
  const unavailableMatches = sortFilms(unavailable.filter(film => matchesUnavailable(film, filters, context)), filters.sort, context);
  return {sections, unavailable: unavailableMatches, visibleCount: visibleKeys.size};
}

// Films that left one of the user's services recently: one entry per film, newest first,
// with every service it left.
export function recentlyRemoved(changes, subscriptions) {
  const byFilm = new Map();
  (changes || [])
    .filter(change => change.change === 'removed' && subscriptions.has(change.provider))
    .sort((a, b) => b.created - a.created)
    .forEach(change => {
      const known = byFilm.get(change.film_key);
      if (known) known.providers.push(change.provider);
      else byFilm.set(change.film_key, {...change, providers: [change.provider]});
    });
  return [...byFilm.values()];
}

// Evening mode: the three best-rated films that fit the time and genre and run on an own service.
// Films in `skip` (watched ones) are left out.
export function eveningSuggestions(films, {maximum, genre, subscriptions, skip = new Set()}) {
  return films
    .filter(film => !skip.has(filmKey(film))
      && (!maximum || (film.runtime > 0 && film.runtime <= maximum))
      && (genre === 'all' || (film.genres || []).includes(genre))
      && Object.entries(film.providers || {}).some(([provider, kinds]) =>
        subscriptions.has(provider) && kinds.some(kind => ['free', 'ads', 'flatrate'].includes(kind))))
    .sort((a, b) => (Number(b.rating) || 0) - (Number(a.rating) || 0) || String(a.title).localeCompare(String(b.title)))
    .slice(0, 3);
}
