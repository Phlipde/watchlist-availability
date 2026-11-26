import {escapeHtml, numberText} from './ui.js';
import {createAppState, createScanState} from './state.js';
import {bestAvailability} from './statistics.js';
import {serviceGroup} from './catalog.js';
import {emptyLink} from './link-filters.js';
import {filmHref, renderResults, runtimeText} from './rendering.js';
import './register-sw.js';
import {renderViews, wireViews} from './saved-views.js';
import {COST, readFilters} from './filters.js';
import {createFilterBar, initPopovers} from './filterbar.js';
import {baseCounts, bestRelaxation, comingSoon, elsewhereOnServices, filmKey, filterFilms, sortRatings} from './filtering.js';
import {abroadFilm, abroadForFilm, abroadServices} from './abroad.js';
import {initCountryPicker} from './country-picker.js';
import {createToast} from './toast.js';
import {createScanFlow} from './scan-flow.js';
import {createTonightPage} from './tonight-page.js';
import {createCompare} from './compare.js';
import {createFilmFlags} from './film-flags.js';
import {createFilmDetails} from './film-details.js';
import {createKeyboardNav} from './keyboard-nav.js';
import {initPhoneSheet} from './phone-sheet.js';
import {createChangesTab} from './changes-tab.js';

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
    const regionLabel = new Intl.DisplayNames(['en'], {type: 'region'});
    const {showToast} = createToast();
    const watchedKeys = () => new Set([
      ...[...state.favorites.values()].filter(film => film.status === 'watched').map(film => film.key),
      ...[...state.flags].filter(([, entry]) => entry.flag === 'watched').map(([key]) => key),
    ]);
    // "Not now": hidden until the date the server gave it.
    const hiddenKeys = () => new Set([...state.flags].filter(([, entry]) => entry.flag === 'not_now' && entry.until > Date.now() / 1000).map(([key]) => key));
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
        if (shown) setActiveKey(key);
        target?.focus();
      });
    });

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
      navItems().find(item => item.dataset.key === activeKey())?.scrollIntoView({block: 'nearest'});
    });
    syncViewMode();
    // Saved views: chips on Tonight and above the grid; "Save view" appears while filters are set.
    function drawViews() {
      renderViews(document.getElementById('saved-views'), {canSave: true, search: location.search});
      renderViews(document.getElementById('tonight-views'));
    }
    ['saved-views', 'tonight-views', 'views-menu'].forEach(id => wireViews(document.getElementById(id), () => location.search, drawViews));
    const {renderTonightPage} = createTonightPage({
      state, imageBaseUrl, view: VIEW, regionLabel, drawViews, ensureAbroad, abroadOnFor, abroadCandidates, abroadFor, abroadList, watchedKeys, hiddenKeys, includedOn, showToast,
      applyTonightRoving: () => applyTonightRoving(), showFilmDetails: (key, opener) => showFilmDetails(key, opener), detailsOpener: () => modalOpeners.get('film-details-modal'),
    });

    const {renderChanges} = createChangesTab({state});
    const {setCompared} = createCompare({state, results, imageBaseUrl, showToast, openModal, renderFilms});
    const {startScan, resumeScan, loadLatestResult, switchCountry, showSavedPanel} = createScanFlow({
      state, scanState, results, filterBar, freeServices, rentalShops, mySubscriptions, greyKeys, populateGenres, renderFilms, showToast,
      loadFavorites: () => loadFavorites(), openPendingFilm: final => openPendingFilm(final),
    });
    const {loadFavorites, setFlag, toggleFavorite, updateFavoriteField} = createFilmFlags({state, results, showToast, renderFilms});
    document.getElementById('empty-reset').addEventListener('click', () => filterBar.resetAll());
    document.getElementById('empty-subscriptions').addEventListener('click', () => filterBar.setServices(mySubscriptions()));
    document.getElementById('empty-relax').addEventListener('click', event => {
      const id = event.currentTarget.dataset.filter;
      if (id === 'genres') { state.genres = {include: new Set(), exclude: new Set()}; populateGenres(); renderFilms(); return; }
      document.querySelector(`.filter-chip[data-filter-id="${id}"] .chip-remove`)?.click();
    });
    document.getElementById('favorites-show-all').addEventListener('click', () => setFavoritesOnly(false));
    const {showFilmDetails, openPendingFilm} = createFilmDetails({
      state, results, imageBaseUrl, openModal, modalOpeners, setDrawerKey: key => { lastDrawerKey = key; }, watchedKeys, hiddenKeys, includedOn, upcomingText,
      toggleFavorite, updateFavoriteField, setCompared, showToast, renderFilms,
    });
    const {applyRoving, applyTonightRoving, navItems, activeKey, setActiveKey} = createKeyboardNav({state, results, view: VIEW, toggleFavorite, setFlag, setCompared, renderFilms});
    // The skip link moves the focus without a #results in the address: going back to a #fragment entry
    // would pull the focus away from the card the details were opened from.
    document.querySelector('.skip-link')?.addEventListener('click', event => { event.preventDefault(); (VIEW === 'tonight' ? document.getElementById('tonight-rows') : results).focus(); });
    document.addEventListener('click', event => {
      const action = event.target.closest('.poster-actions button, .modal-flag');
      if (!action) return;
      event.preventDefault();
      if (action.closest('details')) action.closest('details').open = false;
      if (action.dataset.flag) setFlag(action.dataset.key, action.dataset.flag);
      if (action.dataset.compare) { setCompared(action.dataset.compare, !state.compareKeys.has(action.dataset.compare)); renderFilms(); }
    });
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
    document.querySelectorAll('[data-country-picker]').forEach(root => initCountryPicker(root, {onPick: switchCountry}));
    initPhoneSheet({results, filterBar});
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
