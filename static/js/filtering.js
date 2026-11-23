// Pure filtering over the film data. No DOM access, so it can be tested with `node --test`.
import {linkMatches} from './link-filters.js';

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

// Runtime limit in minutes (0 = any); films without a runtime drop out once a limit is set.
function runtimeMatches(maximum, minutes) {
  return !maximum || (minutes > 0 && minutes <= maximum);
}

// Genres: any of the included ones, none of the excluded ones.
function genresMatch(genres, filmGenres = []) {
  return (!genres.include.length || genres.include.some(genre => filmGenres.includes(genre)))
    && !genres.exclude.some(genre => filmGenres.includes(genre));
}

// Filters that apply the same way to available and unavailable films.
function commonMatches(film, filters, context) {
  const key = filmKey(film);
  if (!linkMatches(film, filters.link, context.availabilityOf)) return false;
  // Films set aside with "Not now" stay away until their date, unless asked for.
  if (!filters.showHidden && context.hiddenKeys?.has(key)) return false;
  const year = Number(film.year) || 0;
  const favoriteMatch = !filters.favoritesOnly || (
    context.favorites.has(key)
    && (filters.favoriteStatus === 'all' || context.favorites.get(key)?.status === filters.favoriteStatus)
  );
  return favoriteMatch
    && [film.title, film.director, ...(film.cast || []), ...(film.keywords || [])]
      .filter(Boolean)
      .some(value => String(value).toLowerCase().includes(filters.query))
    && genresMatch(filters.genres, film.genres)
    && (filters.keyword === 'all' || (film.keywords || []).includes(filters.keyword))
    && ageMatches(filters.age, film.certification)
    && (!filters.language || filters.language === 'all' || film.original_language === filters.language)
    && (!filters.origin || filters.origin === 'all' || (film.origin_countries || []).includes(filters.origin))
    // The server decides this with the rule of the costs page (watchlist_app/costs.py).
    && (!filters.exclusive || film.only_on_my_services === true)
    && runtimeMatches(filters.maxRuntime, Number(film.runtime) || 0)
    && (filters.media === 'all' || (filters.media === 'trailer' && Boolean(film.trailer_url)))
    && (filters.change === 'all' || changeTypes(film, context.selected).includes(filters.change))
    && Object.keys(film.providers || {}).filter(provider => context.selected.has(provider)).length >= filters.minimumProviders
    && (Number(film.rating) || 0) >= filters.minRating
    && (Number(film.vote_count) || 0) >= filters.minVotes
    && (!filters.minLetterboxd || (Number(film.letterboxd_rating) || 0) >= filters.minLetterboxd)
    && year >= filters.yearFrom
    && year <= filters.yearTo;
}

// Age rating filter: `selected` is "all" or a comma list of ratings ("6,12"). Films without a rating
// are left out once a rating is chosen.
export function ageMatches(selected, certification) {
  if (!selected || selected === 'all') return true;
  return Boolean(certification) && selected.split(',').includes(certification);
}

// Ratings in a sensible order: numbers ascending, then the others alphabetically.
export function sortRatings(values) {
  return [...new Set(values.filter(Boolean))].sort((a, b) => {
    const [x, y] = [/^\d+$/.test(a), /^\d+$/.test(b)];
    return x && y ? Number(a) - Number(b) : x !== y ? (x ? -1 : 1) : a.localeCompare(b);
  });
}

// Watchlist films with a cinema or home release still ahead (dates "YYYY-MM-DD"), soonest first.
export function comingSoon(films, today) {
  const next = film => [film.cinema_date, film.home_date].filter(date => date && date >= today).sort()[0];
  return films.filter(next)
    .sort((a, b) => next(a).localeCompare(next(b)) || String(a.title).localeCompare(String(b.title)));
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
const numberOrNull = value => (value === null || value === undefined || value === '' || !Number.isFinite(Number(value)) ? null : Number(value));

// A fixed shuffle per seed: the order stays put while the page redraws (scan polls, favorites).
function shuffleRank(key, seed) {
  let hash = 2166136261 ^ seed;
  for (const char of String(key)) hash = Math.imul(hash ^ char.charCodeAt(0), 16777619);
  return hash >>> 0;
}

// The nine sorts of the filter bar (names in web/routes.py SORTS). context: favorites (Map, for
// "priority") and seed (number, for "random").
export function sortFilms(films, order, context = {}) {
  const byTitle = (a, b) => String(a.title).toLowerCase().localeCompare(String(b.title).toLowerCase());
  const letterboxd = (a, b) => last(numberOrNull(b.letterboxd_rating)) - last(numberOrNull(a.letterboxd_rating));
  const tmdb = (a, b) => (Number(b.rating) || 0) - (Number(a.rating) || 0);
  const favorite = film => Number(Boolean(context.favorites?.has(filmKey(film))));
  const added = film => Number((film.provider_changes?.added || []).length > 0);
  const compare = {
    // Favorites first, then the community's rating, then TMDB's.
    priority: (a, b) => favorite(b) - favorite(a) || letterboxd(a, b) || tmdb(a, b),
    letterboxd: (a, b) => letterboxd(a, b) || tmdb(a, b),
    rating: tmdb,
    runtime: (a, b) => (numberOrNull(a.runtime) || Infinity) - (numberOrNull(b.runtime) || Infinity),
    'year-desc': (a, b) => (Number(b.year) || 0) - (Number(a.year) || 0),
    // Position 0 is the film added last.
    recent: (a, b) => (numberOrNull(a.watchlist_position) ?? Infinity) - (numberOrNull(b.watchlist_position) ?? Infinity),
    // The film that has waited longest (highest position) first.
    oldest: (a, b) => (numberOrNull(b.watchlist_position) ?? -Infinity) - (numberOrNull(a.watchlist_position) ?? -Infinity),
    new: (a, b) => added(b) - added(a) || letterboxd(a, b),
    random: (a, b) => shuffleRank(filmKey(a), context.seed || 0) - shuffleRank(filmKey(b), context.seed || 0),
  }[order] || (() => 0);
  return [...films].sort((a, b) => compare(a, b) || byTitle(a, b));
}

// How many available films the filters show (each film once); no sorting, so it is cheap to repeat.
export function countVisible(films, filters, context) {
  return films.filter(film => SECTIONS.some(section => matchesSection(film, section, filters, context))).length;
}

// Counts per option of one filter, with that filter itself left out ("what if I picked this?").
// open(filters, context) returns the filters and context without the facet; keysOf(film) the
// film's values for it (only values that match `section` when given).
export function facetCounts(films, filters, context, open, keysOf) {
  const [openFilters, openContext] = open(filters, context);
  const counts = new Map();
  films.filter(film => SECTIONS.some(section => matchesSection(film, section, openFilters, openContext)))
    .forEach(film => new Set(keysOf(film)).forEach(key => counts.set(key, (counts.get(key) || 0) + 1)));
  return counts;
}

// For an empty result: the one filter whose removal brings back the most films.
// candidates: [{id, label, open(filters, context) -> [filters, context]}]
export function bestRelaxation(films, filters, context, candidates) {
  return candidates
    .map(candidate => ({...candidate, count: countVisible(films, ...candidate.open(filters, context))}))
    .filter(candidate => candidate.count > 0)
    .sort((a, b) => b.count - a.count)[0] || null;
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
  // One list, each film once, in the chosen order. A film that matches both sections gets a card for "All".
  const sectionOf = new Map();
  SECTIONS.forEach(section => sections[section].forEach(film => sectionOf.set(filmKey(film), sectionOf.has(filmKey(film)) ? 'All' : section)));
  const merged = new Map(SECTIONS.flatMap(section => sections[section]).map(film => [filmKey(film), film]));
  return {sections, films: sortFilms([...merged.values()], filters.sort, context), sectionOf, unavailable: unavailableMatches, visibleCount: visibleKeys.size};
}

// Watchlist films TMDB recommends for `film` that run on an own service without extra cost,
// in TMDB's order. Watched films (`skip`) are left out.
export function similarOnServices(film, films, subscriptions, skip = new Set(), limit = 5) {
  const byKey = new Map(films.map(item => [filmKey(item), item]));
  return [...new Set(film.similar_ids || [])]
    .map(id => byKey.get(String(id)))
    .filter(item => item && item !== film && !skip.has(filmKey(item))
      && Object.entries(item.providers || {}).some(([provider, kinds]) =>
        subscriptions.has(provider) && kinds.some(kind => ['free', 'ads', 'flatrate'].includes(kind))))
    .slice(0, limit);
}

// Other countries where the film runs on one of the user's services without extra cost:
// [[country, [services]]], the current country left out, sorted by country code.
export function elsewhereOnServices(byCountry, subscriptions, current) {
  return Object.entries(byCountry || {})
    .filter(([country]) => country !== current)
    .map(([country, offers]) => [country, Object.entries(offers)
      .filter(([provider, kinds]) => subscriptions.has(provider) && kinds.some(kind => ['free', 'ads', 'flatrate'].includes(kind)))
      .map(([provider]) => provider).sort()])
    .filter(([, services]) => services.length)
    .sort(([a], [b]) => a.localeCompare(b));
}
