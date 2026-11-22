// "The best way to watch it": one function for the film card and the drawer's main button.
// Order: own free service, own subscription, own service with ads, rent (first shop by the shop order),
// buy, abroad on an own service (only when the switch is on), another service that is not yours, nothing.
// No prices anywhere: the data has none; rent and buy show the offer type and the shop only.
import {catalogName} from './catalog.js';

// Rental shops in the order they are listed (the ones ticked in the settings come first, see rankShops).
export const RENT_SHOP_ORDER = ['amazon', 'apple tv', 'google play', 'youtube', 'sky store', 'magenta', 'rakuten', 'maxdome'];
const shopRank = name => {
  const found = RENT_SHOP_ORDER.findIndex(key => name.toLowerCase().includes(key));
  return found < 0 ? RENT_SHOP_ORDER.length : found;
};
const byName = (a, b) => a.localeCompare(b, undefined, {sensitivity: 'base'});

// The films's offers merged by catalogue: [{name, own, kinds}] ("HBO Max" and its Amazon Channel are one).
export function catalogues(film, own) {
  const merged = new Map();
  for (const [raw, kinds] of Object.entries(film.providers || {})) {
    const name = catalogName(raw);
    const entry = merged.get(name) || {name, own: false, kinds: new Set()};
    entry.own = entry.own || own.has(raw) || own.has(name);
    kinds.forEach(kind => entry.kinds.add(kind));
    merged.set(name, entry);
  }
  return [...merged.values()];
}

// abroad: {service, countries (best first)} for this film when the switch is on, else null.
// Returns {kind, service, others, shops, muted, countries} where kind is
// free | flatrate | ads | rent | buy | abroad | foreign | none.
export function bestWay(film, {own, abroad = null} = {}) {
  const entries = catalogues(film, own);
  const withKind = (kind, mine) => entries.filter(entry => entry.kinds.has(kind) && (mine === undefined || entry.own === mine)).sort((a, b) => byName(a.name, b.name));
  const others = service => entries.filter(entry => entry.name !== service).length;
  const pick = (kind, mine) => withKind(kind, mine)[0];
  for (const kind of ['free', 'flatrate', 'ads']) {
    const found = pick(kind, true);
    if (found) return {kind, service: found.name, others: others(found.name), shops: 0, muted: false, countries: []};
  }
  for (const kind of ['rent', 'buy']) {
    const shops = withKind(kind).sort((a, b) => Number(b.own) - Number(a.own) || shopRank(a.name) - shopRank(b.name) || byName(a.name, b.name));
    if (shops.length) return {kind, service: shops[0].name, others: 0, shops: shops.length, muted: false, countries: []};
  }
  if (abroad?.service) return {kind: 'abroad', service: abroad.service, others: Math.max((abroad.countries || []).length - 1, 0), shops: 0, muted: false, countries: abroad.countries || []};
  for (const kind of ['free', 'flatrate', 'ads']) {
    const found = pick(kind, false);
    if (found) return {kind: 'foreign', service: found.name, others: 0, shops: 0, muted: true, countries: []};
  }
  return {kind: 'none', service: null, others: 0, shops: 0, muted: true, countries: []};
}

// The words next to the logo on a card ("Free", "Netflix · Subscription", "Rent · 6 shops" ...).
export function wayText(way) {
  switch (way.kind) {
    case 'free': return 'Free';
    case 'flatrate': return `${way.service} · Subscription`;
    case 'ads': return 'With ads';
    case 'rent': return `Rent · ${way.shops} shop${way.shops === 1 ? '' : 's'}`;
    case 'buy': return `Buy · ${way.shops} shop${way.shops === 1 ? '' : 's'}`;
    case 'abroad': return 'Abroad';
    case 'foreign': return `On ${way.service} · not your service`;
    default: return 'Not streaming';
  }
}
