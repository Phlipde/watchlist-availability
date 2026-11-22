import {test} from 'node:test';
import assert from 'node:assert/strict';

import {abroadFilm, abroadForFilm, abroadHtml, abroadRows, countryScore, groupByRegion, rankCountries} from '../../static/js/abroad.js';

const names = {AT: 'Austria', CH: 'Switzerland', FR: 'France', NL: 'Netherlands', BE: 'Belgium', US: 'United States', GB: 'United Kingdom', AD: 'Andorra', IT: 'Italy', ES: 'Spain', JP: 'Japan', VA: 'Vatican City', SM: 'San Marino'};
const nameOf = code => names[code] || code;

test('for DE the neighbours and German-speaking countries come first, tiny states last', () => {
  assert.equal(countryScore('AT', 'DE'), 6);
  assert.equal(countryScore('CH', 'DE'), 6);
  assert.equal(countryScore('FR', 'DE'), 5);
  assert.equal(countryScore('NL', 'DE'), 5);
  assert.equal(countryScore('BE', 'DE'), 3);
  assert.equal(countryScore('US', 'DE'), 2);
  assert.equal(countryScore('AD', 'DE'), -5);
  assert.deepEqual(rankCountries(['US', 'AD', 'NL', 'CH', 'AT', 'FR', 'BE', 'JP'], 'DE', nameOf), ['AT', 'CH', 'FR', 'NL', 'BE', 'JP', 'US', 'AD']);
});

test('a tie is alphabetical by name; a region without an entry falls back to the well-known VPN countries', () => {
  assert.deepEqual(rankCountries(['NL', 'FR'], 'DE', nameOf), ['FR', 'NL']);
  assert.deepEqual(rankCountries(['SM', 'IT', 'ES', 'VA', 'US'], 'XX', nameOf), ['IT', 'ES', 'US', 'SM', 'VA']);
});

test('one row per own service that has it abroad but not at home, the most countries first', () => {
  const byCountry = {
    DE: {Netflix: ['flatrate']},
    AT: {Netflix: ['flatrate'], 'Prime Video': ['flatrate'], filmfriend: ['free']},
    NL: {'Prime Video': ['flatrate']},
    US: {'Prime Video': ['flatrate'], 'Disney+': ['flatrate'], Hulu: ['rent']},
    IT: {'Prime Video Amazon Channel': ['flatrate']},
  };
  const rows = abroadRows(byCountry, new Set(['Netflix', 'Prime Video', 'filmfriend', 'Hulu']), 'DE', nameOf);
  assert.deepEqual(rows.map(row => [row.service, row.countries, row.hint]), [
    ['Prime Video', ['AT', 'NL', 'IT', 'US'], ''],
    ['filmfriend', ['AT'], 'Free'],
  ]);  // Netflix runs at home; Disney+ is not yours; Hulu is rent only
});

test('the collapsed line counts the countries; three flags a row and the rest behind +N', () => {
  const rows = [{service: 'Prime Video', countries: ['AT', 'NL', 'US', 'IT', 'JP'], kinds: {AT: 'flatrate', NL: 'flatrate', US: 'flatrate', IT: 'flatrate', JP: 'flatrate'}, hint: ''}];
  const html = abroadHtml(rows, {nameOf, logoOf: () => ''});
  assert.match(html, /5 countries/);
  assert.equal((html.match(/class="flag"/g) || []).length, 3 + 2);  // 3 shown plus 2 in the hidden grid
  assert.match(html, /\+2 /);
  assert.match(html, /aria-label="Austria · Prime Video \(subscription\)"/);
  assert.equal(abroadHtml([], {nameOf, logoOf: () => ''}), '');
  assert.deepEqual(groupByRegion(['US', 'AT', 'JP', 'ZZ']), [['Europe', ['AT']], ['Americas', ['US']], ['Asia / Pacific', ['JP']], ['Rest of the world', ['ZZ']]]);
});

test('the card takes the service with the most countries, its countries in the drawer order', () => {
  const entry = {Netflix: {JP: 'flatrate', US: 'flatrate'}, 'Prime Video': {NL: 'flatrate', AT: 'flatrate', FR: 'ads'}};
  const best = abroadForFilm(entry, 'DE', nameOf);
  assert.deepEqual([best.service, best.countries], ['Prime Video', ['AT', 'FR', 'NL']]);
  assert.equal(abroadForFilm({}, 'DE'), null);
  assert.equal(abroadForFilm(undefined, 'DE'), null);
});

test('a film listed because of the abroad switch only has your services abroad as offers', () => {
  const film = abroadFilm({key: '1', title: 'Heat', providers: {HBO: ['flatrate']}}, {Netflix: {AT: 'flatrate', JP: 'ads'}, MUBI: {US: 'flatrate'}});
  assert.deepEqual(film.providers, {Netflix: ['flatrate', 'ads'], MUBI: ['flatrate']});  // the home offers are not mixed in
  assert.equal(film.abroadOnly, true);
  assert.equal(film.title, 'Heat');
});
