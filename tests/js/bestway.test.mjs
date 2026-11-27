import {test} from 'node:test';
import assert from 'node:assert/strict';

import {bestWay, wayText} from '../../static/js/bestway.js';

const own = names => new Set(names);
const film = providers => ({providers});

test('own free beats own subscription beats own ads beats renting', () => {
  const all = film({Arte: ['free'], Netflix: ['flatrate'], Netzkino: ['ads'], 'Amazon VOD': ['rent']});
  assert.deepEqual([bestWay(all, {own: own(['Arte', 'Netflix', 'Netzkino'])}).kind, bestWay(all, {own: own(['Netflix', 'Netzkino'])}).kind, bestWay(all, {own: own(['Netzkino'])}).kind, bestWay(all, {own: own([])}).kind], ['free', 'flatrate', 'ads', 'rent']);
  const way = bestWay(all, {own: own(['Arte', 'Netflix'])});
  assert.deepEqual([way.service, way.others, wayText(way)], ['Arte', 3, 'Free']);  // three more services have it
  assert.equal(wayText(bestWay(film({Netflix: ['flatrate']}), {own: own(['Netflix'])})), 'Netflix · Subscription');
  assert.equal(wayText(bestWay(film({Netzkino: ['ads']}), {own: own(['Netzkino'])})), 'With ads');
});

test('rent: ticked shops first, then the fixed shop order; buy only when nothing can be rented', () => {
  const shops = film({'Rakuten TV': ['rent'], 'Apple TV Store': ['rent'], 'Amazon VOD': ['rent', 'buy'], 'Sky Store': ['rent']});
  const way = bestWay(shops, {own: own([])});
  assert.deepEqual([way.kind, way.service, way.shops, wayText(way)], ['rent', 'Amazon VOD', 4, 'Rent · 4 shops']);
  assert.equal(bestWay(shops, {own: own(['Rakuten TV'])}).service, 'Rakuten TV');  // a shop you ticked comes first
  const buying = bestWay(film({'Apple TV Store': ['buy'], 'Amazon VOD': ['buy'], 'Google Play Movies': ['buy']}), {own: own([])});
  assert.deepEqual([buying.kind, buying.service, wayText(buying)], ['buy', 'Amazon VOD', 'Buy · 3 shops']);
  assert.equal(wayText(bestWay(film({'Amazon VOD': ['rent']}), {own: own([])})), 'Rent · 1 shop');
});

test('abroad only when it is given, then a service that is not yours, then nothing', () => {
  const abroad = {service: 'Prime Video', countries: ['IT', 'ES', 'US', 'JP', 'FR']};
  const nowhere = film({});
  const way = bestWay(nowhere, {own: own(['Prime Video']), abroad});
  assert.deepEqual([way.kind, way.service, way.countries[0], way.others, wayText(way)], ['abroad', 'Prime Video', 'IT', 4, 'Abroad']);
  assert.equal(bestWay(nowhere, {own: own([])}).kind, 'none');
  assert.equal(wayText(bestWay(nowhere, {own: own([])})), 'Not streaming');
  const foreign = bestWay(film({'HBO Max': ['flatrate'], 'HBO Max Amazon Channel': ['flatrate']}), {own: own([])});
  assert.deepEqual([foreign.kind, foreign.muted, wayText(foreign)], ['foreign', true, 'On HBO Max · not your service']);
  // rent beats abroad: you can watch it here
  assert.equal(bestWay(film({'Amazon VOD': ['rent']}), {own: own([]), abroad}).kind, 'rent');
});

test('in Together your and shared services come before a partner\'s one of the same kind', () => {
  const film = {providers: {'Disney+': ['flatrate'], 'Prime Video': ['flatrate']}};
  const own = new Set(['Disney+', 'Prime Video']);
  assert.equal(bestWay(film, {own}).service, 'Disney+');  // by name without Together
  const whose = name => (name === 'Disney+' ? "Anna's" : '');
  assert.equal(bestWay(film, {own, whose}).service, 'Prime Video');
});
