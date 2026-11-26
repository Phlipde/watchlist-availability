import test from 'node:test';
import assert from 'node:assert/strict';
import {countryMatches, countryRank} from '../../static/js/country-picker.js';

test('a country matches by the start of its code or any part of its name', () => {
  assert.ok(countryMatches('PL', 'Poland', 'pl'));
  assert.ok(countryMatches('PL', 'Poland', ' POL '));
  assert.ok(countryMatches('GB', 'United Kingdom', 'kingdom'));
  assert.ok(!countryMatches('PL', '', 'l'));  // not the second letter of the code
  assert.ok(!countryMatches('FR', 'France', 'pl'));
});

test('accents and an empty search do not hide a country', () => {
  assert.ok(countryMatches('CI', 'Côte d’Ivoire', 'cote'));
  assert.ok(countryMatches('FR', 'France', ''));
  assert.ok(countryMatches('XK', '', 'xk'));
});

test('code hits rank before name hits', () => {
  assert.equal(countryRank('FR', 'France', 'fr'), 0);
  assert.equal(countryRank('CF', 'Central African Republic', 'fr'), 1);
  assert.equal(countryRank('PL', 'Poland', 'xyz'), null);
});
