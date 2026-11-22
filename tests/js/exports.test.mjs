import {test} from 'node:test';
import assert from 'node:assert/strict';

import {favoritesCsv, filmsCsv, importLine, importPreview, parseFavorites} from '../../static/js/exports.js';

test('films and favorites become CSV with quoted cells', () => {
  assert.equal(filmsCsv([{title: 'Heat "1995"', year: 1995, providers: {Netflix: ['flatrate'], Arte: ['free']}}]), 'Title,Year,Services\n"Heat ""1995""","1995","Netflix; Arte"');
  assert.equal(favoritesCsv([{key: '949', title: 'Heat', year: 1995, status: 'watching', notes: 'a, b'}]), 'Title,Year,Status,Notes,Key\n"Heat","1995","watching","a, b","949"');
});

test('a favorites file round-trips through CSV and JSON', () => {
  const favorites = [{key: '949', title: 'Heat', year: 1995, status: 'plan', notes: 'later, maybe'}];
  assert.deepEqual(parseFavorites(favoritesCsv(favorites), 'favorites.csv').map(({key, title, notes}) => ({key, title, notes})), [{key: '949', title: 'Heat', notes: 'later, maybe'}]);
  assert.equal(parseFavorites(JSON.stringify(favorites), 'favorites.JSON')[0].title, 'Heat');
  assert.throws(() => parseFavorites('{"a": 1}', 'x.json'), /list of favorites/);
});

test('the import preview says what would happen before anything changes', () => {
  const records = [{key: '1', title: 'A'}, {key: '2', title: 'B'}, {key: '3', title: ''}, null, {key: '4', title: 'D'}];
  const preview = importPreview(records, new Set(['2']));
  assert.deepEqual([preview.found, preview.already, preview.fresh], [3, 1, 2]);  // the empty title and the null are not favorites
  assert.equal(importLine(preview), '3 favorites found · 1 already set · 2 new');
  assert.equal(importLine({found: 1, already: 0, fresh: 1}), '1 favorite found · 0 already set · 1 new');
});
