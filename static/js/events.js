// What changed on the ticked services and what the Tonight page shows. Pure functions, tested with node.
import {filmKey, sortFilms} from './filtering.js';

const WATCH_KINDS = ['free', 'ads', 'flatrate'];  // watchable without paying per film
const FREE_KINDS = ['free', 'ads'];
const DAY = 24 * 3600;
const KIND_NAMES = {free: 'free', ads: 'with ads', flatrate: 'subscription', rent: 'rent'};

// Ticked services on which the film can be watched without paying per film.
export function watchableOn(film, services) {
  return Object.entries(film.providers || {})
    .filter(([service, kinds]) => services.has(service) && kinds.some(kind => WATCH_KINDS.includes(kind)))
    .map(([service]) => service);
}

// New on your services: an "added" on a ticked service within `days`. A switch from one ticked
// service to another (an "added" and a "removed" on ticked services at once) is no news.
export function newOnServices(films, services, now, days = 14) {
  return films.filter(film => {
    const changes = film.provider_changes;
    if (!changes || changes.since < now - days * DAY) return false;
    const added = (changes.added || []).filter(service => services.has(service) && watchableOn(film, new Set([service])).length);
    const removed = (changes.removed || []).filter(service => services.has(service));
    return added.length > 0 && removed.length === 0;
  });
}

// Recently gone from your services: one entry per film, newest first, with where it runs now.
// Films still watchable on another ticked service are left out (a switch, nothing lost).
export function recentlyGone(changes, films, services, now, days = 30) {
  const byKey = new Map(films.map(film => [filmKey(film), film]));
  const byFilm = new Map();
  (changes || [])
    .filter(change => change.change === 'removed' && services.has(change.provider) && change.created >= now - days * DAY)
    .sort((a, b) => b.created - a.created)
    .forEach(change => {
      const known = byFilm.get(change.film_key);
      if (known) { if (!known.providers.includes(change.provider)) known.providers.push(change.provider); return; }
      byFilm.set(change.film_key, {key: change.film_key, title: change.title, year: change.year, created: change.created, providers: [change.provider]});
    });
  return [...byFilm.values()]
    .filter(entry => !(byKey.get(entry.key) && watchableOn(byKey.get(entry.key), services).length))
    .map(entry => {
      const film = byKey.get(entry.key);
      // Where it runs now: the cheapest way per service, watchable ways first.
      const nowOn = Object.entries(film?.providers || {})
        .map(([service, kinds]) => [service, ['free', 'ads', 'flatrate', 'rent'].find(kind => kinds.includes(kind))])
        .filter(([, kind]) => kind)
        .sort((a, b) => Number(b[1] !== 'rent') - Number(a[1] !== 'rent') || a[0].localeCompare(b[0]));
      return {...entry, film, nowOn: nowOn.map(([service, kind]) => ({service, kind: KIND_NAMES[kind]}))};
    });
}

// "now on Prime Video (subscription)", "rent only on Apple TV", "not streaming anywhere".
export function nowOnText(entry) {
  if (!entry.nowOn.length) return 'not streaming anywhere';
  const watch = entry.nowOn.filter(item => item.kind !== 'rent');
  if (!watch.length) return `rent only on ${entry.nowOn.map(item => item.service).slice(0, 2).join(', ')}`;
  return `now on ${watch.slice(0, 2).map(item => `${item.service} (${item.kind})`).join(', ')}`;
}

// Quick filters of the Tonight page; a check gets the film and {services, now}.
export const TONIGHT_CHIPS = [
  ['tonight', 'Under 2 h', film => film.runtime > 0 && film.runtime <= 120],
  ['week', 'New this week', (film, {services, now}) => newOnServices([film], services, now, 7).length > 0],
  ['rated', 'Highly rated', film => (Number(film.letterboxd_rating) ? Number(film.letterboxd_rating) >= 3.7 : Number(film.rating) >= 7.5)],
  ['free', 'Free only', null],
];

// The rows of the Tonight page: new → free → one per subscription (most films first). Empty rows are left out.
// options: services (Set), favorites (Map), skip (Set of watched keys), chips (Set of chip ids), now.
const offeredAs = (film, service, kinds) => (film.providers?.[service] || []).some(kind => kinds.includes(kind));
// The films the quick chips let through that run on the services without paying per film (free ones only with "Free only").
function watchableFor(films, {services, skip, chips, now}) {
  const checks = TONIGHT_CHIPS.filter(([id, , check]) => chips.has(id) && check).map(([, , check]) => check);
  const wanted = films.filter(film => !skip.has(filmKey(film)) && checks.every(check => check(film, {services, now})));
  return wanted.filter(film => chips.has('free')
    ? [...services].some(service => offeredAs(film, service, FREE_KINDS))
    : watchableOn(film, services).length);
}

export function tonightRows(films, {services, favorites = new Map(), skip = new Set(), chips = new Set(), now}) {
  const freeOnly = chips.has('free');
  const watchable = watchableFor(films, {services, skip, chips, now});
  const sorted = list => sortFilms(list, 'priority', {favorites});
  const fresh = sorted(newOnServices(watchable, services, now));
  const freshKeys = new Set(fresh.map(filmKey));  // a film shown under "New" is not repeated in the service rows
  const rows = [
    {id: 'new', title: 'New on your services', films: fresh, href: '/watchlist?changes=added'},
    {id: 'free', title: 'Free', films: sorted(watchable.filter(film => [...services].some(service => offeredAs(film, service, FREE_KINDS)))), href: '/watchlist?cost=free'},
  ];
  if (!freeOnly) {
    [...services]
      .map(service => ({service, films: watchable.filter(film => offeredAs(film, service, ['flatrate']) && !freshKeys.has(filmKey(film)))}))
      .filter(row => row.films.length)
      .sort((a, b) => b.films.length - a.films.length || a.service.localeCompare(b.service))
      .forEach(row => rows.push({
        id: `service:${row.service}`, title: `On ${row.service}`, service: row.service, films: sorted(row.films),
        href: `/watchlist?providers=${encodeURIComponent(row.service)}&cost=subscription`,
      }));
  }
  return {rows: rows.filter(row => row.films.length), available: watchable};
}

// Together (films from /api/together, each with `group`): "On both lists" and "One of you, unseen", with the same
// quick chips and skip as tonightRows. Both rows are always returned, so the page can say when one is empty.
// options: services (the members' services together), members (how many), plus those of tonightRows.
export function togetherRows(films, {services, members = 2, favorites = new Map(), skip = new Set(), chips = new Set(), now}) {
  const watchable = watchableFor(films, {services, skip, chips, now});
  const sorted = list => sortFilms(list, 'priority', {favorites});
  const rows = [
    {id: 'both', title: members > 2 ? "On everyone's list" : 'On both lists', films: sorted(watchable.filter(film => film.group === 'both')), href: ''},
    {id: 'one', title: 'One of you, unseen', films: sorted(watchable.filter(film => film.group !== 'both')), href: ''},
  ];
  return {rows, available: watchable};
}

// "Pick for me": a film from `candidates` that was not picked yet in this visit. Chance grows with the TMDB
// rating (rating cubed, 5 when unrated), so a 4.5 beats a 3.3 most of the time but is not certain.
export function pickFilm(candidates, picked, random = Math.random) {
  const fresh = candidates.filter(film => !picked.has(filmKey(film)));
  const pool = fresh.length ? fresh : candidates;
  if (!pool.length) return null;
  const weights = pool.map(film => Math.max(Number(film.rating) || 5, 1) ** 3);
  let point = random() * weights.reduce((sum, weight) => sum + weight, 0);
  for (let index = 0; index < pool.length; index += 1) {
    point -= weights[index];
    if (point < 0) return pool[index];
  }
  return pool[pool.length - 1];
}

// Why this film was picked, in a few words: "Highly rated · 1h 47m · on Netflix".
export function pickReason(film, serviceText) {
  const parts = [];
  if (Number(film.rating) >= 7.5) parts.push('Highly rated');
  if (Number(film.runtime) > 0) parts.push(`${Math.floor(film.runtime / 60) ? `${Math.floor(film.runtime / 60)}h ` : ''}${film.runtime % 60}m`.trim());
  if (serviceText) parts.push(serviceText);
  return parts.join(' · ');
}
