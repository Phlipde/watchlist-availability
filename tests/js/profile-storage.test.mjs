import test from 'node:test';
import assert from 'node:assert/strict';

import {profileKey, storageFor} from '../../static/js/profile-storage.js';

const fakeStorage = (entries = {}) => {
  const map = new Map(Object.entries(entries));
  return {
    map,
    getItem: key => (map.has(key) ? map.get(key) : null),
    setItem: (key, value) => map.set(key, String(value)),
    removeItem: key => map.delete(key),
  };
};

test('a key carries the profile id', () => {
  assert.equal(profileKey('savedViews', 2), 'p2:savedViews');
  assert.equal(profileKey('viewMode'), 'p1:viewMode');  // no page body: profile 1
});

test('each profile reads and writes its own value', () => {
  const storage = fakeStorage();
  storageFor(storage, 2).setItem('viewMode', 'table');
  assert.equal(storageFor(storage, 2).getItem('viewMode'), 'table');
  assert.equal(storageFor(storage, 1).getItem('viewMode'), null);
  storageFor(storage, 2).removeItem('viewMode');
  assert.deepEqual([...storage.map.keys()], []);
});

test('profile 1 takes over a value saved before profiles had keys, once', () => {
  const storage = fakeStorage({savedViews: '[{"name":"Old"}]'});
  assert.equal(storageFor(storage, 2).getItem('savedViews'), null);  // another profile does not take it
  assert.equal(storageFor(storage, 1).getItem('savedViews'), '[{"name":"Old"}]');
  assert.deepEqual(Object.fromEntries(storage.map), {'p1:savedViews': '[{"name":"Old"}]'});
  storage.setItem('savedViews', 'stale');  // a prefixed value wins over a later unprefixed one
  assert.equal(storageFor(storage, 1).getItem('savedViews'), '[{"name":"Old"}]');
});
