import {escapeHtml, numberText} from './ui.js';
import {createAppState, createScanState} from './state.js';
import {changeSummary, offerBadgesForProviders, renderResults} from './rendering.js';
import {readFilters, selectedProviders, updateProviderCount, updateProviderFilmCounts} from './filters.js';
import {filmKey, filterFilms} from './filtering.js';
import {updateScanFeedback} from './scans.js';
import {favoriteLabel} from './favorites.js';

const imageBaseUrl = window.WATCHLIST_CONFIG.imageBaseUrl;
const scanState = createScanState();
const state = createAppState();
    const providerInputs = document.querySelectorAll('#provider-filters input[type="checkbox"]');
    const rentalShops = new Set(window.WATCHLIST_CONFIG.rentalShops || []);
    // The services saved in Settings for the country shown in the header.
    const mySubscriptions = () => new Set(window.WATCHLIST_CONFIG.subscriptions?.[document.getElementById('country-select').value] || []);
    const results = document.getElementById('results');
    const seen = new Set();
    const toast = window.bootstrap ? bootstrap.Toast.getOrCreateInstance(document.getElementById('app-toast'), {delay: 2400}) : {show() {}};
    function showToast(message) { document.getElementById('toast-message').textContent = message; toast.show(); }

    function greyKeys() {
      if (!scanState.rescanInProgress || !document.getElementById('grey-unavailable').checked) return new Set();
      return new Set(scanState.pendingUnavailable.map(filmKey));
    }
    // Filter the state, then draw the cards from the result. Filters never read card attributes.
    function renderFilms() {
      if (!state.films.length && !state.unavailable.length) return;
      const selected = selectedProviders(providerInputs);
      const filters = readFilters(document, state.favoritesOnly);
      const view = filterFilms(state.films, state.unavailable, filters, {selected, favorites: state.favorites});
      state.view = view;
      renderResults(view, {results, unavailableResults: document.getElementById('unavailable-results')}, {
        imageBaseUrl,
        selected,
        favorites: state.favorites,
        compareKeys: state.compareKeys,
        greyKeys: greyKeys(),
      });
      document.getElementById('unavailable-panel').hidden = view.unavailable.length === 0;
      document.getElementById('unavailable-badge').textContent = view.unavailable.length;
      document.getElementById('visible-count').textContent = view.visibleCount;
      document.getElementById('scan-summary-content').innerHTML = changeSummary(state.changes, selected, state.lastScan);
      document.getElementById('scan-summary').hidden = !state.lastScan;
      document.getElementById('favorites-empty')?.toggleAttribute('hidden', !(state.favoritesOnly && view.visibleCount === 0 && view.unavailable.length === 0));
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
    function updateFilterChips() {
      const filters = [['film-search', 'Search'], ['availability-filter', 'Availability'], ['kind-filter', 'Offer'], ['min-rating', 'Rating'], ['genre-filter', 'Genre'], ['runtime-filter', 'Runtime'], ['year-from', 'From'], ['year-to', 'To']];
      document.getElementById('filter-chips').innerHTML = filters.map(([id, label]) => {
        const input = document.getElementById(id);
        const value = input.value;
        const text = input.options ? input.options[input.selectedIndex].text : value;
        const active = value && value !== 'all' && value !== '0';
        return active ? `<button class="filter-chip" type="button" data-filter-id="${id}">${label}: ${escapeHtml(text)} <i class="ti ti-x"></i></button>` : '';
      }).join('');
    }
    function populateGenres() {
      const select = document.getElementById('genre-filter');
      const current = select.value;
      const genres = [...new Set(state.films.flatMap(film => film.genres || []))].sort();
      select.innerHTML = '<option value="all">All genres</option>' + genres.map(genre => `<option value="${escapeHtml(genre)}">${escapeHtml(genre)}</option>`).join('');
      select.value = genres.includes(current) ? current : 'all';
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
      const film = visible[Math.floor(Math.random() * visible.length)];
      document.querySelector(`#results .film[data-key="${CSS.escape(filmKey(film))}"]`)?.scrollIntoView({behavior: 'smooth', block: 'center'});
      showToast(`Random pick: ${film.title}`);
    }
    function compareFilms() {
      const films = state.films.filter(film => state.compareKeys.has(filmKey(film)));
      if (films.length < 2 || films.length > 4) return showToast('Select 2 to 4 films to compare.');
      const providers = [...new Set(films.flatMap(film => Object.keys(film.providers || {})))].sort();
      const offerCell = film => Object.entries(film.providers || {}).map(([provider, kinds]) => `${escapeHtml(provider)}: ${escapeHtml(kinds.join(', '))}`).join('<br>') || '-';
      const providerRows = providers.map(provider => `<tr><th>${escapeHtml(provider)}</th>${films.map(film => `<td>${escapeHtml((film.providers?.[provider] || []).join(', ') || '—')}</td>`).join('')}</tr>`).join('');
      document.getElementById('compare-table').innerHTML = `<thead><tr><th>Metric</th>${films.map(film => `<th>${escapeHtml(film.title)}</th>`).join('')}</tr></thead><tbody><tr><th>Year</th>${films.map(film => `<td>${numberText(film.year, '-')}</td>`).join('')}</tr><tr><th>Rating</th>${films.map(film => `<td>${numberText(film.rating, '-')}</td>`).join('')}</tr><tr><th>Runtime</th>${films.map(film => `<td>${numberText(film.runtime) ? `${numberText(film.runtime)} min` : '-'}</td>`).join('')}</tr><tr><th>Genres</th>${films.map(film => `<td>${escapeHtml((film.genres || []).join(', ') || '-')}</td>`).join('')}</tr><tr><th>Offers</th>${films.map(film => `<td>${offerCell(film)}</td>`).join('')}</tr>${providerRows}</tbody>`;
      bootstrap.Modal.getOrCreateInstance(document.getElementById('compare-modal')).show();
    }
    function setCompared(key, checked) {
      if (checked) state.compareKeys.add(key);
      else state.compareKeys.delete(key);
      document.querySelectorAll(`.film[data-key="${CSS.escape(key)}"] .comparison-check`).forEach(check => { check.checked = checked; });
    }
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
    // Show a finished scan: films, unavailable films and the stored availability changes.
    function replaceWithScanResults(films, unavailable, changes, lastScan) {
      state.films = films || [];
      state.unavailable = unavailable || [];
      state.changes = changes || [];
      if (lastScan) state.lastScan = lastScan;
      seen.clear();
      state.films.forEach(film => seen.add(filmKey(film)));
      if (!state.films.length && !state.unavailable.length) results.innerHTML = '';
      scanState.pendingResults = [];
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
        response = await fetch(`/api/scan/${jobId}`);
        job = await response.json();
      } catch {
        // The server was not reachable for a moment (sleep, restart): keep asking.
        setTimeout(() => pollScan(jobId), 2000);
        return;
      }
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
      document.getElementById('progress-bar').style.width = `${percent}%`;
      document.getElementById('progress-count').textContent = job.total ? `${percent}% · ${job.completed}/${job.total}` : 'Loading';
      document.getElementById('status-message').textContent = job.message;
      document.getElementById('current-title').textContent = job.current_title || job.phase;
      if (scanState.rescanInProgress) {
        scanState.pendingResults = job.results || [];
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
      const pollSignature = `${job.status}|${job.completed}|${job.results?.length || 0}|${job.unavailable?.length || 0}|${job.failed?.length || 0}`;
      scanState.pollDelay = pollSignature === scanState.lastPollSignature ? Math.min(scanState.pollDelay + 250, 2000) : 350;
      scanState.lastPollSignature = pollSignature;
      if (job.failed?.length) {
        document.getElementById('status-message').textContent =
          `${job.message} ${job.failed.length} lookup${job.failed.length === 1 ? '' : 's'} failed.`;
      }
      if (job.source_name) { document.getElementById('source-name').textContent = job.source_name; document.getElementById('result-meta').hidden = false; document.getElementById('film-filters').hidden = false; }
      if (job.last_updated) document.getElementById('last-updated').textContent = `Last updated ${new Date(job.last_updated * 1000).toLocaleString()}`;
      if (state.films.length) { document.getElementById('stats-section').hidden = false; document.getElementById('result-tools').hidden = false; updateStats(); }
      if (job.status === 'complete' || job.status === 'cancelled') { document.getElementById('progress-bar').style.width = '100%'; document.getElementById('progress-count').textContent = job.status === 'complete' ? 'Complete' : 'Cancelled'; document.getElementById('cancel-scan').hidden = true; document.getElementById('retry-scan').hidden = false;       if (job.status === 'complete') {
        scanState.rescanInProgress = false;
        replaceWithScanResults(job.results, job.unavailable, job.changes, job.last_updated);
      }
      // The server moves favorites saved under "Title|Year" to the TMDB id after a scan.
      if (job.status === 'complete') loadFavorites().then(renderFilms);
      scanState.rescanInProgress = false; scanState.pendingUnavailable = []; applyRescanUnavailableState(); showToast(job.status === 'complete' ? 'Watchlist scan complete.' : 'Scan cancelled. Previous results kept.'); return; }
      // The app was restarted during the scan: it has started a new one, join it.
      if (job.status === 'interrupted') { startScan(); return; }
      if (job.status === 'error') { document.getElementById('error-message').textContent = job.message; document.getElementById('error-message').hidden = false; document.getElementById('cancel-scan').hidden = true; document.getElementById('retry-scan').hidden = false; scanState.rescanInProgress = false; scanState.pendingUnavailable = []; applyRescanUnavailableState(); showToast('Scan failed.'); return; }
      setTimeout(() => pollScan(jobId), scanState.pollDelay);
    }
    async function startScan() {
      scanState.rescanInProgress = state.films.length > 0;
      scanState.pendingResults = [];
      scanState.pendingUnavailable = [];
      if (!scanState.rescanInProgress) {
        state.films = [];
        seen.clear();
        results.innerHTML = '<div class="skeleton-grid" aria-label="Loading films"><div class="skeleton-card"><div class="skeleton-poster"></div><div class="skeleton-line"></div></div><div class="skeleton-card"><div class="skeleton-poster"></div><div class="skeleton-line"></div></div><div class="skeleton-card"><div class="skeleton-poster"></div><div class="skeleton-line"></div></div></div>';
      }
      showToast(scanState.rescanInProgress ? 'Updating availability. Previous results remain visible.' : 'Starting watchlist scan...');
      document.getElementById('cancel-scan').hidden = false; document.getElementById('retry-scan').hidden = true; document.getElementById('error-message').hidden = true;
      state.unavailable = [];
      if (!scanState.rescanInProgress) document.getElementById('unavailable-panel').hidden = true;
      const upload = document.getElementById('csv-upload').files[0];
      const body = new FormData();
      body.append('country', document.getElementById('country-select').value);
      if (upload) body.append('watchlist', upload);
      const response = await fetch('/api/scan', {method: 'POST', body});
      const data = await response.json();
      if (!response.ok) { document.getElementById('error-message').textContent = data.error; document.getElementById('error-message').hidden = false; showToast('Scan could not be started.'); return; }
      scanState.currentJob = data.job_id;
      scanState.pollDelay = 350;
      scanState.lastPollSignature = '';
      const url = new URL(location.href);
      url.searchParams.set('scan', scanState.currentJob);
      history.replaceState({}, '', url);
      pollScan();
    }
    async function loadLatestResult() {
      const country = document.getElementById('country-select').value;
      const response = await fetch(`/api/latest?country=${encodeURIComponent(country)}`);
      if (!response.ok) return;
      const snapshot = await response.json();
      if (!snapshot.available) return;
      replaceWithScanResults(snapshot.results, snapshot.unavailable, snapshot.changes, snapshot.created);
      document.getElementById('source-name').textContent = snapshot.source_name || '';
      document.getElementById('result-meta').hidden = false;
      document.getElementById('film-filters').hidden = false;
      if (snapshot.created) {
        document.getElementById('last-updated').textContent =
          `Last updated ${new Date(snapshot.created * 1000).toLocaleString()}`;
      }
    }
    function resumeScan(jobId) {
      scanState.currentJob = jobId;
      document.getElementById('cancel-scan').hidden = false;
      document.getElementById('retry-scan').hidden = true;
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
      button.disabled = true;
      let response;
      if (previous) {
        response = await fetch(`/api/favorites/${encodeURIComponent(key)}`, {method: 'DELETE'});
        state.favorites.delete(key);
      } else {
        response = await fetch('/api/favorites', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({key, ...film})});
        state.favorites.set(key, {...film, key, status: 'plan', notes: ''});
      }
      if (!response.ok) {
        if (previous) state.favorites.set(key, previous);
        else state.favorites.delete(key);
        button.disabled = false;
        showToast('Could not update favorite.');
        return;
      }
      renderFilms();
      document.querySelectorAll(`.modal-favorite[data-key="${CSS.escape(key)}"]`).forEach(modalButton => {
        const active = state.favorites.has(key);
        modalButton.innerHTML = `<i class="ti ti-star"></i> ${favoriteLabel(active)}`;
        modalButton.classList.toggle('btn-accent', active);
        modalButton.classList.toggle('btn-outline-secondary', !active);
        modalButton.disabled = false;
      });
      showToast(state.favorites.has(key) ? 'Added to favorites.' : 'Removed from favorites.');
    }
    async function updateFavoriteField(control) {
      const card = control.closest('.film');
      const key = card.dataset.key;
      const field = control.classList.contains('favorite-status') ? 'status' : 'notes';
      const response = await fetch(`/api/favorites/${encodeURIComponent(key)}`, {method: 'PATCH', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({[field]: control.value})});
      if (response.ok) { const saved = state.favorites.get(key) || {key}; saved[field] = control.value; state.favorites.set(key, saved); showToast('Favorite updated.'); }
    }
    providerInputs.forEach(input => input.addEventListener('change', renderFilms));
    providerInputs.forEach(input => input.addEventListener('change', reorderProviders));
    document.getElementById('provider-search').addEventListener('input', reorderProviders);
    document.getElementById('provider-sort').addEventListener('change', reorderProviders);
    const providerPanel = document.getElementById('provider-panel');
    const providerToggle = document.getElementById('provider-toggle');
    const closeProviderPanel = () => {
      providerPanel?.classList.remove('show');
      providerPanel?.setAttribute('aria-hidden', 'true');
      providerToggle?.setAttribute('aria-expanded', 'false');
    };
    const openProviderPanel = () => {
      providerPanel?.classList.add('show');
      providerPanel?.setAttribute('aria-hidden', 'false');
      providerToggle?.setAttribute('aria-expanded', 'true');
    };
    providerToggle?.addEventListener('click', () => {
      if (providerPanel.classList.contains('show')) closeProviderPanel();
      else openProviderPanel();
    });
    providerInputs.forEach(input => input.addEventListener('change', () => {
      if (window.innerWidth <= 800 && !document.body.classList.contains('layout-desktop')) {
        closeProviderPanel();
      }
    }));
    document.addEventListener('keydown', event => {
      if (event.key === 'Escape') closeProviderPanel();
    });
    document.addEventListener('click', event => {
      if (window.innerWidth <= 800 && providerPanel?.classList.contains('show') && !providerPanel.contains(event.target) && event.target !== providerToggle) closeProviderPanel();
    });
    document.getElementById('select-all-providers')?.addEventListener('click', () => {
      providerInputs.forEach(input => { if (!input.closest('label').hidden) input.checked = true; });
      reorderProviders();
      renderFilms();
    });
    document.getElementById('clear-providers')?.addEventListener('click', () => {
      providerInputs.forEach(input => { input.checked = false; });
      reorderProviders();
      renderFilms();
    });
    // Two ready-made views: the user's own services, or only the shops that rent single films.
    function selectProviders(names, message) {
      let chosen = 0;
      providerInputs.forEach(input => {
        input.checked = names.has(input.value);
        if (input.checked) chosen += 1;
      });
      reorderProviders();
      renderFilms();
      showToast(message(chosen));
      if (window.innerWidth <= 800 && !document.body.classList.contains('layout-desktop')) closeProviderPanel();
    }
    document.getElementById('reset-providers')?.addEventListener('click', () => {
      selectProviders(mySubscriptions(), count => `Showing your ${count} subscriptions.`);
    });
    document.getElementById('rental-providers')?.addEventListener('click', () => {
      selectProviders(rentalShops, count => `Showing ${count} rental shops.`);
    });
    document.getElementById('stats-scope').addEventListener('change', updateStats);
    reorderProviders();
    document.getElementById('filter-chips').addEventListener('click', event => { const button = event.target.closest('.filter-chip'); if (!button) return; const input = document.getElementById(button.dataset.filterId); input.value = input.options ? 'all' : ''; input.dispatchEvent(new Event('input', {bubbles: true})); });
    results.addEventListener('click', event => { const favoriteButton = event.target.closest('.favorite'); if (favoriteButton) { event.preventDefault(); toggleFavorite(favoriteButton); } });
    function showFilmDetails(key) {
      const film = [...state.films, ...state.unavailable].find(item => filmKey(item) === key);
      if (!film) return;
      document.getElementById('film-details-title').textContent = film.title;
      const letterboxdSearch = `https://letterboxd.com/search/${encodeURIComponent(`${film.title} ${film.year || ''}`.trim())}/`;
      const trailerLink = film.trailer_url ? `<a class="btn btn-sm btn-outline-secondary" href="${escapeHtml(film.trailer_url)}" target="_blank" rel="noreferrer"><i class="ti ti-brand-youtube"></i> Trailer</a>` : '';
      const providerRows = offerBadgesForProviders(film.providers);
      const poster = film.poster_path ? `<img class="film-modal-poster" src="${imageBaseUrl}${escapeHtml(film.poster_path)}" alt="Poster for ${escapeHtml(film.title)}">` : '';
      const favoriteButtonClass = state.favorites.has(key) ? 'btn-accent' : 'btn-outline-secondary';
      const selectedForCompare = state.compareKeys.has(key);
      document.getElementById('film-details-content').innerHTML = `<div class="film-modal-layout">${poster}<div><p class="film-modal-meta">${numberText(film.year, 'Year unknown')}${numberText(film.rating) ? ` · TMDB ${Number(film.rating).toFixed(1)}/10` : ''}${numberText(film.runtime) ? ` · ${numberText(film.runtime)} min` : ''}</p><p>${escapeHtml(film.overview || 'No description available.')}</p><p class="film-modal-genres">${escapeHtml((film.genres || []).join(', ') || 'No genres available.')}</p></div></div><h6 class="film-modal-section-title">Availability</h6><ul class="film-provider-list">${providerRows || '<li>No provider data available.</li>'}</ul><div class="film-modal-actions"><button class="btn btn-sm ${favoriteButtonClass} modal-favorite" type="button" data-key="${escapeHtml(key)}"><i class="ti ti-star"></i> ${favoriteLabel(state.favorites.has(key))}</button><button class="btn btn-sm btn-outline-secondary modal-compare" type="button" data-key="${escapeHtml(key)}"><i class="ti ti-columns-gap"></i> ${selectedForCompare ? 'Remove from comparison' : 'Add to comparison'}</button>${film.tmdb_url ? `<a class="btn btn-sm btn-outline-secondary" href="${escapeHtml(film.tmdb_url)}" target="_blank" rel="noreferrer"><i class="ti ti-brand-tmdb"></i> TMDB</a>` : ''}${trailerLink}<a class="btn btn-sm btn-outline-secondary" href="${letterboxdSearch}" target="_blank" rel="noreferrer"><i class="ti ti-device-tv"></i> Search Letterboxd</a></div>`;
      bootstrap.Modal.getOrCreateInstance(document.getElementById('film-details-modal')).show();
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
        compareButton.innerHTML = `<i class="ti ti-columns-gap"></i> ${state.compareKeys.has(key) ? 'Remove from comparison' : 'Add to comparison'}`;
      }
    });
    results.addEventListener('change', event => {
      const check = event.target.closest('.comparison-check');
      if (check) setCompared(check.closest('.film').dataset.key, check.checked);
    });
    results.addEventListener('keydown', event => {
      if ((event.key !== 'Enter' && event.key !== ' ') || event.target.closest('button, a, input, select, textarea')) return;
      const card = event.target.closest('.film');
      if (!card) return;
      event.preventDefault();
      showFilmDetails(card.dataset.key);
    });
    results.addEventListener('click', event => {
      const detailsButton = event.target.closest('.film-details-button');
      if (detailsButton) showFilmDetails(detailsButton.dataset.key);
    });
    results.addEventListener('click', event => { const trailer = event.target.closest('.trailer-link'); if (!trailer) return; document.getElementById('trailer-frame').src = `https://www.youtube.com/embed/${encodeURIComponent(trailer.dataset.trailer)}?autoplay=1`; bootstrap.Modal.getOrCreateInstance(document.getElementById('trailer-modal')).show(); });
    document.getElementById('trailer-modal').addEventListener('hidden.bs.modal', () => { document.getElementById('trailer-frame').src = ''; });
    results.addEventListener('change', event => { if (event.target.classList.contains('favorite-status')) updateFavoriteField(event.target); });
    results.addEventListener('change', event => { if (event.target.classList.contains('favorite-note')) updateFavoriteField(event.target); });
    function syncUrl() {
      const url = new URL(location.href);
      const values = {
        q: document.getElementById('film-search').value,
        availability: document.getElementById('availability-filter').value,
        kind: document.getElementById('kind-filter').value,
        rating: document.getElementById('min-rating').value,
        sort: document.getElementById('sort-order').value,
        match: document.getElementById('match-mode').value,
        genre: document.getElementById('genre-filter').value,
        runtime: document.getElementById('runtime-filter').value,
        from: document.getElementById('year-from').value,
        to: document.getElementById('year-to').value,
        media: document.getElementById('media-filter').value,
        changes: document.getElementById('change-filter').value,
        providers: [...selectedProviders(providerInputs)].join(','),
        minproviders: document.getElementById('provider-count-filter').value,
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
    ['film-search', 'availability-filter', 'kind-filter', 'genre-filter', 'runtime-filter', 'year-from', 'year-to', 'min-rating', 'media-filter', 'change-filter', 'provider-count-filter'].forEach(id => document.getElementById(id).addEventListener('input', renderFilms));
    const initialUrl = new URL(location.href).searchParams;
    const setInitial = (id, parameter, fallback) => {
      const element = document.getElementById(id);
      const value = initialUrl.get(parameter) ?? fallback;
      if (element && (!element.options || [...element.options].some(option => option.value === value))) element.value = value;
    };
    setInitial('film-search', 'q', window.WATCHLIST_CONFIG.initialFilters.query);
    setInitial('availability-filter', 'availability', window.WATCHLIST_CONFIG.initialFilters.availability);
    setInitial('kind-filter', 'kind', window.WATCHLIST_CONFIG.initialFilters.kind);
    setInitial('sort-order', 'sort', window.WATCHLIST_CONFIG.initialFilters.sort);
    setInitial('min-rating', 'rating', window.WATCHLIST_CONFIG.initialFilters.min_rating);
    setInitial('match-mode', 'match', 'any');
    setInitial('genre-filter', 'genre', 'all');
    setInitial('runtime-filter', 'runtime', 'all');
    setInitial('year-from', 'from', '');
    setInitial('year-to', 'to', '');
    setInitial('media-filter', 'media', 'all');
    setInitial('change-filter', 'changes', 'all');
    setInitial('provider-count-filter', 'minproviders', '0');
    setInitial('favorite-status-filter', 'favoriteStatus', 'all');
    const urlProviders = initialUrl.get('providers');
    if (urlProviders) providerInputs.forEach(input => { input.checked = urlProviders.split(',').includes(input.value); });
    ['match-mode', 'sort-order', 'favorite-status-filter'].forEach(id => document.getElementById(id).addEventListener('change', renderFilms));
    const favoritesButton = document.getElementById('favorites-view');
    state.favoritesOnly = initialUrl.get('favorites') === '1';
    favoritesButton.classList.toggle('active', state.favoritesOnly);
    favoritesButton.innerHTML = state.favoritesOnly ? '<i class="ti ti-grid"></i> All films' : '<i class="ti ti-star-fill"></i> My favorites';
    favoritesButton.addEventListener('click', event => { state.favoritesOnly = !state.favoritesOnly; event.currentTarget.classList.toggle('active', state.favoritesOnly); event.currentTarget.innerHTML = state.favoritesOnly ? '<i class="ti ti-grid"></i> All films' : '<i class="ti ti-star-fill"></i> My favorites'; renderFilms(); });
    document.getElementById('random-film').addEventListener('click', showRandomFilm);
    document.getElementById('compare-films').addEventListener('click', compareFilms);
    document.getElementById('cancel-scan').addEventListener('click', async event => {
      if (!scanState.currentJob || event.currentTarget.disabled) return;
      if (!window.confirm('Cancel this scan? Your previous successful results will remain visible.')) return;
      event.currentTarget.disabled = true;
      try {
        const response = await fetch(`/api/scan/${scanState.currentJob}/cancel`, {method: 'POST'});
        if (!response.ok) {
          event.currentTarget.disabled = false;
          showToast('The scan could not be cancelled.');
        }
      } catch {
        event.currentTarget.disabled = false;
        showToast('The scan could not be cancelled.');
      }
    });
    document.getElementById('retry-scan').addEventListener('click', startScan);
    document.getElementById('grey-unavailable').checked = localStorage.getItem('greyUnavailableDuringRescan') === 'true';
    document.getElementById('grey-unavailable').addEventListener('change', event => {
      localStorage.setItem('greyUnavailableDuringRescan', String(event.target.checked));
      applyRescanUnavailableState();
    });
    document.getElementById('country-select').addEventListener('change', startScan);
    const layoutToggle = document.getElementById('layout-toggle');
    function updateLayoutMode() {
      const desktop = localStorage.getItem('watchlistLayout') === 'desktop';
      document.body.classList.toggle('layout-desktop', desktop);
      layoutToggle.classList.toggle('active', desktop);
      layoutToggle.innerHTML = desktop ? '<i class="ti ti-layout-sidebar"></i> Responsive layout' : '<i class="ti ti-layout-sidebar"></i> Desktop layout';
    }
    layoutToggle?.addEventListener('click', () => {
      localStorage.setItem('watchlistLayout', document.body.classList.contains('layout-desktop') ? 'responsive' : 'desktop');
      updateLayoutMode();
    });
    if (layoutToggle) updateLayoutMode();
    document.getElementById('share-button')?.addEventListener('click', async () => { await navigator.clipboard.writeText(location.href); document.getElementById('share-message').textContent = 'Link copied'; });
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
        showToast(error.message || 'Could not import favorites.');
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
    document.getElementById('export-csv').addEventListener('click', () => download('watchlist.csv', ['Title,Year,Providers', ...state.films.map(film => [film.title, film.year, Object.keys(film.providers).join('; ')].map(value => `"${String(value ?? '').replaceAll('"', '""')}"`).join(','))].join('\n'), 'text/csv'));
    function download(name, data, type) { const link = document.createElement('a'); link.href = URL.createObjectURL(new Blob([data], {type})); link.download = name; link.click(); URL.revokeObjectURL(link.href); }
    // The offline worker was removed; drop the one older versions installed.
    navigator.serviceWorker?.getRegistrations().then(found => found.forEach(worker => worker.unregister()));
    loadFavorites().then(async () => {
      await loadLatestResult();
      const savedJob = new URL(location.href).searchParams.get('scan');
      if (savedJob) {
        resumeScan(savedJob);
      } else {
        startScan();
      }
    });
