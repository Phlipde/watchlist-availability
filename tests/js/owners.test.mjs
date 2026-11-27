import {test} from 'node:test';
import assert from 'node:assert/strict';

import {ownerText, ownersOf, whose} from '../../static/js/owners.js';
import {filmCard} from '../../static/js/rendering.js';
import {togetherRows} from '../../static/js/events.js';

const MEMBERS = [{id: 1, name: 'Me'}, {id: 2, name: 'anna'}, {id: 3, name: 'Ben'}];
const OWNERS = {Netflix: [1], 'MUBI Amazon Channel': [2], Arte: [1, 3]};

test('owners of a service, in member order; an Amazon Channel counts as its service', () => {
  assert.deepEqual(ownersOf('Netflix', OWNERS, MEMBERS), [{id: 1, name: 'Me', initial: 'M'}]);
  assert.deepEqual(ownersOf('MUBI', OWNERS, MEMBERS), [{id: 2, name: 'anna', initial: 'A'}]);
  assert.deepEqual(ownersOf('Arte', OWNERS, MEMBERS).map(owner => owner.id), [1, 3]);
  assert.deepEqual(ownersOf('Disney+', OWNERS, MEMBERS), []);
  assert.deepEqual(ownersOf('Netflix', undefined, undefined), []);
});

test('whose: "your" for the active profile, a name for another, nothing when shared', () => {
  assert.equal(whose(ownersOf('Netflix', OWNERS, MEMBERS), 1), 'your');
  assert.equal(whose(ownersOf('MUBI', OWNERS, MEMBERS), 1), "anna's");
  assert.equal(whose(ownersOf('Arte', OWNERS, MEMBERS), 1), '');
  assert.equal(whose([], 1), '');
  assert.equal(ownerText(ownersOf('Netflix', OWNERS, MEMBERS), 1), 'your service');
  assert.equal(ownerText(ownersOf('MUBI', OWNERS, MEMBERS), 1), "anna's service");
  assert.equal(ownerText(ownersOf('Arte', OWNERS, MEMBERS), 1), 'shared: you, Ben');
  assert.equal(ownerText([], 1), '');
});

test('a card in Together marks each logo with its owner, in the badge and in the name', () => {
  const film = {key: '9', title: 'Up', year: 2009, providers: {'MUBI Amazon Channel': ['flatrate'], Netflix: ['flatrate']}};
  const base = {imageBaseUrl: '', selected: new Set(['Netflix', 'MUBI Amazon Channel']), favorites: new Map(), compareKeys: new Set(), greyKeys: new Set()};
  assert.ok(!filmCard(film, 'Paid', base).includes('way-badge-owner'));
  const ownersFor = service => { const owners = ownersOf(service, OWNERS, MEMBERS); return {owners, text: ownerText(owners, 1)}; };
  const html = filmCard(film, 'Paid', {...base, ownersOf: ownersFor});
  assert.match(html, /aria-label="MUBI · Subscription · anna&#39;s service"/);
  assert.match(html, /aria-label="Netflix · Subscription · your service"/);
  assert.match(html, /way-badge-owner" aria-hidden="true">A</);
});

test('together rows: on both lists, then one of you; the chips and skip apply, only watchable films', () => {
  const films = [
    {key: '1', title: 'Shared', group: 'both', runtime: 100, providers: {Netflix: ['flatrate']}},
    {key: '2', title: 'Long', group: 'both', runtime: 200, providers: {MUBI: ['flatrate']}},
    {key: '3', title: 'Mine', group: 'one', providers: {Netflix: ['flatrate']}},
    {key: '4', title: 'Rent only', group: 'one', providers: {'Apple TV': ['rent']}},
    {key: '5', title: 'Seen', group: 'one', providers: {Netflix: ['flatrate']}},
  ];
  const services = new Set(['Netflix', 'MUBI']);
  const titles = rows => rows.map(row => [row.title, row.films.map(film => film.title).sort()]);
  const {rows, available} = togetherRows(films, {services, skip: new Set(['5']), now: 0});
  assert.deepEqual(titles(rows), [['On both lists', ['Long', 'Shared']], ['One of you, unseen', ['Mine']]]);
  assert.equal(available.length, 3);
  const short = togetherRows(films, {services, members: 3, chips: new Set(['tonight']), now: 0});
  assert.deepEqual(titles(short.rows), [["On everyone's list", ['Shared']], ['One of you, unseen', []]]);
});

test('the grid in Together reads its ids from ?together= and links back without it', async () => {
  const {myListHref, togetherIdsFrom} = await import('../../static/js/together-grid.js');
  assert.deepEqual(togetherIdsFrom('?together=2,3,2,x,0,-1'), [2, 3]);
  assert.deepEqual(togetherIdsFrom('?cost=free'), []);
  assert.equal(myListHref('http://h/watchlist?together=2&providers=MUBI&cost=free'), '/watchlist?cost=free');
});
