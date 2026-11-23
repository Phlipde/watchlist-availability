import assert from 'node:assert/strict';
import test from 'node:test';
import {hiddenCount, itemText, logoStackHtml, stackLabel, stackMode} from '../../static/js/logo-stack.js';

const item = (name, kind = 'flatrate', extra = {}) => ({name, kind, logo: `/${name}.png`, ...extra});
const many = count => Array.from({length: count}, (_, i) => item(`S${i}`));

test('text of a logo: name, type, and the country for a service abroad', () => {
  assert.equal(itemText(item('Netflix')), 'Netflix · Subscription');
  assert.equal(itemText(item('Prime Video', 'abroad', {country: 'Italy'})), 'Prime Video · Subscription · Italy');
});

test('aria label counts and names the services', () => {
  assert.equal(stackLabel([item('Netflix'), item('Prime Video')]), '2 services: Netflix, Prime Video');
  assert.equal(stackLabel([item('Netflix')]), '1 service: Netflix');
});

test('first three side by side, two overlap, the rest is +N; more than 8 is a list', () => {
  assert.equal(hiddenCount(many(5)), 0);
  assert.equal(hiddenCount(many(6)), 1);
  assert.equal(stackMode(many(8)), 'fan');
  assert.equal(stackMode(many(9)), 'list');
  const html = logoStackHtml(many(6));
  assert.equal((html.match(/is-extra/g) || []).length, 1);
  assert.match(html, /<span class="lstack-more">\+1<\/span>/);
  assert.match(html, /aria-expanded="false" aria-label="6 services: S0, S1/);
  assert.ok(!html.includes('lstack-list'));
  assert.match(logoStackHtml(many(9)), /<ul class="lstack-list" hidden>/);
});

test('one logo has no toggle; the plain variant has none either; no logo shows the name', () => {
  assert.ok(!logoStackHtml([item('Arte')]).includes('lstack-toggle'));
  assert.ok(!logoStackHtml(many(3), {interactive: false}).includes('lstack-toggle'));
  assert.match(logoStackHtml([{name: 'Joyn', kind: 'free', logo: ''}]), /lstack-name">Joyn/);
  assert.equal(logoStackHtml([]), '');
});
