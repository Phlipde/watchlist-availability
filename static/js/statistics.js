// Numbers for the stats page, from one saved scan. Pure functions, so they are tested without a page.
import {serviceGroup} from './catalog.js';

const WATCH_KINDS = ['free', 'ads', 'flatrate'];  // watchable without paying per film
const DAY = 24 * 3600;

// [[key, count], …] sorted by count, then by key; empty keys are skipped.
export function countBy(items, keysOf) {
  const counts = new Map();
  items.forEach(item => new Set(keysOf(item) || []).forEach(key => {
    if (key === null || key === undefined || key === '') return;
    counts.set(key, (counts.get(key) || 0) + 1);
  }));
  return [...counts].sort((a, b) => b[1] - a[1] || String(a[0]).localeCompare(String(b[0])));
}

const numbers = values => values.map(Number).filter(value => Number.isFinite(value) && value > 0);
const average = values => (values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : null);
const kindsOf = film => Object.values(film.providers || {}).flat();

// Every film gets exactly one of these, the best way to watch it, so the counts add up to the watchlist.
export const AVAILABILITY = ['own_subscription', 'free', 'ads', 'other_subscription', 'rent_buy', 'coming_soon', 'unavailable'];

// own_subscription: free, ad-supported or subscription on a service you have; then free, ads, a subscription you
// do not have, rent or buy; no offer at all: coming soon (future release date) or unavailable.
// `own` holds service groups (a Netflix subscription covers every Netflix plan).
export function bestAvailability(film, own, today) {
  const offers = Object.entries(film.providers || {});
  const kinds = offers.flatMap(([, list]) => list);
  if (offers.some(([service, list]) => own.has(serviceGroup(service)) && list.some(kind => ['free', 'ads', 'flatrate'].includes(kind)))) return 'own_subscription';
  if (kinds.includes('free')) return 'free';
  if (kinds.includes('ads')) return 'ads';
  if (kinds.includes('flatrate')) return 'other_subscription';
  if (kinds.some(kind => kind === 'rent' || kind === 'buy')) return 'rent_buy';
  return [film.cinema_date, film.home_date].some(date => date && date > today) ? 'coming_soon' : 'unavailable';
}

// TMDB fills unreleased films with far-away placeholder dates: a year more than 3 years ahead counts as unknown.
export const plausibleYear = (year, now) => {
  const value = Number(year);
  return value > 0 && value <= new Date(now * 1000).getUTCFullYear() + 3 ? value : null;
};

// Technical TMDB keywords nobody searches for.
export const KEYWORD_BLOCKLIST = new Set(['duringcreditsstinger', 'aftercreditsstinger', 'amused', 'aftercredits', 'post-credits scene', 'sequel', '3d animation']);

// Films grouped into fixed ranges, in the order given, e.g. runtime or rating bands.
function bands(films, valueOf, ranges) {
  return ranges.map(([label, low, high]) => [label, films.filter(film => {
    const value = Number(valueOf(film));
    return Number.isFinite(value) && value > 0 && value >= low && value < high;
  }).length]);
}

// stats({results, unavailable, changes}, {subscriptions, favorites, now}) -> sections for the stats page.
export function watchlistStats(scan, {subscriptions = [], favorites = [], now = Date.now() / 1000} = {}) {
  const available = scan.results || [];
  const unavailable = scan.unavailable || [];
  const all = [...available, ...unavailable];
  const own = new Set(subscriptions);
  const watchableOn = (film, services) => Object.entries(film.providers || {})
    .some(([service, kinds]) => services.has(service) && kinds.some(kind => WATCH_KINDS.includes(kind)));
  const onOwn = available.filter(film => watchableOn(film, own));
  const today = new Date(now * 1000).toISOString().slice(0, 10);
  const runtimes = numbers(available.map(film => film.runtime));
  const years = numbers(all.map(film => plausibleYear(film.year, now)));
  const availability = Object.fromEntries(AVAILABILITY.map(name => [name, 0]));
  const ownGroups = new Set(subscriptions.map(serviceGroup));
  all.forEach(film => { availability[bestAvailability(film, ownGroups, today)] += 1; });

  const overview = {
    total: all.length,
    availability,
    unknownYears: all.length - numbers(all.map(film => plausibleYear(film.year, now))).length,
    available: available.length,
    unavailable: unavailable.length,
    onSubscriptions: onOwn.length,
    free: available.filter(film => kindsOf(film).some(kind => kind === 'free' || kind === 'ads')).length,
    subscription: available.filter(film => kindsOf(film).includes('flatrate')).length,
    rentOnly: available.filter(film => kindsOf(film).length && kindsOf(film).every(kind => kind === 'rent')).length,
    hoursAvailable: Math.round(runtimes.reduce((sum, value) => sum + value, 0) / 60),
    hoursOnSubscriptions: Math.round(numbers(onOwn.map(film => film.runtime)).reduce((sum, value) => sum + value, 0) / 60),
    averageRuntime: average(runtimes),
    averageTmdb: average(numbers(all.map(film => film.rating))),
    averageLetterboxd: average(numbers(all.map(film => film.letterboxd_rating))),
    oldestYear: years.length ? Math.min(...years) : null,
    newestYear: years.length ? Math.max(...years) : null,
    comingSoon: all.filter(film => [film.cinema_date, film.home_date].some(date => date && date > today)).length,
    favorites: favorites.length,
    watched: favorites.filter(favorite => favorite.status === 'watched').length,
  };

  // Per service: films, hours, offer types and films no other service has (only counting ways to watch without paying per film).
  const services = countBy(available, film => Object.keys(film.providers || {})).map(([name, films]) => {
    const on = available.filter(film => film.providers[name]);
    const exclusive = on.filter(film => {
      const watchable = Object.entries(film.providers).filter(([, kinds]) => kinds.some(kind => WATCH_KINDS.includes(kind)));
      return watchable.length === 1 && watchable[0][0] === name;
    }).length;
    const has = kind => on.filter(film => film.providers[name].includes(kind)).length;
    return {
      name, films, exclusive, own: own.has(name),
      hours: Math.round(numbers(on.map(film => film.runtime)).reduce((sum, value) => sum + value, 0) / 60),
      free: has('free'), ads: has('ads'), subscription: has('flatrate'), rent: has('rent'),
    };
  });

  // Own subscriptions: what each one adds that no other own subscription has.
  const ownServices = [...own].sort().map(name => {
    const others = new Set([...own].filter(other => other !== name));
    const films = onOwn.filter(film => watchableOn(film, new Set([name])));
    return {name, films: films.length, onlyHere: films.filter(film => !watchableOn(film, others)).length};
  }).sort((a, b) => b.films - a.films || a.name.localeCompare(b.name));

  const offerTypes = [['Free', 'free'], ['With ads', 'ads'], ['Subscription', 'flatrate'], ['Rent', 'rent']]
    .map(([label, kind]) => [label, available.filter(film => kindsOf(film).includes(kind)).length]);

  const genres = countBy(all, film => film.genres).map(([name, total]) => ({
    name, total, available: available.filter(film => (film.genres || []).includes(name)).length,
  }));

  const decades = countBy(all, film => (plausibleYear(film.year, now) ? [`${Math.floor(film.year / 10) * 10}s`] : []))
    .sort((a, b) => a[0].localeCompare(b[0]));

  const recent = (scan.changes || []).filter(change => change.created >= now - 30 * DAY);
  const weeks = Array.from({length: 8}, (_, index) => {
    const end = now - index * 7 * DAY;
    const inWeek = (scan.changes || []).filter(change => change.created < end && change.created >= end - 7 * DAY);
    return {
      start: end - 7 * DAY,
      added: inWeek.filter(change => change.change === 'added').length,
      removed: inWeek.filter(change => change.change === 'removed').length,
    };
  });

  const ratingOf = film => Number(film.letterboxd_rating) || Number(film.rating) / 2 || 0;
  return {
    overview,
    services,
    ownServices,
    offerTypes,
    genres,
    decades,
    runtimes: bands(all, film => film.runtime, [['Under 90 min', 0, 90], ['90–119 min', 90, 120], ['120–149 min', 120, 150], ['150 min and longer', 150, Infinity]]),
    tmdbRatings: bands(all, film => film.rating, [['Under 5', 0, 5], ['5–5.9', 5, 6], ['6–6.9', 6, 7], ['7–7.9', 7, 8], ['8 and higher', 8, 11]]),
    letterboxdRatings: bands(all, film => film.letterboxd_rating, [['Under 2.5', 0, 2.5], ['2.5–2.9', 2.5, 3], ['3–3.4', 3, 3.5], ['3.5–3.9', 3.5, 4], ['4 and higher', 4, 6]]),
    languages: countBy(all, film => [film.original_language]),
    countries: countBy(all, film => film.origin_countries),
    // Age ratings read best in age order (0, 6, 12 …); other systems (PG-13) after them by count.
    ageRatings: countBy(all, film => [film.certification]).sort((a, b) => (Number.isFinite(+a[0]) && Number.isFinite(+b[0]) ? a[0] - b[0] : Number.isFinite(+b[0]) - Number.isFinite(+a[0]))),
    directors: countBy(all, film => [film.director]).filter(([, count]) => count > 1),
    actors: countBy(all, film => film.cast).filter(([, count]) => count > 1),
    collections: countBy(all, film => [film.collection]).filter(([, count]) => count > 1),
    keywords: countBy(all, film => (film.keywords || []).filter(word => !KEYWORD_BLOCKLIST.has(word))),
    changes: {
      added30: recent.filter(change => change.change === 'added').length,
      removed30: recent.filter(change => change.change === 'removed').length,
      byService: countBy(recent, change => [change.provider]),
      weeks,
    },
    // Longest on the watchlist (highest position) and watchable on an own subscription: the "dust collectors".
    longestWaiting: [...onOwn].filter(film => Number(film.watchlist_position) > 0)
      .sort((a, b) => b.watchlist_position - a.watchlist_position).slice(0, 8),
    bestOnSubscriptions: [...onOwn].sort((a, b) => ratingOf(b) - ratingOf(a)).slice(0, 8),
  };
}
