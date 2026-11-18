import {test} from 'node:test';
import assert from 'node:assert/strict';

import {bestCombinations, coverage, rotation} from '../../static/js/planner.js';

// Five films; weights 3 (favorite), 2, 1. "Free" films are always covered.
const data = {
  weights: {a: 3, b: 2, c: 1, d: 1, e: 1},
  base: ['e'],
  services: {Netflix: ['a', 'b'], Disney: ['b', 'c', 'd'], MUBI: ['a'], Pricey: ['a', 'b', 'c', 'd']},
};

test('coverage counts the free base, shares films between services once and weights them', () => {
  assert.deepEqual(coverage([], data), {films: 1, weight: 1, percent: 20});
  assert.deepEqual(coverage(['Netflix', 'Disney'], data), {films: 5, weight: 8, percent: 100});
  assert.equal(coverage(['Netflix', 'MUBI'], data).films, 3);  // a is on both
  assert.equal(coverage(['Nowhere'], data).films, 1);
});

test('the best set within a budget never costs more than the budget', () => {
  const prices = {Netflix: 8, Disney: 7, MUBI: 3, Pricey: 20};
  const best = bestCombinations(data, prices, 15);
  assert.ok(best.every(item => item.cost <= 15));
  assert.deepEqual(best[0].names.sort(), ['Disney', 'MUBI']);  // covers everything for 10, cheaper than Disney + Netflix
  assert.equal(best[0].percent, 100);
  // A smaller budget: Disney alone gives 4 weight (b, c, d) plus the base; Netflix 5 plus the base.
  assert.deepEqual(bestCombinations(data, prices, 8)[0].names, ['Netflix']);
  assert.deepEqual(bestCombinations(data, prices, 2), []);
});

test('on a tie the cheaper set wins, and a service without a price is left out', () => {
  const tie = {weights: {a: 1}, base: [], services: {X: ['a'], Y: ['a']}};
  assert.deepEqual(bestCombinations(tie, {X: 9, Y: 4}, 10)[0].names, ['Y']);
  assert.deepEqual(bestCombinations(tie, {X: 9}, 10)[0].names, ['X']);
  assert.deepEqual(bestCombinations(tie, {}, 10), []);
});

test('the rotation takes the service that adds the most each month and stops when nothing is left', () => {
  const plan = rotation(data, 3);
  assert.equal(plan[0].name, 'Pricey');  // a, b, c, d = weight 7
  assert.equal(plan.length, 1);  // everything else adds nothing
  const without = rotation(data, 3, ['Pricey']);
  assert.deepEqual(without.map(step => step.name), ['Netflix', 'Disney']);  // a, b first (weight 5), then c, d
  assert.equal(without[1].films, 2);
});
