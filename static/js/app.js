import {dateTime, escapeHtml, numberText} from './ui.js';
import {createAppState, createScanState} from './state.js';
import {bestAvailability} from './statistics.js';
import {serviceGroup} from './catalog.js';
import {emptyLink} from './link-filters.js';
import {similarOnServices} from './similar.js';
import {bestIndexes, favoriteFields, filmCard, filmHref, renderResults, runtimeText} from './rendering.js';
import './register-sw.js';
import {scanProblem} from './problems.js';
import {renderViews, wireViews} from './saved-views.js';
import {showDeadlines} from './deadlines.js';
import {TONIGHT_CHIPS, nowOnText, pickFilm, pickReason, recentlyGone, tonightRows} from './events.js';
import {COST, readFilters} from './filters.js';
import {createFilterBar, initPopovers} from './filterbar.js';
import {baseCounts, bestRelaxation, comingSoon, elsewhereOnServices, filmKey, filterFilms, sortFilms, sortRatings} from './filtering.js';
import {updateScanFeedback} from './scans.js';
import {abroadFilm, abroadForFilm, abroadHtml, abroadRows, abroadServices} from './abroad.js';
import {NAV_KEYS, columnsFromTops, nextIndex, nextInRows} from './gridnav.js';
import {drawerHtml, letterboxdUrl, seriesOrder} from './drawer.js';

const imageBaseUrl = window.WATCHLIST_CONFIG.imageBaseUrl;
const scanState = createScanState();
const state = createAppState();
    const rentalShops = new Set(window.WATCHLIST_CONFIG.rentalShops || []);
    const freeServices = new Set(window.WATCHLIST_CONFIG.freeServices || []);
    // The services saved in Settings for the country shown in the header.
    const mySubscriptions = () => new Set(window.WATCHLIST_CONFIG.subscriptions?.[document.getElementById('country-select').value] || []);
    // The ticked services: one source for the grid, Tonight and the details. A link's providers= wins.
    const linkProviders = new URL(location.href).searchParams.get('providers');
    state.selected = linkProviders !== null ? new Set(linkProviders.split(',').filter(Boolean)) : mySubscriptions();
    state.genres = {include: new Set(), exclude: new Set()};
    state.seed = Math.floor(Math.random() * 2 ** 31);  // "Random" keeps one order per visit
    const filterBar = createFilterBar({state, config: window.WATCHLIST_CONFIG, mySubscriptions, freeServices, rentalShops, onChange: () => renderFilms()});
    initPopovers(document);
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
    const watchedKeys = () => new Set([
      ...[...state.favorites.values()].filter(film => film.status === 'watched').map(film => film.key),
      ...[...state.flags].filter(([, entry]) => entry.flag === 'watched').map(([key]) => key),
    ]);
    // "Not now": hidden until the date the server gave it.
    const hiddenKeys = () => new Set([...state.flags].filter(([, entry]) => entry.flag === 'not_now' && entry.until > Date.now() / 1000).map(([key]) => key));
    // The dot in the header: nothing to see while the data is fresh; yellow when old, red after an error.
    function setSync(name, text) {
      document.getElementById('sync-toggle').dataset.state = name;
      document.getElementById('sync-label').textContent = text;
    }
    // One place decides the header's state from the age of the data; it runs again when the new scan has arrived.
    function updateSyncLabel(failed = false) {
      const age = state.lastScan ? Date.now() / 1000 - state.lastScan : Infinity;
      if (failed) setSync('error', 'Scan failed');
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
    }
    function showScanRunning() {
      setSync('running', 'Checking…');
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
    function setProgress(percent) {
      const bar = document.getElementById('progress-bar');
      bar.style.width = `${percent}%`;
      bar.parentElement.setAttribute('aria-valuenow', String(percent));
      if (document.getElementById('sync-toggle').dataset.state === 'running') setSync('running', `${Math.round(percent)}%`);
    }
    // Bootstrap does not give the focus back after a dialog: return it to the control that opened it.
    // A redrawn card has a new button, so look it up again by the film key.
    const modalOpeners = new Map();
    let lastDrawerKey = null;  // the film the drawer showed last
    function openModal(id, opener = document.activeElement) {
      modalOpeners.set(id, opener);
      bootstrap.Modal.getOrCreateInstance(document.getElementById(id)).show();
    }
    ['film-details-modal', 'trailer-modal', 'compare-modal'].forEach(id => {
      document.getElementById(id).addEventListener('hidden.bs.modal', () => {
        const opener = modalOpeners.get(id);
        modalOpeners.delete(id);
        if (!opener || opener === document.body) return;
        // After paging through the drawer the focus goes to the film that was shown last, not the one that opened it.
        const key = (id === 'film-details-modal' && lastDrawerKey) || opener.dataset?.key;
        const shown = key && document.querySelector(`#results .film-open[data-key="${CSS.escape(key)}"]`);
        const target = shown || (opener.isConnected ? opener : null);
        if (shown) { activeKey = key; applyRoving(); }
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
    // ---- Abroad: films your ticked services have in another country but not at home ----
    state.abroad = null;
    let abroadLoadedFor = '';
    function ensureAbroad() {
      const country = document.getElementById('country-select').value;
      const services = [...state.selected].sort().join(',');
      const wanted = `${country}|${services}`;
      if (wanted === abroadLoadedFor || !services) return;
      abroadLoadedFor = wanted;
      fetch(`/api/abroad?country=${encodeURIComponent(country)}&services=${encodeURIComponent(services)}`)
        .then(response => (response.ok ? response.json() : {}), () => ({}))
        .then(data => { if (abroadLoadedFor === wanted) { state.abroad = data; renderFilms(); } });
    }
    const abroadOnFor = () => (VIEW === 'tonight' ? localStorage.getItem('abroadOn') === '1' : document.getElementById('where-filter').value !== 'all');
    const abroadFor = film => abroadForFilm(state.abroad?.[filmKey(film)], document.getElementById('country-select').value, code => regionLabel.of(code) || code);
    // With the switch on, every card also shows your services that have the film abroad.
    const abroadList = film => (abroadOnFor() ? abroadServices(state.abroad?.[filmKey(film)], document.getElementById('country-select').value, code => regionLabel.of(code) || code) : []);
    // Films with an abroad entry that are not already shown as films you can watch here (those count as "here").
    const abroadCandidates = shownKeys => (state.abroad ? [...state.films, ...state.unavailable].filter(film => state.abroad[filmKey(film)] && !shownKeys.has(filmKey(film))).map(film => abroadFilm(film, state.abroad[filmKey(film)])) : []);
    // Filter the state, then draw the cards from the result. Filters never read card attributes.
    // "+4 coming soon · +2 to check" beside the count; the matches to check arrive after the films (not needed to draw).
    let comingCount = 0;
    let toCheck = 0;
    function baseLine(coming = comingCount) {
      comingCount = coming;
      const extra = [coming ? `+${coming} coming soon` : '', toCheck ? `<a href="/settings/matches">+${toCheck} to check</a>` : ''].filter(Boolean);
      document.getElementById('base-extra').innerHTML = extra.length ? ` · ${extra.join(' · ')}` : '';
    }
    const VIEW = window.WATCHLIST_CONFIG.view;  // "tonight" (start page) or "watchlist"
    // The switch shows how many films would come in; the cost segments show their abroad share while it is on.
    function showAbroadControls(filters, context, candidates, count, where) {
      const toggle = document.getElementById('abroad-toggle');
      const on = where !== 'all';
      toggle.setAttribute('aria-pressed', String(on));
      document.getElementById('abroad-count').textContent = count ? `+${count}` : '';
      toggle.setAttribute('aria-disabled', String(!count && !on));
      toggle.title = !count && !on ? 'No extra films abroad on your services' : 'Also show films available on your services in other countries (needs a VPN)';
      const note = document.getElementById('vpn-count');
      note.hidden = !on;
      document.getElementById('vpn-n').textContent = count;
      document.querySelectorAll('[data-cost-count]').forEach(span => {
        const note = document.querySelector(`[data-cost-abroad="${span.dataset.costCount}"]`);
        if (note) note.hidden = true;
        if (!on) return;
        const [availability, kind] = COST[span.dataset.costCount] || COST.all;
        const extra = filterFilms(candidates, [], {...filters, availability, kind}, context).films.length;
        const base = Number(span.textContent.replace(/\D.*/, '')) || 0;
        span.textContent = String(base + extra);
        if (note && extra) { note.textContent = `incl. ${extra} abroad`; note.hidden = false; }
      });
    }
    function renderFilms() {
      if (!state.films.length && !state.unavailable.length) return;
      if (VIEW === 'tonight') {
        renderTonightPage();
        results.setAttribute('aria-busy', 'false');
        openPendingFilm();
        return;
      }
      // A "best way to watch" link looks at every service, not only the ticked ones (rent or buy is rarely on yours).
      const selected = state.link.availability.length ? new Set(state.films.flatMap(film => Object.keys(film.providers || {}))) : state.selected;
      const filters = {...readFilters(document, state.favoritesOnly, {include: [...state.genres.include], exclude: [...state.genres.exclude]}), mode: state.matchMode || 'any', link: state.link};
      // Best way to watch, for the links from the stats page.
      const ownGroups = new Set([...mySubscriptions()].map(serviceGroup));
      const today = new Date().toISOString().slice(0, 10);
      const filterContext = {selected, favorites: state.favorites, seed: state.seed, hiddenKeys: hiddenKeys(), availabilityOf: film => bestAvailability(film, ownGroups, today)};
      ensureAbroad();
      const view = filterFilms(state.films, state.unavailable, filters, filterContext);
      // The abroad films, sorted and filtered like the others, listed after the films you can watch here.
      const hereKeys = new Set(view.films.map(filmKey));
      const abroadView = filterFilms(abroadCandidates(hereKeys), [], filters, filterContext);
      const where = filters.where || 'all';
      const abroadCount = abroadView.films.length;
      if (where === 'both') {
        abroadView.films.forEach(film => view.sectionOf.set(filmKey(film), 'All'));
        view.films = [...view.films, ...abroadView.films];
        view.visibleCount += abroadCount;
      } else if (where === 'abroad') {
        abroadView.films.forEach(film => view.sectionOf.set(filmKey(film), 'All'));
        view.films = abroadView.films;
        view.visibleCount = abroadCount;
      }
      state.view = view;
      // A redraw (e.g. when a scan finishes) replaces the note field someone is typing in; carry the text and cursor over.
      const heldKey = document.activeElement?.closest?.('#results [data-key]')?.dataset.key;
      const typing = document.activeElement?.matches('#results .favorite-note') ? document.activeElement : null;
      const typed = typing && {key: typing.dataset.key, value: typing.value, start: typing.selectionStart, end: typing.selectionEnd};
      renderResults(view, {results, unavailableResults: document.getElementById('unavailable-results')}, {
        imageBaseUrl,
        providerLogos: window.WATCHLIST_CONFIG.providerLogos,
        logoBaseUrl: window.WATCHLIST_CONFIG.logoBaseUrl,
        selected,
        favorites: state.favorites,
        watched: watchedKeys(),
        hiddenKeys: hiddenKeys(),
        compareKeys: state.compareKeys,
        greyKeys: greyKeys(),
        favoritesOnly: state.favoritesOnly,
        viewMode: viewMode(),
        pageHref: location.href,
        country: document.getElementById('country-select').value,
        countryName: code => regionLabel.of(code) || code,
        abroadFor,
        abroadList,
      });
      const note = typed && results.querySelector(`.favorite-note[data-key="${CSS.escape(typed.key)}"]`);
      if (note) { note.value = typed.value; note.focus(); note.setSelectionRange(typed.start, typed.end); }
      applyRoving();
      if (heldKey && !note && document.activeElement === document.body) results.querySelector(`.film-open[data-key="${CSS.escape(heldKey)}"]`)?.focus();
      openPendingFilm();
      document.getElementById('unavailable-panel').hidden = view.unavailable.length === 0;
      document.getElementById('unavailable-badge').textContent = view.unavailable.length;
      document.getElementById('visible-count').textContent = view.visibleCount;
      const base = baseCounts(state.films, state.unavailable, today);
      document.getElementById('film-total').textContent = base.watchlist;
      baseLine(base.comingSoon);
      document.querySelectorAll('.filter-sheet-done span').forEach(element => { element.textContent = view.visibleCount; });
      filterBar.updateCounts(state.films, filters, filterContext);
      showAbroadControls(filters, filterContext, abroadCandidates(hereKeys), abroadCount, where);
      filterBar.fitBar();
      results.setAttribute('aria-busy', 'false');
      renderChanges();
      drawViews();
      renderComingSoon();
      document.getElementById('favorite-status-filter').hidden = !state.favoritesOnly;
      document.getElementById('favorites-empty')?.toggleAttribute('hidden', !(state.favoritesOnly && view.visibleCount === 0 && view.unavailable.length === 0));
      document.getElementById('favorites-banner').hidden = !state.favoritesOnly;
      // "Why is my film missing?": say so and offer the way out instead of an empty page.
      const nothing = view.visibleCount === 0 && view.unavailable.length === 0;
      document.getElementById('filters-empty').hidden = state.favoritesOnly || !nothing;
      document.getElementById('empty-subscriptions').hidden = selected.size > 0;
      // Name the one filter that keeps the most films out, with a button that removes just that one.
      const way = nothing && selected.size ? bestRelaxation(state.films, filters, filterContext, relaxations()) : null;
      document.getElementById('empty-relax').hidden = !way;
      document.getElementById('filters-empty-hint').textContent = way ? `Without the ${way.label} filter there would be ${way.count}.` : 'No film matches these filters.';
      if (way) { document.getElementById('empty-relax').dataset.filter = way.id; document.getElementById('empty-relax').textContent = `Remove ${way.label}`; }
      syncUrl();
      filterBar.updateChips();
    }
    // Filters an empty result could drop: [{id, label, open(filters, context)}]; id is the control or "genres".
    function relaxations() {
      const reset = {
        'film-search': ['search', {query: ''}], 'cost-filter': ['cost', {availability: 'available', kind: 'all'}],
        'runtime-filter': ['runtime', {maxRuntime: 0}], 'lb-filter': ['Letterboxd rating', {minLetterboxd: 0}], 'tmdb-filter': ['TMDB rating', {minRating: 0}],
        'year-from': ['year', {yearFrom: 0}], 'year-to': ['year', {yearTo: 9999}], 'min-votes': ['votes', {minVotes: 0}],
        'keyword-filter': ['keyword', {keyword: 'all'}], 'media-filter': ['trailer', {media: 'all'}], 'change-filter': ['changes', {change: 'all'}],
        'provider-count-filter': ['number of services', {minimumProviders: 0, exclusive: false}],
        'age-filter': ['age rating', {age: 'all'}], 'language-filter': ['language', {language: 'all'}], 'origin-filter': ['country', {origin: 'all'}],
      };
      const candidates = Object.entries(reset).filter(([id]) => {
        const input = document.getElementById(id);
        return input && (input.type === 'checkbox' ? input.checked : input.dataset.default !== undefined ? input.value !== input.dataset.default : input.options ? input.value !== input.options[0].value : Boolean(input.value));
      }).map(([id, [label, values]]) => ({id, label, open: (f, c) => [{...f, ...values}, c]}));
      if (state.genres.include.size || state.genres.exclude.size) candidates.push({id: 'genres', label: 'genre', open: (f, c) => [{...f, genres: {include: [], exclude: []}}, c]});
      if (JSON.stringify(state.link) !== JSON.stringify(emptyLink())) candidates.push({id: 'link', label: 'link filter', open: (f, c) => [{...f, link: emptyLink()}, c]});
      return candidates;
    }
    // Films that just left one of the user's services, from the stored changes of the last 14 days.
    function fillSelect(select, allText, values) {
      // A value from a link waits in data-pending until a scan brings films that have it.
      const wanted = select.dataset.pending || select.value;
      select.innerHTML = `<option value="all">${allText}</option>` + values.map(value => `<option value="${escapeHtml(value)}">${escapeHtml(value)}</option>`).join('');
      select.value = values.includes(wanted) ? wanted : 'all';
      if (select.value === wanted) delete select.dataset.pending;
    }
    function populateGenres() {
      filterBar.buildGenreMenu([...new Set(state.films.flatMap(film => film.genres || []))].sort());
      fillSelect(document.getElementById('keyword-filter'), 'All keywords', [...new Set(state.films.flatMap(film => film.keywords || []))].sort());
      filterBar.buildAgeChips(sortRatings([...state.films, ...state.unavailable].map(film => film.certification)));
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
      filterBar.setRatingAvailability(rated);
      document.querySelector('#sort-menu input[value="letterboxd"]').disabled = !rated;
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
    // The own services a film runs on without extra cost (for "Similar on your services").
    function includedOn(film, subscriptions) {
      return Object.entries(film.providers || {})
        .filter(([provider, kinds]) => subscriptions.has(provider) && kinds.some(kind => ['free', 'ads', 'flatrate'].includes(kind)))
        .map(([provider]) => provider).sort().join(', ');
    }
    // ---- Tonight (start page): rows of films, a context line, quick chips and "Pick for me" ----
    const tonightChips = new Set(JSON.parse(localStorage.getItem('tonightChips') || '[]'));
    const picked = new Set(JSON.parse(sessionStorage.getItem('pickedFilms') || '[]'));
    let tonightAvailable = [];
    function ago(seconds) {
      const hours = Math.floor((Date.now() / 1000 - seconds) / 3600);
      return hours < 1 ? 'just now' : hours < 48 ? `${hours} h ago` : `${Math.floor(hours / 24)} days ago`;
    }
    // Grid, Compact (posters only) or Table; the choice stays in this browser.
    const viewMode = () => localStorage.getItem('viewMode') || 'grid';
    function syncViewMode() {
      const mode = viewMode();
      document.querySelectorAll('#view-switch input').forEach(input => { input.checked = input.value === mode; });
      results.classList.toggle('view-compact', mode === 'compact');
    }
    document.getElementById('view-switch')?.addEventListener('change', event => {
      localStorage.setItem('viewMode', event.target.value);
      syncViewMode();
      renderFilms();
      // The same film stays the active one (the tab stop) and in sight after the layout changed.
      navItems().find(item => item.dataset.key === activeKey)?.scrollIntoView({block: 'nearest'});
    });
    syncViewMode();
    // Saved views: chips on Tonight and above the grid; "Save view" appears while filters are set.
    function drawViews() {
      renderViews(document.getElementById('saved-views'), {canSave: true, search: location.search});
      renderViews(document.getElementById('tonight-views'));
    }
    ['saved-views', 'tonight-views', 'views-menu'].forEach(id => wireViews(document.getElementById(id), () => location.search, drawViews));
    function renderTonightPage() {
      drawViews();
      showDeadlines(document.getElementById('deadline-banner'), window.WATCHLIST_CONFIG.deadlines, {link: true});
      const {rows, available} = tonightRows(state.films, {services: state.selected, favorites: state.favorites, skip: new Set([...watchedKeys(), ...hiddenKeys()]), chips: tonightChips, now: Date.now() / 1000});
      tonightAvailable = available;
      // With the abroad switch on (remembered in this browser) a last row lists what your services have abroad.
      ensureAbroad();
      if (abroadOnFor()) {
        const shown = new Set([...available.map(filmKey), ...watchedKeys(), ...hiddenKeys()]);
        const checks = TONIGHT_CHIPS.filter(([id, , check]) => tonightChips.has(id) && check).map(([, , check]) => check);
        const list = sortFilms(abroadCandidates(shown).filter(film => checks.every(check => check(film))), 'priority', {favorites: state.favorites});
        if (list.length) rows.push({id: 'abroad', title: 'On your services abroad', films: list, href: '/watchlist?where=abroad'});
      }
      document.getElementById('context-text').innerHTML = `${available.length} films available on <a href="/subscriptions">${state.selected.size} services</a>${state.lastScan ? ` · synced ${ago(state.lastScan)}` : ''}`;
      document.querySelectorAll('.quick-chip').forEach(chip => chip.setAttribute('aria-pressed', String(tonightChips.has(chip.dataset.chip))));
      const context = {imageBaseUrl, providerLogos: window.WATCHLIST_CONFIG.providerLogos, logoBaseUrl: window.WATCHLIST_CONFIG.logoBaseUrl, selected: state.selected, favorites: state.favorites, compareKeys: state.compareKeys, greyKeys: new Set(), favoritesOnly: false, pageHref: location.href, country: document.getElementById('country-select').value, countryName: code => regionLabel.of(code) || code, abroadFor, abroadList};
      const section = (row, film) => (row.id === 'free' || (row.id === 'new' && !Object.values(film.providers || {}).flat().includes('flatrate')) ? 'Free' : 'Paid');
      document.getElementById('tonight-rows').innerHTML = rows.map(row => `<section class="film-row" aria-labelledby="row-${escapeHtml(row.id)}"><div class="film-row-head"><h2 id="row-${escapeHtml(row.id)}">${escapeHtml(row.title)} <span class="row-count">${row.films.length}</span></h2><a class="film-link" href="${escapeHtml(row.href)}">See all <span aria-hidden="true">→</span></a></div><div class="row-scroller"><button class="row-arrow row-prev" type="button" aria-label="Scroll ${escapeHtml(row.title)} back" tabindex="-1"><i class="ti ti-chevron-left" aria-hidden="true"></i></button><div class="row-track films">${row.films.slice(0, 24).map(film => filmCard(film, section(row, film), context)).join('')}</div><button class="row-arrow row-next" type="button" aria-label="Scroll ${escapeHtml(row.title)} on" tabindex="-1"><i class="ti ti-chevron-right" aria-hidden="true"></i></button></div></section>`).join('')
        || '<p class="empty">No film fits. Tick more services or turn a quick filter off.</p>';
      applyTonightRoving();
      const gone = recentlyGone(state.changes, [...state.films, ...state.unavailable], state.selected, Date.now() / 1000);
      document.getElementById('tonight-gone').hidden = gone.length === 0;
      document.getElementById('tonight-gone-count').textContent = gone.length;
      document.getElementById('tonight-gone-list').innerHTML = gone.map(entry => {
        const title = escapeHtml(entry.title) + (entry.year ? ` (${numberText(entry.year)})` : '');
        const name = entry.film ? `<a class="film-link film-open" href="${escapeHtml(filmHref(location.href, entry.key))}" data-key="${escapeHtml(entry.key)}">${title}</a>` : title;
        return `<li>${name} · gone from ${escapeHtml(entry.providers.join(', '))} ${new Date(entry.created * 1000).toLocaleDateString([], {dateStyle: 'medium'})} · ${escapeHtml(nowOnText(entry))}</li>`;
      }).join('');
    }
    document.querySelector('.tonight-chips')?.addEventListener('click', event => {
      const chip = event.target.closest('.quick-chip');
      if (!chip) return;
      if (tonightChips.has(chip.dataset.chip)) tonightChips.delete(chip.dataset.chip); else tonightChips.add(chip.dataset.chip);
      localStorage.setItem('tonightChips', JSON.stringify([...tonightChips]));
      renderTonightPage();
    });
    // Rows scroll sideways; the arrows move one screen of cards.
    document.getElementById('tonight-rows')?.addEventListener('click', event => {
      const arrow = event.target.closest('.row-arrow');
      if (!arrow) return;
      const track = arrow.parentElement.querySelector('.row-track');
      track.scrollBy({left: (arrow.classList.contains('row-next') ? 1 : -1) * track.clientWidth * 0.9, behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth'});
    });
    function pickForMe(opener) {
      const film = pickFilm(tonightAvailable, picked);
      if (!film) { showToast('No film fits the quick filters.', true); return; }
      picked.add(filmKey(film));
      sessionStorage.setItem('pickedFilms', JSON.stringify([...picked]));
      document.getElementById('pick-for-me').innerHTML = '<i class="ti ti-dice-5" aria-hidden="true"></i> Again';
      showFilmDetails(filmKey(film), opener);
      // The drawer covers the button, so the reason and "Pick another" sit inside it.
      const where = includedOn(film, state.selected);
      const reason = pickReason(film, where ? `on ${where}` : '');
      document.getElementById('film-details-content').insertAdjacentHTML('afterbegin', `<p class="pick-reason"><span>Picked for you${reason ? `: ${escapeHtml(reason)}` : ''}</span><button class="film-link pick-again" type="button"><i class="ti ti-dice-5" aria-hidden="true"></i> Pick another</button></p>`);
    }
    document.getElementById('film-details-content').addEventListener('click', event => {
      if (event.target.closest('.pick-again')) pickForMe(modalOpeners.get('film-details-modal'));
    });
    document.getElementById('pick-for-me')?.addEventListener('click', event => pickForMe(event.currentTarget));
    // "r" picks a film; only outside text fields and dialogs.
    document.addEventListener('keydown', event => {
      if (VIEW !== 'tonight' || event.key !== 'r' || event.ctrlKey || event.metaKey || event.altKey) return;
      if (event.target.closest('input, select, textarea, [contenteditable], .modal')) return;
      pickForMe(document.getElementById('pick-for-me'));
    });

    // ---- Changes tab of the watchlist: every stored change, newest first, filterable ----
    function renderChanges() {
      const service = document.getElementById('changes-service');
      const kind = document.getElementById('changes-kind').value;
      const mine = document.getElementById('changes-mine').checked;
      const all = (state.changes || []).filter(change => !mine || state.selected.has(change.provider));
      const services = [...new Set(all.map(change => change.provider))].sort();
      const wanted = services.includes(service.value) ? service.value : '';
      service.innerHTML = '<option value="">All services</option>' + services.map(name => `<option value="${escapeHtml(name)}">${escapeHtml(name)}</option>`).join('');
      service.value = wanted;
      const rows = all.filter(change => (!wanted || change.provider === wanted) && (!kind || change.change === kind));
      const known = new Set([...state.films, ...state.unavailable].map(filmKey));
      document.getElementById('changes-body').innerHTML = rows.map(change => {
        const title = escapeHtml(change.title) + (change.year ? ` (${numberText(change.year)})` : '');
        const film = known.has(change.film_key) ? `<a class="film-link film-open" href="${escapeHtml(filmHref(location.href, change.film_key))}" data-key="${escapeHtml(change.film_key)}">${title}</a>` : title;
        const event = change.change === 'added' ? '<span class="pill pill-ok">New</span>' : '<span class="pill pill-gone">Gone</span>';
        return `<tr><td>${new Date(change.created * 1000).toLocaleDateString([], {dateStyle: 'medium'})}</td><td>${film}</td><td>${escapeHtml(change.provider)}</td><td>${event}</td></tr>`;
      }).join('') || '<tr><td colspan="4" class="empty">No changes in the last 30 days.</td></tr>';
      document.getElementById('tab-changes-count').textContent = rows.length;
    }
    ['changes-service', 'changes-kind', 'changes-mine'].forEach(id => document.getElementById(id)?.addEventListener('change', renderChanges));
    // Films | Changes: a tab list; arrow keys move between the tabs.
    function showTab(name) {
      ['films', 'changes'].forEach(tab => {
        const button = document.getElementById(`tab-${tab}`);
        button.setAttribute('aria-selected', String(tab === name));
        button.tabIndex = tab === name ? 0 : -1;
        document.getElementById(`${tab}-panel`).hidden = tab !== name;
      });
    }
    document.querySelector('.view-tabs')?.addEventListener('click', event => {
      const tab = event.target.closest('[role=tab]');
      if (tab) showTab(tab.id.replace('tab-', ''));
    });
    document.querySelector('.view-tabs')?.addEventListener('keydown', event => {
      if (event.key !== 'ArrowRight' && event.key !== 'ArrowLeft') return;
      const next = document.getElementById(event.target.id === 'tab-films' ? 'tab-changes' : 'tab-films');
      next.focus();
      showTab(next.id.replace('tab-', ''));
    });
    // The tick boxes on the posters only show while choosing films to compare.
    // The bar at the bottom appears with the first chosen film; the boxes on the posters show while it is there.
    function setCompareMode(on) {
      document.body.classList.toggle('compare-mode', on);
    }
    function compareFilms() {
      const films = state.films.filter(film => state.compareKeys.has(filmKey(film)));
      if (films.length < 2 || films.length > 4) return showToast('Choose 2 to 4 films to compare.');
      const providers = [...new Set(films.flatMap(film => Object.keys(film.providers || {})))].sort();
      const offerCell = film => Object.entries(film.providers || {}).map(([provider, kinds]) => `${escapeHtml(provider)}: ${escapeHtml(kinds.join(', '))}`).join('<br>') || '-';
      const providerRows = providers.map(provider => `<tr><th>${escapeHtml(provider)}</th>${films.map(film => `<td>${escapeHtml((film.providers?.[provider] || []).join(', ') || '—')}</td>`).join('')}</tr>`).join('');
      // The best value of a row is marked (rating: highest, runtime: shortest, own services: most).
      const row = (label, values, show, prefer) => {
        const best = prefer ? bestIndexes(values, prefer) : [];
        return `<tr><th>${label}</th>${values.map((value, index) => `<td${best.includes(index) ? ' class="best"' : ''}>${show(value)}${best.includes(index) ? '<span class="visually-hidden"> (best)</span>' : ''}</td>`).join('')}</tr>`;
      };
      const ownCount = film => Object.keys(film.providers || {}).filter(name => state.selected.has(name)).length;
      document.getElementById('compare-table').innerHTML = `<thead><tr><th>Metric</th>${films.map(film => `<th>${escapeHtml(film.title)}</th>`).join('')}</tr></thead><tbody>${row('Year', films.map(film => film.year), value => numberText(value, '-'))}${row('Letterboxd', films.map(film => film.letterboxd_rating), value => (numberText(value) ? Number(value).toFixed(1) : '-'), 'high')}${row('TMDB', films.map(film => film.rating), value => (numberText(value) ? Number(value).toFixed(1) : '-'), 'high')}${row('Runtime', films.map(film => film.runtime), value => (numberText(value) ? `${numberText(value)} min` : '-'), 'low')}${row('On your services', films.map(ownCount), value => String(value), 'high')}<tr><th>Genres</th>${films.map(film => `<td>${escapeHtml((film.genres || []).join(', ') || '-')}</td>`).join('')}</tr><tr><th>Offers</th>${films.map(film => `<td>${offerCell(film)}</td>`).join('')}</tr>${providerRows}</tbody>`;
      openModal('compare-modal');
    }
    function updateCompareButton() {
      const count = state.compareKeys.size;
      setCompareMode(count > 0);
      const bar = document.getElementById('compare-bar');
      bar.hidden = count === 0;
      const countText = document.getElementById('compare-count');
      countText.textContent = count === 1 ? 'Pick one more' : count > 4 ? `${count} chosen: at most 4` : `${count} to compare`;
      countText.dataset.hint = String(count < 2 || count > 4);
      document.getElementById('compare-thumbs').innerHTML = state.films.filter(film => state.compareKeys.has(filmKey(film)) && film.poster_path).map(film => `<img src="${imageBaseUrl.replace("/w500", "/w92")}${escapeHtml(film.poster_path)}" alt="${escapeHtml(film.title)}">`).join('');
      document.getElementById('compare-go').disabled = count < 2 || count > 4;
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
    function showFreeServices(names) {
      freeServices.clear();
      names.forEach(name => freeServices.add(name));
      filterBar.buildServicesMenu();
    }
    // Show a finished scan: films, unavailable films and the stored availability changes.
    function replaceWithScanResults(films, unavailable, changes, lastScan, free) {
      if (free) showFreeServices(free);
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
      if (state.films.length) showResultTools();
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
    // quiet: the page started it by itself because the data is old, so no toast over the films.
    async function startScan(quiet = false) {
      scanState.rescanInProgress = state.films.length > 0;
      scanState.pendingUnavailable = [];
      if (!scanState.rescanInProgress) {
        state.films = [];
        seen.clear();
        results.setAttribute('aria-busy', 'true');
        results.innerHTML = '<div class="skeleton-grid" role="status" aria-label="Loading films"><div class="skeleton-card"><div class="skeleton-poster"></div><div class="skeleton-line"></div></div><div class="skeleton-card"><div class="skeleton-poster"></div><div class="skeleton-line"></div></div><div class="skeleton-card"><div class="skeleton-poster"></div><div class="skeleton-line"></div></div></div>';
      }
      if (!quiet) showToast(scanState.rescanInProgress ? 'Updating availability. Previous results remain visible.' : 'Starting watchlist scan...');
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
    async function loadLatestResult(request = null) {
      const country = document.getElementById('country-select').value;
      const response = await (request || fetch(`/api/latest?country=${encodeURIComponent(country)}`));
      if (!response.ok) return null;
      const snapshot = await response.json();
      // The service worker answers from its copy when the app cannot be reached: say how old the data is.
      if (response.headers.get('X-From-Cache') && snapshot.created) showToast(`Offline: showing the data from ${new Date(snapshot.created * 1000).toLocaleString([], {dateStyle: 'medium', timeStyle: 'short'})}.`);
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
      if (new URL(location.href).searchParams.get('providers') === null) state.selected = mySubscriptions();
      filterBar.buildServicesMenu();
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
      // Both requests at once: the page redraws when they are in, and a later redraw steals the keyboard focus.
      const [response, flags] = await Promise.all([
        fetch('/api/favorites'),
        fetch('/api/flags').then(answer => (answer.ok ? answer.json() : []), () => []),
      ]);
      const favorites = await response.json();
      state.favorites = new Map(favorites.map(movie => [movie.key, movie]));
      state.flags = new Map(flags.map(entry => [entry.key, entry]));
    }
    // Watched / Not now from the card menu, the details and the keys; "Undo" puts the film back for five seconds.
    async function setFlag(key, flag) {
      const before = state.flags.get(key);
      const turnOff = before?.flag === flag && (flag === 'watched' || before.until > Date.now() / 1000);
      const request = (target, kind) => (kind ? fetch(`/api/flags/${encodeURIComponent(target)}`, {method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({flag: kind})}) : fetch(`/api/flags/${encodeURIComponent(target)}`, {method: 'DELETE'}));
      const apply = async kind => {
        const response = await request(key, kind).catch(() => null);
        if (!response?.ok) { showToast('Could not save this. Reload the page and try again.', true); return false; }
        if (kind) state.flags.set(key, await response.json()); else state.flags.delete(key);
        return true;
      };
      if (!(await apply(turnOff ? null : flag))) return;
      const title = [...state.films, ...state.unavailable].find(film => filmKey(film) === key)?.title || 'Film';
      const message = turnOff ? `${title}: back on the list` : flag === 'watched' ? `${title}: hidden away` : `${title}: set aside for 30 days`;
      showToast(message, false, async () => { if (await apply(before?.flag ?? null)) renderFilms(); });
      renderFilms();
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
        modalButton.innerHTML = `<i class="ti ${active ? 'ti-heart-filled' : 'ti-heart'}" aria-hidden="true"></i><span class="tool-label">Favorite</span>`;
        const label = active ? 'Remove favorite' : 'Add to favorites';
        modalButton.title = label;
        modalButton.setAttribute('aria-label', label);
        modalButton.setAttribute('aria-pressed', String(active));
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
    document.getElementById('empty-reset').addEventListener('click', () => filterBar.resetAll());
    document.getElementById('empty-subscriptions').addEventListener('click', () => filterBar.setServices(mySubscriptions()));
    document.getElementById('empty-relax').addEventListener('click', event => {
      const id = event.currentTarget.dataset.filter;
      if (id === 'genres') { state.genres = {include: new Set(), exclude: new Set()}; populateGenres(); renderFilms(); return; }
      document.querySelector(`.filter-chip[data-filter-id="${id}"] .chip-remove`)?.click();
    });
    document.getElementById('favorites-show-all').addEventListener('click', () => setFavoritesOnly(false));
    results.addEventListener('click', event => { const favoriteButton = event.target.closest('.favorite'); if (favoriteButton) { event.preventDefault(); toggleFavorite(favoriteButton); } });
    // "Abroad on your services": from stored scan data (no TMDB request); filled in when it arrives.
    async function showElsewhere(tmdbId, key, own) {
      let byCountry;
      try {
        const response = await fetch(`/api/films/${encodeURIComponent(tmdbId)}/countries`);
        if (!response.ok) return;
        byCountry = await response.json();
      } catch {
        return;
      }
      const target = document.getElementById('film-abroad');
      // The dialog may show another film by now.
      if (!target || document.getElementById('modal-favorite-fields')?.dataset.key !== key) return;
      const regions = new Intl.DisplayNames(['en'], {type: 'region'});
      const nameOf = code => regions.of(code) || code;
      const {providerLogos, logoBaseUrl} = window.WATCHLIST_CONFIG;
      const logoOf = (name, className = 'provider-logo') => (providerLogos[name] ? `<img class="${className}" src="${escapeHtml(logoBaseUrl + providerLogos[name])}" alt="" loading="lazy">` : '');
      const rows = abroadRows(byCountry, own, document.getElementById('country-select').value, nameOf);
      if (!rows.length) return;
      target.innerHTML = abroadHtml(rows, {nameOf, logoOf});
      target.hidden = false;
      // The block lives inside "Other services": show that, and say in its line how many countries there are.
      const more = document.getElementById('film-more');
      more.hidden = false;
      const total = new Set(rows.flatMap(row => row.countries)).size;
      more.querySelector('.os-abroad').textContent = ` · ${total} abroad`;
      revealMore();
    }
    // A tooltip must stay inside the drawer: near the right edge it grows to the left.
    const placeTip = event => {
      const target = event.target.closest?.('.flag[data-tip], .svc[data-tip]');
      if (!target) return;
      const room = document.getElementById('film-details-content').getBoundingClientRect().right - target.getBoundingClientRect().left;
      target.dataset.side = room < 240 ? 'end' : 'start';
    };
    document.getElementById('film-details-content').addEventListener('pointerover', placeTip);
    document.getElementById('film-details-content').addEventListener('focusin', placeTip);
    document.getElementById('film-details-content').addEventListener('click', event => {
      const more = event.target.closest('.flag-more');
      if (!more) return;
      const grid = more.closest('.abroad-row').querySelector('.flag-grid');
      grid.hidden = !grid.hidden;
      more.setAttribute('aria-expanded', String(!grid.hidden));
    });
    const regionLabel = new Intl.DisplayNames(['en'], {type: 'region'});
    // Every ISO country name in lower case (from the browser), to keep places out of the keyword chips.
    let countryNameSet = null;
    function allCountryNames() {
      if (countryNameSet) return countryNameSet;
      const names = new Intl.DisplayNames(['en'], {type: 'region'});
      countryNameSet = new Set();
      for (const a of 'ABCDEFGHIJKLMNOPQRSTUVWXYZ') for (const b of 'ABCDEFGHIJKLMNOPQRSTUVWXYZ') {
        try { const name = names.of(a + b); if (name && name !== a + b) countryNameSet.add(name.toLowerCase()); } catch { /* not a region code */ }
      }
      return countryNameSet;
    }
    // The title of the hero shows in the header once it scrolls out of sight.
    let heroTitleWatcher = null;
    function watchHeroTitle() {
      heroTitleWatcher?.disconnect();
      const header = document.querySelector('#film-details-modal .modal-header');
      header.classList.remove('show-title');
      const title = document.getElementById('film-hero-title');
      if (!title || !('IntersectionObserver' in window)) { header.classList.add('show-title'); return; }
      heroTitleWatcher = new IntersectionObserver(([entry]) => header.classList.toggle('show-title', !entry.isIntersecting), {root: document.getElementById('film-details-content')});
      heroTitleWatcher.observe(title);
    }
    function showFilmDetails(key, opener = document.activeElement) {
      const all = [...state.films, ...state.unavailable];
      const film = all.find(item => filmKey(item) === key);
      if (!film) return;
      document.getElementById('film-details-title').textContent = film.title;
      lastDrawerKey = key;
      const country = document.getElementById('country-select').value;
      const regions = new Intl.DisplayNames(['en'], {type: 'region'});
      const own = state.selected;
      const saved = state.favorites.get(key);
      const watched = watchedKeys();
      const ctx = {
        own, country, key, watched,
        regionName: regions.of(country) || country,
        regionNames: code => regions.of(code) || code,
        logos: window.WATCHLIST_CONFIG.providerLogos, logoBaseUrl: window.WATCHLIST_CONFIG.logoBaseUrl, imageBaseUrl,
        countryNames: allCountryNames(),
        isFavorite: state.favorites.has(key),
        isSeen: state.flags.get(key)?.flag === 'watched' || saved?.status === 'watched',
        isHidden: hiddenKeys().has(key),
        inCompare: state.compareKeys.has(key),
        series: film.collection ? seriesOrder(all.filter(item => item.collection === film.collection)) : [],
        similar: similarOnServices(film, state.films, own, watched),
        serviceOf: item => includedOn(item, own).split(', ')[0],
        keyOf: filmKey,
        releaseText: upcomingText(film),
        scanAt: state.lastScan,
        favoriteFields: saved ? favoriteFields(key, film.title, saved) : '',
      };
      document.getElementById('film-details-content').innerHTML = drawerHtml(film, ctx);
      watchHeroTitle();
      if (film.tmdb_id) showElsewhere(film.tmdb_id, key, own);
      const detailsOpen = document.getElementById('film-details-modal').classList.contains('show');
      openModal('film-details-modal', opener);
      setFilmAddress(key, !detailsOpen);
    }
    // ---- Arrow keys through the films: grid, compact grid and table share one navigation ----
    const CARD_CONTROLS = '.film-open, .favorite, .card-action, .best-way-link, .best-more, .lstack';
    let activeKey = null;  // the film that holds the tab stop (roving tabindex): one stop in the whole list
    const navItems = () => [...results.querySelectorAll('article.film[data-key], tr[data-key]')];
    function applyRoving() {
      const items = navItems();
      if (!items.length) return;
      // Until a film was chosen (focus or arrow keys) the first one holds the tab stop; a choice that was filtered away falls back to it.
      const current = items.find(item => item.dataset.key === activeKey) || items[0];
      for (const item of items) item.querySelectorAll(CARD_CONTROLS).forEach(control => { control.tabIndex = item === current ? 0 : -1; });
    }
    function focusItem(item) {
      activeKey = item.dataset.key;
      applyRoving();
      item.querySelector('.film-open')?.focus();
      item.scrollIntoView({block: 'nearest'});
    }
    results.addEventListener('focusin', event => {
      const item = event.target.closest('article.film[data-key], tr[data-key]');
      if (item && item.dataset.key !== activeKey) { activeKey = item.dataset.key; applyRoving(); }
    });
    document.addEventListener('keydown', event => {
      if (!NAV_KEYS.has(event.key) || event.ctrlKey || event.metaKey || event.altKey || event.shiftKey || event.isComposing) return;
      const item = event.target.closest?.('#results article.film[data-key], #results tr[data-key]');
      // Not in a text field, a menu or a dialog: the arrows keep their own meaning there.
      if (!item || event.target.closest('input, select, textarea, [contenteditable], dialog, details[open]') || document.querySelector('.modal.show')) return;
      const items = navItems();
      const columns = results.querySelector('table.film-table') ? 1 : columnsFromTops(items.map(card => card.getBoundingClientRect().top));
      const next = nextIndex(event.key, items.indexOf(item), columns, items.length);
      if (next === null) return;
      event.preventDefault();
      focusItem(items[next]);
    });
    // The Tonight rows: ←/→ along a row, ↑/↓ to the row above or below (same position as far as it reaches).
    let tonightSpot = [0, 0];  // [row, column] of the film that holds the tab stop
    const tonightGrid = () => [...document.querySelectorAll('#tonight-rows .film-row')].map(row => [...row.querySelectorAll('article.film[data-key]')]);
    function applyTonightRoving() {
      const grid = tonightGrid();
      if (!grid.length) return;
      const row = Math.min(tonightSpot[0], grid.length - 1);
      const col = Math.min(tonightSpot[1], Math.max(grid[row].length - 1, 0));
      grid.forEach((cards, r) => cards.forEach((card, c) => card.querySelectorAll(CARD_CONTROLS).forEach(control => { control.tabIndex = r === row && c === col ? 0 : -1; })));
    }
    document.getElementById('tonight-rows')?.addEventListener('focusin', event => {
      const card = event.target.closest('article.film[data-key]');
      const grid = tonightGrid();
      const row = grid.findIndex(cards => cards.includes(card));
      if (row >= 0) { tonightSpot = [row, grid[row].indexOf(card)]; applyTonightRoving(); }
    });
    document.addEventListener('keydown', event => {
      if (!NAV_KEYS.has(event.key) || event.ctrlKey || event.metaKey || event.altKey || event.shiftKey || event.isComposing) return;
      const card = event.target.closest?.('#tonight-rows article.film[data-key]');
      if (!card || event.target.closest('input, select, textarea, [contenteditable], dialog, details[open]') || document.querySelector('.modal.show')) return;
      const grid = tonightGrid();
      const row = grid.findIndex(cards => cards.includes(card));
      const next = nextInRows(event.key, row, grid[row].indexOf(card), grid.map(cards => cards.length));
      if (!next) return;
      event.preventDefault();
      tonightSpot = next;
      applyTonightRoving();
      const target = grid[next[0]][next[1]];
      target.querySelector('.film-open')?.focus();
      target.scrollIntoView({block: 'nearest', inline: 'nearest'});
    });
    // After "+N": scroll so "Other services" ends just above the bottom edge (or starts at the top when it is taller).
    // Called again when the abroad block has loaded into it, which makes the section taller.
    let pendingMore = false;
    const detailsModal = document.getElementById('film-details-modal');
    ['hidden.bs.modal', 'pointerdown'].forEach(type => detailsModal.addEventListener(type, () => { pendingMore = false; }));
    function revealMore() {
      const box = document.getElementById('film-more');
      const body = document.querySelector('#film-details-modal .modal-body');
      if (!pendingMore || !box || !body) return;
      const section = box.getBoundingClientRect();
      const view = body.getBoundingClientRect();
      const toBottom = section.bottom - (view.bottom - 16);
      const toTop = section.top - (view.top + 8);
      const smooth = !matchMedia('(prefers-reduced-motion: reduce)').matches;
      body.scrollTo({top: body.scrollTop + Math.min(toBottom, toTop), behavior: smooth ? 'smooth' : 'auto'});
    }
    // "+N" and "Abroad" on a card open the details at "Other services".
    document.addEventListener('click', event => {
      const more = event.target.closest('[data-open-more]');
      if (!more) return;
      event.preventDefault();
      // On a phone "+N" goes straight to the full-screen sheet: the list of services needs the room.
      document.getElementById('film-details-modal').classList.toggle('is-full', matchMedia('(max-width: 800px)').matches);
      showFilmDetails(more.dataset.key, more);
      const box = document.getElementById('film-more');
      if (box) box.open = true;
      pendingMore = true;
      const modal = document.getElementById('film-details-modal');
      if (modal.classList.contains('show')) revealMore();
      else modal.addEventListener('shown.bs.modal', revealMore, {once: true});
    });
    // Touch: the first tap on a card's logo shows what it is; a second tap goes to the service. A tap elsewhere closes it.
    document.addEventListener('click', event => {
      const link = event.target.closest('.best-way-link');
      const open = document.querySelector('.best-way-link.is-open');
      if (open && open !== link) open.classList.remove('is-open');
      if (!link || !matchMedia('(pointer: coarse)').matches) return;
      if (!link.classList.contains('is-open')) {
        event.preventDefault();
        event.stopImmediatePropagation();
        link.classList.add('is-open');
      }
    }, true);
    // Touch: a long press on a card shows its action bar (compare, not now, hide); a tap elsewhere hides it.
    let pressTimer = null;
    let swallowClick = false;
    results.addEventListener('pointerdown', event => {
      if (event.pointerType !== 'touch') return;
      const card = event.target.closest('article.film');
      if (!card || event.target.closest('button, a, input')) return;
      pressTimer = setTimeout(() => {
        results.querySelectorAll('.show-actions').forEach(other => other.classList.remove('show-actions'));
        card.classList.add('show-actions');
        swallowClick = true;
        navigator.vibrate?.(10);
      }, 500);
    });
    ['pointerup', 'pointercancel', 'pointermove'].forEach(type => results.addEventListener(type, () => clearTimeout(pressTimer)));
    results.addEventListener('click', event => {
      if (!swallowClick) return;
      swallowClick = false;
      event.stopImmediatePropagation();
      event.preventDefault();
    }, true);
    document.addEventListener('pointerdown', event => {
      if (!event.target.closest('.show-actions')) results.querySelectorAll('.show-actions').forEach(card => card.classList.remove('show-actions'));
    });
    // Phone sheet: opens at 80 %. Pulling the grip or the header up makes it full screen, pulling down shrinks it or
    // closes it, a tap on the grip toggles, and scrolling the content makes it full screen too (like a native sheet).
    (() => {
      const modal = document.getElementById('film-details-modal');
      const handles = [document.getElementById('sheet-grip'), modal.querySelector('.modal-header')];
      const dialog = modal.querySelector('.modal-dialog');
      let startY = null;
      let baseOffset = 0;
      handles.forEach(handle => {
        handle.addEventListener('pointerdown', event => {
          if (event.target.closest('button, a')) return;  // the arrows and the close button stay buttons
          startY = event.clientY;
          baseOffset = modal.classList.contains('is-full') ? 0 : innerHeight * 0.2;
          handle.setPointerCapture(event.pointerId);
        });
        // The sheet follows the finger (transform only); on release the classes decide where it settles.
        handle.addEventListener('pointermove', event => {
          if (startY === null) return;
          dialog.style.transition = 'none';
          dialog.style.transform = `translateY(${Math.max(0, baseOffset + event.clientY - startY)}px)`;
        });
        const release = () => { dialog.style.transition = ''; dialog.style.transform = ''; };
        handle.addEventListener('pointercancel', () => { startY = null; release(); });
        handle.addEventListener('pointerup', event => {
          if (startY === null) return;
          const moved = event.clientY - startY;
          startY = null;
          release();
          const full = modal.classList.contains('is-full');
          if (moved < -24) modal.classList.add('is-full');
          else if (moved > 48) { if (full) modal.classList.remove('is-full'); else modal.querySelector('.btn-close').click(); }
          else if (Math.abs(moved) < 8 && handle.id === 'sheet-grip') modal.classList.toggle('is-full', !full);
        });
      });
      modal.querySelector('.modal-body').addEventListener('scroll', event => {
        if (matchMedia('(max-width: 800px)').matches && event.target.scrollTop > 24) modal.classList.add('is-full');
      });
      modal.addEventListener('hidden.bs.modal', () => modal.classList.remove('is-full'));
    })();
    // Previous / next film of the list behind the drawer (the grid or the Tonight rows, as drawn); ← and → do the same.
    function neighbourFilm(step) {
      const keys = [...new Set([...document.querySelectorAll('#results article.film[data-key], #results tr[data-key], #tonight-rows article.film[data-key]')].map(card => card.dataset.key))];
      const current = new URL(location.href).searchParams.get('film');
      const next = keys[keys.indexOf(current) + step];
      if (next !== undefined && keys.indexOf(current) >= 0) showFilmDetails(next, modalOpeners.get('film-details-modal'));
    }
    document.getElementById('film-prev').addEventListener('click', () => neighbourFilm(-1));
    document.getElementById('film-next').addEventListener('click', () => neighbourFilm(1));
    document.addEventListener('keydown', event => {
      if (!document.getElementById('film-details-modal').classList.contains('show') || event.altKey || event.ctrlKey || event.metaKey) return;
      if (event.target.closest('input, select, textarea, [contenteditable]')) return;
      if (event.key === 'ArrowLeft') { event.preventDefault(); neighbourFilm(-1); }
      if (event.key === 'ArrowRight') { event.preventDefault(); neighbourFilm(1); }
    });
    // Keyboard shortcuts (outside text fields and dialogs): the film is the one in the open details, else the card in focus or under the pointer.
    let hoveredCard = null;
    document.addEventListener('pointerover', event => { hoveredCard = event.target.closest?.('article.film') || hoveredCard; });
    function filmInFocus() {
      const open = document.getElementById('film-details-modal').classList.contains('show');
      if (open) return {key: new URL(location.href).searchParams.get('film'), card: null};
      const card = document.activeElement?.closest?.('article.film') || (hoveredCard?.isConnected && hoveredCard.matches(':hover') ? hoveredCard : null);
      return {key: card?.dataset.key, card};
    }
    let goPending = false;
    document.addEventListener('keydown', event => {
      if (event.ctrlKey || event.metaKey || event.altKey || event.isComposing) return;
      if (event.target.closest?.('input, select, textarea, [contenteditable], dialog, .modal:not(#film-details-modal)')) return;
      const dialog = document.getElementById('shortcuts-dialog');
      if (event.key === '?') { dialog.showModal(); return; }
      if (goPending) {
        goPending = false;
        const target = {t: '/', w: '/watchlist', s: '/subscriptions'}[event.key];
        if (target) { event.preventDefault(); location.href = target; return; }
      }
      if (event.key === 'g') { goPending = true; setTimeout(() => { goPending = false; }, 1000); return; }
      if (event.key === '/' && VIEW !== 'tonight') { event.preventDefault(); document.getElementById('film-search').focus(); return; }
      if (event.key === 'R' && event.shiftKey) { document.getElementById('retry-scan')?.click(); return; }
      const {key, card} = filmInFocus();
      if (!key) return;
      if (event.key === 'f') {
        const button = (card || document).querySelector(card ? '.favorite' : '.modal-favorite');
        if (button) { event.preventDefault(); toggleFavorite(button); }
      } else if (event.key === 's') { event.preventDefault(); setFlag(key, 'watched'); }
      else if (event.key === 'n') { event.preventDefault(); setFlag(key, 'not_now'); }
      else if (event.key === 'l') {
        const film = [...state.films, ...state.unavailable].find(item => filmKey(item) === key);
        if (film) { event.preventDefault(); window.open(letterboxdUrl(film), '_blank', 'noopener'); }
      }
      else if (event.key === 'c') { event.preventDefault(); setCompared(key, !state.compareKeys.has(key)); renderFilms(); }
    });
    // The skip link moves the focus without a #results in the address: going back to a #fragment entry
    // would pull the focus away from the card the details were opened from.
    document.querySelector('.skip-link')?.addEventListener('click', event => { event.preventDefault(); (VIEW === 'tonight' ? document.getElementById('tonight-rows') : results).focus(); });
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
      const action = event.target.closest('.poster-actions button, .modal-flag');
      if (!action) return;
      event.preventDefault();
      if (action.closest('details')) action.closest('details').open = false;
      if (action.dataset.flag) setFlag(action.dataset.key, action.dataset.flag);
      if (action.dataset.compare) { setCompared(action.dataset.compare, !state.compareKeys.has(action.dataset.compare)); renderFilms(); }
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
        // A link opened in a new tab (or the installed app) goes straight to the full-screen sheet on a phone.
        document.getElementById('film-details-modal').classList.toggle('is-full', matchMedia('(max-width: 800px)').matches);
        showFilmDetails(key, results);
      } else if (final) {
        pendingFilm = null;
        setFilmAddress(null);
        showToast('That film is not on this watchlist (or not in this country).', true);
      }
    }
    results.addEventListener('click', event => {
      if (event.target.closest('button, a, input, select, textarea, label, summary, .poster-actions')) return;
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
        const label = state.compareKeys.has(key) ? 'Remove from comparison' : 'Add to comparison';
        compareButton.innerHTML = '<i class="ti ti-layout-columns" aria-hidden="true"></i><span class="tool-label">Compare</span>';
        compareButton.title = label;
        compareButton.setAttribute('aria-label', label);
        compareButton.setAttribute('aria-pressed', String(state.compareKeys.has(key)));
      }
      if (event.target.closest('.modal-share')) {
        navigator.clipboard?.writeText(location.href).then(() => showToast('Link copied.'), () => showToast('Could not copy the link.', true));
      }
      const more = event.target.closest('.overview-more');
      // On a phone a tap on the cut-off text opens it as well (it only expands; "less" is the button).
      const tapped = matchMedia('(max-width: 800px)').matches && event.target.closest('.overview-box.clamped .film-modal-overview');
      if (more || tapped) {
        const box = (more || tapped).closest('.overview-box');
        const button = box.querySelector('.overview-more');
        const clamped = more ? box.classList.toggle('clamped') : (box.classList.remove('clamped'), false);
        button.textContent = clamped ? 'more' : 'less';
        button.setAttribute('aria-expanded', String(!clamped));
      }
      const extra = event.target.closest('.chip-more');
      if (extra) {
        extra.parentElement.querySelectorAll('.is-extra').forEach(chip => { chip.hidden = false; });
        extra.remove();
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
        votes: document.getElementById('min-votes').value,
        sort: document.getElementById('sort-order').value,
        keyword: document.getElementById('keyword-filter').dataset.pending || document.getElementById('keyword-filter').value,
        ages: document.getElementById('age-filter').value,
        lang: document.getElementById('language-filter').dataset.pending || document.getElementById('language-filter').value,
        origin: document.getElementById('origin-filter').dataset.pending || document.getElementById('origin-filter').value,
        from: document.getElementById('year-from').value,
        to: document.getElementById('year-to').value,
        media: document.getElementById('media-filter').value,
        changes: document.getElementById('change-filter').value,
        providers: [...state.selected].sort().join(','),
        minproviders: document.getElementById('provider-count-filter').value,
        hidden: document.getElementById('show-hidden').checked ? '1' : '',
        where: document.getElementById('where-filter').value,
        favoriteStatus: document.getElementById('favorite-status-filter').value,
        favorites: state.favoritesOnly ? '1' : '',
      };
      // Values equal to the page's default stay out of the link.
      const defaults = {sort: 'priority'};
      Object.entries(values).forEach(([name, value]) => {
        const isDefault = name in defaults ? value === defaults[name] : ['all', '0', 'any'].includes(value);
        if (value && !isDefault) url.searchParams.set(name, value);
        else url.searchParams.delete(name);
      });
      filterBar.writeUrl(url);
      history.replaceState({}, '', url);
    }
    // Only 'input': a 'change' event also fires when a text field loses focus, and redrawing the
    // cards at that moment (on mousedown) swallowed the first click on a card or a star.
    // Typing in the search redraws only after a short pause, not on every key.
    let searchTimer;
    document.getElementById('film-search').addEventListener('input', () => { clearTimeout(searchTimer); searchTimer = setTimeout(renderFilms, 150); });
    ['where-filter', 'show-unavailable', 'show-hidden', 'keyword-filter', 'age-filter', 'language-filter', 'origin-filter', 'lb-filter', 'tmdb-filter', 'year-from', 'year-to', 'min-votes', 'media-filter', 'change-filter', 'provider-count-filter'].forEach(id => document.getElementById(id).addEventListener('input', renderFilms));
    const initialUrl = new URL(location.href).searchParams;
    const setInitial = (id, parameter, fallback) => {
      const element = document.getElementById(id);
      const value = initialUrl.get(parameter) ?? fallback;
      if (element && (!element.options || [...element.options].some(option => option.value === value))) element.value = value;
      else if (element && ['keyword-filter', 'language-filter', 'origin-filter'].includes(id) && value !== 'all') element.dataset.pending = value;
    };
    ['keyword-filter', 'language-filter', 'origin-filter'].forEach(id => document.getElementById(id).addEventListener('input', event => delete event.target.dataset.pending));
    setInitial('film-search', 'q', window.WATCHLIST_CONFIG.initialFilters.query);
    setInitial('sort-order', 'sort', window.WATCHLIST_CONFIG.initialFilters.sort);
    setInitial('min-votes', 'votes', '0');
    setInitial('keyword-filter', 'keyword', 'all');
    setInitial('age-filter', 'ages', 'all');
    setInitial('language-filter', 'lang', 'all');
    setInitial('origin-filter', 'origin', 'all');
    setInitial('year-from', 'from', '');
    setInitial('year-to', 'to', '');
    setInitial('media-filter', 'media', 'all');
    setInitial('change-filter', 'changes', 'all');
    setInitial('provider-count-filter', 'minproviders', '0');
    setInitial('favorite-status-filter', 'favoriteStatus', 'all');
    // Older links used only=1 or availability=exclusive for what is now "Number of services: Only 1".
    if (initialUrl.get('only') === '1' || initialUrl.get('availability') === 'exclusive') document.getElementById('provider-count-filter').value = 'only1';
    document.getElementById('show-hidden').checked = initialUrl.get('hidden') === '1';
    setInitial('where-filter', 'where', initialUrl.get('abroad') === '1' ? 'both' : 'all');
    filterBar.readUrl(initialUrl);
    filterBar.buildServicesMenu();
    ['sort-order', 'favorite-status-filter'].forEach(id => document.getElementById(id).addEventListener('change', renderFilms));
    const favoritesButton = document.getElementById('favorites-view');
    const showHeart = on => {
      favoritesButton.querySelector('i').className = on ? 'ti ti-heart-filled' : 'ti ti-heart';
      document.getElementById('favorites-panel').checked = on;
    };
    state.favoritesOnly = initialUrl.get('favorites') === '1';
    // The button keeps its name; whether the view is on is said by aria-pressed and the line above the films.
    function setFavoritesOnly(on) {
      state.favoritesOnly = on;
      favoritesButton.classList.toggle('active', on);
      favoritesButton.setAttribute('aria-pressed', String(on));
      showHeart(on);
      renderFilms();
    }
    favoritesButton.classList.toggle('active', state.favoritesOnly);
    favoritesButton.setAttribute('aria-pressed', String(state.favoritesOnly));
    showHeart(state.favoritesOnly);
    favoritesButton.addEventListener('click', () => setFavoritesOnly(!state.favoritesOnly));
    document.getElementById('favorites-panel').addEventListener('change', event => setFavoritesOnly(event.target.checked));
    // The abroad switch and the "Where" field in the panel are one setting; Tonight remembers it in this browser.
    document.getElementById('abroad-toggle').addEventListener('click', event => {
      if (event.currentTarget.getAttribute('aria-disabled') === 'true') return;
      const select = document.getElementById('where-filter');
      select.value = select.value === 'all' ? 'both' : 'all';
      localStorage.setItem('abroadOn', select.value === 'all' ? '' : '1');
      renderFilms();
    });
    document.getElementById('where-filter').addEventListener('change', event => localStorage.setItem('abroadOn', event.target.value === 'all' ? '' : '1'));
    document.getElementById('compare-go').addEventListener('click', compareFilms);
    document.getElementById('compare-bar-clear').addEventListener('click', () => { [...state.compareKeys].forEach(key => setCompared(key, false)); renderFilms(); });
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
    // Phones: "Filters" opens the bar as a sheet from the bottom, a modal dialog while open.
    // Phones keep the heart and the link inside the sheet; wider screens put them with the view switch in the tab row, so the bar stays one row.
    const phoneQuery = matchMedia('(max-width: 800px)');
    const placeViewTools = () => {
      const phone = phoneQuery.matches;
      const tabs = document.getElementById('tabs-view-slot');
      const home = document.getElementById(phone ? 'sheet-view-slot' : 'tabs-view-slot');
      ['favorites-view', 'share-button'].forEach(id => home.append(document.getElementById(id)));
      tabs.append(document.getElementById('view-switch'));
    };
    placeViewTools();
    phoneQuery.addEventListener('change', placeViewTools);
    const toolsToggle = document.getElementById('tools-toggle');
    const filterSheet = document.getElementById('film-filters');
    const behindSheet = () => [document.getElementById('app-header'), document.querySelector('.skip-link'), ...document.querySelectorAll('#watchlist-view > :not(.watch-bar), .watch-bar > :not(#film-filters)')].filter(Boolean);
    let sheetTimer = null;
    // Closing on a phone slides the sheet down first (`tools-closing`), then drops `tools-open`.
    function setSheet(open, instant = false) {
      clearTimeout(sheetTimer);
      const body = document.body;
      const slide = !open && !instant && body.classList.contains('tools-open') && phoneQuery.matches
        && !matchMedia('(prefers-reduced-motion: reduce)').matches;
      body.classList.toggle('tools-closing', slide);
      if (slide) sheetTimer = setTimeout(() => body.classList.remove('tools-open', 'tools-closing'), 230);
      else body.classList.toggle('tools-open', open);
      toolsToggle?.setAttribute('aria-expanded', String(open));
      filterSheet.setAttribute('role', open ? 'dialog' : 'search');
      if (open) filterSheet.setAttribute('aria-modal', 'true'); else filterSheet.removeAttribute('aria-modal');
      behindSheet().forEach(element => { element.inert = open; });
      // On a touch screen the search would raise the keyboard before anything is chosen: focus the close button instead.
      if (open) document.getElementById(matchMedia('(pointer: coarse)').matches ? 'filter-sheet-close' : 'film-search').focus();
      else toolsToggle?.focus();
    }
    toolsToggle?.addEventListener('click', () => setSheet(!document.body.classList.contains('tools-open')));
    // Pulling the sheet's header down follows the finger; past 80 px it slides out and closes.
    (() => {
      const head = filterSheet.querySelector('.sheet-head');
      let startY = null;
      head.addEventListener('pointerdown', event => {
        if (event.target.closest('button, a') || !phoneQuery.matches) return;
        startY = event.clientY;
        head.setPointerCapture(event.pointerId);
      });
      head.addEventListener('pointermove', event => {
        if (startY === null) return;
        filterSheet.style.transition = 'none';
        filterSheet.style.transform = `translateY(${Math.max(0, event.clientY - startY)}px)`;
      });
      const end = event => {
        if (startY === null) return;
        const far = event.type === 'pointerup' && event.clientY - startY > 80;
        startY = null;
        filterSheet.style.transition = 'transform .22s cubic-bezier(.2, .8, .2, 1)';
        filterSheet.style.transform = far ? 'translateY(100%)' : '';
        setTimeout(() => {
          filterSheet.style.transition = '';
          if (far) { setSheet(false, true); filterSheet.style.transform = ''; }
        }, 230);
      };
      head.addEventListener('pointerup', end);
      head.addEventListener('pointercancel', end);
    })();
    document.getElementById('filter-sheet-done').addEventListener('click', () => setSheet(false));
    document.getElementById('filter-sheet-close').addEventListener('click', () => setSheet(false));
    document.getElementById('filter-sheet-reset').addEventListener('click', () => filterBar.resetAll());
    // The dimmed page behind the sheet is the body's ::before: a tap on it closes the sheet.
    document.body.addEventListener('click', event => { if (event.target === document.body && document.body.classList.contains('tools-open')) setSheet(false); });
    document.addEventListener('keydown', event => {
      if (event.key === 'Escape' && document.body.classList.contains('tools-open') && !event.target.closest?.('details[open]')) setSheet(false);
    });
    localStorage.removeItem('watchlistLayout');  // "Wide view" is gone; forget the old choice
    // The header slims down once the page scrolls.
    const appHeader = document.getElementById('app-header');
    // Two thresholds: on a short page the 8px it saves would push scrollY back under one threshold and flicker.
    addEventListener('scroll', () => {
      if (scrollY > 64) appHeader.classList.add('compact');
      else if (scrollY < 8) appHeader.classList.remove('compact');
    }, {passive: true});
    document.getElementById('share-button')?.addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText(location.href);
        showToast('Link copied.');
      } catch {
        // No clipboard over plain http in the home network: show the link to copy by hand.
        window.prompt('Copy this link:', location.href);
      }
    });
    // The films load while the favorites do (the page preloads the same address).
    const latestRequest = fetch(`/api/latest?country=${encodeURIComponent(document.getElementById('country-select').value)}`);
    loadFavorites().then(async () => {
      const snapshot = await loadLatestResult(latestRequest);
      fetch('/api/matches').then(response => (response.ok ? response.json() : [])).then(rows => { toCheck = rows.length; baseLine(); }).catch(() => {});
      const savedJob = new URL(location.href).searchParams.get('scan');
      if (savedJob) {
        resumeScan(savedJob);
      } else if (!snapshot || snapshot.stale) {
        startScan(true);
      } else {
        showSavedPanel();
        openPendingFilm(true);
      }
    });
