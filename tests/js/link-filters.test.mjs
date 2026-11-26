import {test} from 'node:test';
import assert from 'node:assert/strict';

import {clearLink, emptyLink, isLinkSet, linkChips, linkMatches, needsUnavailable, parseLink, writeLink} from '../../static/js/link-filters.js';
import {filterFilms, sortFilms} from '../../static/js/filtering.js';

test('parseLink reads the four link filters and ignores unknown availability values', () => {
  assert.deepEqual(parseLink(new URLSearchParams('availability=free,ads,bogus&person=Ridley Scott&collection=Alien&runtimeMin=105')),
    {availability: ['free', 'ads'], person: 'Ridley Scott', collection: 'Alien', runtimeMin: 105});
  assert.deepEqual(parseLink(new URLSearchParams('availability=exclusive&runtimeMin=-3')), emptyLink());
});

test('writeLink round trip, empty values removed from the address', () => {
  const link = {availability: ['rent_buy'], person: '', collection: 'Alien', runtimeMin: 90};
  const params = new URLSearchParams('availability=exclusive&person=x');
  writeLink(link, params);
  assert.equal(params.toString(), 'availability=rent_buy&collection=Alien&runtimeMin=90');
  assert.deepEqual(parseLink(params), link);
});

test('chips and clearing', () => {
  const link = {availability: ['own_subscription', 'ads'], person: 'A', collection: '', runtimeMin: 0};
  assert.deepEqual(linkChips(link).map(chip => chip.key), ['availability', 'person']);
  assert.equal(isLinkSet(clearLink(clearLink(link, 'availability'), 'person')), false);
  assert.equal(needsUnavailable({...emptyLink(), availability: ['coming_soon']}), true);
});

test('linkMatches: best way, person (director or cast), series, minimum runtime', () => {
  const film = {director: 'Ridley Scott', cast: ['Sigourney Weaver'], collection: 'Alien Collection', runtime: 117};
  const of = () => 'own_subscription';
  assert.equal(linkMatches(film, emptyLink(), of), true);
  assert.equal(linkMatches(film, {...emptyLink(), availability: ['own_subscription']}, of), true);
  assert.equal(linkMatches(film, {...emptyLink(), availability: ['free']}, of), false);
  assert.equal(linkMatches(film, {...emptyLink(), person: 'Sigourney Weaver'}, of), true);
  assert.equal(linkMatches(film, {...emptyLink(), person: 'Nobody'}, of), false);
  assert.equal(linkMatches(film, {...emptyLink(), collection: 'Alien Collection'}, of), true);
  assert.equal(linkMatches(film, {...emptyLink(), runtimeMin: 120}, of), false);
});

test('filterFilms applies the link filter and the "oldest" sort', () => {
  const films = [
    {key: '1', title: 'A', providers: {Netflix: ['flatrate']}, director: 'X', watchlist_position: 2},
    {key: '2', title: 'B', providers: {Netflix: ['flatrate']}, director: 'Y', watchlist_position: 9},
  ];
  const filters = {query: '', availability: 'available', kind: 'all', genres: {include: [], exclude: []}, keyword: 'all', age: 'all', mode: 'any', yearFrom: 0, yearTo: 9999, minimumProviders: 0, minRating: 0, minVotes: 0, maxRuntime: 0, media: 'all', change: 'all', favoriteStatus: 'all', sort: 'oldest', favoritesOnly: false, where: 'all', link: {...emptyLink(), person: 'Y'}};
  const context = {selected: new Set(['Netflix']), favorites: new Map(), availabilityOf: () => 'own_subscription'};
  assert.deepEqual(filterFilms(films, [], filters, context).films.map(film => film.key), ['2']);
  assert.deepEqual(sortFilms(films, 'oldest').map(film => film.key), ['2', '1']);
});
