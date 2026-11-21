import {test} from 'node:test';
import assert from 'node:assert/strict';

import {numberText} from '../../static/js/ui.js';
import {availabilityByOffer, filmCard, filmHref, runtimeText, unavailableCard} from '../../static/js/rendering.js';

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

test('runtime on the card reads as hours and minutes', () => {
  assert.equal(runtimeText(154), '2h 34m');
  assert.equal(runtimeText(58), '58m');
  assert.equal(runtimeText(120), '2h');
  assert.equal(runtimeText(attack), '');
  assert.equal(runtimeText(0), '');
});

test('a film link keeps the page address, drops the scan job and adds the film', () => {
  assert.equal(filmHref('http://host/?genre=Drama&scan=abc', '12'), '/?genre=Drama&film=12');
  assert.equal(filmHref('http://host/?film=1', 'Heat|1995'), '/?film=Heat%7C1995');
});

test('the card title is the link to the details; TMDB, trailer and Details button are gone', () => {
  const film = {key: 'x', title: 'Film', year: 2010, runtime: 118, rating: 7.7, tmdb_url: 'https://tmdb.example/1', trailer_url: 'https://youtube.com/watch?v=abc', providers: {}};
  const context = {imageBaseUrl: '', selected: new Set(), favorites: new Map(), compareKeys: new Set(), greyKeys: new Set(), pageHref: 'http://host/?genre=Drama'};
  const html = filmCard(film, 'Paid', context);
  assert.match(html, /<a class="film-open" href="\/\?genre=Drama&amp;film=x" data-key="x" title="Film">Film<\/a>/);
  assert.ok(!html.includes('tmdb.example') && !html.includes('trailer') && !html.includes('Details'), html);
  assert.match(html, /2010 · <span aria-hidden="true">1h 58m<\/span><span class="visually-hidden">1 hour 58 minutes<\/span> · TMDB 7\.7</);
  assert.match(html, /<img src="[^"]*" alt=""|no-poster/);
  assert.ok(!html.includes('/10'));
});

test('the card prefers the Letterboxd rating', () => {
  const film = {key: 'x', title: 'Film', year: 2010, rating: 7.7, letterboxd_rating: 3.94, providers: {}};
  const context = {imageBaseUrl: '', selected: new Set(), favorites: new Map(), compareKeys: new Set(), greyKeys: new Set()};
  assert.match(filmCard(film, 'Paid', context), /★<\/span><span class="visually-hidden">Letterboxd<\/span> 3\.9</);
});

test('cards list every ticked service of the section by name, marked by offer type', () => {
  const film = {key: 'x', title: 'Film', providers: {YouTube: ['ads', 'rent'], Arte: ['free'], Netflix: ['flatrate'], Rakuten: ['rent'], MUBI: ['flatrate']}};
  const context = {imageBaseUrl: '', selected: new Set(['YouTube', 'Arte', 'Netflix', 'Rakuten']), favorites: new Map(), compareKeys: new Set(), greyKeys: new Set()};
  const free = filmCard(film, 'Free', context);
  assert.deepEqual([...free.matchAll(/data-provider="([^"]+)"/g)].map(match => match[1]), ['Arte', 'YouTube']);
  assert.match(free, /data-provider="YouTube">.*?title="YouTube, with ads, rent".*?service-mark-ads" aria-hidden="true">Ad</);
  assert.match(free, /service-mark-free/);
  const paid = filmCard(film, 'Paid', context);
  // MUBI is not ticked; a subscription has no mark, rent shows "€".
  assert.deepEqual([...paid.matchAll(/data-provider="([^"]+)"/g)].map(match => match[1]), ['Netflix', 'Rakuten', 'YouTube']);
  assert.ok(!/data-provider="Netflix"[^]*?service-mark[^]*?data-provider="Rakuten"/.test(paid), 'no mark on a subscription');
  assert.match(paid, /data-provider="YouTube"[^>]*>.*?service-mark-rent" aria-hidden="true">€</);
  assert.ok(!paid.includes('offer-badge'));
});

test('a new film gets one badge on the poster, a greyed-out favorite says so instead', () => {
  const film = {key: 'x', title: 'Film', providers: {Netflix: ['flatrate']}, provider_changes: {added: ['Netflix']}};
  const base = {imageBaseUrl: '', selected: new Set(['Netflix']), compareKeys: new Set(), greyKeys: new Set()};
  const fresh = filmCard(film, 'Paid', {...base, favorites: new Map()});
  assert.match(fresh, /class="poster-badge poster-badge-new"/);
  const watched = filmCard(film, 'Paid', {...base, favorites: new Map([['x', {status: 'watched'}]])});
  assert.match(watched, /<span class="poster-badge">Greyed out<\/span>/);
  assert.match(watched, /<article class="film is-watched"/);  // dimmed in the grid
  assert.ok(!fresh.includes('is-watched'));
  assert.ok(!watched.includes('poster-badge-new'));
  assert.match(watched, /aria-pressed="true"[^>]*><i class="ti ti-heart-filled"/);
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

test('cards show a service logo with its name as alt text, else the name', () => {
  const film = {key: 'x', title: 'Film', providers: {Netflix: ['flatrate'], Arte: ['flatrate']}};
  const context = {imageBaseUrl: '', selected: new Set(['Netflix', 'Arte']), favorites: new Map(), compareKeys: new Set(), greyKeys: new Set(),
    providerLogos: {Netflix: '/n.png'}, logoBaseUrl: 'https://img/'};
  const html = filmCard(film, 'Paid', context);
  assert.match(html, /<img class="service-logo" src="https:\/\/img\/\/n\.png" alt="Netflix, subscription"/);
  assert.match(html, /data-provider="Arte"><span class="pill pill-service" title="Arte, subscription">Arte<span class="visually-hidden">, subscription<\/span><\/span>/);
});

test('card for "All" lists every ticked service, the cheapest offer decides the mark', () => {
  const film = {key: 'x', title: 'Film', providers: {Arte: ['free'], Netflix: ['flatrate'], Rakuten: ['rent']}};
  const context = {imageBaseUrl: '', selected: new Set(['Arte', 'Netflix', 'Rakuten']), favorites: new Map(), compareKeys: new Set(), greyKeys: new Set()};
  assert.deepEqual([...filmCard(film, 'All', context).matchAll(/data-provider="([^"]+)"/g)].map(match => match[1]), ['Arte', 'Netflix', 'Rakuten']);
});

test('the table view lists title link, year, runtime, rating and only the services you ticked', async () => {
  const {filmTable, renderResults} = await import('../../static/js/rendering.js');
  const films = [{key: '1', title: 'Heat', year: 1995, runtime: 170, letterboxd_rating: 4.1, providers: {Netflix: ['flatrate'], MUBI: ['flatrate']}}];
  const html = filmTable(films, {selected: new Set(['Netflix'])});
  assert.match(html, /<th scope="row"><a class="[^"]*film-open" href="[^"]*film=1"[^>]*>Heat<\/a>/);
  assert.match(html, /<td>1995<\/td>/);
  assert.match(html, /★ 4\.1/);
  assert.match(html, /<td>Netflix<\/td>/);  // MUBI is not ticked
  const containers = {results: {dataset: {}}, unavailableResults: {}};
  renderResults({films, sectionOf: new Map(), unavailable: []}, containers, {viewMode: 'table', selected: new Set(['Netflix'])});
  assert.equal(containers.results.dataset.mode, 'table');
  assert.match(containers.results.innerHTML, /film-table/);
});
