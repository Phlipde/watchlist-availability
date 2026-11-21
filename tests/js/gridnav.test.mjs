import {test} from 'node:test';
import assert from 'node:assert/strict';

import {columnsFromTops, nextInRows, nextIndex} from '../../static/js/gridnav.js';

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

test('rows of different length: left and right along the row, up and down keep the column as far as it reaches', () => {
  const lengths = [5, 2, 8];
  assert.deepEqual(nextInRows('ArrowRight', 0, 3, lengths), [0, 4]);
  assert.equal(nextInRows('ArrowRight', 0, 4, lengths), null);
  assert.deepEqual(nextInRows('ArrowDown', 0, 3, lengths), [1, 1]);  // the next row has only 2 films
  assert.deepEqual(nextInRows('ArrowDown', 1, 1, lengths), [2, 1]);
  assert.deepEqual(nextInRows('ArrowUp', 2, 6, lengths), [1, 1]);
  assert.equal(nextInRows('ArrowUp', 0, 0, lengths), null);
  assert.equal(nextInRows('ArrowDown', 2, 0, lengths), null);
  assert.deepEqual(nextInRows('End', 2, 0, lengths), [2, 7]);
  assert.deepEqual(nextInRows('Home', 2, 5, lengths), [2, 0]);
  assert.equal(nextInRows('ArrowLeft', 0, 0, lengths), null);
});
