// "Similar on your services": watchlist films on a service you have, ranked by what they share with the film.
// Genres x3, keywords x2 (places and countries left out), same director x4, shared lead actors x1,
// release within 10 years +1, TMDB lists it as similar or recommended +5. Under MIN_SCORE a film is no match.
import {dedupeKeywords} from './drawer.js';
import {filmKey} from './filtering.js';
import {serviceGroup} from './catalog.js';

export const MIN_SCORE = 10;
const WATCH = ['free', 'ads', 'flatrate'];
const shared = (a, b) => (a || []).filter(item => (b || []).includes(item)).length;

export function similarScore(film, other) {
  const keywords = film.keywords?.length ? dedupeKeywords(film.keywords).map(word => word.toLowerCase()) : [];
  const otherWords = dedupeKeywords(other.keywords).map(word => word.toLowerCase());
  return shared(film.genres, other.genres) * 3
    + shared(keywords, otherWords) * 2
    + (film.director && film.director === other.director ? 4 : 0)
    + shared((film.cast || []).slice(0, 3), (other.cast || []).slice(0, 3))
    + (Math.abs(Number(film.year) - Number(other.year)) <= 10 ? 1 : 0)
    + ((film.similar_ids || []).map(String).includes(String(other.tmdb_id)) ? 5 : 0);
}

// `own` is a Set of service names; plans of one service count as that service.
export function similarOnServices(film, films, own, skip = new Set(), limit = 6) {
  const groups = new Set([...own].map(serviceGroup));
  return films
    .filter(item => item !== film && filmKey(item) !== filmKey(film) && !skip.has(filmKey(item))
      && Object.entries(item.providers || {}).some(([service, kinds]) => groups.has(serviceGroup(service)) && kinds.some(kind => WATCH.includes(kind))))
    .map(item => ({item, score: similarScore(film, item)}))
    .filter(({score}) => score >= MIN_SCORE)
    .sort((a, b) => b.score - a.score || String(a.item.title).localeCompare(String(b.item.title)))
    .slice(0, limit)
    .map(({item}) => item);
}
