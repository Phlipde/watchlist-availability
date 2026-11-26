import {test} from 'node:test';
import assert from 'node:assert/strict';

import {numberText} from '../../static/js/ui.js';
import {filmCard, filmHref, runtimeText, unavailableCard} from '../../static/js/rendering.js';

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

test('a new film gets one badge on the poster, a hidden-away favorite says so instead', () => {
  const film = {key: 'x', title: 'Film', providers: {Netflix: ['flatrate']}, provider_changes: {added: ['Netflix']}};
  const base = {imageBaseUrl: '', selected: new Set(['Netflix']), compareKeys: new Set(), greyKeys: new Set()};
  const fresh = filmCard(film, 'Paid', {...base, favorites: new Map()});
  assert.match(fresh, /class="poster-badge poster-badge-new"/);
  const watched = filmCard(film, 'Paid', {...base, favorites: new Map([['x', {status: 'watched'}]])});
  assert.match(watched, /<span class="poster-badge">Hidden<\/span>/);
  assert.match(watched, /<article class="film is-watched"/);  // dimmed in the grid
  assert.ok(!fresh.includes('is-watched'));
  assert.ok(!watched.includes('poster-badge-new'));
  assert.match(watched, /aria-pressed="true"[^>]*><i class="ti ti-heart-filled"/);
});

test('a card has one stack of your free, subscription and ads services, no rent or buy; the best logo carries its type icon', () => {
  const film = {key: 'x', title: 'Film', providers: {Arte: ['free'], Netflix: ['flatrate'], Rakuten: ['rent'], MUBI: ['flatrate'], Sky: ['buy'], WOW: ['flatrate']}};
  const base = {imageBaseUrl: '', favorites: new Map(), compareKeys: new Set(), greyKeys: new Set(), providerLogos: {Arte: '/a.png'}, logoBaseUrl: 'https://img/', country: 'DE'};
  const html = filmCard(film, 'All', {...base, selected: new Set(['Arte', 'Netflix'])});
  assert.equal((html.match(/class="best-way(?:"| )/g) || []).length, 1);
  assert.match(html, /lstack-item is-wide" data-tip="Arte · Free"><img class="lstack-logo" src="https:\/\/img\/\/a\.png"[^>]*><span class="way-badge way-badge-free"/);
  assert.match(html, /aria-label="2 services: Arte, Netflix · details"/);
  assert.ok(!html.includes('Rakuten') && !html.includes('lstack-more'));
  assert.ok(!html.includes('data-provider='), 'no grid of logos');
});

test('the corner icon tells free, sub, ads, rent or buy; without a logo the name shows; nothing is said plainly', () => {
  const base = {imageBaseUrl: '', favorites: new Map(), compareKeys: new Set(), greyKeys: new Set(), providerLogos: {}, country: 'DE'};
  const ads = filmCard({key: 'a', title: 'A', providers: {Netzkino: ['ads']}}, 'All', {...base, selected: new Set(['Netzkino'])});
  assert.match(ads, /lstack-name">Netzkino<\/span><span class="way-badge way-badge-ads" aria-hidden="true"><i class="ti ti-ad"><\/i>/);
  const sub = filmCard({key: 's', title: 'S', providers: {Netflix: ['flatrate']}}, 'All', {...base, selected: new Set(['Netflix'])});
  assert.match(sub, /way-badge-flatrate" aria-hidden="true"><i class="ti ti-repeat"><\/i>/);
  const rent = filmCard({key: 'b', title: 'B', providers: {'Amazon VOD': ['rent'], 'Rakuten TV': ['rent']}}, 'All', {...base, selected: new Set()});
  assert.ok(!rent.includes('lstack'), 'rent is not on the card');
  assert.match(rent, /Rent · 2 shops/);
  const nothing = filmCard({key: 'c', title: 'C', providers: {}}, 'All', {...base, selected: new Set()});
  assert.match(nothing, /class="best-way is-muted"><span class="best-way-link is-static" tabindex="0"><i class="ti ti-ban way-none" aria-hidden="true"><\/i><span class="way-text">Not streaming<\/span>/);
});

test('a film that is only available abroad shows the logo with the flag of its best country', () => {
  const film = {key: 'x', title: 'Film', providers: {'Prime Video': ['flatrate']}, abroadOnly: true};  // listed because of the switch
  const context = {imageBaseUrl: '', selected: new Set(['Prime Video']), favorites: new Map(), compareKeys: new Set(), greyKeys: new Set(),
    providerLogos: {'Prime Video': '/p.png'}, logoBaseUrl: 'https://img/', country: 'DE', countryName: code => ({IT: 'Italy'}[code] || code),
    abroadFor: () => ({service: 'Prime Video', countries: ['IT', 'ES', 'US']})};
  const html = filmCard(film, 'All', context);
  assert.match(html, /<span class="way-badge way-badge-flag" aria-hidden="true"><img src="\/static\/flags\/it\.svg" alt=""><\/span>/);
  assert.match(html, /data-tip="Prime Video · Subscription · Italy, ES, US"/);
});

test('with the switch on, your services abroad follow the ones you can use here; the same service is not shown twice', () => {
  const film = {key: 'x', title: 'Film', providers: {Netflix: ['flatrate']}};
  const abroadList = () => [{service: 'Netflix', countries: ['IT']}, {service: 'Disney+', countries: ['IT', 'ES']}];
  const context = {imageBaseUrl: '', selected: new Set(['Netflix', 'Disney+']), favorites: new Map(), compareKeys: new Set(), greyKeys: new Set(),
    providerLogos: {}, country: 'DE', countryName: code => code, abroadList};
  const html = filmCard(film, 'All', context);
  assert.match(html, /aria-label="2 services: Netflix, Disney\+ · details"/);  // Netflix here, Disney+ abroad
  assert.match(html, /data-tip="Disney\+ · Subscription · IT, ES"/);
});

test('the card has a small heart on the poster and an action bar, no "..." menu', () => {
  const html = filmCard({key: 'x', title: 'Film', providers: {Netflix: ['flatrate']}}, 'All', {imageBaseUrl: '', selected: new Set(['Netflix']), favorites: new Map(), compareKeys: new Set(), greyKeys: new Set(), country: 'DE'});
  assert.match(html, /<div class="poster">.*<button class="favorite"/);
  assert.ok(html.indexOf('film-title') < html.indexOf('class="poster"'), 'the title comes first for the keyboard');
  assert.match(html, /<div class="poster-actions" role="group" aria-label="Actions: Film">/);
  assert.match(html, /title="Add to comparison"/);
  assert.match(html, /title="Not now: off Tonight and suggestions for 30 days"/);
  assert.match(html, /title="Hide: stays hidden until you unhide it"/);
  assert.ok(!html.includes('card-menu') && !html.includes('card-more'));
});

test('the table lists title link, year, runtime, rating and a stack of every service, yours first', async () => {
  const {filmTable, renderResults} = await import('../../static/js/rendering.js');
  const films = [{key: '1', title: 'Heat', year: 1995, runtime: 170, letterboxd_rating: 4.1, providers: {Netflix: ['flatrate'], MUBI: ['flatrate'], 'Amazon VOD': ['rent', 'buy']}}];
  const context = {selected: new Set(['Netflix']), providerLogos: {Netflix: '/n.png', MUBI: '/m.png'}, logoBaseUrl: 'https://img/'};
  const html = filmTable(films, context);
  assert.match(html, /<th scope="row"><span class="table-title"><span class="table-poster" aria-hidden="true"><\/span><a class="[^"]*film-open" href="[^"]*film=1"[^>]*>Heat<\/a>/);
  assert.match(html, /<td class="col-year">1995<\/td>/);
  assert.match(html, /★ 4\.1/);
  assert.match(html, /<th scope="col">Services<\/th>/);
  assert.match(html, /aria-label="3 services: Netflix, Amazon VOD, MUBI · details"/);  // yours first, one stack
  assert.match(html, /data-tip="Netflix · Subscription"/);
  const containers = {results: {dataset: {}}, unavailableResults: {}};
  renderResults({films, sectionOf: new Map(), unavailable: []}, containers, {...context, viewMode: 'table'});
  assert.equal(containers.results.dataset.mode, 'table');
  assert.match(containers.results.innerHTML, /film-table/);
});
