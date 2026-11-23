import {test} from 'node:test';
import assert from 'node:assert/strict';

import {DEFAULTS, activeFilters, filterServices, parseState, sortServices, stateToSearch} from '../../static/js/service-table.js';

const service = (group, extra) => ({group, plans: [group], status: 'other', own: false, films: 10, exclusive: 0, hours: 20, free: 0, ads: 0, subscription: 10, rent: 0, averageRating: 3.5, costPerExclusiveFilm: null, ...extra});
const list = [
  service('Netflix', {status: 'own', own: true, films: 74, exclusive: 21, plans: ['Netflix', 'Netflix Standard with Ads'], costPerExclusiveFilm: 0.4}),
  service('MUBI', {films: 5, exclusive: 2, averageRating: 4.1}),
  service('Joyn', {status: 'free', films: 8, subscription: 0, ads: 8, averageRating: null}),
  service('Apple TV Store', {status: 'store', films: 400, subscription: 0, rent: 400}),
];
const names = items => items.map(item => item.group);

test('default view hides rent stores', () => {
  assert.deepEqual(names(filterServices(list, DEFAULTS)), ['Netflix', 'MUBI', 'Joyn']);
  assert.deepEqual(names(filterServices(list, {type: 'all'})), ['Netflix', 'MUBI', 'Joyn', 'Apple TV Store']);
  assert.deepEqual(names(filterServices(list, {type: 'store'})), ['Apple TV Store']);
  assert.deepEqual(names(filterServices(list, {type: 'free'})), ['Joyn']);
});

test('filters combine: search also finds plans, mine, exclusive, minimum', () => {
  assert.deepEqual(names(filterServices(list, {q: ' with ads '})), ['Netflix']);
  assert.deepEqual(names(filterServices(list, {mine: true})), ['Netflix']);
  assert.deepEqual(names(filterServices(list, {exclusive: true})), ['Netflix', 'MUBI']);
  assert.deepEqual(names(filterServices(list, {exclusive: true, min: 6})), ['Netflix']);
  assert.deepEqual(filterServices(list, {q: 'zzz'}), []);
});

test('sorting: either direction, missing values always last, ties by films', () => {
  assert.deepEqual(names(sortServices(list, 'films', 'desc')), ['Apple TV Store', 'Netflix', 'Joyn', 'MUBI']);
  assert.deepEqual(names(sortServices(list, 'name', 'asc')), ['Apple TV Store', 'Joyn', 'MUBI', 'Netflix']);
  assert.equal(sortServices(list, 'rating', 'desc').at(-1).group, 'Joyn');
  assert.equal(sortServices(list, 'rating', 'asc').at(-1).group, 'Joyn');
  assert.equal(sortServices(list, 'cost', 'asc')[0].group, 'Netflix');
});

test('URL state: round trip, defaults left out, unknown values ignored', () => {
  assert.equal(stateToSearch(DEFAULTS), '');
  const state = {...DEFAULTS, q: 'net', type: 'all', mine: true, exclusive: true, min: 3, sort: 'exclusive', dir: 'asc', all: true};
  assert.deepEqual(parseState(stateToSearch(state)), state);
  assert.deepEqual(parseState('?svctype=bogus&sort=bogus:up&min=-2'), DEFAULTS);
  assert.equal(stateToSearch(DEFAULTS, '?film=x&mine=1'), '?film=x');
  assert.equal(activeFilters(state), 5);
});
