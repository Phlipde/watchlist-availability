import {test} from 'node:test';
import assert from 'node:assert/strict';

import {scanResultText} from '../../static/js/scans.js';

test('the scan toast counts films new on your services since the scan started', () => {
  const job = {
    started_at: 100,
    changes: [
      {film_key: '1', provider: 'Netflix', change: 'added', created: 150},
      {film_key: '1', provider: 'Netflix Standard with Ads', change: 'added', created: 150},  // same film, same service
      {film_key: '2', provider: 'RTL+ Max Amazon Channel', change: 'added', created: 160},  // a channel of your RTL+
      {film_key: '3', provider: 'MUBI', change: 'added', created: 160},  // not yours
      {film_key: '4', provider: 'Netflix', change: 'removed', created: 160},
      {film_key: '5', provider: 'Netflix', change: 'added', created: 50},  // an earlier scan
    ],
  };
  assert.equal(scanResultText(job, new Set(['Netflix', 'RTL+'])), 'Scan complete: 2 new on your services.');
  assert.equal(scanResultText({...job, started_at: undefined}, new Set(['Netflix'])), 'Watchlist scan complete.');
});
