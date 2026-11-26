import {test} from 'node:test';
import assert from 'node:assert/strict';

import {
  alternatives, catalogName, catalogRows, certificationText, dedupeKeywords, isReleased, letterboxdUrl, metaLine, primaryAction,
  runtimeLong, seriesOrder, statusBadges,
} from '../../static/js/drawer.js';

const own = names => new Set(names);

test('runtime and age rating read the way people say them', () => {
  assert.equal(runtimeLong(148), '2 h 28');
  assert.equal(runtimeLong(121), '2 h 01');
  assert.equal(runtimeLong(58), '58 min');
  assert.equal(runtimeLong(0), '');
  assert.equal(certificationText('12', 'DE'), 'FSK 12');
  assert.equal(certificationText('PG-13', 'US'), 'rated PG-13');
  assert.equal(certificationText('', 'DE'), '');
  assert.equal(metaLine({year: 2021, runtime: 148, certification: '16', genres: ['Sci-Fi', 'Action']}, 'DE'), '2021 · 2 h 28 · FSK 16 · Sci-Fi, Action');
});

test('keywords: one of each, no countries or places', () => {
  const countries = new Set(['united states', 'japan']);
  assert.deepEqual(dedupeKeywords(['Heist', 'heist ', 'United States', 'tokyo, japan', 'tokyo', 'Great Britain', 'dream'], countries), ['Heist', 'dream']);
  assert.deepEqual(dedupeKeywords(undefined), []);
});

test('an Amazon Channel is the same catalogue as its service', () => {
  assert.equal(catalogName('HBO Max Amazon Channel'), 'HBO Max');
  assert.equal(catalogName('Netflix'), 'Netflix');
  const groups = catalogRows({'HBO Max': ['flatrate'], 'HBO Max Amazon Channel': ['flatrate'], Netflix: ['flatrate', 'rent'], 'Apple TV': ['buy']}, own(['Netflix']));
  assert.deepEqual(groups.map(group => group.kind), ['flatrate', 'rent', 'buy']);
  const subscription = groups[0].rows;
  assert.deepEqual(subscription.map(row => [row.name, row.own, row.via]), [['Netflix', true, []], ['HBO Max', false, ['Amazon Channel']]]);
});

test('the main button always says what to do, never "Where to watch"', () => {
  const href = 'https://www.themoviedb.org/movie/1/watch?locale=DE';
  const film = providers => ({tmdb_url: 'https://www.themoviedb.org/movie/1', providers});
  const free = primaryAction(film({Arte: ['free'], Netflix: ['flatrate']}), own(['Netflix', 'Arte']), 'DE');
  assert.deepEqual([free.primary, free.text, free.href], [true, 'Watch on Arte · Free', href]);
  assert.equal(primaryAction(film({Netflix: ['flatrate']}), own(['Netflix']), 'DE').text, 'Watch on Netflix · Subscription');
  const rent = primaryAction(film({'Apple TV': ['rent']}), own(['Apple TV']), 'DE');
  assert.deepEqual([rent.primary, rent.text], [false, 'Rent on Apple TV']);
  assert.equal(primaryAction(film({'HBO Max': ['flatrate']}), own(['Netflix']), 'DE').text, 'On HBO Max (not your service)');
  assert.equal(primaryAction(film({Amazon: ['buy', 'rent']}), own([]), 'DE').text, 'Rent on Amazon');
  assert.equal(primaryAction({title: 'Heat', providers: {Arte: ['free']}}, own(['Arte']), 'DE').href, 'https://www.justwatch.com/de/search?q=Heat');  // no TMDB address: never an empty link
  const none = primaryAction(film({}), own(['Netflix']), 'DE', 'Germany');
  assert.deepEqual([none.disabled, none.text], [true, 'Not streaming in Germany']);
});

test('more own services come as alternatives; status badges carry the date', () => {
  const film = {providers: {Arte: ['free'], filmfriend: ['free'], Netflix: ['flatrate'], Other: ['flatrate']}, provider_changes: {added: ['Netflix'], removed: ['Prime Video'], since: new Date(2026, 10, 12).getTime() / 1000}};
  assert.deepEqual(alternatives(film, own(['Arte', 'filmfriend', 'Netflix']), 'Arte'), [{name: 'filmfriend', kind: 'free'}, {name: 'Netflix', kind: 'flatrate'}]);
  assert.deepEqual(statusBadges(film, own(['Netflix', 'Prime Video'])), [
    {tone: 'gone', text: 'No longer on Prime Video · since 12.11.'},
    {tone: 'new', text: 'New on Netflix · since 12.11.'},
  ]);
});

test('links: Letterboxd goes to the film by TMDB id', () => {
  assert.equal(letterboxdUrl({tmdb_id: 603, title: 'The Matrix'}), 'https://letterboxd.com/tmdb/603/');
  assert.equal(letterboxdUrl({title: 'The Matrix', year: 1999}), 'https://letterboxd.com/search/The%20Matrix%201999/');
});

test('keywords: cities, states and "<nationality> american" are places or origins, not topics', () => {
  const words = ['los angeles, california', 'beverly hills', 'philadelphia, pennsylvania', 'boston, massachusetts', 'italian american', 'friendship', 'african american', 'time travel'];
  assert.deepEqual(dedupeKeywords(words), ['friendship', 'african american', 'time travel']);
});

test('a series: oldest first, parts with no date or year last, and only released parts can be "start with"', () => {
  const parts = [{title: 'Grown Ups 3'}, {title: 'Grown Ups 2', year: 2013}, {title: 'Grown Ups', year: 2010}, {title: 'Grown Ups 4', release_date: '2031-07-01', year: 2031}];
  assert.deepEqual(seriesOrder(parts).map(part => part.title), ['Grown Ups', 'Grown Ups 2', 'Grown Ups 4', 'Grown Ups 3']);
  assert.equal(isReleased({year: 2013}, '2026-11-22'), true);
  assert.equal(isReleased({}, '2026-11-22'), false);
  assert.equal(isReleased({year: 2026, release_date: '2026-12-25'}, '2026-11-22'), false);
  assert.equal(isReleased({year: 2026, release_date: '2026-03-01'}, '2026-11-22'), true);
});

test('an unreleased film: no TMDB 0.0, and the main button says when it is in cinemas', async () => {
  const {primaryAction, drawerHtml, sourceText, catalogRows} = await import('../../static/js/drawer.js');
  const own = new Set(['Netflix']);
  const soon = {title: 'Avatar 4', providers: {}, cinema_date: '2027-06-30', rating: 0};
  const action = primaryAction(soon, own, 'DE', 'Germany', '2026-11-24');
  assert.equal(action.text, 'In cinemas 30.06.2027');
  assert.ok(action.disabled);
  assert.equal(primaryAction({title: 'X', providers: {}}, own, 'DE', 'Germany', '2026-11-24').text, 'Not streaming in Germany');
  assert.match(sourceText('DE', Date.UTC(2026, 10, 22, 12, 0) / 1000), /^Source: TMDB \(JustWatch data\), DE, as of 22\.11\.2026 \d\d:\d\d$/);
  assert.equal(sourceText('DE', 0), 'Source: TMDB (JustWatch data), DE');
  // The same catalogue under two names is one row.
  const rows = catalogRows({'Prime Video': ['flatrate'], 'Amazon Prime Video with Ads': ['flatrate'], 'MUBI Amazon Channel': ['flatrate'], MUBI: ['flatrate']}, own)[0].rows;
  assert.deepEqual(rows.map(row => row.name), ['MUBI', 'Prime Video']);
});
