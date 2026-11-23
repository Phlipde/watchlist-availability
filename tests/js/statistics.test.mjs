import {test} from 'node:test';
import assert from 'node:assert/strict';

import {AVAILABILITY, bestAvailability, countBy, plausibleYear, watchlistStats} from '../../static/js/statistics.js';
import {serviceGroup} from '../../static/js/catalog.js';

const NOW = Date.UTC(2026, 10, 17) / 1000;
const DAY = 24 * 3600;
const scan = {
  results: [
    {key: '1', title: 'Heat', year: 1995, runtime: 170, rating: 8.3, letterboxd_rating: 4.2, genres: ['Crime', 'Drama'], providers: {Netflix: ['flatrate']}, original_language: 'en', origin_countries: ['US'], director: 'Michael Mann', cast: ['Al Pacino'], watchlist_position: 9},
    {key: '2', title: 'Thief', year: 1981, runtime: 120, rating: 7.4, genres: ['Crime'], providers: {Netflix: ['flatrate'], MUBI: ['flatrate']}, original_language: 'en', director: 'Michael Mann', cast: ['Al Pacino'], watchlist_position: 3},
    {key: '3', title: 'Shoplifters', year: 2018, runtime: 121, rating: 7.8, genres: ['Drama'], providers: {Arte: ['free'], 'Apple TV': ['rent']}, original_language: 'ja', origin_countries: ['JP'], watchlist_position: 5},
    {key: '4', title: 'Rental', year: 2020, runtime: 80, providers: {'Apple TV': ['rent']}},
  ],
  unavailable: [{key: '5', title: 'Gone', year: 1960, genres: ['Drama'], cinema_date: '2027-01-10'}],
  changes: [
    {film_key: '1', provider: 'Netflix', change: 'added', created: NOW - 2 * DAY},
    {film_key: '5', provider: 'MUBI', change: 'removed', created: NOW - 10 * DAY},
    {film_key: '2', provider: 'MUBI', change: 'added', created: NOW - 40 * DAY},
  ],
};

test('countBy counts each key once per item, most first, then by name', () => {
  assert.deepEqual(countBy([{a: ['x', 'y', 'x']}, {a: ['y']}, {a: [null, '']}], item => item.a), [['y', 2], ['x', 1]]);
});

test('overview counts films, offer types, hours and coming soon', () => {
  const {overview} = watchlistStats(scan, {subscriptions: ['Netflix'], favorites: [{status: 'watched'}, {status: 'plan'}], now: NOW});
  assert.equal(overview.total, 5);
  assert.equal(overview.available, 4);
  assert.equal(overview.unavailable, 1);
  assert.equal(overview.onSubscriptions, 2);
  assert.equal(overview.free, 1);
  assert.equal(overview.subscription, 2);
  assert.equal(overview.rentOnly, 1);
  assert.equal(overview.hoursAvailable, Math.round((170 + 120 + 121 + 80) / 60));
  assert.equal(overview.hoursOnSubscriptions, Math.round(290 / 60));
  assert.equal(overview.comingSoon, 1);
  assert.equal(overview.oldestYear, 1960);
  assert.equal(overview.watched, 1);
});

test('services: exclusive counts only ways to watch without paying per film', () => {
  const {services, ownServices} = watchlistStats(scan, {subscriptions: ['Netflix', 'MUBI'], now: NOW});
  const netflix = services.find(service => service.name === 'Netflix');
  assert.deepEqual([netflix.films, netflix.exclusive, netflix.subscription, netflix.own], [2, 1, 2, true]);
  // Shoplifters is free on Arte; renting it on Apple TV does not make Arte less exclusive.
  assert.equal(services.find(service => service.name === 'Arte').exclusive, 1);
  assert.equal(services.find(service => service.name === 'Apple TV').exclusive, 0);
  assert.deepEqual(ownServices, [{name: 'Netflix', films: 2, onlyHere: 1}, {name: 'MUBI', films: 1, onlyHere: 0}]);
});

test('groups: genres, decades, runtime bands, people with more than one film', () => {
  const stats = watchlistStats(scan, {now: NOW});
  assert.deepEqual(stats.genres[0], {name: 'Drama', total: 3, available: 2});
  assert.deepEqual(stats.decades, [['1960s', 1], ['1980s', 1], ['1990s', 1], ['2010s', 1], ['2020s', 1]]);
  assert.deepEqual(stats.runtimes.map(([, count]) => count), [1, 0, 2, 1]);
  assert.deepEqual(stats.directors, [['Michael Mann', 2]]);
  assert.deepEqual(stats.actors, [['Al Pacino', 2]]);
  assert.deepEqual(stats.languages, [['en', 2], ['ja', 1]]);
  const rated = watchlistStats({results: [{certification: 'PG-13'}, {certification: '16'}, {certification: '6'}, {certification: '16'}]}, {now: NOW});
  assert.deepEqual(rated.ageRatings, [['6', 1], ['16', 2], ['PG-13', 1]]);
});

test('changes: last 30 days per service and per week', () => {
  const {changes} = watchlistStats(scan, {now: NOW});
  assert.equal(changes.added30, 1);
  assert.equal(changes.removed30, 1);
  assert.deepEqual(changes.byService, [['MUBI', 1], ['Netflix', 1]]);
  assert.deepEqual(changes.weeks.slice(0, 2).map(week => [week.added, week.removed]), [[1, 0], [0, 1]]);
});

test('film lists: waiting longest and best rated on own subscriptions', () => {
  const stats = watchlistStats(scan, {subscriptions: ['Netflix', 'Arte'], now: NOW});
  assert.deepEqual(stats.longestWaiting.map(film => film.title), ['Heat', 'Shoplifters', 'Thief']);
  assert.deepEqual(stats.bestOnSubscriptions.map(film => film.title), ['Heat', 'Shoplifters', 'Thief']);
});

test('availability: every film has exactly one best way, so the counts add up to the watchlist', () => {
  const stats = watchlistStats(scan, {subscriptions: ['Netflix'], now: NOW});
  const counts = stats.overview.availability;
  assert.deepEqual(Object.keys(counts), AVAILABILITY);
  assert.equal(Object.values(counts).reduce((sum, count) => sum + count, 0), stats.overview.total);
  // Heat and Thief are on your Netflix, Shoplifters is free on Arte, Rental only rent, Gone has a future date.
  assert.deepEqual(counts, {own_subscription: 2, free: 1, ads: 0, other_subscription: 0, rent_buy: 1, coming_soon: 1, unavailable: 0});
});

test('bestAvailability: own subscription beats free, free beats ads, ads beat a subscription you do not have', () => {
  const own = new Set(['Netflix']);
  const of = providers => bestAvailability({providers}, own, '2026-11-17');
  assert.equal(of({Netflix: ['flatrate'], Arte: ['free']}), 'own_subscription');
  assert.equal(of({Arte: ['free'], MUBI: ['flatrate']}), 'free');
  assert.equal(of({Joyn: ['ads'], MUBI: ['flatrate']}), 'ads');
  assert.equal(of({MUBI: ['flatrate'], Apple: ['rent']}), 'other_subscription');
  assert.equal(of({Apple: ['buy']}), 'rent_buy');
  assert.equal(of({}), 'unavailable');
});

test('years: a placeholder date far in the future is unknown and stays out of range and decades', () => {
  assert.equal(plausibleYear(2031, NOW), null);
  assert.equal(plausibleYear(2029, NOW), 2029);
  const stats = watchlistStats({results: [{key: 'a', year: 1990, providers: {}}, {key: 'b', year: 2031, providers: {}}], unavailable: []}, {now: NOW});
  assert.equal(stats.overview.newestYear, 1990);
  assert.equal(stats.overview.unknownYears, 1);
  assert.deepEqual(stats.decades, [['1990s', 1]]);
});

test('keywords: technical tags are dropped', () => {
  const stats = watchlistStats({results: [{key: 'a', keywords: ['heist', 'aftercreditsstinger', 'amused']}], unavailable: []}, {now: NOW});
  assert.deepEqual(stats.keywords, [['heist', 1]]);
});

test('serviceGroup: plans of one provider are one service, stores and tiers stay apart', () => {
  assert.equal(serviceGroup('Netflix Standard with Ads'), 'Netflix');
  assert.equal(serviceGroup('Netflix'), 'Netflix');
  assert.equal(serviceGroup('Amazon Prime Video with Ads'), 'Prime Video');
  assert.equal(serviceGroup('HBO Max Amazon Channel'), 'HBO Max');
  assert.equal(serviceGroup('ARD Plus Apple TV Channel'), 'ARD Plus');
  assert.equal(serviceGroup('MagentaTV'), 'MagentaTV');
  assert.equal(serviceGroup('Magenta TV+'), 'Magenta TV+');
  assert.equal(serviceGroup('Amazon Prime Video Free with Ads'), 'Amazon Prime Video Free with Ads');
});
