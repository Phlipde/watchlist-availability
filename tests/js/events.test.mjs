import {test} from 'node:test';
import assert from 'node:assert/strict';

import {newOnServices, nowOnText, pickFilm, pickReason, recentlyGone, tonightRows, watchableOn} from '../../static/js/events.js';

const NOW = 2_000_000_000;
const DAY = 24 * 3600;
const titles = list => list.map(film => film.title);

test('watchable means free, with ads or in a subscription on a ticked service', () => {
  const film = {providers: {Netflix: ['flatrate'], 'Apple TV': ['rent'], Arte: ['free']}};
  assert.deepEqual(watchableOn(film, new Set(['Netflix', 'Apple TV'])), ['Netflix']);
});

test('new on your services: recent, on a ticked service, and not a switch between two of them', () => {
  const films = [
    {key: '1', title: 'Fresh', providers: {Netflix: ['flatrate']}, provider_changes: {added: ['Netflix'], removed: [], since: NOW - 2 * DAY}},
    {key: '2', title: 'Old news', providers: {Netflix: ['flatrate']}, provider_changes: {added: ['Netflix'], removed: [], since: NOW - 20 * DAY}},
    {key: '3', title: 'Switch', providers: {MUBI: ['flatrate']}, provider_changes: {added: ['MUBI'], removed: ['Netflix'], since: NOW - DAY}},
    {key: '4', title: 'Elsewhere', providers: {Disney: ['flatrate']}, provider_changes: {added: ['Disney'], removed: [], since: NOW - DAY}},
    {key: '5', title: 'Rent', providers: {Netflix: ['rent']}, provider_changes: {added: ['Netflix'], removed: [], since: NOW - DAY}},
  ];
  assert.deepEqual(titles(newOnServices(films, new Set(['Netflix', 'MUBI']), NOW)), ['Fresh']);
});

test('recently gone: one entry per film, newest first, with where it runs now; switches left out', () => {
  const changes = [
    {film_key: '1', title: 'Heat', provider: 'Netflix', change: 'removed', created: NOW - 3 * DAY},
    {film_key: '2', title: 'Alien', provider: 'Netflix', change: 'removed', created: NOW - DAY},
    {film_key: '3', title: 'Moved', provider: 'Netflix', change: 'removed', created: NOW - DAY},
    {film_key: '4', title: 'Long ago', provider: 'Netflix', change: 'removed', created: NOW - 40 * DAY},
    {film_key: '1', title: 'Heat', provider: 'Arte', change: 'added', created: NOW - DAY},
  ];
  const films = [
    {key: '1', title: 'Heat', providers: {'Prime Video': ['flatrate'], 'Apple TV': ['rent']}},
    {key: '2', title: 'Alien', providers: {'Apple TV': ['rent']}},
    {key: '3', title: 'Moved', providers: {MUBI: ['flatrate']}},
  ];
  const gone = recentlyGone(changes, films, new Set(['Netflix', 'MUBI']), NOW);
  assert.deepEqual(gone.map(entry => entry.title), ['Alien', 'Heat']);
  assert.equal(nowOnText(gone[0]), 'rent only on Apple TV');
  assert.equal(nowOnText(gone[1]), 'now on Prime Video (subscription)');
  assert.equal(nowOnText({nowOn: []}), 'not streaming anywhere');
});

test('tonight rows: new, free, one per subscription by size; chips narrow every row', () => {
  const films = [
    {key: '1', title: 'Heat', runtime: 170, rating: 8, letterboxd_rating: 4.1, providers: {Netflix: ['flatrate']}},
    {key: '2', title: 'Alien', runtime: 117, rating: 8.1, letterboxd_rating: 4.0, providers: {Netflix: ['flatrate'], Arte: ['free']}},
    {key: '3', title: 'Thief', runtime: 120, rating: 7, letterboxd_rating: 3.5, providers: {MUBI: ['flatrate']}},
    {key: '4', title: 'Seen', runtime: 90, providers: {Netflix: ['flatrate']}},
    {key: '5', title: 'Rental', runtime: 90, providers: {'Apple TV': ['rent']}},
  ];
  const services = new Set(['Netflix', 'Arte', 'MUBI', 'Apple TV']);
  const {rows, available} = tonightRows(films, {services, skip: new Set(['4']), now: NOW});
  assert.deepEqual(rows.map(row => [row.title, titles(row.films)]), [
    ['Free', ['Alien']], ['On Netflix', ['Heat', 'Alien']], ['On MUBI', ['Thief']],
  ]);
  assert.equal(available.length, 3);
  assert.equal(rows[1].href, '/watchlist?providers=Netflix&cost=subscription');
  const short = tonightRows(films, {services, chips: new Set(['tonight', 'rated']), now: NOW}).rows;
  assert.deepEqual(short.map(row => [row.title, titles(row.films)]), [['Free', ['Alien']], ['On Netflix', ['Alien']]]);
  assert.deepEqual(tonightRows(films, {services, chips: new Set(['free']), now: NOW}).rows.map(row => row.title), ['Free']);
});

test('pick for me avoids films picked before, until none is left', () => {
  const films = [{key: '1'}, {key: '2'}];
  assert.equal(pickFilm(films, new Set(['1']), () => 0.9).key, '2');
  assert.ok(['1', '2'].includes(pickFilm(films, new Set(['1', '2']), () => 0).key));
  assert.equal(pickFilm([], new Set()), null);
});

test('pick for me favours well rated films and says why', () => {
  const films = [{key: '1', rating: 1}, {key: '2', rating: 8.2, runtime: 107}];
  assert.equal(pickFilm(films, new Set(), () => 0.5).key, '2');  // a 1.0 has almost no chance next to an 8.2
  assert.equal(pickFilm(films, new Set(), () => 0).key, '1');  // but it is still possible
  assert.equal(pickReason(films[1], 'on Netflix'), 'Highly rated · 1h 47m · on Netflix');
  assert.equal(pickReason({key: '3'}, ''), '');
});

test('a film under "New" is not repeated in the service rows', () => {
  const films = [
    {key: '1', title: 'Fresh', providers: {Netflix: ['flatrate']}, provider_changes: {added: ['Netflix'], since: NOW - 3600}},
    {key: '2', title: 'Old', providers: {Netflix: ['flatrate']}},
  ];
  const {rows} = tonightRows(films, {services: new Set(['Netflix']), now: NOW});
  assert.deepEqual(rows.map(row => [row.title, titles(row.films)]), [['New on your services', ['Fresh']], ['On Netflix', ['Old']]]);
});
