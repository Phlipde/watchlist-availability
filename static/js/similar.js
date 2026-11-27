// "Similar on your services": watchlist films on a service you have, ranked by what they share with the film.
// Genres x3, keywords x3 (places and countries left out), same director x4, shared lead actors x1,
// release within 10 years +1, TMDB lists it as similar or recommended +4. A match shares a genre and at least
// one of: a keyword, the director, TMDB's list; under MIN_SCORE it is no match. Films of the same series are left
// out (the series has its own row), and fewer than MIN_MATCHES matches show nothing rather than weak fillers.
import {dedupeKeywords} from './drawer.js';
import {filmKey} from './filtering.js';
import {serviceGroup} from './catalog.js';

export const MIN_SCORE = 10;
export const MIN_MATCHES = 3;
const WATCH = ['free', 'ads', 'flatrate'];
const shared = (a, b) => (a || []).filter(item => (b || []).includes(item)).length;
const words = film => dedupeKeywords(film.keywords || []).map(word => word.toLowerCase());

export function similarScore(film, other) {
  const genres = shared(film.genres, other.genres);
  const keywords = shared(words(film), words(other));
  const director = Boolean(film.director && film.director === other.director);
  const listed = (film.similar_ids || []).map(String).includes(String(other.tmdb_id));
  if (!genres || !(keywords || director || listed)) return 0;
  return genres * 3 + keywords * 3 + (director ? 4 : 0)
    + shared((film.cast || []).slice(0, 3), (other.cast || []).slice(0, 3))
    + (Math.abs(Number(film.year) - Number(other.year)) <= 10 ? 1 : 0)
    + (listed ? 4 : 0);
}

// `own` is a Set of service names; plans of one service count as that service.
export function similarOnServices(film, films, own, skip = new Set(), limit = 6) {
  const groups = new Set([...own].map(serviceGroup));
  const matches = films
    .filter(item => item !== film && filmKey(item) !== filmKey(film) && !skip.has(filmKey(item))
      && !(film.collection && item.collection === film.collection)
      && Object.entries(item.providers || {}).some(([service, kinds]) => groups.has(serviceGroup(service)) && kinds.some(kind => WATCH.includes(kind))))
    .map(item => ({item, score: similarScore(film, item)}))
    .filter(({score}) => score >= MIN_SCORE)
    .sort((a, b) => b.score - a.score || String(a.item.title).localeCompare(String(b.item.title)));
  return matches.length < MIN_MATCHES ? [] : matches.slice(0, limit).map(({item}) => item);
}
