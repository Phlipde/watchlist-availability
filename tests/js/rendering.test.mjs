import {test} from 'node:test';
import assert from 'node:assert/strict';

import {numberText} from '../../static/js/ui.js';
import {filmCard, unavailableCard} from '../../static/js/rendering.js';

const attack = '<img src=x onerror="alert(1)">';

test('numberText writes only finite numbers', () => {
  assert.equal(numberText(1995), '1995');
  assert.equal(numberText('1995'), '1995');
  assert.equal(numberText(7.5), '7.5');
  assert.equal(numberText(attack, 'Year unknown'), 'Year unknown');
  assert.equal(numberText(null, '-'), '-');
  assert.equal(numberText('', '-'), '-');
  assert.equal(numberText(true, '-'), '-');
  assert.equal(numberText(Infinity, '-'), '-');
});

test('cards never put text from year, runtime or rating into the HTML', () => {
  const film = {key: 'x', title: 'Evil', year: attack, runtime: attack, rating: attack, providers: {}};
  const context = {imageBaseUrl: '', selected: new Set(), favorites: new Map(), compareKeys: new Set(), greyKeys: new Set()};
  for (const html of [filmCard(film, 'Paid', context), unavailableCard(film, new Set())]) {
    assert.ok(!html.includes('<img src=x'), html);
    assert.ok(html.includes('Year unknown'));
  }
});
