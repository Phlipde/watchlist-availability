// Filters that only links set (the stats page uses them): best way to watch, a person, a film series, a minimum runtime.
// They live in the address, show as chips with a small x and are cleared by "Reset all". Pure functions.
import {AVAILABILITY, AVAILABILITY_LABEL} from './statistics.js';

export const emptyLink = () => ({availability: [], person: '', collection: '', runtimeMin: 0});

export const isLinkSet = link => Boolean(link.availability.length || link.person || link.collection || link.runtimeMin);

// ?availability=free,ads&person=Ridley Scott&collection=Alien Collection&runtimeMin=105
export function parseLink(params) {
  const min = Number.parseInt(params.get('runtimeMin'), 10);
  return {
    // The old link value availability=exclusive is not one of these and is ignored here.
    availability: (params.get('availability') || '').split(',').filter(kind => AVAILABILITY.includes(kind)),
    person: params.get('person') || '',
    collection: params.get('collection') || '',
    runtimeMin: min > 0 ? min : 0,
  };
}

export function writeLink(link, searchParams) {
  const set = (name, value) => (value ? searchParams.set(name, value) : searchParams.delete(name));
  set('availability', link.availability.join(','));
  set('person', link.person);
  set('collection', link.collection);
  set('runtimeMin', link.runtimeMin ? String(link.runtimeMin) : '');
}

// [{key, text}] for the chips.
export function linkChips(link) {
  return [
    ...(link.availability.length ? [{key: 'availability', text: `Best way: ${link.availability.map(kind => AVAILABILITY_LABEL[kind]).join(' or ')}`}] : []),
    ...(link.person ? [{key: 'person', text: `Person: ${link.person}`}] : []),
    ...(link.collection ? [{key: 'collection', text: `Series: ${link.collection}`}] : []),
    ...(link.runtimeMin ? [{key: 'runtimeMin', text: `Runtime: ${link.runtimeMin} min and longer`}] : []),
  ];
}

export function clearLink(link, key) {
  return {...link, [key]: emptyLink()[key]};
}

// `availabilityOf(film)` gives a film's best way to watch (statistics.js bestAvailability).
export function linkMatches(film, link, availabilityOf) {
  if (!link || !isLinkSet(link)) return true;
  if (link.availability.length && !link.availability.includes(availabilityOf(film))) return false;
  if (link.person && ![film.director, ...(film.cast || [])].includes(link.person)) return false;
  if (link.collection && film.collection !== link.collection) return false;
  return !link.runtimeMin || Number(film.runtime) >= link.runtimeMin;
}

// Films that are not available anywhere only show when "Also not available" is on.
export const needsUnavailable = link => link.availability.some(kind => kind === 'unavailable' || kind === 'coming_soon');
