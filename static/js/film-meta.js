// Pure facts about a film for the details drawer (no HTML, no DOM): times, ratings, offers, links.
import {numberText} from './ui.js';
import {selectedChanges} from './filtering.js';
import {catalogName, serviceGroup} from './catalog.js';
import {bestWay} from './bestway.js';
import {PLACE_ALIASES, US_STATES, CITIES, ORIGIN_AMERICAN} from './places.js';

const KIND_ORDER = ['free', 'ads', 'flatrate', 'rent', 'buy'];
const KIND_LABEL = {free: 'Free', ads: 'With ads', flatrate: 'Subscription', rent: 'Rent', buy: 'Buy'};
const WATCH = ['free', 'ads', 'flatrate'];
const PAY = ['rent', 'buy'];

export {catalogName};
const isChannel = name => catalogName(name) !== name;

// 148 → "2 h 28", 61 → "1 h 01", 58 → "58 min".
export function runtimeLong(minutes) {
  const total = Math.round(Number(minutes));
  if (!Number.isFinite(total) || total <= 0) return '';
  return total < 60 ? `${total} min` : `${Math.floor(total / 60)} h ${String(total % 60).padStart(2, '0')}`;
}

// The age rating the way people in that country say it: "FSK 12" in Germany, "rated 12" elsewhere.
export function certificationText(certification, country) {
  const text = String(certification ?? '').trim();
  if (!text) return '';
  return country === 'DE' ? `FSK ${text}` : text === '0' ? 'all ages' : `rated ${text}`;
}

export function metaLine(film, country) {
  return [numberText(film.year, ''), runtimeLong(film.runtime), certificationText(film.certification, country), (film.genres || []).join(', ')]
    .filter(Boolean).join(' · ');
}

// Country, place and origin words say where a film comes from or is set, not what it is about: they leave the
// keyword chips. `countryNames` is a Set of lower-case names (all ISO countries, from Intl.DisplayNames in the browser).
export function dedupeKeywords(keywords, countryNames = new Set()) {
  const places = new Set([...countryNames, ...PLACE_ALIASES, ...US_STATES, ...CITIES]);
  const seen = new Set();
  const kept = [];
  for (const raw of keywords || []) {
    const word = String(raw).trim();
    const key = word.toLowerCase();
    if (!word || seen.has(key)) continue;
    seen.add(key);
    if (key.split(',').some(part => places.has(part.trim())) || ORIGIN_AMERICAN.test(key)) continue;
    kept.push(word);
  }
  return kept;
}

// A part of a series is released once its release date (else its year) has come; one with neither is not.
export function isReleased(item, today = new Date().toISOString().slice(0, 10)) {
  if (item.release_date) return item.release_date <= today;
  const year = Number(item.year);
  return year > 0 && year <= Number(today.slice(0, 4));
}

// The films of a series, oldest first; parts with no date and no year come last.
export function seriesOrder(items) {
  const when = item => item.release_date || (Number(item.year) ? `${item.year}-12-31` : '9999');
  return [...items].sort((a, b) => when(a).localeCompare(when(b)));
}

// {kind: [names]} → rows per offer type; "X" and "X Amazon Channel" are one row, the channel noted.
// Returns [{kind, label, rows: [{name, own, via}]}] in the order Free, With ads, Subscription, Rent, Buy.
export function catalogRows(providers, own) {
  const entries = Object.entries(providers || {});
  return KIND_ORDER.map(kind => {
    const byCatalog = new Map();
    for (const [name, kinds] of entries) {
      if (!kinds.includes(kind)) continue;
      const catalog = serviceGroup(name);
      const row = byCatalog.get(catalog) || {name: catalog, own: false, via: []};
      row.own = row.own || own.has(name) || own.has(catalog) || own.has(catalogName(name));
      if (isChannel(name)) row.via.push('Amazon Channel');
      byCatalog.set(catalog, row);
    }
    const rows = [...byCatalog.values()].sort((a, b) => Number(b.own) - Number(a.own) || a.name.localeCompare(b.name, undefined, {sensitivity: 'base'}));
    return {kind, label: KIND_LABEL[kind], rows};
  }).filter(group => group.rows.length);
}

// TMDB's watch page (JustWatch data); the JustWatch search when the film has no TMDB address (never an empty link).
export function watchUrl(film, country) {
  return film.tmdb_url ? `${film.tmdb_url}/watch?locale=${encodeURIComponent(country)}` : justWatchSearch(film, country);
}
export const justWatchSearch = (film, country) => `https://www.justwatch.com/${encodeURIComponent(String(country).toLowerCase())}/search?q=${encodeURIComponent(film.title)}`;

// The main button: the best way (bestWay, the same as on the card) in words, or why there is none. `primary` is
// true only for something watchable on an own service (the only gold button).
export function primaryAction(film, own, country, regionName = country, today = new Date().toISOString().slice(0, 10)) {
  const href = watchUrl(film, country);
  const way = bestWay(film, {own});
  const label = {free: 'Free', flatrate: 'Subscription', ads: 'With ads'};
  switch (way.kind) {
    case 'free':
    case 'flatrate':
    case 'ads': return {primary: true, text: `Watch on ${way.service} · ${label[way.kind]}`, service: way.service, href};
    case 'rent': return {primary: false, text: `Rent on ${way.service}`, service: way.service, href};
    case 'buy': return {primary: false, text: `Buy on ${way.service}`, service: way.service, href};
    case 'foreign': return {primary: false, text: `On ${way.service} (not your service)`, service: way.service, href};
    default: {
      // A film still in the cinema or not out yet has nothing to stream: say when it comes instead.
      const cinema = film.cinema_date && film.cinema_date >= today ? film.cinema_date : '';
      const text = cinema ? `In cinemas ${cinema.split('-').reverse().join('.')}` : `Not streaming in ${regionName}`;
      return {primary: false, text, service: null, href: '', disabled: true};
    }
  }
}

// More own services that carry it for nothing extra, besides the one on the button.
export function alternatives(film, own, primaryService) {
  const names = new Map();
  for (const [name, offered] of Object.entries(film.providers || {})) {
    const catalog = catalogName(name);
    if (catalog === primaryService || !(own.has(name) || own.has(catalog))) continue;
    const kind = WATCH.find(item => offered.includes(item));
    if (kind && (!names.has(catalog) || WATCH.indexOf(kind) < WATCH.indexOf(names.get(catalog)))) names.set(catalog, kind);
  }
  return [...names].map(([name, kind]) => ({name, kind})).sort((a, b) => a.name.localeCompare(b.name));
}

// "12.11." from epoch seconds.
const shortDate = seconds => { const day = new Date(seconds * 1000); return `${day.getDate()}.${day.getMonth() + 1}.`; };

// "New on Netflix · since 12.11." / "No longer on Prime Video · since 14.11.", only for the services that count.
export function statusBadges(film, selected) {
  const {added, removed} = selectedChanges(film, selected);
  const since = film.provider_changes?.since;
  const when = since ? ` · since ${shortDate(since)}` : '';
  return [
    ...removed.map(name => ({tone: 'gone', text: `No longer on ${name}${when}`})),
    ...added.map(name => ({tone: 'new', text: `New on ${name}${when}`})),
  ];
}

// Letterboxd redirects /tmdb/<id> to the film page; the search is only the way out when there is no id.
export function letterboxdUrl(film) {
  return film.tmdb_id ? `https://letterboxd.com/tmdb/${encodeURIComponent(film.tmdb_id)}/` : `https://letterboxd.com/search/${encodeURIComponent(`${film.title} ${film.year || ''}`.trim())}/`;
}

// "Source: TMDB (JustWatch data), DE, as of 22.11.2026 23:40"; the date is that of the last scan.
export function sourceText(country, seconds) {
  const when = seconds ? new Date(seconds * 1000) : null;
  const two = number => String(number).padStart(2, '0');
  const stamp = when ? `, as of ${two(when.getDate())}.${two(when.getMonth() + 1)}.${when.getFullYear()} ${two(when.getHours())}:${two(when.getMinutes())}` : '';
  return `Source: TMDB (JustWatch data), ${country}${stamp}`;
}
