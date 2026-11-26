import assert from 'node:assert/strict';
import test from 'node:test';
import {MIN_SCORE, similarOnServices, similarScore} from '../../static/js/similar.js';

const own = new Set(['Netflix']);
const film = (key, title, extra = {}) => ({key, title, tmdb_id: Number(key), genres: [], keywords: [], cast: [], year: 2012, providers: {Netflix: ['flatrate']}, ...extra});

test('scoring: genres x3, keywords x2, director x4, lead actors x1, year +1, TMDB list +5', () => {
  const a = film('1', 'A', {genres: ['Comedy', 'Music'], keywords: ['a cappella'], director: 'X', cast: ['P', 'Q'], similar_ids: [2]});
  const b = film('2', 'B', {genres: ['Comedy', 'Music'], keywords: ['A Cappella'], director: 'X', cast: ['P'], year: 2015});
  assert.equal(similarScore(a, b), 6 + 2 + 4 + 1 + 1 + 5);
});

test('places and countries are no shared keywords', () => {
  const a = film('1', 'A', {keywords: ['los angeles', 'heist']});
  const b = film('2', 'B', {keywords: ['los angeles', 'heist']});
  assert.equal(similarScore(a, b), 2 + 1);  // only "heist" and the year
});

test('Pitch Perfect does not suggest Beverly Hills Cop: one shared genre and a TMDB hint are not enough', () => {
  const pitch = film('1', 'Pitch Perfect', {genres: ['Comedy', 'Music', 'Romance'], similar_ids: [2, 3], year: 2012});
  const cop = film('2', 'Beverly Hills Cop', {genres: ['Action', 'Comedy', 'Crime'], year: 1984});
  const sing = film('3', 'Pitch Perfect 2', {genres: ['Comedy', 'Music'], keywords: ['a cappella'], year: 2015});
  pitch.keywords = ['a cappella'];
  const result = similarOnServices(pitch, [pitch, cop, sing], own);
  assert.deepEqual(result.map(item => item.title), ['Pitch Perfect 2']);
  assert.ok(similarScore(pitch, cop) < MIN_SCORE);
});

test('only films on an own service, not skipped, never the film itself; an empty result hides the row', () => {
  const a = film('1', 'A', {genres: ['Drama', 'War'], director: 'X'});
  const same = film('2', 'Same', {genres: ['Drama', 'War'], director: 'X'});
  const rent = film('3', 'Rent', {genres: ['Drama', 'War'], director: 'X', providers: {Netflix: ['rent']}});
  const plan = film('4', 'Plan', {genres: ['Drama', 'War'], director: 'X', providers: {'Netflix Standard with Ads': ['ads']}});
  assert.deepEqual(similarOnServices(a, [a, same, rent, plan], own).map(item => item.title), ['Plan', 'Same']);
  assert.deepEqual(similarOnServices(a, [a, same, rent, plan], own, new Set(['2'])).map(item => item.title), ['Plan']);
  assert.deepEqual(similarOnServices({key: 'x', title: 'Old scan'}, [same], own), []);
});
