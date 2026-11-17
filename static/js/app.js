import {dateTime, escapeHtml, numberText} from './ui.js';
import {createAppState, createScanState} from './state.js';
import {availabilityByOffer, changeBadgesFor, changeSummary, compareButtonState, favoriteFields, filmHref, renderResults} from './rendering.js';
import {activeFilters, clearFilter, readFilters, resetFilters, selectedProviders, updateProviderCount, updateProviderFilmCounts} from './filters.js';
import {comingSoon, elsewhereOnServices, eveningSuggestions, filmKey, filterFilms, recentlyRemoved, similarOnServices, sortRatings} from './filtering.js';
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
    // The dot in the header: nothing to see while the data is fresh; yellow when old, red after an error.
    function setSync(name, text) {
      document.getElementById('sync-toggle').dataset.state = name;
      document.getElementById('sync-label').textContent = text;
    }
    // After a scan the button starts another one; "Retry" is only right after an error.
    function showScanButton(failed = false) {
      const age = state.lastScan ? Date.now() / 1000 - state.lastScan : Infinity;
      if (failed) setSync('error', 'Scan failed');
      else if (age > 24 * 3600) setSync('stale', 'Out of date');
      else setSync('ok', state.lastScan ? `Synced ${dateTime(state.lastScan)}` : 'Synced');
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
    }
    function showScanRunning() {
      setSync('running', 'Checking…');
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
      if (document.getElementById('sync-toggle').dataset.state === 'running') setSync('running', `${Math.round(percent)}%`);
    }
    // Bootstrap does not give the focus back after a dialog: return it to the control that opened it.
    // A redrawn card has a new button, so look it up again by the film key.
    const modalOpeners = new Map();
    function openModal(id, opener = document.activeElement) {
      modalOpeners.set(id, opener);
      bootstrap.Modal.getOrCreateInstance(document.getElementById(id)).show();
    }
    ['film-details-modal', 'trailer-modal', 'compare-modal'].forEach(id => {
      document.getElementById(id).addEventListener('hidden.bs.modal', () => {
        const opener = modalOpeners.get(id);
        modalOpeners.delete(id);
        if (!opener || opener === document.body) return;
        const key = opener.dataset?.key;
        const target = opener.isConnected ? opener : key && document.querySelector(`#results .film-open[data-key="${CSS.escape(key)}"]`);
        target?.focus();
      });
    });
    function showResultTools() {
      if (!state.films.length) return;
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
      // A redraw (e.g. when a scan finishes) replaces the note field someone is typing in; carry the text and cursor over.
      const typing = document.activeElement?.matches('#results .favorite-note') ? document.activeElement : null;
      const typed = typing && {key: typing.dataset.key, value: typing.value, start: typing.selectionStart, end: typing.selectionEnd};
      renderResults(view, {results, unavailableResults: document.getElementById('unavailable-results')}, {
        imageBaseUrl,
        providerLogos: window.WATCHLIST_CONFIG.providerLogos,
        logoBaseUrl: window.WATCHLIST_CONFIG.logoBaseUrl,
        selected,
        favorites: state.favorites,
        compareKeys: state.compareKeys,
        greyKeys: greyKeys(),
        favoritesOnly: state.favoritesOnly,
        pageHref: location.href,
      });
      const note = typed && results.querySelector(`.favorite-note[data-key="${CSS.escape(typed.key)}"]`);
      if (note) { note.value = typed.value; note.focus(); note.setSelectionRange(typed.start, typed.end); }
      openPendingFilm();
      document.getElementById('unavailable-panel').hidden = view.unavailable.length === 0;
      document.getElementById('unavailable-badge').textContent = view.unavailable.length;
      document.getElementById('visible-count').textContent = view.visibleCount;
      document.getElementById('provider-done-count').textContent = view.visibleCount;
      results.setAttribute('aria-busy', 'false');
      document.getElementById('scan-summary-content').innerHTML = changeSummary(state.changes, selected, state.lastScan);
      renderRecentlyRemoved();
      renderTonight();
      renderComingSoon();
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
        const name = known.has(item.film_key) ? `<a class="film-link film-open" href="${escapeHtml(filmHref(location.href, item.film_key))}" data-key="${escapeHtml(item.film_key)}">${title}</a>` : title;
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
      const age = document.getElementById('age-filter');
      fillSelect(age, 'Any age rating', sortRatings([...state.films, ...state.unavailable].map(film => film.certification)));
      [...age.options].slice(1).forEach(option => { if (/^\d+$/.test(option.value)) option.textContent = `Up to ${option.value}`; });
      // Codes as values ("ja", "JP"), names as text ("Japanese", "Japan"), sorted by name.
      const all = [...state.films, ...state.unavailable];
      const named = (select, allText, codes, type) => {
        const names = new Intl.DisplayNames(['en'], {type});
        const sorted = [...new Set(codes.filter(Boolean))].sort((a, b) => (names.of(a) || a).localeCompare(names.of(b) || b));
        fillSelect(select, allText, sorted);
        [...select.options].slice(1).forEach(option => { option.textContent = names.of(option.value) || option.value; });
      };
      named(document.getElementById('language-filter'), 'Any language', all.map(film => film.original_language), 'language');
      named(document.getElementById('origin-filter'), 'Any country', all.flatMap(film => film.origin_countries || []), 'region');
      // Ratings arrive with the first scan after the update; until then the filter and sort would only empty the list.
      const rated = all.some(film => film.letterboxd_rating != null);
      const letterboxd = document.getElementById('letterboxd-filter');
      letterboxd.disabled = !rated;
      if (!rated) letterboxd.value = '0';
      letterboxd.options[0].textContent = rated ? 'Any Letterboxd rating' : 'Letterboxd rating: after the next scan';
      document.querySelector('#sort-order option[value="letterboxd"]').disabled = !rated;
    }
    // "15 Mar 2027" for a date "2027-03-15".
    function day(date) {
      return new Date(`${date}T00:00:00`).toLocaleDateString([], {dateStyle: 'medium'});
    }
    function today() {
      return new Date().toLocaleDateString('sv');  // local date as YYYY-MM-DD
    }
    // Cinema and home releases still ahead, e.g. "in cinemas 5 Mar 2027 · at home 1 Jun 2027".
    function upcomingText(film) {
      return [['in cinemas', film.cinema_date], ['at home', film.home_date]]
        .filter(([, date]) => date && date >= today())
        .map(([label, date]) => `${label} ${day(date)}`).join(' · ');
    }
    function renderComingSoon() {
      const films = comingSoon([...state.films, ...state.unavailable], today());
      document.getElementById('coming-panel').hidden = films.length === 0;
      document.getElementById('coming-count').textContent = films.length;
      document.getElementById('coming-list').innerHTML = films.map(film => {
        const title = escapeHtml(film.title) + (film.year ? ` (${numberText(film.year)})` : '');
        const rating = film.certification ? ` · rated ${escapeHtml(film.certification)}` : '';
        return `<li><a class="film-link film-open" href="${escapeHtml(filmHref(location.href, filmKey(film)))}" data-key="${escapeHtml(filmKey(film))}">${title}</a> · ${escapeHtml(upcomingText(film))}${rating}</li>`;
      }).join('');
    }
    // The own services a film runs on without extra cost.
    function includedOn(film, subscriptions) {
      return Object.entries(film.providers || {})
        .filter(([provider, kinds]) => subscriptions.has(provider) && kinds.some(kind => ['free', 'ads', 'flatrate'].includes(kind)))
        .map(([provider]) => provider).sort().join(', ');
    }
    // "Tonight": the best films for the saved runtime and genre on the ticked services, right above the results.
    let tonightShuffled = null;  // keys picked by "Shuffle"; null = best rated first
    function tonightCriteria() {
      const savedRuntime = localStorage.getItem('eveningRuntime');
      return {maximum: savedRuntime === null ? 150 : Number(savedRuntime), genre: localStorage.getItem('eveningGenre') || 'all'};
    }
    function tonightCandidates() {
      return eveningSuggestions(state.films, {...tonightCriteria(), subscriptions: selectedProviders(providerInputs), skip: watchedKeys(), limit: Infinity});
    }
    function renderTonight() {
      const {maximum, genre} = tonightCriteria();
      const runtime = document.getElementById('tonight-runtime');
      runtime.value = maximum ? String(maximum) : '';
      if (runtime.value !== (maximum ? String(maximum) : '')) runtime.value = '150';  // an old free-text value
      const genreSelect = document.getElementById('tonight-genre');
      const genres = [...new Set(state.films.flatMap(film => film.genres || []))].sort();
      genreSelect.innerHTML = '<option value="all">Any genre</option>' + genres.map(value => `<option value="${escapeHtml(value)}">${escapeHtml(value)}</option>`).join('');
      genreSelect.value = genres.includes(genre) ? genre : 'all';
      const subscriptions = selectedProviders(providerInputs);
      const candidates = state.favoritesOnly ? [] : tonightCandidates();
      const byKey = new Map(candidates.map(film => [filmKey(film), film]));
      // A shuffle stays until a pick no longer fits (filters, services or criteria changed).
      if (tonightShuffled && !tonightShuffled.every(key => byKey.has(key))) tonightShuffled = null;
      const picks = tonightShuffled ? tonightShuffled.map(key => byKey.get(key)) : candidates.slice(0, 3);
      document.getElementById('tonight').hidden = state.favoritesOnly || !state.films.length;
      document.getElementById('tonight-shuffle').disabled = candidates.length <= 3;
      document.getElementById('tonight-criteria').textContent = picks.length
        ? `${tonightShuffled ? 'Shuffled' : 'Best rated first'} · on the services ticked under Services`
        : 'No unwatched film on the ticked services fits. Try a longer runtime or another genre.';
      document.getElementById('tonight-picks').innerHTML = picks.map(film => {
        const poster = film.poster_path ? `<img src="${imageBaseUrl}${escapeHtml(film.poster_path)}" alt="" loading="lazy">` : '<span class="tonight-noposter"></span>';
        const facts = [numberText(film.rating) ? Number(film.rating).toFixed(1) : '', numberText(film.runtime) ? `${numberText(film.runtime)} min` : '', includedOn(film, subscriptions)].filter(Boolean).join(' · ');
        return `<li><a class="tonight-pick film-open" href="${escapeHtml(filmHref(location.href, filmKey(film)))}" data-key="${escapeHtml(filmKey(film))}">${poster}<span class="tonight-title">${escapeHtml(film.title)}</span><span class="tonight-meta">${escapeHtml(facts)}</span></a></li>`;
      }).join('');
    }
    function changeTonight() {
      localStorage.setItem('eveningRuntime', document.getElementById('tonight-runtime').value);
      localStorage.setItem('eveningGenre', document.getElementById('tonight-genre').value);
      tonightShuffled = null;
      renderTonight();
    }
    document.getElementById('tonight-runtime').addEventListener('change', changeTonight);
    document.getElementById('tonight-genre').addEventListener('change', changeTonight);
    document.getElementById('tonight-shuffle').addEventListener('click', () => {
      const shown = new Set(tonightShuffled || []);
      // Prefer films not on screen right now, so a click always brings something new when there is more.
      const pool = tonightCandidates().sort(() => Math.random() - 0.5).sort((a, b) => shown.has(filmKey(a)) - shown.has(filmKey(b)));
      tonightShuffled = pool.slice(0, 3).map(filmKey);
      renderTonight();
    });
    // The tick boxes on the posters only show while choosing films to compare.
    function setCompareMode(on) {
      document.body.classList.toggle('compare-mode', on);
      document.getElementById('compare-films').setAttribute('aria-pressed', String(on));
    }
    function compareFilms() {
      const films = state.films.filter(film => state.compareKeys.has(filmKey(film)));
      if (!document.body.classList.contains('compare-mode') && films.length < 2) {
        setCompareMode(true);
        return showToast('Tick 2 to 4 films, then press Compare again.');
      }
      if (films.length < 2 || films.length > 4) return showToast('Select 2 to 4 films to compare.');
      const providers = [...new Set(films.flatMap(film => Object.keys(film.providers || {})))].sort();
      const offerCell = film => Object.entries(film.providers || {}).map(([provider, kinds]) => `${escapeHtml(provider)}: ${escapeHtml(kinds.join(', '))}`).join('<br>') || '-';
      const providerRows = providers.map(provider => `<tr><th>${escapeHtml(provider)}</th>${films.map(film => `<td>${escapeHtml((film.providers?.[provider] || []).join(', ') || '—')}</td>`).join('')}</tr>`).join('');
      document.getElementById('compare-table').innerHTML = `<thead><tr><th>Metric</th>${films.map(film => `<th>${escapeHtml(film.title)}</th>`).join('')}</tr></thead><tbody><tr><th>Year</th>${films.map(film => `<td>${numberText(film.year, '-')}</td>`).join('')}</tr><tr><th>Rating</th>${films.map(film => `<td>${numberText(film.rating, '-')}</td>`).join('')}</tr><tr><th>Runtime</th>${films.map(film => `<td>${numberText(film.runtime) ? `${numberText(film.runtime)} min` : '-'}</td>`).join('')}</tr><tr><th>Genres</th>${films.map(film => `<td>${escapeHtml((film.genres || []).join(', ') || '-')}</td>`).join('')}</tr><tr><th>Offers</th>${films.map(film => `<td>${offerCell(film)}</td>`).join('')}</tr>${providerRows}</tbody>`;
      openModal('compare-modal');
    }
    function updateCompareButton() {
      const {text} = compareButtonState(state.compareKeys.size);
      document.getElementById('compare-films').innerHTML = `<i class="ti ti-columns-gap" aria-hidden="true"></i> ${text}`;
      if (state.compareKeys.size) setCompareMode(true);
    }
    function setCompared(key, checked) {
      if (checked) state.compareKeys.add(key);
      else state.compareKeys.delete(key);
      document.querySelectorAll(`.film[data-key="${CSS.escape(key)}"] .comparison-check`).forEach(check => { check.checked = checked; });
      updateCompareButton();
    }
    document.getElementById('clear-compare').addEventListener('click', () => {
      [...state.compareKeys].forEach(key => setCompared(key, false));
      setCompareMode(false);
      bootstrap.Modal.getInstance(document.getElementById('compare-modal'))?.hide();
    });
    // The film count per service in the sidebar; the statistics themselves are on /stats.
    function updateStats() {
      updateProviderFilmCounts(state.films, document.querySelectorAll('.provider-film-count[data-provider-count]'));
      reorderProviders();
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
      renderFilms();
    }
    // The page does not reload on a country switch: relabel the services from the new country's scan.
    function showFreeServices(names) {
      freeServices.clear();
      names.forEach(name => freeServices.add(name));
      document.querySelectorAll('[data-provider-label]').forEach(label => {
        const isFree = freeServices.has(label.dataset.providerLabel);
        const tag = label.querySelector('.free-tag');
        if (isFree && !tag) label.querySelector('.provider-name').insertAdjacentHTML('beforeend', '<span class="free-tag pill pill-ok">Mostly free</span>');
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
      if (job.status === 'running') scanState.resultsReceived += (job.results || []).length;
      const pollSignature = `${job.status}|${job.completed}|${job.stats?.total || 0}|${job.unavailable?.length || 0}|${job.failed?.length || 0}`;
      scanState.pollDelay = pollSignature === scanState.lastPollSignature ? Math.min(scanState.pollDelay + 250, 2000) : 350;
      scanState.lastPollSignature = pollSignature;
      if (job.failed?.length) {
        document.getElementById('status-message').textContent =
          `${job.message} ${job.failed.length} lookup${job.failed.length === 1 ? '' : 's'} failed.`;
      }
      if (job.source_name) { document.getElementById('source-name').textContent = job.source_name; document.getElementById('result-meta').hidden = false; document.getElementById('film-filters').hidden = false; }
      if (state.films.length) { showResultTools(); updateStats(); }
      if (job.status === 'complete' || job.status === 'cancelled') { if (job.status === 'complete') setProgress(100); else document.getElementById('progress-bar').classList.add('cancelled'); document.getElementById('progress-count').textContent = job.status === 'complete' ? 'Complete' : 'Cancelled'; showScanButton();       if (job.status === 'complete') {
        scanState.rescanInProgress = false;
        replaceWithScanResults(job.results, job.unavailable, job.changes, job.last_updated, job.free_services);
      }
      // The server moves favorites saved under "Title|Year" to the TMDB id after a scan.
      if (job.status === 'complete') loadFavorites().then(renderFilms).then(() => openPendingFilm(true));
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
      if (previous) showToast(`Removed “${previous.title || film?.title || 'film'}” from favorites.`, false, () => restoreFavorite(previous));
      const fields = document.getElementById('modal-favorite-fields');
      if (fields?.dataset.key === key) fields.innerHTML = state.favorites.has(key) ? favoriteFields(key, state.favorites.get(key).title || film?.title || '', state.favorites.get(key)) : '';
      // The redraw replaces the card: put the focus back on the same star.
      if (hadFocus) results.querySelector(`.film[data-key="${CSS.escape(key)}"] .favorite`)?.focus();
      document.querySelectorAll(`.modal-favorite[data-key="${CSS.escape(key)}"]`).forEach(modalButton => {
        const active = state.favorites.has(key);
        modalButton.innerHTML = `<i class="ti ${active ? 'ti-heart-filled' : 'ti-heart'}" aria-hidden="true"></i> ${favoriteLabel(active)}`;
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
      showToast(`“${previous.title}” is back in your favorites.`);
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
    // While open on a phone the panel is a modal dialog: the page behind it is inert.
    const pageBehindPanel = () => [document.querySelector('main > header'), ...document.querySelectorAll('.workspace > section, .skip-link')].filter(Boolean);
    const setPanelModal = on => {
      ['role', 'aria-modal'].forEach((name, i) => on ? providerPanel.setAttribute(name, ['dialog', 'true'][i]) : providerPanel.removeAttribute(name));
      pageBehindPanel().forEach(element => { element.inert = on; });
    };
    const closeProviderPanel = () => {
      if (!providerPanel?.classList.contains('show')) return;
      providerPanel.classList.remove('show');
      setPanelModal(false);
      providerToggle?.setAttribute('aria-expanded', 'false');
      if (providerPanel.contains(document.activeElement)) providerToggle?.focus();
    };
    const openProviderPanel = () => {
      providerPanel?.classList.add('show');
      // On the desktop the panel is an ordinary sidebar and the page stays usable.
      if (window.innerWidth <= 800) setPanelModal(true);
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
    // "Also on your services in United Kingdom (Netflix)", from stored scan data; filled in when it arrives.
    async function showElsewhere(tmdbId, key, own) {
      let byCountry;
      try {
        const response = await fetch(`/api/films/${encodeURIComponent(tmdbId)}/countries`);
        if (!response.ok) return;
        byCountry = await response.json();
      } catch {
        return;
      }
      const target = document.getElementById('film-elsewhere');
      // The dialog may show another film by now.
      if (!target || document.getElementById('modal-favorite-fields')?.dataset.key !== key) return;
      const places = elsewhereOnServices(byCountry, own, document.getElementById('country-select').value);
      if (!places.length) return;
      const names = new Intl.DisplayNames(['en'], {type: 'region'});
      places.sort(([a], [b]) => (names.of(a) || a).localeCompare(names.of(b) || b));
      const shown = places.slice(0, 6).map(([country, services]) => `${escapeHtml(names.of(country) || country)} (${escapeHtml(services.join(', '))})`);
      if (places.length > 6) shown.push(`${places.length - 6} more`);
      target.innerHTML = `Also on your services in ${shown.join(', ')}.<span class="film-modal-note">Watching there needs a VPN or being in that country.</span>`;
      target.hidden = false;
    }
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
      const keywords = film.keywords?.length ? `<p class="film-modal-keywords">${escapeHtml(film.keywords.slice(0, 5).join(', '))}</p>` : '';
      // The user's own services first; the other services fold away when there is at least one own.
      const own = mySubscriptions();
      const offers = film.providers || {};
      const pick = mine => Object.fromEntries(Object.entries(offers).filter(([name]) => own.has(name) === mine));
      const rows = list => availabilityByOffer(list, window.WATCHLIST_CONFIG.providerLogos, window.WATCHLIST_CONFIG.logoBaseUrl, own);
      const otherCount = Object.keys(pick(false)).length;
      const providerRows = Object.keys(pick(true)).length
        ? rows(pick(true)) + (otherCount ? `<details class="film-other-services"><summary>Other services (${otherCount})</summary>${rows(pick(false))}</details>` : '')
        : rows(offers);
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
      // Watchlist films TMDB recommends for this one that the user can watch now.
      const similar = similarOnServices(film, state.films, own, watchedKeys());
      const similarLine = similar.length
        ? `<p class="film-modal-similar">Similar on your services: ${similar.map(item => `<button class="film-link series-pick" type="button" data-key="${escapeHtml(filmKey(item))}">${escapeHtml(item.title)}${item.year ? ` (${numberText(item.year)})` : ''}</button> · ${escapeHtml(includedOn(item, own))}`).join(', ')}</p>`
        : '';
      const upcoming = upcomingText(film);
      const releaseLine = upcoming ? `<p class="film-modal-release">Coming ${escapeHtml(upcoming)}</p>` : '';
      const poster = film.poster_path ? `<img class="film-modal-poster" src="${imageBaseUrl}${escapeHtml(film.poster_path)}" alt="Poster for ${escapeHtml(film.title)}">` : '';
      const favoriteButtonClass = state.favorites.has(key) ? 'btn-accent' : 'btn-outline-secondary';
      const selectedForCompare = state.compareKeys.has(key);
      // Where to watch comes first: the own services and the actions, then the story and the rest.
      document.getElementById('film-details-content').innerHTML = `<div class="film-modal-layout">${poster}<div><p class="film-modal-meta">${numberText(film.year, 'Year unknown')}${numberText(film.rating) ? ` · TMDB ${Number(film.rating).toFixed(1)}/10` : ''}${numberText(film.runtime) ? ` · ${numberText(film.runtime)} min` : ''}${numberText(film.letterboxd_rating) ? ` · Letterboxd ${Number(film.letterboxd_rating).toFixed(2)}/5` : ''}${film.certification ? ` · rated ${escapeHtml(film.certification)}` : ''}</p><div class="film-modal-watch">${providerRows || '<p class="empty">No service data available.</p>'}${changeBadgesFor(film, selectedProviders(providerInputs)) ? `<p class="provider-changes">${changeBadgesFor(film, selectedProviders(providerInputs))}</p>` : ''}</div><div class="film-modal-actions">${watchLink}<button class="btn btn-sm ${favoriteButtonClass} modal-favorite" type="button" data-key="${escapeHtml(key)}"><i class="ti ${state.favorites.has(key) ? 'ti-heart-filled' : 'ti-heart'}" aria-hidden="true"></i> ${favoriteLabel(state.favorites.has(key))}</button><button class="btn btn-sm btn-outline-secondary modal-compare" type="button" data-key="${escapeHtml(key)}"><i class="ti ti-columns-gap" aria-hidden="true"></i> ${selectedForCompare ? 'Remove from comparison' : 'Add to comparison'}</button></div></div></div><div class="film-modal-about"><p>${escapeHtml(film.overview || 'No description available.')}</p><p class="film-modal-genres">${escapeHtml((film.genres || []).join(', ') || 'No genres available.')}</p>${releaseLine}${credits}${seriesLine}${similarLine}<p class="film-modal-elsewhere" id="film-elsewhere" hidden></p>${keywords}<p class="film-modal-links">${film.tmdb_url ? `<a class="film-link" href="${escapeHtml(film.tmdb_url)}" target="_blank" rel="noreferrer"><i class="ti ti-brand-tmdb" aria-hidden="true"></i> TMDB</a>` : ''}${trailerLink}<a class="film-link" href="${letterboxdSearch}" target="_blank" rel="noreferrer"><i class="ti ti-device-tv" aria-hidden="true"></i> Search Letterboxd</a></p></div><div id="modal-favorite-fields" data-key="${escapeHtml(key)}">${savedFavorite ? favoriteFields(key, film.title, savedFavorite) : ''}</div>`;
      if (film.tmdb_id) showElsewhere(film.tmdb_id, key, own);
      const detailsOpen = document.getElementById('film-details-modal').classList.contains('show');
      openModal('film-details-modal', opener);
      setFilmAddress(key, !detailsOpen);
    }
    // The skip link moves the focus without a #results in the address: going back to a #fragment entry
    // would pull the focus away from the card the details were opened from.
    document.querySelector('.skip-link')?.addEventListener('click', event => { event.preventDefault(); results.focus(); });
    // The details window has an address (?film=<key>): links open in a new tab, Back closes it, shared links open it.
    let filmPushed = false;  // opening added a history entry, so closing goes back instead of adding another
    function setFilmAddress(key, push = false) {
      const url = new URL(location.href);
      if ((url.searchParams.get('film') || null) === key) return;
      if (key) url.searchParams.set('film', key); else url.searchParams.delete('film');
      if (push) { history.pushState(history.state, '', url); filmPushed = true; } else history.replaceState(history.state, '', url);
    }
    document.getElementById('film-details-modal').addEventListener('hidden.bs.modal', () => {
      if (!new URL(location.href).searchParams.has('film')) return;
      if (filmPushed) { filmPushed = false; history.back(); } else setFilmAddress(null);
    });
    window.addEventListener('popstate', () => {
      filmPushed = false;
      const key = new URL(location.href).searchParams.get('film');
      if (key) showFilmDetails(key, results);
      else bootstrap.Modal.getInstance(document.getElementById('film-details-modal'))?.hide();
    });
    document.addEventListener('click', event => {
      const link = event.target.closest('a.film-open');
      // Middle, Ctrl, Cmd and Shift clicks keep the browser's own behaviour: a new tab or window.
      if (!link || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
      showFilmDetails(link.dataset.key, link);
    });
    // Filters may have changed since the link was drawn; refresh it before the browser (or a screen reader) uses it.
    const refreshFilmLink = event => {
      const link = event.target.closest?.('a.film-open');
      if (link) link.href = filmHref(location.href, link.dataset.key);
    };
    document.addEventListener('pointerdown', refreshFilmLink);
    document.addEventListener('focusin', refreshFilmLink);
    // A shared ?film= link opens once the film is loaded; after the last data arrives a missing film gets a note.
    let pendingFilm = new URL(location.href).searchParams.get('film');
    function openPendingFilm(final = false) {
      if (!pendingFilm) return;
      const key = pendingFilm;
      if ([...state.films, ...state.unavailable].some(film => filmKey(film) === key)) {
        pendingFilm = null;
        showFilmDetails(key, results);
      } else if (final) {
        pendingFilm = null;
        setFilmAddress(null);
        showToast('That film is not on this watchlist (or not in this country).', true);
      }
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
        age: document.getElementById('age-filter').dataset.pending || document.getElementById('age-filter').value,
        lang: document.getElementById('language-filter').dataset.pending || document.getElementById('language-filter').value,
        lb: document.getElementById('letterboxd-filter').value,
        origin: document.getElementById('origin-filter').dataset.pending || document.getElementById('origin-filter').value,
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
      // Values equal to the page's default stay out of the link.
      const defaults = {availability: 'available', sort: 'rating'};
      Object.entries(values).forEach(([name, value]) => {
        const isDefault = name in defaults ? value === defaults[name] : ['all', '0', 'any'].includes(value);
        if (value && !isDefault) url.searchParams.set(name, value);
        else url.searchParams.delete(name);
      });
      history.replaceState({}, '', url);
    }
    // Only 'input': a 'change' event also fires when a text field loses focus, and redrawing the
    // cards at that moment (on mousedown) swallowed the first click on a card or a star.
    // Typing in the search redraws only after a short pause, not on every key.
    let searchTimer;
    document.getElementById('film-search').addEventListener('input', () => { clearTimeout(searchTimer); searchTimer = setTimeout(renderFilms, 150); });
    ['exclusive-filter', 'availability-filter', 'kind-filter', 'genre-filter', 'keyword-filter', 'age-filter', 'language-filter', 'origin-filter', 'letterboxd-filter', 'runtime-filter', 'year-from', 'year-to', 'min-rating', 'min-votes', 'media-filter', 'change-filter', 'provider-count-filter'].forEach(id => document.getElementById(id).addEventListener('input', renderFilms));
    const initialUrl = new URL(location.href).searchParams;
    const setInitial = (id, parameter, fallback) => {
      const element = document.getElementById(id);
      const value = initialUrl.get(parameter) ?? fallback;
      if (element && (!element.options || [...element.options].some(option => option.value === value))) element.value = value;
      else if (element && ['genre-filter', 'keyword-filter', 'age-filter', 'language-filter', 'origin-filter'].includes(id) && value !== 'all') element.dataset.pending = value;
    };
    ['genre-filter', 'keyword-filter', 'age-filter', 'language-filter', 'origin-filter'].forEach(id => document.getElementById(id).addEventListener('input', event => delete event.target.dataset.pending));
    setInitial('film-search', 'q', window.WATCHLIST_CONFIG.initialFilters.query);
    setInitial('availability-filter', 'availability', window.WATCHLIST_CONFIG.initialFilters.availability);
    setInitial('kind-filter', 'kind', window.WATCHLIST_CONFIG.initialFilters.kind);
    setInitial('sort-order', 'sort', window.WATCHLIST_CONFIG.initialFilters.sort);
    setInitial('min-rating', 'rating', window.WATCHLIST_CONFIG.initialFilters.min_rating);
    setInitial('min-votes', 'votes', '0');
    setInitial('match-mode', 'match', 'any');
    setInitial('genre-filter', 'genre', 'all');
    setInitial('keyword-filter', 'keyword', 'all');
    setInitial('age-filter', 'age', 'all');
    setInitial('language-filter', 'lang', 'all');
    setInitial('letterboxd-filter', 'lb', '0');
    setInitial('origin-filter', 'origin', 'all');
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
    const toolsToggle = document.getElementById('tools-toggle');
    toolsToggle?.addEventListener('click', () => {
      const open = document.body.classList.toggle('tools-open');
      toolsToggle.setAttribute('aria-expanded', String(open));
      if (open) document.getElementById('result-tools').scrollIntoView({block: 'start'});
    });
    // The sync panel closes on a click outside it and on Escape, like a menu.
    const syncPanel = document.getElementById('sync');
    document.addEventListener('click', event => { if (syncPanel.open && !syncPanel.contains(event.target)) syncPanel.open = false; });
    syncPanel.addEventListener('keydown', event => {
      if (event.key !== 'Escape' || !syncPanel.open) return;
      syncPanel.open = false;
      document.getElementById('sync-toggle').focus();
    });
    localStorage.removeItem('watchlistLayout');  // "Wide view" is gone; forget the old choice
    // The header slims down once the page scrolls.
    const appHeader = document.getElementById('app-header');
    addEventListener('scroll', () => appHeader.classList.toggle('compact', scrollY > 8), {passive: true});
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
          if (!response.ok) throw new Error(`Could not import “${movie.title}”.`);
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
        openPendingFilm(true);
      }
    });
