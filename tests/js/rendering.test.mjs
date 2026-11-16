import {test} from 'node:test';
import assert from 'node:assert/strict';

import {numberText} from '../../static/js/ui.js';
import {availabilityByOffer, filmCard, unavailableCard} from '../../static/js/rendering.js';

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

test('cards use the shared link class for TMDB and trailers', () => {
  const film = {key: 'x', title: 'Film', tmdb_url: 'https://tmdb.example/1', trailer_url: 'https://youtube.com/watch?v=abc', providers: {}};
  const context = {imageBaseUrl: '', selected: new Set(), favorites: new Map(), compareKeys: new Set(), greyKeys: new Set()};
  const html = filmCard(film, 'Paid', context);
  assert.match(html, /class="film-link" href="https:\/\/tmdb\.example\/1"/);
  assert.match(html, /class="film-link trailer-link" data-trailer="abc"/);
});

test('availability is grouped by offer type, in a fixed order, with logos', () => {
  const html = availabilityByOffer(
    {'Sky Store': ['rent'], WOW: ['flatrate', 'rent'], 'Pluto TV': ['ads'], arte: ['free']},
    {WOW: '/wow.png'},
    'https://img/w92',
  );
  const headings = [...html.matchAll(/<\/i> ([^<]+)<\/h6>/g)].map(match => match[1]);
  assert.deepEqual(headings, ['Free', 'With ads', 'Subscription', 'Rent']);
  const rent = html.slice(html.indexOf('data-offer="rent"'));
  assert.deepEqual([...rent.matchAll(/<span>([^<]+)<\/span>/g)].map(match => match[1]), ['Sky Store', 'WOW']);
  assert.equal((html.match(/src="https:\/\/img\/w92\/wow.png"/g) || []).length, 2); // WOW in two groups
  assert.ok(!html.includes('<img class="provider-logo" src="https://img/w92undefined'));
  assert.ok(!html.includes('offer-free'), 'groups have no offer colors');
  assert.equal(availabilityByOffer({}), '');
});
