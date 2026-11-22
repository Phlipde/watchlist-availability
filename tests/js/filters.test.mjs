import test from 'node:test';
import assert from 'node:assert/strict';
import {durationText} from '../../static/js/filters.js';

test('durationText says minutes under two hours and hours from there', () => {
  assert.equal(durationText(95), '95 min');
  assert.equal(durationText(90), '90 min');
  assert.equal(durationText(120), '2 h');
  assert.equal(durationText(125), '2 h 05');
  assert.equal(durationText(225), '3 h 45');
  assert.equal(durationText(0), '');
  assert.equal(durationText('x'), '');
});
