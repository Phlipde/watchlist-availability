import {test} from 'node:test';
import assert from 'node:assert/strict';

import {storageFor} from '../../static/js/profile-storage.js';
import {copyView, loadViews, saveViewHtml, viewSearch, viewsMenuHtml} from '../../static/js/saved-views.js';

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

test('each view offers its link, and "Copy to" only when other profiles exist', () => {
  const view = [{name: 'Night', search: '?cost=free'}];
  assert.match(viewsMenuHtml(view), /data-share-view="Night"/);
  assert.doesNotMatch(viewsMenuHtml(view), /data-copy-view/);
  const html = viewsMenuHtml(view, [{id: '2', name: 'Anna & Ben'}]);
  assert.match(html, /data-copy-view="Night"/);
  assert.match(html, /<option value="2">Anna &amp; Ben<\/option>/);
});

test('copying a view adds it to the other profile only and replaces one with the same name', () => {
  const data = new Map([['p2:savedViews', '[{"name":"Night","search":"?old=1"},{"name":"Kids","search":"?g=1"}]']]);
  const storage = {getItem: key => data.get(key) ?? null, setItem: (key, value) => data.set(key, value), removeItem: key => data.delete(key)};
  copyView({name: 'Night', search: '?cost=free'}, storageFor(storage, 2));
  assert.deepEqual(loadViews(storageFor(storage, 2)), [{name: 'Kids', search: '?g=1'}, {name: 'Night', search: '?cost=free'}]);
  assert.deepEqual(loadViews(storageFor(storage, 3)), []);
});
