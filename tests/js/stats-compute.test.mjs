import {test} from 'node:test';
import assert from 'node:assert/strict';

import {computeStats} from '../../static/js/stats-compute.js';

const NOW = Date.UTC(2026, 10, 17) / 1000;
const film = (key, extra) => ({key, title: key, runtime: 120, providers: {}, ...extra});
const scan = {
  results: [
    film('a', {providers: {Netflix: ['flatrate']}, letterboxd_rating: 4.4, rating: 8.0, watchlist_position: 9, collection: 'Saga'}),
    film('b', {providers: {'Netflix Standard with Ads': ['flatrate'], MUBI: ['flatrate']}, letterboxd_rating: 3.9, rating: 7.0, watchlist_position: 2, collection: 'Saga'}),
    film('c', {providers: {MUBI: ['flatrate']}, letterboxd_rating: 4.1, rating: 6.0}),
    film('d', {providers: {Joyn: ['ads']}, runtime: 60}),
    film('e', {providers: {Apple: ['rent'], Amazon: ['buy']}, letterboxd_rating: 4.5, rating: 8.5}),
    film('f', {providers: {Apple: ['rent']}, letterboxd_rating: 3.0, rating: 7}),
  ],
  unavailable: [film('g', {runtime: null})],
};
const stats = computeStats(scan, {subscriptions: ['Netflix'], prices: {Netflix: 10}, now: NOW});

test('breakdown adds up to the watchlist and hours count what you can watch now', () => {
  assert.equal(stats.availabilityBreakdown.reduce((sum, item) => sum + item.films, 0), 7);
  assert.deepEqual(Object.fromEntries(stats.availabilityBreakdown.map(item => [item.kind, item.films])),
    {own_subscription: 2, free: 0, ads: 1, other_subscription: 1, rent_buy: 2, coming_soon: 0, unavailable: 1});
  assert.equal(stats.hoursAvailableNow, 5);  // 120 + 120 + 60 min
});

test('service value: plans merge into one service, exclusive and price per exclusive film', () => {
  const netflix = stats.serviceValue.find(item => item.group === 'Netflix');
  assert.deepEqual(netflix.plans, ['Netflix', 'Netflix Standard with Ads']);
  assert.equal(netflix.films, 2);
  assert.equal(netflix.exclusive, 1);  // film b is also on MUBI
  assert.equal(netflix.status, 'own');
  assert.equal(netflix.onlyHere, 2);  // b is on MUBI too, but MUBI is not yours: you still lose it
  assert.equal(netflix.costPerLostFilm, 5);
  const mubi = stats.serviceValue.find(item => item.group === 'MUBI');
  assert.equal(mubi.price, null);
  assert.equal(mubi.costPerLostFilm, null);
  assert.equal(stats.serviceValue.find(item => item.group === 'Joyn').status, 'free');
  assert.equal(stats.serviceValue.find(item => item.group === 'Apple').status, 'store');
});

test('gain if subscribed: only films you cannot watch yet, best candidate as rotation tip', () => {
  assert.deepEqual(stats.gainIfSubscribed, [{group: 'MUBI', films: 1, hours: 2, onlyThere: 1}]);  // b is already on your Netflix
  assert.equal(stats.rotationSuggestion.group, 'MUBI');
});

test('lists: worth renting, best on own subscriptions, waiting longest, series, rating gap', () => {
  assert.deepEqual(stats.worthRenting.map(item => item.key), ['e']);
  assert.deepEqual(stats.bestOnOwnSubs.map(item => item.key), ['a', 'b']);
  assert.deepEqual(stats.waitingLongest.map(item => item.key), ['a', 'b']);
  assert.deepEqual(stats.collectionsPlanner, [{name: 'Saga', films: 2, hours: 4, inOwn: 2}]);
  assert.equal(stats.ratingGap.positive[0].film.key, 'c');  // 8.2 against 6.0
  assert.equal(stats.ratingGap.negative[0].film.key, 'f');
});

test('footnotes: films without runtime or rating', () => {
  assert.equal(stats.withoutRuntime, 1);
  assert.equal(stats.withoutRating, 2);  // d and g
});

test('a rent store with a few ad-supported films is still a store', () => {
  const mixed = {results: [film('x', {providers: {Rakuten: ['rent']}}), film('y', {providers: {Rakuten: ['rent']}}), film('z', {providers: {Rakuten: ['ads']}})], unavailable: []};
  const rakuten = computeStats(mixed, {now: NOW}).serviceValue.find(item => item.group === 'Rakuten');
  assert.equal(rakuten.status, 'store');
  assert.equal(rakuten.rent, 2);
});

test('histograms: runtime in 15-minute steps, rating in 0.25 steps, with the average', () => {
  const sample = {results: [film('r1', {runtime: 70, letterboxd_rating: 2.0}), film('r2', {runtime: 95, letterboxd_rating: 3.6}), film('r3', {runtime: 100, letterboxd_rating: 3.7}), film('r4', {runtime: 200, letterboxd_rating: 5})], unavailable: []};
  const {runtimeHistogram, ratingHistogram} = computeStats(sample, {now: NOW});
  assert.deepEqual(runtimeHistogram.bins.filter(bin => bin.count).map(bin => [bin.label, bin.count]), [['Under 75 min', 1], ['90–104', 2], ['165 min +', 1]]);
  assert.equal(runtimeHistogram.average, 116.25);
  assert.deepEqual(ratingHistogram.bins.filter(bin => bin.count).map(bin => [bin.label, bin.count]), [['Under 2.25', 1], ['3.50', 2], ['5', 1]]);
});

test('recent changes: newest first, at most ten', () => {
  const many = {results: [], unavailable: [], changes: Array.from({length: 12}, (_, index) => ({film_key: `k${index}`, provider: 'Netflix', change: 'added', created: index}))};
  const recent = computeStats(many, {now: NOW}).recentChanges;
  assert.equal(recent.length, 10);
  assert.equal(recent[0].created, 11);
});

test('"Only here" counts the same films as on Subscriptions (shared case with tests/test_costs.py)', async () => {
  const {readFile} = await import('node:fs/promises');
  const cases = JSON.parse(await readFile(new URL('../only_here_cases.json', import.meta.url), 'utf8'));
  const result = computeStats({results: cases.films, unavailable: []}, {subscriptions: cases.subscriptions, now: NOW});
  for (const [group, count] of Object.entries(cases.only_here)) {
    assert.equal(result.serviceValue.find(item => item.group === group).onlyHere, count, group);
  }
});
