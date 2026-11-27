// The scan: the panel and the sync dot in the header, start, poll, resume, cancel, the saved result and a country switch.
import {local} from './profile-storage.js';
import {ago, dateTime} from './ui.js';
import {scanProblem} from './problems.js';
import {scanResultText, updateScanFeedback} from './scans.js';
import {filmKey} from './filtering.js';
import {saveCountry} from './country-picker.js';

export function createScanFlow({state, scanState, results, filterBar, freeServices, rentalShops, mySubscriptions, greyKeys, populateGenres, renderFilms, showToast, loadFavorites, openPendingFilm, showTogether = () => false}) {
  const seen = new Set();
  // The dot in the header: nothing to see while the data is fresh; yellow when old, red after an error.
  function setSync(name, text) {
    document.getElementById('sync-toggle').dataset.state = name;
    document.getElementById('sync-label').textContent = text;
  }
  // One place decides the header's state from the age of the data; it runs again when the new scan has arrived.
  function updateSyncLabel(failed = false) {
    const age = state.lastScan ? Date.now() / 1000 - state.lastScan : Infinity;
    if (failed) setSync('error', 'Scan failed');
    else if (!state.lastScan) setSync('stale', 'Not synced yet');  // a new profile: no scan to date
    else if (age > 24 * 3600) setSync('stale', `Out of date · ${ago(state.lastScan)}`);
    else setSync('ok', state.lastScan ? `Synced ${ago(state.lastScan)}` : 'Synced');
  }
  // After a scan the button starts another one; "Retry" is only right after an error.
  function showScanButton(failed = false) {
    if (!failed) document.getElementById('state-banner').hidden = true;
    updateSyncLabel(failed);
    document.getElementById('cancel-scan').hidden = true;
    document.getElementById('cancel-scan').disabled = false;
    const button = document.getElementById('retry-scan');
    button.innerHTML = `<i class="ti ti-arrow-clockwise" aria-hidden="true"></i> ${failed ? 'Retry scan' : 'Scan now'}`;
    // A routine rescan stays quiet; only a failed scan asks for attention.
    button.classList.toggle('btn-accent', failed);
    button.classList.toggle('btn-outline-secondary', !failed);
    button.hidden = false;
    // No scan running: the panel shrinks to one line with the message and the button.
    document.getElementById('loading-panel').classList.add('idle');
    document.getElementById('grey-unavailable-label').hidden = true;
    document.getElementById('scan-line').hidden = true;
  }
  function showScanRunning() {
    setSync('running', 'Scanning…');
    document.getElementById('loading-panel').classList.remove('idle');
    document.getElementById('cancel-scan').hidden = false;
    document.getElementById('retry-scan').hidden = true;
    // Greying out only means something while a new scan checks the old films.
    document.getElementById('grey-unavailable-label').hidden = !scanState.rescanInProgress;
  }
  // A failed scan: a banner in plain words with the way out, and the old data stays on the page.
  function showStateBanner(message) {
    const problem = scanProblem(message);
    const old = state.lastScan ? ` Showing the data from ${dateTime(state.lastScan)}.` : '';
    document.getElementById('state-text').textContent = `${problem.text}${old} ${problem.action}`;
    const link = document.getElementById('state-link');
    link.hidden = !problem.link;
    if (problem.link) { link.href = problem.link; link.textContent = problem.link.includes('settings#') ? 'Open settings' : 'Details'; }
    document.getElementById('state-banner').hidden = false;
  }
  document.getElementById('state-retry').addEventListener('click', () => {
    document.getElementById('state-banner').hidden = true;
    startScan();
  });
  function showScanError(message, toastText) {
    showStateBanner(message);
    document.getElementById('error-message').textContent = message;
    document.getElementById('error-message').hidden = false;
    showScanButton(true);
    showToast(toastText, true);
  }
  // Saved results and no scan running: show the panel as finished.
  function showSavedPanel() {
    document.getElementById('status-message').textContent = state.lastScan ? `Saved results from ${dateTime(state.lastScan)}.` : 'Saved results.';
    document.getElementById('scan-phase').textContent = 'Saved';
    document.getElementById('current-title').textContent = '';
    document.getElementById('scan-live-stats').textContent = `${state.films.length} available · ${state.unavailable.length} unavailable`;
    document.getElementById('progress-bar').classList.remove('cancelled');
    setProgress(100);
    document.getElementById('progress-count').textContent = 'Complete';
    document.getElementById('error-message').hidden = true;
    showScanButton();
  }
  // The panel's bar, plus a slim line at the top of the page while a scan runs (the old films stay visible below it).
  function setProgress(percent, label = `${Math.round(percent)}%`) {
    const bar = document.getElementById('progress-bar');
    bar.style.width = `${percent}%`;
    bar.parentElement.setAttribute('aria-valuenow', String(percent));
    const running = document.getElementById('sync-toggle').dataset.state === 'running';
    if (running) setSync('running', label);
    document.getElementById('scan-line').hidden = !running;
    document.getElementById('scan-line').firstElementChild.style.width = `${percent}%`;
  }
  function showResultTools() {
    if (!state.films.length) return;
    document.getElementById('result-tools').hidden = false;
  }
  function appendUnavailable(films) {
    if (!films?.length) return;
    const changed = films.length !== state.unavailable.length;
    state.unavailable = films;
    if (changed) renderFilms();
  }
  function applyRescanUnavailableState() {
    const keys = greyKeys();
    document.querySelectorAll('#results .film').forEach(card => {
      card.classList.toggle('rescan-unavailable', keys.has(card.dataset.key));
    });
  }
  function appendFilms(films) {
    let added = false;
    films.forEach(film => {
      const key = filmKey(film);
      if (seen.has(key)) return;
      seen.add(key);
      state.films.push(film);
      added = true;
    });
    if (!added) return;
    populateGenres();
    renderFilms();
  }
  // The page does not reload on a country switch: relabel the services from the new country's scan.
  function showServiceLabels(free, rental) {
    [[freeServices, free], [rentalShops, rental]].forEach(([set, names]) => {
      set.clear();
      names.forEach(name => set.add(name));
    });
    filterBar.buildServicesMenu();
  }
  // Show a finished scan: films, unavailable films and the stored availability changes.
  function replaceWithScanResults(films, unavailable, changes, lastScan, free, rental) {
    if (free) showServiceLabels(free, rental || []);
    state.films = films || [];
    state.unavailable = unavailable || [];
    state.changes = changes || [];
    if (lastScan) {
      state.lastScan = lastScan;
      // The scan has just arrived: a header that still says "Out of date" would contradict the page.
      if (['ok', 'stale'].includes(document.getElementById('sync-toggle').dataset.state)) updateSyncLabel();
    }
    seen.clear();
    state.films.forEach(film => seen.add(filmKey(film)));
    if (!state.films.length && !state.unavailable.length) results.innerHTML = '';
    scanState.pendingUnavailable = [];
    if (showTogether()) return;  // /watchlist?together=: the merged list replaces yours
    populateGenres();
    renderFilms();
  }
  async function pollScan(jobId = scanState.currentJob) {
    if (jobId !== scanState.currentJob) return;
    let response, job;
    try {
      // Only the films found since the last answer; the page keeps the earlier ones.
      response = await fetch(`/api/scan/${jobId}?from=${scanState.resultsReceived}`);
      job = await response.json();
    } catch {
      // The server was not reachable for a moment (sleep, restart): keep asking, and say so if it lasts.
      scanState.pollFailures += 1;
      if (scanState.pollFailures >= 3) document.getElementById('status-message').textContent = 'Lost connection to the app, retrying…';
      setTimeout(() => pollScan(jobId), 2000);
      return;
    }
    scanState.pollFailures = 0;
    if (jobId !== scanState.currentJob) return;
    if (!response.ok) {
      const url = new URL(location.href);
      url.searchParams.delete('scan');
      history.replaceState({}, '', url);
      document.getElementById('error-message').textContent = 'The previous scan is no longer available. Starting a new scan.';
      document.getElementById('error-message').hidden = false;
      startScan();
      return;
    }
    const percent = job.total ? Math.round(job.completed / job.total * 100) : 3;
    updateScanFeedback(job);
    setProgress(percent, job.total ? `Scanning ${job.completed}/${job.total}` : 'Scanning…');
    document.getElementById('progress-count').textContent = job.total ? `${percent}% · ${job.completed}/${job.total}` : 'Loading';
    document.getElementById('status-message').textContent = job.message;
    document.getElementById('current-title').textContent = job.current_title || job.phase;
    if (scanState.rescanInProgress) {
      scanState.pendingUnavailable = job.unavailable || [];
      applyRescanUnavailableState();
    } else {
      if (job.results?.length) appendFilms(job.results);
      if (job.unavailable?.length) appendUnavailable(job.unavailable);
    }
    if (job.status === 'running') scanState.resultsReceived += (job.results || []).length;
    const pollSignature = `${job.status}|${job.completed}|${job.stats?.total || 0}|${job.unavailable?.length || 0}|${job.failed?.length || 0}`;
    scanState.pollDelay = pollSignature === scanState.lastPollSignature ? Math.min(scanState.pollDelay + 250, 2000) : 350;
    scanState.lastPollSignature = pollSignature;
    if (job.failed?.length) {
      document.getElementById('status-message').textContent =
        `${job.message} ${job.failed.length} lookup${job.failed.length === 1 ? '' : 's'} failed.`;
    }
    if (job.source_name) { document.getElementById('source-name').textContent = job.source_name; document.getElementById('result-meta').hidden = false; document.getElementById('film-filters').hidden = false; }
    if (state.films.length) showResultTools();
    if (job.status === 'complete' || job.status === 'cancelled') { if (job.status === 'complete') setProgress(100); else document.getElementById('progress-bar').classList.add('cancelled'); document.getElementById('progress-count').textContent = job.status === 'complete' ? 'Complete' : 'Cancelled'; showScanButton();       if (job.status === 'complete') {
      scanState.rescanInProgress = false;
      replaceWithScanResults(job.results, job.unavailable, job.changes, job.last_updated, job.free_services, job.rental_shops);
    }
    // The server moves favorites saved under "Title|Year" to the TMDB id after a scan.
    if (job.status === 'complete') loadFavorites().then(renderFilms).then(() => openPendingFilm(true));
    scanState.rescanInProgress = false; scanState.pendingUnavailable = []; applyRescanUnavailableState(); showToast(job.status === 'complete' ? scanResultText(job, mySubscriptions()) : 'Scan cancelled. Previous results kept.'); return; }
    // The app was restarted during the scan: it has started a new one, join it.
    if (job.status === 'interrupted') { startScan(); return; }
    if (job.status === 'error') { scanState.rescanInProgress = false; scanState.pendingUnavailable = []; applyRescanUnavailableState(); showScanError(job.message, 'Scan failed. The reason is shown above the films.'); return; }
    setTimeout(() => pollScan(jobId), scanState.pollDelay);
  }
  // quiet: the page started it by itself because the data is old, so no toast over the films.
  async function startScan(quiet = false) {
    scanState.rescanInProgress = state.films.length > 0;
    scanState.pendingUnavailable = [];
    if (!scanState.rescanInProgress) {
      state.films = [];
      seen.clear();
      results.setAttribute('aria-busy', 'true');
      results.innerHTML = '<div class="skeleton-grid" role="status" aria-label="Loading films"><div class="skeleton-card"><div class="skeleton-poster"></div><div class="skeleton-line"></div><div class="skeleton-line is-short"></div><div class="skeleton-logos"></div></div><div class="skeleton-card"><div class="skeleton-poster"></div><div class="skeleton-line"></div><div class="skeleton-line is-short"></div><div class="skeleton-logos"></div></div><div class="skeleton-card"><div class="skeleton-poster"></div><div class="skeleton-line"></div><div class="skeleton-line is-short"></div><div class="skeleton-logos"></div></div></div>';
    }
    if (!quiet) showToast(scanState.rescanInProgress ? 'Updating availability. Previous results remain visible.' : 'Starting watchlist scan...');
    showScanRunning(); document.getElementById('error-message').hidden = true;
    document.getElementById('progress-bar').classList.remove('cancelled');
    state.unavailable = [];
    if (!scanState.rescanInProgress) document.getElementById('unavailable-panel').hidden = true;
    const upload = document.getElementById('csv-upload').files[0];
    const country = document.getElementById('country-select').value;
    const body = new FormData();
    body.append('country', country);
    if (upload) body.append('watchlist', upload);
    let response, data;
    try {
      response = await fetch('/api/scan', {method: 'POST', body});
      data = await response.json();
    } catch {
      data = {};
    }
    // Another country was picked meanwhile: its own scan follows, this answer is old.
    if (country !== document.getElementById('country-select').value) return;
    if (!response?.ok || !data.job_id) {
      scanState.rescanInProgress = false;
      showScanError(data.error || 'Could not reach the app. Check that it is running, then try again.', 'Scan could not be started.');
      return;
    }
    scanState.currentJob = data.job_id;
    scanState.resultsReceived = 0;
    scanState.pollDelay = 350;
    scanState.pollFailures = 0;
    scanState.lastPollSignature = '';
    const url = new URL(location.href);
    url.searchParams.set('scan', scanState.currentJob);
    history.replaceState({}, '', url);
    pollScan();
  }
  async function loadLatestResult(request = null) {
    const country = document.getElementById('country-select').value;
    const response = await (request || fetch(`/api/latest?country=${encodeURIComponent(country)}`));
    if (!response.ok) return null;
    const snapshot = await response.json();
    // A newer country switch has started: this answer belongs to the old country.
    if (country !== document.getElementById('country-select').value) return null;
    if (snapshot.subscriptions) window.WATCHLIST_CONFIG.subscriptions = {...window.WATCHLIST_CONFIG.subscriptions, [country]: snapshot.subscriptions};
    // The service worker answers from its copy when the app cannot be reached: say how old the data is.
    if (response.headers.get('X-From-Cache') && snapshot.created) showToast(`Offline: showing the data from ${new Date(snapshot.created * 1000).toLocaleString('en-GB', {dateStyle: 'medium', timeStyle: 'short'})}.`);
    if (!snapshot.available) return snapshot;
    replaceWithScanResults(snapshot.results, snapshot.unavailable, snapshot.changes, snapshot.created, snapshot.free_services, snapshot.rental_shops);
    document.getElementById('source-name').textContent = snapshot.source_name || '';
    document.getElementById('result-meta').hidden = false;
    document.getElementById('film-filters').hidden = false;
    showResultTools();
    return snapshot;
  }
  // A country switch saves the country, shows its saved scan at once and always starts a scan
  // (the server reuses a scan of the same list from today, so that is quick).
  // Resolves once the country is saved, so the picker takes the next choice only then.
  async function switchCountry(code) {
    const select = document.getElementById('country-select');
    let saved;
    try {
      saved = await saveCountry(code);
    } catch (error) {
      showToast(error.message, true);
      return false;
    }
    // The new country and its services together: a render in between would see a country without services.
    window.WATCHLIST_CONFIG.subscriptions = {...window.WATCHLIST_CONFIG.subscriptions, [code]: saved.subscriptions || []};
    select.value = code;
    // The page writes the ticked services into the address on every render, so providers= is no sign of a
    // shared link here: a new country always starts with its own services.
    state.selected = mySubscriptions();
    filterBar.buildServicesMenu();
    scanState.currentJob = undefined;
    scanState.rescanInProgress = false;
    const url = new URL(location.href);
    url.searchParams.delete('scan');
    history.replaceState({}, '', url);
    loadLatestResult().catch(() => null).then(snapshot => {
      if (code !== select.value) return;
      // No scan for this country yet: the other country's films must not stay under its name.
      if (!snapshot?.available) { state.lastScan = null; replaceWithScanResults([], [], [], null); }
      startScan();
    });
    return true;
  }
  function resumeScan(jobId) {
    scanState.currentJob = jobId;
    scanState.resultsReceived = 0;
    showScanRunning();
    showToast('Reconnecting to the scan...');
    pollScan();
  }
  document.getElementById('cancel-scan').addEventListener('click', async event => {
    if (!scanState.currentJob || event.currentTarget.disabled) return;
    event.currentTarget.disabled = true;
    try {
      const response = await fetch(`/api/scan/${scanState.currentJob}/cancel`, {method: 'POST'});
      if (!response.ok) {
        event.currentTarget.disabled = false;
        showToast('The scan could not be cancelled. It may have just finished; reload the page.', true);
      }
    } catch {
      event.currentTarget.disabled = false;
      showToast('The scan could not be cancelled. It may have just finished; reload the page.', true);
    }
  });
  document.getElementById('retry-scan').addEventListener('click', startScan);
  // A button of our own instead of the browser's file field (whose text follows the browser's language and gets cut).
  document.getElementById('csv-upload').addEventListener('change', event => {
    document.getElementById('csv-name').textContent = event.target.files[0]?.name || 'No file chosen';
  });
  document.getElementById('grey-unavailable').checked = local.getItem('greyUnavailableDuringRescan') === 'true';
  document.getElementById('grey-unavailable').addEventListener('change', event => {
    local.setItem('greyUnavailableDuringRescan', String(event.target.checked));
    applyRescanUnavailableState();
  });
  return {startScan, resumeScan, loadLatestResult, switchCountry, showSavedPanel, updateSyncLabel};
}
