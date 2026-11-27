import assert from 'node:assert/strict';
import test from 'node:test';
import {MIN_SCORE, similarOnServices, similarScore} from '../../static/js/similar.js';

const own = new Set(['Netflix']);
const film = (key, title, extra = {}) => ({key, title, tmdb_id: Number(key), genres: [], keywords: [], cast: [], year: 2012, providers: {Netflix: ['flatrate']}, ...extra});

test('scoring: genres x3, keywords x3, director x4, lead actors x1, year +1, TMDB list +4', () => {
  const a = film('1', 'A', {genres: ['Comedy', 'Music'], keywords: ['a cappella'], director: 'X', cast: ['P', 'Q'], similar_ids: [2]});
  const b = film('2', 'B', {genres: ['Comedy', 'Music'], keywords: ['A Cappella'], director: 'X', cast: ['P'], year: 2015});
  assert.equal(similarScore(a, b), 6 + 3 + 4 + 1 + 1 + 4);
});

test('places and countries are no shared keywords; without a shared genre nothing counts', () => {
  const a = film('1', 'A', {genres: ['Crime'], keywords: ['los angeles', 'heist']});
  const b = film('2', 'B', {genres: ['Crime'], keywords: ['los angeles', 'heist']});
  assert.equal(similarScore(a, b), 3 + 3 + 1);  // the genre, only "heist" and the year
  assert.equal(similarScore({...a, genres: []}, b), 0);
});

test('a shared genre plus TMDB hint and year is no match without a shared keyword or director (Jurassic Park III vs LOTR)', () => {
  const dino = film('1', 'Jurassic Park III', {genres: ['Adventure', 'Science Fiction'], keywords: ['dinosaur'], similar_ids: [2], year: 2001});
  const ring = film('2', 'The Lord of the Rings', {genres: ['Adventure', 'Fantasy'], keywords: ['elves'], year: 2001});
  assert.equal(similarScore(dino, ring), 3 + 1 + 4);
  assert.ok(similarScore(dino, ring) < MIN_SCORE);
});

const war = (key, title, extra = {}) => film(key, title, {genres: ['Drama', 'War'], director: 'X', ...extra});

test('only films on an own service, not skipped, never the film itself; fewer than three matches hide the row', () => {
  const a = war('1', 'A');
  const films = [a, war('2', 'Same'), war('3', 'Rent', {providers: {Netflix: ['rent']}}), war('4', 'Plan', {providers: {'Netflix Standard with Ads': ['ads']}}), war('5', 'Third')];
  assert.deepEqual(similarOnServices(a, films, own).map(item => item.title), ['Plan', 'Same', 'Third']);
  assert.deepEqual(similarOnServices(a, films, own, new Set(['2'])), []);  // two left: not enough
  assert.deepEqual(similarOnServices({key: 'x', title: 'Old scan'}, films, own), []);
});

test('films of the same series stay in the series row, not in Similar', () => {
  const a = war('1', 'Jurassic Park', {collection: 'Jurassic Park Collection'});
  const films = [a, war('2', 'Jurassic World', {collection: 'Jurassic Park Collection'}), war('3', 'B'), war('4', 'C'), war('5', 'D')];
  assert.deepEqual(similarOnServices(a, films, own).map(item => item.title), ['B', 'C', 'D']);
});
