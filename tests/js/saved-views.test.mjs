import {test} from 'node:test';
import assert from 'node:assert/strict';

import {saveViewHtml, viewSearch, viewsMenuHtml} from '../../static/js/saved-views.js';

test('a view keeps the filters but not the open film or the scan job', () => {
  assert.equal(viewSearch('?genre=Drama&film=12&scan=abc'), '?genre=Drama');
  assert.equal(viewSearch('?film=12'), '');
});

test('"Save view" is offered only while filters are set', () => {
  assert.equal(saveViewHtml('?film=12'), '');
  assert.match(saveViewHtml('?cost=free'), /Save view/);
});

test('the Views dropdown lists the views as links with a delete button and escapes the names', () => {
  const html = viewsMenuHtml([{name: 'Movie <b>night</b>', search: '?cost=free'}]);
  assert.match(html, /href="\/watchlist\?cost=free"/);
  assert.match(html, /Movie &lt;b&gt;night&lt;\/b&gt;/);
  assert.match(html, /data-remove-view="Movie &lt;b&gt;night&lt;\/b&gt;"/);
  assert.equal(viewsMenuHtml([]), '');
});
