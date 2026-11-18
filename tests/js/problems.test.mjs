import {test} from 'node:test';
import assert from 'node:assert/strict';

import {scanProblem} from '../../static/js/problems.js';

test('a failed scan names who is not answering and what to do', () => {
  assert.match(scanProblem('Could not read the Letterboxd watchlist.').text, /Letterboxd is not responding/);
  assert.match(scanProblem('TMDB returned 401.').text, /does not accept the API key/);
  assert.equal(scanProblem('TMDB returned 401.').link, '/settings#tmdb');
  assert.match(scanProblem('TMDB request failed (ConnectionError).').text, /TMDB is not responding/);
  assert.match(scanProblem('No film could be checked: TMDB request failed.').text, /TMDB is not responding/);
  assert.equal(scanProblem('The scan failed unexpectedly.').link, '/settings/data');
  assert.equal(scanProblem(undefined).text, 'The scan failed.');
});
