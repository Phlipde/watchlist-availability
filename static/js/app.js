import {dateTime, escapeHtml, numberText} from './ui.js';
import {createAppState, createScanState} from './state.js';
import {availabilityByOffer, changeSummary, compareButtonState, favoriteFields, renderResults} from './rendering.js';
import {activeFilters, clearFilter, readFilters, resetFilters, selectedProviders, updateProviderCount, updateProviderFilmCounts} from './filters.js';
import {eveningSuggestions, filmKey, filterFilms, recentlyRemoved} from './filtering.js';
import {updateScanFeedback} from './scans.js';
import {favoriteLabel} from './favorites.js';

const imageBaseUrl = window.WATCHLIST_CONFIG.imageBaseUrl;
const scanState = createScanState();
const state = createAppState();
    const providerInputs = document.querySelectorAll('#provider-filters input[type="checkbox"]');
    const rentalShops = new Set(window.WATCHLIST_CONFIG.rentalShops || []);
    const freeServices = new Set(window.WATCHLIST_CONFIG.freeServices || []);
    // The services saved in Settings for the country shown in the header.
    const mySubscriptions = () => new Set(window.WATCHLIST_CONFIG.subscriptions?.[document.getElementById('country-select').value] || []);
    const results = document.getElementById('results');
    const seen = new Set();
    const toastElement = document.getElementById('app-toast');
    const toast = window.bootstrap ? bootstrap.Toast.getOrCreateInstance(toastElement, {autohide: false}) : {show() {}, hide() {}};
    let toastTimer;
    let toastUndo = null;
    // An error must not look like routine feedback: red border, announced at once, shown longer.
    // With `undo` the toast offers "Undo" for about five seconds.
    function showToast(message, error = false, undo = null) {
      document.getElementById('toast-message').textContent = message;
      toastElement.classList.toggle('toast-error', error);
      toastElement.setAttribute('role', error ? 'alert' : 'status');
      toastUndo = undo;
      document.getElementById('toast-undo').hidden = !undo;
      clearTimeout(toastTimer);
      toast.show();
      toastTimer = setTimeout(() => { toastUndo = null; toast.hide(); }, error ? 6000 : undo ? 5000 : 2400);
    }
    document.getElementById('toast-undo').addEventListener('click', () => {
      const undo = toastUndo;
      toastUndo = null;
      toast.hide();
      undo?.();
    });
    const watchedKeys = () => new Set([...state.favorites.values()].filter(film => film.status === 'watched').map(film => film.key));
    // After a scan the button starts another one; "Retry" is only right after an error.
    function showScanButton(failed = false) {
      document.getElementById('cancel-scan').hidden = true;
      document.getElementById('cancel-scan').disabled = false;
      const button = document.getElementById('retry-scan');
      button.innerHTML = `<i class="ti ti-arrow-clockwise" aria-hidden="true"></i> ${failed ? 'Retry scan' : 'Scan now'}`;
      button.hidden = false;
      // No scan running: the panel shrinks to one line with the message and the button.
      document.getElementById('loading-panel').classList.add('idle');
      document.getElementById('grey-unavailable-label').hidden = true;
    }
    function showScanRunning() {
      document.getElementById('loading-panel').classList.remove('idle');
      document.getElementById('cancel-scan').hidden = false;
      document.getElementById('retry-scan').hidden = true;
      // Greying out only means something while a new scan checks the old films.
      document.getElementById('grey-unavailable-label').hidden = !scanState.rescanInProgress;
    }
    function showScanError(message, toastText) {
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
    function setProgress(percent) {
      const bar = document.getElementById('progress-bar');
      bar.style.width = `${percent}%`;
      bar.parentElement.setAttribute('aria-valuenow', String(percent));
    }
    // Bootstrap does not give the focus back after a dialog: return it to the control that opened it.
    // A redrawn card has a new button, so look it up again by the film key.
    const modalOpeners = new Map();
    function openModal(id, opener = document.activeElement) {
      modalOpeners.set(id, opener);
      bootstrap.Modal.getOrCreateInstance(document.getElementById(id)).show();
    }
    ['film-details-modal', 'trailer-modal', 'compare-modal', 'evening-modal'].forEach(id => {
      document.getElementById(id).addEventListener('hidden.bs.modal', () => {
        const opener = modalOpeners.get(id);
        modalOpeners.delete(id);
        if (!opener || opener === document.body) return;
        const key = opener.dataset?.key;
        const target = opener.isConnected ? opener : key && document.querySelector(`#results .film-details-button[data-key="${CSS.escape(key)}"]`);
        target?.focus();
      });
    });
    function showResultTools() {
      if (!state.films.length) return;
      document.getElementById('stats-section').hidden = false;
      document.getElementById('result-tools').hidden = false;
    }

    function greyKeys() {
      if (!scanState.rescanInProgress || !document.getElementById('grey-unavailable').checked) return new Set();
      return new Set(scanState.pendingUnavailable.map(filmKey));
    }
    // Filter the state, then draw the cards from the result. Filters never read card attributes.
    function renderFilms() {
      if (!state.films.length && !state.unavailable.length) return;
      const selected = selectedProviders(providerInputs);
      const filters = readFilters(document, state.favoritesOnly);
      const view = filterFilms(state.films, state.unavailable, filters, {selected, favorites: state.favorites, subscriptions: mySubscriptions()});
      state.view = view;
      renderResults(view, {results, unavailableResults: document.getElementById('unavailable-results')}, {
        imageBaseUrl,
        selected,
        favorites: state.favorites,
        compareKeys: state.compareKeys,
        greyKeys: greyKeys(),
        favoritesOnly: state.favoritesOnly,
      });
      document.getElementById('unavailable-panel').hidden = view.unavailable.length === 0;
      document.getElementById('unavailable-badge').textContent = view.unavailable.length;
      document.getElementById('visible-count').textContent = view.visibleCount;
      document.getElementById('provider-done-count').textContent = view.visibleCount;
      results.setAttribute('aria-busy', 'false');
      document.getElementById('scan-summary-content').innerHTML = changeSummary(state.changes, selected, state.lastScan);
      renderRecentlyRemoved();
      document.getElementById('scan-summary').hidden = !state.lastScan;
      document.getElementById('favorite-status-filter').hidden = !state.favoritesOnly;
      document.getElementById('favorites-empty')?.toggleAttribute('hidden', !(state.favoritesOnly && view.visibleCount === 0 && view.unavailable.length === 0));
      document.getElementById('favorites-banner').hidden = !state.favoritesOnly;
      // "Why is my film missing?": say so and offer the way out instead of an empty page.
      const nothing = view.visibleCount === 0 && (view.unavailable.length === 0 || (selected.size === 0 && filters.availability !== 'unavailable'));
      document.getElementById('filters-empty').hidden = state.favoritesOnly || !nothing;
      document.getElementById('empty-subscriptions').hidden = selected.size > 0;
      syncUrl();
      updateFilterChips();
    }
    function reorderProviders() {
      const query = document.getElementById('provider-search').value.toLowerCase().trim();
      const sortMode = document.getElementById('provider-sort').value;
      updateProviderCount(providerInputs, document.getElementById('provider-count'));
      document.querySelectorAll('.provider-list').forEach(list => {
        [...list.querySelectorAll('label')]
          .sort((a, b) => {
            const countDifference = Number(b.querySelector('.provider-film-count')?.textContent || 0) - Number(a.querySelector('.provider-film-count')?.textContent || 0);
            const selectedDifference = Number(b.querySelector('input').checked) - Number(a.querySelector('input').checked);
            if (sortMode === 'count') return countDifference || a.textContent.localeCompare(b.textContent);
            if (sortMode === 'selected') return selectedDifference || countDifference || a.textContent.localeCompare(b.textContent);
            return a.textContent.localeCompare(b.textContent);
          })
          .forEach(label => {
            const matches = label.dataset.providerAvailable !== 'false' && (!query || label.textContent.toLowerCase().includes(query));
            label.hidden = !matches;
            list.appendChild(label);
          });
      });
    }
    // Films that just left one of the user's services, from the stored changes of the last 14 days.
    function renderRecentlyRemoved() {
      const removed = recentlyRemoved(state.changes, mySubscriptions());
      const known = new Set([...state.films, ...state.unavailable].map(filmKey));
      document.getElementById('recently-removed').hidden = removed.length === 0;
      document.getElementById('recently-removed-count').textContent = removed.length;
      document.getElementById('recently-removed-list').innerHTML = removed.map(item => {
        const title = escapeHtml(item.title) + (item.year ? ` (${numberText(item.year)})` : '');
        const name = known.has(item.film_key) ? `<button class="film-link removed-pick" type="button" data-key="${escapeHtml(item.film_key)}">${title}</button>` : title;
        return `<li>${name} · no longer on ${escapeHtml(item.providers.join(', '))} · ${new Date(item.created * 1000).toLocaleDateString([], {dateStyle: 'medium'})}</li>`;
      }).join('');
    }
    function updateFilterChips() {
      const chips = activeFilters(document).map(({id, label, text}) => {
        const name = text ? `${label}: ${escapeHtml(text)}` : label;
        return `<button class="filter-chip" type="button" data-filter-id="${id}" aria-label="Remove filter ${name}">${name} <i class="ti ti-x" aria-hidden="true"></i></button>`;
      });
      if (chips.length) chips.push('<button class="filter-chip filter-reset" type="button" data-reset-filters>Reset filters</button>');
      document.getElementById('filter-chips').innerHTML = chips.join('');
      // A set filter behind "More filters" must not be forgotten: count it on the summary.
      const hidden = activeFilters(document).filter(({id}) => document.getElementById(id).closest('#more-filters')).length;
      document.getElementById('more-filters-count').textContent = hidden ? `(${hidden} active)` : '';
    }
    function resetAllFilters() {
      resetFilters(document);
      renderFilms();
    }
    function fillSelect(select, allText, values) {
      // A value from a link waits in data-pending until a scan brings films that have it.
      const wanted = select.dataset.pending || select.value;
      select.innerHTML = `<option value="all">${allText}</option>` + values.map(value => `<option value="${escapeHtml(value)}">${escapeHtml(value)}</option>`).join('');
      select.value = values.includes(wanted) ? wanted : 'all';
      if (select.value === wanted) delete select.dataset.pending;
    }
    function populateGenres() {
      fillSelect(document.getElementById('genre-filter'), 'All genres', [...new Set(state.films.flatMap(film => film.genres || []))].sort());
      fillSelect(document.getElementById('keyword-filter'), 'All keywords', [...new Set(state.films.flatMap(film => film.keywords || []))].sort());
    }
    function updateAnalysis() {
      const counts = {};
      state.films.forEach(film => (film.genres || []).forEach(genre => { counts[genre] = (counts[genre] || 0) + 1; }));
      const top = Object.entries(counts).sort((a, b) => b[1] - a[1])[0];
      const ratings = state.films.filter(film => film.rating).map(film => film.rating);
      const runtimes = state.films.filter(film => film.runtime).map(film => film.runtime);
    const decades = state.films.filter(film => film.release_date).map(film => new Date(film.release_date).getFullYear());
      document.getElementById('top-genre').textContent = top ? `${top[0]} (${top[1]})` : '-';
      document.getElementById('average-rating').textContent = ratings.length ? (ratings.reduce((a, b) => a + b, 0) / ratings.length).toFixed(1) : '-';
      document.getElementById('average-runtime').textContent = runtimes.length ? `${Math.round(runtimes.reduce((a, b) => a + b, 0) / runtimes.length)} min` : '-';
      document.getElementById('analysis-panel').hidden = !state.films.length;
      document.getElementById('decades').textContent = decades.length ? `${Math.min(...decades)}-${Math.max(...decades)}` : '-';
    }
    function showRandomFilm() {
      const visible = state.view ? [...new Map(Object.values(state.view.sections).flat().map(film => [filmKey(film), film])).values()] : [];
      if (!visible.length) return showToast('No film matches the current filters.');
      const watched = watchedKeys();
      const unseen = visible.filter(film => !watched.has(filmKey(film)));
      if (!unseen.length) return showToast('You have watched every film that matches the filters.');
      const film = unseen[Math.floor(Math.random() * unseen.length)];
      showFilmDetails(filmKey(film));
    }
    function showEveningSuggestions() {
      const genre = document.getElementById('evening-genre');
      genre.innerHTML = '<option value="all">Any genre</option>' + [...new Set(state.films.flatMap(film => film.genres || []))]
        .sort().map(value => `<option value="${escapeHtml(value)}">${escapeHtml(value)}</option>`).join('');
      // The last evening's choice is the likely one again.
      const savedGenre = localStorage.getItem('eveningGenre');
      if ([...genre.options].some(option => option.value === savedGenre)) genre.value = savedGenre;
      document.getElementById('evening-runtime').value = localStorage.getItem('eveningRuntime') || '150';
      openModal('evening-modal');
    }
    function renderEveningSuggestions() {
      const maximum = Number(document.getElementById('evening-runtime').value);
      const genre = document.getElementById('evening-genre').value;
      localStorage.setItem('eveningRuntime', String(maximum || ''));
      localStorage.setItem('eveningGenre', genre);
      const subscriptions = mySubscriptions();
      const suggestions = eveningSuggestions(state.films, {maximum, genre, subscriptions, skip: watchedKeys()});
      const onServices = film => Object.entries(film.providers || {})
        .filter(([provider, kinds]) => subscriptions.has(provider) && kinds.some(kind => ['free', 'ads', 'flatrate'].includes(kind)))
        .map(([provider]) => provider).sort().join(', ');
      document.getElementById('evening-results').innerHTML = suggestions.length
        ? `<ol class="evening-suggestions">${suggestions.map(film => `<li><button class="film-link evening-pick" type="button" data-key="${escapeHtml(filmKey(film))}">${escapeHtml(film.title)}</button> · ${numberText(film.runtime, '?')} min · TMDB ${numberText(film.rating) ? Number(film.rating).toFixed(1) : '?'}/10 · on ${escapeHtml(onServices(film))}</li>`).join('')}</ol>`
        : '<p class="empty">No matching films on your subscriptions.</p>';
    }
    document.getElementById('evening-results').addEventListener('click', event => {
      const pick = event.target.closest('.evening-pick');
      if (!pick) return;
      // One dialog at a time: the details replace the evening mode, the focus later goes back to its button.
      const opener = modalOpeners.get('evening-modal');
      modalOpeners.delete('evening-modal');
      bootstrap.Modal.getInstance(document.getElementById('evening-modal'))?.hide();
      showFilmDetails(pick.dataset.key, opener);
    });
    function compareFilms() {
      const films = state.films.filter(film => state.compareKeys.has(filmKey(film)));
      if (films.length < 2 || films.length > 4) return showToast('Select 2 to 4 films to compare.');
      const providers = [...new Set(films.flatMap(film => Object.keys(film.providers || {})))].sort();
      const offerCell = film => Object.entries(film.providers || {}).map(([provider, kinds]) => `${escapeHtml(provider)}: ${escapeHtml(kinds.join(', '))}`).join('<br>') || '-';
      const providerRows = providers.map(provider => `<tr><th>${escapeHtml(provider)}</th>${films.map(film => `<td>${escapeHtml((film.providers?.[provider] || []).join(', ') || '—')}</td>`).join('')}</tr>`).join('');
      document.getElementById('compare-table').innerHTML = `<thead><tr><th>Metric</th>${films.map(film => `<th>${escapeHtml(film.title)}</th>`).join('')}</tr></thead><tbody><tr><th>Year</th>${films.map(film => `<td>${numberText(film.year, '-')}</td>`).join('')}</tr><tr><th>Rating</th>${films.map(film => `<td>${numberText(film.rating, '-')}</td>`).join('')}</tr><tr><th>Runtime</th>${films.map(film => `<td>${numberText(film.runtime) ? `${numberText(film.runtime)} min` : '-'}</td>`).join('')}</tr><tr><th>Genres</th>${films.map(film => `<td>${escapeHtml((film.genres || []).join(', ') || '-')}</td>`).join('')}</tr><tr><th>Offers</th>${films.map(film => `<td>${offerCell(film)}</td>`).join('')}</tr>${providerRows}</tbody>`;
      openModal('compare-modal');
    }
    function updateCompareButton() {
      const {text, disabled} = compareButtonState(state.compareKeys.size);
      const button = document.getElementById('compare-films');
      button.innerHTML = `<i class="ti ti-columns-gap" aria-hidden="true"></i> ${text}`;
      button.disabled = disabled;
    }
    function setCompared(key, checked) {
      if (checked) state.compareKeys.add(key);
      else state.compareKeys.delete(key);
      document.querySelectorAll(`.film[data-key="${CSS.escape(key)}"] .comparison-check`).forEach(check => { check.checked = checked; });
      updateCompareButton();
    }
    document.getElementById('clear-compare').addEventListener('click', () => {
      [...state.compareKeys].forEach(key => setCompared(key, false));
      bootstrap.Modal.getInstance(document.getElementById('compare-modal'))?.hide();
    });
    function updateStats() {
      const selected = new Set([...providerInputs].filter(input => input.checked).map(input => input.value));
      updateProviderFilmCounts(state.films, document.querySelectorAll('.provider-film-count[data-provider-count]'));
      reorderProviders();
      const scope = document.getElementById('stats-scope').value;
      const scopedFilms = scope === 'selected'
        ? state.films.filter(film => Object.keys(film.providers).some(provider => selected.has(provider)))
        : state.films;
      const providers = {};
      scopedFilms.forEach(film => Object.keys(film.providers).forEach(provider => {
        if (scope === 'all' || selected.has(provider)) providers[provider] = (providers[provider] || 0) + 1;
      }));
      const top = Object.entries(providers).sort((a, b) => b[1] - a[1])[0];
      const scopedProviderCount = film => Object.keys(film.providers).filter(provider => scope === 'all' || selected.has(provider)).length;
      document.getElementById('total-count').textContent = scopedFilms.length;
      document.getElementById('free-count').textContent = scopedFilms.filter(film => Object.entries(film.providers).some(([provider, kinds]) => (scope === 'all' || selected.has(provider)) && kinds.some(kind => ['free', 'ads'].includes(kind)))).length;
      document.getElementById('paid-count').textContent = scopedFilms.filter(film => Object.entries(film.providers).some(([provider, kinds]) => (scope === 'all' || selected.has(provider)) && kinds.some(kind => ['flatrate', 'rent'].includes(kind)))).length;
      const hasKind = (film, kinds) => Object.entries(film.providers).some(([provider, offered]) => (scope === 'all' || selected.has(provider)) && offered.some(kind => kinds.includes(kind)));
      document.getElementById('both-count').textContent = scopedFilms.filter(film => hasKind(film, ['free', 'ads']) && hasKind(film, ['flatrate', 'rent'])).length;
      document.getElementById('unavailable-count').textContent = state.unavailable.length;
      document.getElementById('coverage-percent').textContent = `${state.films.length ? Math.round(scopedFilms.length / state.films.length * 100) : 0}%`;
      document.getElementById('average-providers').textContent = scopedFilms.length ? (scopedFilms.reduce((total, film) => total + scopedProviderCount(film), 0) / scopedFilms.length).toFixed(1) : '0';
      document.getElementById('top-provider').textContent = top ? `${top[0]} (${top[1]})` : '-';
      const coverage = document.getElementById('coverage');
      const max = scopedFilms.length || 1;
      coverage.innerHTML = Object.entries(providers).sort((a, b) => b[1] - a[1]).slice(0, 8).map(([provider, count]) => `<div class="coverage-row"><span>${escapeHtml(provider)}</span><div class="progress"><div class="progress-bar" style="width:${Math.round(count / max * 100)}%"></div></div><strong>${count}</strong></div>`).join('');
      coverage.hidden = !state.films.length;
    }
    function appendUnavailable(films) {
      if (!films?.length) return;
      const changed = films.length !== state.unavailable.length;
      state.unavailable = films;
      updateStats();
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
      updateStats();
      populateGenres();
      updateAnalysis();
      renderFilms();
    }
    // The page does not reload on a country switch: relabel the services from the new country's scan.
    function showFreeServices(names) {
      freeServices.clear();
      names.forEach(name => freeServices.add(name));
      document.querySelectorAll('[data-provider-label]').forEach(label => {
        const isFree = freeServices.has(label.dataset.providerLabel);
        const tag = label.querySelector('.free-tag');
        if (isFree && !tag) label.querySelector('.provider-name').insertAdjacentHTML('afterend', '<span class="free-tag pill pill-ok">Mostly free</span>');
        if (!isFree) tag?.remove();
      });
    }
    // Show a finished scan: films, unavailable films and the stored availability changes.
    function replaceWithScanResults(films, unavailable, changes, lastScan, free) {
      if (free) showFreeServices(free);
      state.films = films || [];
      state.unavailable = unavailable || [];
      state.changes = changes || [];
      if (lastScan) state.lastScan = lastScan;
      seen.clear();
      state.films.forEach(film => seen.add(filmKey(film)));
      if (!state.films.length && !state.unavailable.length) results.innerHTML = '';
      scanState.pendingUnavailable = [];
      updateStats();
      populateGenres();
      updateAnalysis();
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
      setProgress(percent);
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
      if (job.stats) {
        document.getElementById('total-count').textContent = job.stats.total;
        document.getElementById('free-count').textContent = job.stats.free;
        document.getElementById('paid-count').textContent = job.stats.paid;
        document.getElementById('top-provider').textContent = job.stats.top_provider === '-' ? '-' : `${job.stats.top_provider} (${job.stats.top_provider_count})`;
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
      if (job.last_updated) document.getElementById('last-updated').textContent = `Last updated ${dateTime(job.last_updated)}`;
      if (state.films.length) { showResultTools(); updateStats(); }
      if (job.status === 'complete' || job.status === 'cancelled') { if (job.status === 'complete') setProgress(100); else document.getElementById('progress-bar').classList.add('cancelled'); document.getElementById('progress-count').textContent = job.status === 'complete' ? 'Complete' : 'Cancelled'; showScanButton();       if (job.status === 'complete') {
        scanState.rescanInProgress = false;
        replaceWithScanResults(job.results, job.unavailable, job.changes, job.last_updated, job.free_services);
      }
      // The server moves favorites saved under "Title|Year" to the TMDB id after a scan.
      if (job.status === 'complete') loadFavorites().then(renderFilms);
      scanState.rescanInProgress = false; scanState.pendingUnavailable = []; applyRescanUnavailableState(); showToast(job.status === 'complete' ? 'Watchlist scan complete.' : 'Scan cancelled. Previous results kept.'); return; }
      // The app was restarted during the scan: it has started a new one, join it.
      if (job.status === 'interrupted') { startScan(); return; }
      if (job.status === 'error') { scanState.rescanInProgress = false; scanState.pendingUnavailable = []; applyRescanUnavailableState(); showScanError(job.message, 'Scan failed. The reason is shown above the films.'); return; }
      setTimeout(() => pollScan(jobId), scanState.pollDelay);
    }
    async function startScan() {
      scanState.rescanInProgress = state.films.length > 0;
      scanState.pendingUnavailable = [];
      if (!scanState.rescanInProgress) {
        state.films = [];
        seen.clear();
        results.setAttribute('aria-busy', 'true');
        results.innerHTML = '<div class="skeleton-grid" role="status" aria-label="Loading films"><div class="skeleton-card"><div class="skeleton-poster"></div><div class="skeleton-line"></div></div><div class="skeleton-card"><div class="skeleton-poster"></div><div class="skeleton-line"></div></div><div class="skeleton-card"><div class="skeleton-poster"></div><div class="skeleton-line"></div></div></div>';
      }
      showToast(scanState.rescanInProgress ? 'Updating availability. Previous results remain visible.' : 'Starting watchlist scan...');
      showScanRunning(); document.getElementById('error-message').hidden = true;
      document.getElementById('progress-bar').classList.remove('cancelled');
      state.unavailable = [];
      if (!scanState.rescanInProgress) document.getElementById('unavailable-panel').hidden = true;
      const upload = document.getElementById('csv-upload').files[0];
      const body = new FormData();
      body.append('country', document.getElementById('country-select').value);
      if (upload) body.append('watchlist', upload);
      let response, data;
      try {
        response = await fetch('/api/scan', {method: 'POST', body});
        data = await response.json();
      } catch {
        data = {};
      }
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
    async function loadLatestResult() {
      const country = document.getElementById('country-select').value;
      const response = await fetch(`/api/latest?country=${encodeURIComponent(country)}`);
      if (!response.ok) return null;
      const snapshot = await response.json();
      if (!snapshot.available) return snapshot;
      replaceWithScanResults(snapshot.results, snapshot.unavailable, snapshot.changes, snapshot.created, snapshot.free_services);
      document.getElementById('source-name').textContent = snapshot.source_name || '';
      document.getElementById('result-meta').hidden = false;
      document.getElementById('film-filters').hidden = false;
      showResultTools();
      if (snapshot.created) {
        document.getElementById('last-updated').textContent =
          `Last updated ${dateTime(snapshot.created)}`;
      }
      return snapshot;
    }
    // A country switch shows that country's saved scan; it only scans when there is none or it is old.
    async function switchCountry() {
      scanState.currentJob = undefined;
      scanState.rescanInProgress = false;
      const url = new URL(location.href);
      url.searchParams.delete('scan');
      history.replaceState({}, '', url);
      const snapshot = await loadLatestResult().catch(() => null);
      if (snapshot?.available && !snapshot.stale) { showSavedPanel(); return; }
      // No scan for this country yet: the other country's films must not stay under its name.
      if (!snapshot?.available) { state.lastScan = null; replaceWithScanResults([], [], [], null); }
      startScan();
    }
    function resumeScan(jobId) {
      scanState.currentJob = jobId;
      scanState.resultsReceived = 0;
      showScanRunning();
      showToast('Reconnecting to the scan...');
      pollScan();
    }
    async function loadFavorites() {
      const response = await fetch('/api/favorites');
      const favorites = await response.json();
      state.favorites = new Map(favorites.map(movie => [movie.key, movie]));
    }
    async function toggleFavorite(button) {
      const card = button.closest('.film');
      const key = card?.dataset.key || button.dataset.key;
      if (!key || button.disabled) return;
      const previous = state.favorites.get(key);
      const film = state.films.find(movie => filmKey(movie) === key);
      if (!previous && !film) return;
      // Disabling the button below takes the focus away, so remember it first.
      const hadFocus = document.activeElement === button && results.contains(button);
      button.disabled = true;
      let response;
      try {
        response = previous
          ? await fetch(`/api/favorites/${encodeURIComponent(key)}`, {method: 'DELETE'})
          : await fetch('/api/favorites', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({key, ...film})});
      } catch {
        response = null;
      }
      if (!response?.ok) {
        button.disabled = false;
        showToast('Could not save the favorite. Reload the page and try again.', true);
        return;
      }
      if (previous) state.favorites.delete(key);
      else state.favorites.set(key, {...film, key, status: 'plan', notes: ''});
      renderFilms();
      if (previous) showToast(`Removed "${previous.title || film?.title || 'film'}" from favorites.`, false, () => restoreFavorite(previous));
      const fields = document.getElementById('modal-favorite-fields');
      if (fields?.dataset.key === key) fields.innerHTML = state.favorites.has(key) ? favoriteFields(key, state.favorites.get(key).title || film?.title || '', state.favorites.get(key)) : '';
      // The redraw replaces the card: put the focus back on the same star.
      if (hadFocus) results.querySelector(`.film[data-key="${CSS.escape(key)}"] .favorite`)?.focus();
      document.querySelectorAll(`.modal-favorite[data-key="${CSS.escape(key)}"]`).forEach(modalButton => {
        const active = state.favorites.has(key);
        modalButton.innerHTML = `<i class="ti ti-star" aria-hidden="true"></i> ${favoriteLabel(active)}`;
        modalButton.classList.toggle('btn-accent', active);
        modalButton.classList.toggle('btn-outline-secondary', !active);
        modalButton.disabled = false;
      });
    }
    // Undo after removing: the favorite comes back with its status and note.
    async function restoreFavorite(previous) {
      try {
        const response = await fetch('/api/favorites', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(previous)});
        if (!response.ok) throw new Error();
      } catch {
        showToast('Could not restore the favorite.', true);
        return;
      }
      state.favorites.set(previous.key, previous);
      renderFilms();
      showToast(`"${previous.title}" is back in your favorites.`);
    }
    async function updateFavoriteField(control) {
      const key = control.dataset.key || control.closest('.film')?.dataset.key;
      const field = control.classList.contains('favorite-status') ? 'status' : 'notes';
      let response;
      try {
        response = await fetch(`/api/favorites/${encodeURIComponent(key)}`, {method: 'PATCH', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({[field]: control.value})});
      } catch {
        response = null;
      }
      // An unsaved note looks saved until the next redraw: mark the field until a retry works.
      control.classList.toggle('is-invalid', !response?.ok);
      if (!response?.ok) { showToast(`Could not save the ${field === 'notes' ? 'note' : 'status'}. It is still in the field; change it again to retry.`, true); return; }
      const saved = state.favorites.get(key) || {key}; saved[field] = control.value; state.favorites.set(key, saved);
    }
    providerInputs.forEach(input => input.addEventListener('change', renderFilms));
    // updateStats also reorders the services; the statistics must follow the selection.
    providerInputs.forEach(input => input.addEventListener('change', updateStats));
    document.getElementById('provider-search').addEventListener('input', reorderProviders);
    document.getElementById('provider-sort').addEventListener('change', reorderProviders);
    const providerPanel = document.getElementById('provider-panel');
    const providerToggle = document.getElementById('provider-toggle');
    // On a phone the panel stays open while services are ticked; "Done" or Escape closes it.
    const closeProviderPanel = () => {
      if (!providerPanel?.classList.contains('show')) return;
      providerPanel.classList.remove('show');
      providerToggle?.setAttribute('aria-expanded', 'false');
      if (providerPanel.contains(document.activeElement)) providerToggle?.focus();
    };
    const openProviderPanel = () => {
      providerPanel?.classList.add('show');
      providerToggle?.setAttribute('aria-expanded', 'true');
      document.getElementById('provider-done')?.focus();
    };
    providerToggle?.addEventListener('click', () => {
      if (providerPanel.classList.contains('show')) closeProviderPanel();
      else openProviderPanel();
    });
    document.getElementById('provider-done')?.addEventListener('click', closeProviderPanel);
    document.addEventListener('keydown', event => {
      if (event.key === 'Escape' && providerPanel?.classList.contains('show') && !document.querySelector('.modal.show')) closeProviderPanel();
    });
    document.addEventListener('click', event => {
      if (window.innerWidth <= 800 && providerPanel?.classList.contains('show') && !providerPanel.contains(event.target) && event.target !== providerToggle) closeProviderPanel();
    });
    document.getElementById('select-all-providers')?.addEventListener('click', () => {
      providerInputs.forEach(input => { if (!input.closest('label').hidden) input.checked = true; });
      updateStats();
      renderFilms();
    });
    document.getElementById('clear-providers')?.addEventListener('click', () => {
      providerInputs.forEach(input => { input.checked = false; });
      updateStats();
      renderFilms();
    });
    // Two ready-made views: the user's own services, or only the shops that rent single films.
    function selectProviders(names, message) {
      let chosen = 0;
      providerInputs.forEach(input => {
        input.checked = names.has(input.value);
        if (input.checked) chosen += 1;
      });
      updateStats();
      renderFilms();
      showToast(message(chosen));
    }
    document.getElementById('reset-providers')?.addEventListener('click', () => {
      selectProviders(mySubscriptions(), count => `Showing your ${count} subscriptions.`);
    });
    document.getElementById('rental-providers')?.addEventListener('click', () => {
      selectProviders(rentalShops, count => `Showing ${count} rental shops.`);
    });
    document.getElementById('free-providers')?.addEventListener('click', () => {
      selectProviders(freeServices, count => `Showing ${count} free services.`);
    });
    document.getElementById('stats-scope').addEventListener('change', updateStats);
    reorderProviders();
    document.getElementById('filter-chips').addEventListener('click', event => {
      const button = event.target.closest('.filter-chip');
      if (!button) return;
      if (button.hasAttribute('data-reset-filters')) { resetAllFilters(); return; }
      const input = document.getElementById(button.dataset.filterId);
      clearFilter(input);
      input.dispatchEvent(new Event('input', {bubbles: true}));
    });
    document.getElementById('empty-reset').addEventListener('click', resetAllFilters);
    document.getElementById('empty-subscriptions').addEventListener('click', () => document.getElementById('reset-providers').click());
    document.getElementById('favorites-show-all').addEventListener('click', () => setFavoritesOnly(false));
    results.addEventListener('click', event => { const favoriteButton = event.target.closest('.favorite'); if (favoriteButton) { event.preventDefault(); toggleFavorite(favoriteButton); } });
    function showFilmDetails(key, opener = document.activeElement) {
      const film = [...state.films, ...state.unavailable].find(item => filmKey(item) === key);
      if (!film) return;
      document.getElementById('film-details-title').textContent = film.title;
      const letterboxdSearch = `https://letterboxd.com/search/${encodeURIComponent(`${film.title} ${film.year || ''}`.trim())}/`;
      const trailerId = film.trailer_url ? new URL(film.trailer_url).searchParams.get('v') : null;
      const trailerLink = trailerId ? `<button class="film-link trailer-link" data-trailer="${escapeHtml(trailerId)}" type="button"><i class="ti ti-brand-youtube" aria-hidden="true"></i> Trailer</button>` : '';
      const credits = film.director || (film.cast || []).length
        ? `<p class="film-modal-credits">${film.director ? `Directed by ${escapeHtml(film.director)}` : ''}${film.director && film.cast?.length ? ' · ' : ''}${film.cast?.length ? `Cast: ${escapeHtml(film.cast.join(', '))}` : ''}</p>`
        : '';
      const keywords = film.keywords?.length ? `<p class="film-modal-keywords">${escapeHtml(film.keywords.join(', '))}</p>` : '';
      const providerRows = availabilityByOffer(film.providers, window.WATCHLIST_CONFIG.providerLogos, window.WATCHLIST_CONFIG.logoBaseUrl, mySubscriptions());
      // TMDB's watch page (JustWatch data) for the shown country; tmdb_url is checked on the server.
      const country = document.getElementById('country-select').value;
      const watchLink = film.tmdb_url ? `<a class="btn btn-sm btn-accent" href="${escapeHtml(`${film.tmdb_url}/watch?locale=${encodeURIComponent(country)}`)}" target="_blank" rel="noreferrer"><i class="ti ti-player-play" aria-hidden="true"></i> Where to watch</a>` : '';
      const savedFavorite = state.favorites.get(key);
      // Other films of the same series on the watchlist, oldest first.
      const series = film.collection
        ? [...state.films, ...state.unavailable].filter(item => item.collection === film.collection && filmKey(item) !== key)
          .sort((a, b) => (Number(a.year) || 0) - (Number(b.year) || 0))
        : [];
      const seriesLine = film.collection
        ? `<p class="film-modal-series">Part of ${escapeHtml(film.collection)}${series.length ? `: also on your watchlist ${series.map(item => `<button class="film-link series-pick" type="button" data-key="${escapeHtml(filmKey(item))}">${escapeHtml(item.title)}${item.year ? ` (${numberText(item.year)})` : ''}</button>`).join(', ')}` : ''}</p>`
        : '';
      const poster = film.poster_path ? `<img class="film-modal-poster" src="${imageBaseUrl}${escapeHtml(film.poster_path)}" alt="Poster for ${escapeHtml(film.title)}">` : '';
      const favoriteButtonClass = state.favorites.has(key) ? 'btn-accent' : 'btn-outline-secondary';
      const selectedForCompare = state.compareKeys.has(key);
      document.getElementById('film-details-content').innerHTML = `<div class="film-modal-layout">${poster}<div><p class="film-modal-meta">${numberText(film.year, 'Year unknown')}${numberText(film.rating) ? ` · TMDB ${Number(film.rating).toFixed(1)}/10` : ''}${numberText(film.runtime) ? ` · ${numberText(film.runtime)} min` : ''}</p><p>${escapeHtml(film.overview || 'No description available.')}</p><p class="film-modal-genres">${escapeHtml((film.genres || []).join(', ') || 'No genres available.')}</p>${credits}${seriesLine}${keywords}</div></div><h6 class="film-modal-section-title">Availability</h6>${providerRows || '<p class="empty">No service data available.</p>'}<div class="film-modal-actions">${watchLink}<button class="btn btn-sm ${favoriteButtonClass} modal-favorite" type="button" data-key="${escapeHtml(key)}"><i class="ti ti-star" aria-hidden="true"></i> ${favoriteLabel(state.favorites.has(key))}</button><button class="btn btn-sm btn-outline-secondary modal-compare" type="button" data-key="${escapeHtml(key)}"><i class="ti ti-columns-gap" aria-hidden="true"></i> ${selectedForCompare ? 'Remove from comparison' : 'Add to comparison'}</button>${film.tmdb_url ? `<a class="film-link" href="${escapeHtml(film.tmdb_url)}" target="_blank" rel="noreferrer"><i class="ti ti-brand-tmdb" aria-hidden="true"></i> TMDB</a>` : ''}${trailerLink}<a class="film-link" href="${letterboxdSearch}" target="_blank" rel="noreferrer"><i class="ti ti-device-tv" aria-hidden="true"></i> Search Letterboxd</a></div><div id="modal-favorite-fields" data-key="${escapeHtml(key)}">${savedFavorite ? favoriteFields(key, film.title, savedFavorite) : ''}</div>`;
      openModal('film-details-modal', opener);
    }
    results.addEventListener('click', event => {
      if (event.target.closest('button, a, input, select, textarea, label')) return;
      const card = event.target.closest('.film');
      if (card) showFilmDetails(card.dataset.key);
    });
    document.getElementById('film-details-content').addEventListener('click', event => {
      const button = event.target.closest('.modal-favorite');
      if (button) {
        event.preventDefault();
        toggleFavorite(button);
      }
      const compareButton = event.target.closest('.modal-compare');
      if (compareButton) {
        const key = compareButton.dataset.key;
        setCompared(key, !state.compareKeys.has(key));
        compareButton.innerHTML = `<i class="ti ti-columns-gap" aria-hidden="true"></i> ${state.compareKeys.has(key) ? 'Remove from comparison' : 'Add to comparison'}`;
      }
    });
    results.addEventListener('change', event => {
      const check = event.target.closest('.comparison-check');
      if (check) setCompared(check.closest('.film').dataset.key, check.checked);
    });
    results.addEventListener('click', event => {
      const detailsButton = event.target.closest('.film-details-button');
      if (detailsButton) showFilmDetails(detailsButton.dataset.key);
    });
    function openTrailer(trailer, opener = trailer) {
      document.getElementById('trailer-frame').src = `https://www.youtube.com/embed/${encodeURIComponent(trailer.dataset.trailer)}?autoplay=1`;
      openModal('trailer-modal', opener);
    }
    results.addEventListener('click', event => { const trailer = event.target.closest('.trailer-link'); if (trailer) openTrailer(trailer); });
    document.getElementById('film-details-content').addEventListener('click', event => {
      const trailer = event.target.closest('.trailer-link');
      if (!trailer) return;
      // Bootstrap shows one modal at a time; left open, the details would cover the player.
      // After the trailer the focus goes back to what opened the details.
      const opener = modalOpeners.get('film-details-modal');
      modalOpeners.delete('film-details-modal');
      bootstrap.Modal.getInstance(document.getElementById('film-details-modal'))?.hide();
      openTrailer(trailer, opener);
    });
    document.getElementById('trailer-modal').addEventListener('hidden.bs.modal', () => { document.getElementById('trailer-frame').src = ''; });
    results.addEventListener('change', event => { if (event.target.classList.contains('favorite-status')) updateFavoriteField(event.target); });
    // Another film of the series replaces the content; the focus later still goes back to the first opener.
    document.getElementById('film-details-content').addEventListener('click', event => {
      const pick = event.target.closest('.series-pick');
      if (pick) showFilmDetails(pick.dataset.key, modalOpeners.get('film-details-modal'));
    });
    document.getElementById('recently-removed-list').addEventListener('click', event => {
      const pick = event.target.closest('.removed-pick');
      if (pick) showFilmDetails(pick.dataset.key);
    });
    document.getElementById('film-details-content').addEventListener('change', event => { if (event.target.matches('.favorite-status, .favorite-note')) updateFavoriteField(event.target).then(renderFilms); });
    results.addEventListener('change', event => { if (event.target.classList.contains('favorite-note')) updateFavoriteField(event.target); });
    function syncUrl() {
      const url = new URL(location.href);
      const values = {
        q: document.getElementById('film-search').value,
        availability: document.getElementById('availability-filter').value,
        kind: document.getElementById('kind-filter').value,
        rating: document.getElementById('min-rating').value,
        votes: document.getElementById('min-votes').value,
        sort: document.getElementById('sort-order').value,
        match: document.getElementById('match-mode').value,
        genre: document.getElementById('genre-filter').dataset.pending || document.getElementById('genre-filter').value,
        keyword: document.getElementById('keyword-filter').dataset.pending || document.getElementById('keyword-filter').value,
        runtime: document.getElementById('runtime-filter').value,
        from: document.getElementById('year-from').value,
        to: document.getElementById('year-to').value,
        media: document.getElementById('media-filter').value,
        changes: document.getElementById('change-filter').value,
        providers: [...selectedProviders(providerInputs)].join(','),
        minproviders: document.getElementById('provider-count-filter').value,
        only: document.getElementById('exclusive-filter').checked ? '1' : '',
        favoriteStatus: document.getElementById('favorite-status-filter').value,
        favorites: state.favoritesOnly ? '1' : '',
      };
      Object.entries(values).forEach(([name, value]) => {
        if (value && !['all', '0', 'any'].includes(value)) url.searchParams.set(name, value);
        else url.searchParams.delete(name);
      });
      history.replaceState({}, '', url);
    }
    // Only 'input': a 'change' event also fires when a text field loses focus, and redrawing the
    // cards at that moment (on mousedown) swallowed the first click on a card or a star.
    // Typing in the search redraws only after a short pause, not on every key.
    let searchTimer;
    document.getElementById('film-search').addEventListener('input', () => { clearTimeout(searchTimer); searchTimer = setTimeout(renderFilms, 150); });
    ['exclusive-filter', 'availability-filter', 'kind-filter', 'genre-filter', 'keyword-filter', 'runtime-filter', 'year-from', 'year-to', 'min-rating', 'min-votes', 'media-filter', 'change-filter', 'provider-count-filter'].forEach(id => document.getElementById(id).addEventListener('input', renderFilms));
    const initialUrl = new URL(location.href).searchParams;
    const setInitial = (id, parameter, fallback) => {
      const element = document.getElementById(id);
      const value = initialUrl.get(parameter) ?? fallback;
      if (element && (!element.options || [...element.options].some(option => option.value === value))) element.value = value;
      else if (element && ['genre-filter', 'keyword-filter'].includes(id) && value !== 'all') element.dataset.pending = value;
    };
    ['genre-filter', 'keyword-filter'].forEach(id => document.getElementById(id).addEventListener('input', event => delete event.target.dataset.pending));
    setInitial('film-search', 'q', window.WATCHLIST_CONFIG.initialFilters.query);
    setInitial('availability-filter', 'availability', window.WATCHLIST_CONFIG.initialFilters.availability);
    setInitial('kind-filter', 'kind', window.WATCHLIST_CONFIG.initialFilters.kind);
    setInitial('sort-order', 'sort', window.WATCHLIST_CONFIG.initialFilters.sort);
    setInitial('min-rating', 'rating', window.WATCHLIST_CONFIG.initialFilters.min_rating);
    setInitial('min-votes', 'votes', '0');
    setInitial('match-mode', 'match', 'any');
    setInitial('genre-filter', 'genre', 'all');
    setInitial('keyword-filter', 'keyword', 'all');
    setInitial('runtime-filter', 'runtime', 'all');
    setInitial('year-from', 'from', '');
    setInitial('year-to', 'to', '');
    setInitial('media-filter', 'media', 'all');
    setInitial('change-filter', 'changes', 'all');
    setInitial('provider-count-filter', 'minproviders', '0');
    setInitial('favorite-status-filter', 'favoriteStatus', 'all');
    // Older links used availability=exclusive for what is now its own checkbox.
    document.getElementById('exclusive-filter').checked = initialUrl.get('only') === '1' || initialUrl.get('availability') === 'exclusive';
    const urlProviders = initialUrl.get('providers');
    if (urlProviders) providerInputs.forEach(input => { input.checked = urlProviders.split(',').includes(input.value); });
    ['match-mode', 'sort-order', 'favorite-status-filter'].forEach(id => document.getElementById(id).addEventListener('change', renderFilms));
    const favoritesButton = document.getElementById('favorites-view');
    state.favoritesOnly = initialUrl.get('favorites') === '1';
    // The button keeps its name; whether the view is on is said by aria-pressed and the line above the films.
    function setFavoritesOnly(on) {
      state.favoritesOnly = on;
      favoritesButton.classList.toggle('active', on);
      favoritesButton.setAttribute('aria-pressed', String(on));
      renderFilms();
    }
    favoritesButton.classList.toggle('active', state.favoritesOnly);
    favoritesButton.setAttribute('aria-pressed', String(state.favoritesOnly));
    favoritesButton.addEventListener('click', () => setFavoritesOnly(!state.favoritesOnly));
    document.getElementById('random-film').addEventListener('click', showRandomFilm);
    document.getElementById('evening-mode').addEventListener('click', showEveningSuggestions);
    document.getElementById('evening-form').addEventListener('submit', event => { event.preventDefault(); renderEveningSuggestions(); });
    document.getElementById('compare-films').addEventListener('click', compareFilms);
    updateCompareButton();
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
    document.getElementById('grey-unavailable').checked = localStorage.getItem('greyUnavailableDuringRescan') === 'true';
    document.getElementById('grey-unavailable').addEventListener('change', event => {
      localStorage.setItem('greyUnavailableDuringRescan', String(event.target.checked));
      applyRescanUnavailableState();
    });
    document.getElementById('country-select').addEventListener('change', switchCountry);
    const layoutToggle = document.getElementById('layout-toggle');
    function updateLayoutMode() {
      const desktop = localStorage.getItem('watchlistLayout') === 'desktop';
      document.body.classList.toggle('layout-desktop', desktop);
      layoutToggle.classList.toggle('active', desktop);
      layoutToggle.setAttribute('aria-pressed', String(desktop));
    }
    layoutToggle?.addEventListener('click', () => {
      localStorage.setItem('watchlistLayout', document.body.classList.contains('layout-desktop') ? 'responsive' : 'desktop');
      updateLayoutMode();
    });
    if (layoutToggle) updateLayoutMode();
    document.getElementById('share-button')?.addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText(location.href);
        showToast('Link copied.');
      } catch {
        // No clipboard over plain http in the home network: show the link to copy by hand.
        window.prompt('Copy this link:', location.href);
      }
    });
    document.getElementById('export-json').addEventListener('click', () => download('watchlist.json', JSON.stringify(state.films, null, 2), 'application/json'));
    document.getElementById('export-favorites').addEventListener('click', () => download('favorites.csv', ['Title,Year,Status,Notes', ...[...state.favorites.values()].map(film => [film.title, film.year, film.status || 'plan', film.notes || ''].map(value => `"${String(value ?? '').replaceAll('"', '""')}"`).join(','))].join('\n'), 'text/csv'));
    document.getElementById('export-favorites-json').addEventListener('click', () => download('favorites.json', JSON.stringify([...state.favorites.values()], null, 2), 'application/json'));
    document.getElementById('import-favorites').addEventListener('change', async event => {
      const file = event.target.files[0];
      if (!file) return;
      try {
        const text = await file.text();
        const records = file.name.toLowerCase().endsWith('.json') ? JSON.parse(text) : parseFavoriteCsv(text);
        if (!Array.isArray(records)) throw new Error('The import must contain a list of favorites.');
        const valid = records.filter(movie => movie && movie.title && movie.key);
        if (!valid.length) throw new Error('No valid favorites found.');
        for (const movie of valid) {
          const response = await fetch('/api/favorites', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({...movie, status: ['plan', 'watching', 'watched'].includes(movie.status) ? movie.status : 'plan', notes: String(movie.notes || '')})});
          if (!response.ok) throw new Error(`Could not import "${movie.title}".`);
        }
        await loadFavorites();
        renderFilms();
        showToast(`Imported ${valid.length} favorite${valid.length === 1 ? '' : 's'}.`);
      } catch (error) {
        showToast(error.message || 'Could not import favorites.', true);
      } finally {
        event.target.value = '';
      }
    });
    function parseFavoriteCsv(text) {
      const lines = text.split(/\r?\n/).filter(Boolean);
      if (lines.length < 2) return [];
      const headers = lines.shift().split(',').map(value => value.trim().toLowerCase());
      return lines.map(line => {
        const values = line.match(/(?:"([^"]*(?:""[^"]*)*)"|([^,]*))(?:,|$)/g)?.map(value => value.replace(/,$/, '').replace(/^"|"$/g, '').replaceAll('""', '"')) || [];
        const record = Object.fromEntries(headers.map((header, index) => [header, values[index] || '']));
        return {key: record.key || `${record.title}|${record.year}`, title: record.title, year: record.year, status: record.status, notes: record.notes};
      });
    }
    document.getElementById('export-csv').addEventListener('click', () => download('watchlist.csv', ['Title,Year,Services', ...state.films.map(film => [film.title, film.year, Object.keys(film.providers).join('; ')].map(value => `"${String(value ?? '').replaceAll('"', '""')}"`).join(','))].join('\n'), 'text/csv'));
    function download(name, data, type) { const link = document.createElement('a'); link.href = URL.createObjectURL(new Blob([data], {type})); link.download = name; link.click(); URL.revokeObjectURL(link.href); }
    // The offline worker was removed; drop the one older versions installed.
    navigator.serviceWorker?.getRegistrations().then(found => found.forEach(worker => worker.unregister()));
    loadFavorites().then(async () => {
      const snapshot = await loadLatestResult();
      const savedJob = new URL(location.href).searchParams.get('scan');
      if (savedJob) {
        resumeScan(savedJob);
      } else if (!snapshot || snapshot.stale) {
        startScan();
      } else {
        showSavedPanel();
      }
    });
