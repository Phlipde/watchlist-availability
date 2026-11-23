import assert from 'node:assert/strict';
import test from 'node:test';
import {hiddenCount, itemText, logoStackHtml, stackLabel} from '../../static/js/logo-stack.js';

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

test('first three side by side, two overlap, the rest is +N; the card stack opens the details', () => {
  assert.equal(hiddenCount(many(5)), 0);
  assert.equal(hiddenCount(many(6)), 1);
  const html = logoStackHtml(many(6), {key: 'k'});
  assert.equal((html.match(/lstack-item/g) || []).length, 5);
  assert.match(html, /<span class="lstack-more">\+1<\/span>/);
  assert.match(html, /class="lstack" data-open-more data-key="k"/);
  assert.match(html, /aria-label="6 services: S0, S1/);
});

test('the plain variant has no button; no logo shows the name; no items give nothing', () => {
  assert.ok(!logoStackHtml(many(3)).includes('lstack-toggle'));
  assert.match(logoStackHtml([{name: 'Joyn', kind: 'free', logo: ''}]), /lstack-name">Joyn/);
  assert.equal(logoStackHtml([]), '');
});
