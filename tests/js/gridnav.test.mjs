import {test} from 'node:test';
import assert from 'node:assert/strict';

import {columnsFromTops, nextIndex} from '../../static/js/gridnav.js';

test('the column count is measured from the tops of the first row', () => {
  assert.equal(columnsFromTops([100, 100, 100, 100, 420, 420]), 4);
  assert.equal(columnsFromTops([100, 101, 99, 420]), 3);  // a pixel or two apart is still one row
  assert.equal(columnsFromTops([100, 420, 740]), 1);  // a phone, or the table
  assert.equal(columnsFromTops([100, 100]), 2);  // everything in one row
  assert.equal(columnsFromTops([]), 1);
});

test('left and right step one film, home and end jump', () => {
  assert.equal(nextIndex('ArrowRight', 2, 4, 10), 3);
  assert.equal(nextIndex('ArrowLeft', 2, 4, 10), 1);
  assert.equal(nextIndex('ArrowLeft', 0, 4, 10), null);
  assert.equal(nextIndex('ArrowRight', 9, 4, 10), null);
  assert.equal(nextIndex('Home', 6, 4, 10), 0);
  assert.equal(nextIndex('End', 6, 4, 10), 9);
});

test('up and down keep the column; below a short last row they land on the last film', () => {
  assert.equal(nextIndex('ArrowDown', 1, 4, 10), 5);
  assert.equal(nextIndex('ArrowUp', 5, 4, 10), 1);
  assert.equal(nextIndex('ArrowUp', 2, 4, 10), null);  // first row: nothing above
  assert.equal(nextIndex('ArrowDown', 6, 4, 10), 9);  // the row below has only 2 films
  assert.equal(nextIndex('ArrowDown', 9, 4, 10), null);  // already in the last row
  assert.equal(nextIndex('ArrowDown', 3, 1, 5), 4);  // the table: one column
  assert.equal(nextIndex('ArrowUp', 3, 1, 5), 2);
  assert.equal(nextIndex('x', 3, 4, 10), null);
  assert.equal(nextIndex('ArrowDown', 0, 4, 0), null);
});
