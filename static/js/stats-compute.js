// The numbers behind the stats page: one object from a scan, no DOM. The page only draws it.
import {AVAILABILITY, bestAvailability, watchlistStats} from './statistics.js';
import {serviceGroup} from './catalog.js';

const WATCH = ['free', 'ads', 'flatrate'];  // ways to watch without paying per film
const NOW_WATCHING = ['own_subscription', 'free', 'ads'];
const hoursOf = films => Math.round(films.reduce((sum, film) => sum + (Number(film.runtime) > 0 ? Number(film.runtime) : 0), 0) / 60);
const ratingOf = film => Number(film.letterboxd_rating) || 0;
const average = values => (values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : null);

// Offers of one film by service group: {Netflix: Set(kinds)}, plans of a provider merged.
function offersByGroup(film) {
  const groups = new Map();
  Object.entries(film.providers || {}).forEach(([service, kinds]) => {
    const group = serviceGroup(service);
    const entry = groups.get(group) || {kinds: new Set(), services: new Set()};
    kinds.forEach(kind => entry.kinds.add(kind));
    entry.services.add(service);
    groups.set(group, entry);
  });
  return groups;
}
const watchableGroups = offers => [...offers].filter(([, entry]) => WATCH.some(kind => entry.kinds.has(kind))).map(([group]) => group);

// computeStats(scan, {subscriptions, prices, favorites, now}) -> watchlistStats plus the decision numbers of the plan.
// prices: {service: monthly price}; without a price nothing about money is returned for that service.
export function computeStats(scan, {subscriptions = [], prices = {}, favorites = [], now = Date.now() / 1000} = {}) {
  const base = watchlistStats(scan, {subscriptions, favorites, now});
  const films = [...(scan.results || []), ...(scan.unavailable || [])];
  const own = new Set(subscriptions);
  const ownGroups = new Set(subscriptions.map(serviceGroup));
  const today = new Date(now * 1000).toISOString().slice(0, 10);
  const best = new Map(films.map(film => [film, bestAvailability(film, ownGroups, today)]));
  const where = kind => films.filter(film => best.get(film) === kind);
  const offers = new Map(films.map(film => [film, offersByGroup(film)]));

  const availabilityBreakdown = AVAILABILITY.map(kind => ({kind, films: where(kind).length, hours: hoursOf(where(kind))}));
  const hoursAvailableNow = hoursOf(films.filter(film => NOW_WATCHING.includes(best.get(film))));

  // Per service group. "Exclusive": no other group shows the film without paying per film.
  const names = new Set();
  films.forEach(film => offers.get(film).forEach((_, group) => names.add(group)));
  const serviceValue = [...names].map(group => {
    const on = films.filter(film => offers.get(film).has(group));
    const entries = on.map(film => offers.get(film).get(group));
    const watchable = on.filter(film => watchableGroups(offers.get(film)).includes(group));
    const exclusive = watchable.filter(film => watchableGroups(offers.get(film)).length === 1);
    const plans = [...new Set(entries.flatMap(entry => [...entry.services]))].sort();
    const mine = plans.filter(plan => own.has(plan));
    const priced = mine.filter(plan => prices[plan] > 0);
    const price = priced.length ? priced.reduce((sum, plan) => sum + prices[plan], 0) : null;
    const has = kind => entries.filter(entry => entry.kinds.has(kind)).length;
    const isOwn = ownGroups.has(group);
    // A rent store with three ad-supported films (Rakuten TV) is still a store: it counts by what most of its films are.
    const rentFilms = has('rent') + has('buy') - entries.filter(entry => entry.kinds.has('rent') && entry.kinds.has('buy')).length;
    const status = isOwn ? 'own' : rentFilms > has('flatrate') + has('free') + has('ads') ? 'store' : has('flatrate') ? 'other' : 'free';
    return {
      group, plans, status, own: isOwn,
      films: on.length, watchable: watchable.length, exclusive: exclusive.length,
      hours: hoursOf(on), exclusiveHours: hoursOf(exclusive),
      free: has('free'), ads: has('ads'), subscription: has('flatrate'), rent: rentFilms,
      averageRating: average(on.map(ratingOf).filter(value => value > 0)),
      price, costPerExclusiveFilm: price && exclusive.length ? price / exclusive.length : null,
      topFilms: [...watchable].sort((a, b) => ratingOf(b) - ratingOf(a)).slice(0, 5),
    };
  }).sort((a, b) => b.films - a.films || a.group.localeCompare(b.group));

  // What a service you do not have would add: its subscription films you cannot watch yet.
  const gainIfSubscribed = serviceValue.filter(item => !ownGroups.has(item.group) && item.subscription).map(item => {
    const gained = films.filter(film => offers.get(film).get(item.group)?.kinds.has('flatrate') && !NOW_WATCHING.includes(best.get(film)));
    const onlyThere = gained.filter(film => watchableGroups(offers.get(film)).length === 1);
    return {group: item.group, films: gained.length, hours: hoursOf(gained), onlyThere: onlyThere.length};
  }).filter(item => item.films > 0).sort((a, b) => b.films - a.films || a.group.localeCompare(b.group));

  const collections = new Map();
  films.filter(film => film.collection).forEach(film => collections.set(film.collection, [...(collections.get(film.collection) || []), film]));
  const collectionsPlanner = [...collections].filter(([, list]) => list.length >= 2).map(([name, list]) => ({
    name, films: list.length, hours: hoursOf(list), inOwn: list.filter(film => best.get(film) === 'own_subscription').length,
  })).sort((a, b) => b.films - a.films || a.name.localeCompare(b.name));

  // Letterboxd against TMDB on a 10-point scale: positive = the Letterboxd crowd likes it more.
  const gaps = films.filter(film => ratingOf(film) > 0 && Number(film.rating) > 0)
    .map(film => ({film, gap: ratingOf(film) * 2 - Number(film.rating)})).sort((a, b) => b.gap - a.gap);

  // Histograms for the distribution charts: runtime in 15-minute steps, Letterboxd rating in 0.25 steps.
  const runtimes = films.map(film => Number(film.runtime)).filter(value => value > 0);
  const runtimeBins = [[0, 75, 'Under 75 min'], ...[75, 90, 105, 120, 135, 150].map(from => [from, from + 15, `${from}–${from + 14}`]), [165, Infinity, '165 min +']];
  const ratings = films.map(ratingOf).filter(value => value > 0);
  const ratingBins = [[0, 2.25, 'Under 2.25'], ...Array.from({length: 11}, (_, index) => [2.25 + index * 0.25, 2.5 + index * 0.25, (2.25 + index * 0.25).toFixed(2)]), [5, Infinity, '5']];
  const histogram = (values, bins) => bins.map(([from, to, label]) => ({label, from, to, count: values.filter(value => value >= from && value < to).length}));

  return {
    ...base,
    runtimeHistogram: {bins: histogram(runtimes, runtimeBins), average: average(runtimes)},
    ratingHistogram: {bins: histogram(ratings, ratingBins), average: average(ratings)},
    recentChanges: [...(scan.changes || [])].sort((a, b) => b.created - a.created).slice(0, 10),
    availabilityBreakdown,
    hoursAvailableNow,
    serviceValue,
    gainIfSubscribed,
    rotationSuggestion: gainIfSubscribed[0] || null,
    worthRenting: where('rent_buy').filter(film => ratingOf(film) >= 4).sort((a, b) => ratingOf(b) - ratingOf(a)),
    bestOnOwnSubs: where('own_subscription').sort((a, b) => ratingOf(b) - ratingOf(a)).slice(0, 10),
    collectionsPlanner,
    ratingGap: {positive: gaps.slice(0, 5), negative: gaps.slice(-5).reverse()},
    waitingLongest: where('own_subscription').filter(film => Number(film.watchlist_position) > 0)
      .sort((a, b) => b.watchlist_position - a.watchlist_position).slice(0, 8),
    // Footnote numbers: films the sums above leave out.
    withoutRuntime: films.filter(film => !(Number(film.runtime) > 0)).length,
    withoutRating: films.filter(film => !(ratingOf(film) > 0)).length,
  };
}
