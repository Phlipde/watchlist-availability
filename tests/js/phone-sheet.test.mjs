import {test} from 'node:test';
import assert from 'node:assert/strict';

import {swipeCloses} from '../../static/js/phone-sheet.js';

test('a swipe closes the drawer past 28 % of its size or with a quick flick, else it springs back', () => {
  assert.equal(swipeCloses(100, 600, 300), true);   // a third of the sheet, slowly
  assert.equal(swipeCloses(60, 60, 300), true);     // short but quick (1 px/ms)
  assert.equal(swipeCloses(60, 600, 300), false);   // short and slow
  assert.equal(swipeCloses(15, 5, 300), false);     // a twitch is no flick
  assert.equal(swipeCloses(-80, 50, 300), false);   // the other way
});
