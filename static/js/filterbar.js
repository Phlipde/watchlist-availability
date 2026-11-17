// The filter bar of the watchlist page: services menu, cost, genres, runtime, rating, chips and counts.
// Pure counting lives in filtering.js; this module only reads and writes the bar's DOM.
import {escapeHtml} from './ui.js';
import {COST, FILTER_CONTROLS, activeFilters, clearFilter, resetFilters} from './filters.js';
import {SECTION_KINDS, countVisible, facetCounts} from './filtering.js';

const ALL_KINDS = ['free', 'ads', 'flatrate', 'rent'];
const RUNTIME_STEPS = [90, 120, 150];
const runtimeText = minutes => (Number(minutes) ? `Up to ${minutes} min` : 'Any length');

// Offer types a cost choice allows, for the per-service counts.
function costKinds(filters) {
  if (filters.kind !== 'all') return [filters.kind];
  return SECTION_KINDS[filters.availability] || ALL_KINDS;
}

// Popovers (<details>): one open at a time, closed by a click outside or Escape (focus back on its summary),
// arrow keys move through the controls inside. Bootstrap's dropdown toggles twice here (tabler.min.js
// brings a second Bootstrap), so these are plain <details>.
// A menu opens under its button; when that runs past the window edge, slide it back in.
function keepInView(menu) {
  if (!menu) return;
  menu.style.translate = '';
  const {left, right} = menu.getBoundingClientRect();
  const margin = 8;
  const shift = right > innerWidth - margin ? innerWidth - margin - right : 0;
  menu.style.translate = `${Math.max(shift, margin - left)}px 0`;
}

export function initPopovers(doc = document) {
  const popovers = () => [...doc.querySelectorAll('details.filter-pop, details.sync, details.export-menu')];
  doc.addEventListener('toggle', event => {
    if (!event.target.matches?.('details.filter-pop, details.sync, details.export-menu') || !event.target.open) return;
    popovers().forEach(other => { if (other !== event.target) other.open = false; });
    keepInView(event.target.querySelector('.filter-menu, .sync-panel'));
  }, true);
  doc.addEventListener('click', event => {
    popovers().forEach(popover => { if (popover.open && !popover.contains(event.target)) popover.open = false; });
  });
  doc.addEventListener('keydown', event => {
    const popover = event.target.closest?.('details.filter-pop, details.sync, details.export-menu');
    if (!popover?.open) return;
    if (event.key === 'Escape') {
      popover.open = false;
      popover.querySelector('summary').focus();
      event.stopPropagation();
      return;
    }
    if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') return;
    if (event.target.matches('select, input[type=range], input[type=number], input[type=radio]')) return;
    const items = [...popover.querySelectorAll('summary, .filter-menu input:not([type=hidden]), .filter-menu button, .filter-menu select')]
      .filter(item => !item.closest('[hidden]'));
    const index = items.indexOf(event.target);
    if (index < 0) return;
    event.preventDefault();
    items[Math.max(0, Math.min(items.length - 1, index + (event.key === 'ArrowDown' ? 1 : -1)))].focus();
  });
}

export function createFilterBar({state, config, mySubscriptions, freeServices, rentalShops, onChange}) {
  const $ = id => document.getElementById(id);
  const logos = config.providerLogos || {};
  const logo = name => (logos[name] ? `<img class="provider-logo-sm" src="${escapeHtml((config.logoBaseUrl || '') + logos[name])}" alt="" loading="lazy">` : '');

  // ---- services -------------------------------------------------------------------------------
  function groups() {
    const mine = [...mySubscriptions()].sort();
    const used = new Set(mine);
    const take = names => [...names].filter(name => !used.has(name) && used.add(name)).sort();
    const free = take(freeServices);
    const rental = take(rentalShops);
    // A service ticked through a link but in none of the groups stays visible, so it can be unticked.
    const other = take(state.selected);
    return [['My subscriptions', mine], ['Free', free], ['Rental shops', rental], ['Other', other]].filter(([, names]) => names.length);
  }
  function buildServicesMenu() {
    $('services-menu').innerHTML = groups().map(([title, names]) => `<section class="services-group" data-group="${escapeHtml(title)}"><div class="services-group-head"><h3>${escapeHtml(title)}</h3><button class="film-link" type="button" data-group-toggle>All</button></div>${names.map(name => `<label class="service-option" data-provider-label="${escapeHtml(name)}"><input type="checkbox" value="${escapeHtml(name)}"${state.selected.has(name) ? ' checked' : ''}>${logo(name)}<span class="provider-name">${escapeHtml(name)}${freeServices.has(name) ? '<span class="free-tag pill pill-ok">Mostly free</span>' : ''}</span><span class="option-count" data-service-count="${escapeHtml(name)}"></span></label>`).join('')}</section>`).join('')
      + `<div class="services-foot"><select class="form-select form-select-sm" id="match-mode" aria-label="How the ticked services are combined"><option value="any">Films on any ticked service</option><option value="all">Films on all ticked services</option></select><button class="btn btn-sm btn-outline-secondary" type="button" id="clear-providers">Clear</button><a class="film-link" href="/subscriptions">Edit my subscriptions</a></div>`
      + '<p class="hint">Changing services filters the list; it does not start a scan.</p>';
    $('match-mode').value = state.matchMode || 'any';
    updateServicesButton();
  }
  function updateServicesButton() {
    const chosen = [...state.selected].sort((a, b) => Number(Boolean(logos[b])) - Number(Boolean(logos[a])) || a.localeCompare(b));
    const shown = chosen.filter(name => logos[name]).slice(0, 4);
    $('services-logos').innerHTML = shown.map(logo).join('') + (chosen.length > shown.length ? `<span class="logo-more">+${chosen.length - shown.length}</span>` : '');
    $('services-label').textContent = chosen.length ? (shown.length ? '' : `${chosen.length} services`) : 'No services';
    $('services-button').setAttribute('aria-label', `Services: ${chosen.length} ticked`);
  }
  $('services-menu').addEventListener('change', event => {
    if (event.target.id === 'match-mode') { state.matchMode = event.target.value; onChange(); return; }
    if (event.target.type !== 'checkbox') return;
    if (event.target.checked) state.selected.add(event.target.value); else state.selected.delete(event.target.value);
    updateServicesButton();
    onChange();
  });
  $('services-menu').addEventListener('click', event => {
    if (event.target.id === 'clear-providers') { setServices([]); return; }
    const toggle = event.target.closest('[data-group-toggle]');
    if (!toggle) return;
    // "All" ticks the whole group; when it is all ticked already, the same button unticks it.
    const boxes = [...toggle.closest('.services-group').querySelectorAll('input[type=checkbox]')];
    const on = !boxes.every(box => box.checked);
    boxes.forEach(box => { box.checked = on; if (on) state.selected.add(box.value); else state.selected.delete(box.value); });
    updateServicesButton();
    onChange();
  });
  function setServices(names) {
    state.selected = new Set(names);
    buildServicesMenu();
    onChange();
  }

  // ---- cost, runtime --------------------------------------------------------------------------
  function setCost(value, notify = true) {
    const input = $('cost-filter');
    input.value = COST[value] ? value : 'all';
    input.dataset.text = document.querySelector(`#cost-options input[value="${input.value}"]`).nextElementSibling.textContent;
    document.querySelector(`#cost-options input[value="${input.value}"]`).checked = true;
    if (notify) onChange();
  }
  $('cost-options').addEventListener('change', event => setCost(event.target.value));
  function setRuntime(minutes, notify = true) {
    const value = Math.max(0, Number(minutes) || 0);
    const input = $('runtime-filter');
    input.value = String(value);
    input.dataset.text = runtimeText(value);
    $('runtime-summary').textContent = value ? `≤ ${value}` : '';
    const radio = document.querySelector(`#runtime-pop input[name=runtime][value="${value}"]`);
    document.querySelectorAll('#runtime-pop input[name=runtime]').forEach(item => { item.checked = item === radio; });
    if (value) { $('runtime-slider').value = String(value); $('runtime-slider-value').textContent = value; }
    if (notify) onChange();
  }
  $('runtime-pop').addEventListener('change', event => {
    if (event.target.name === 'runtime') setRuntime(event.target.value);
  });
  $('runtime-slider').addEventListener('input', event => setRuntime(event.target.value));

  // ---- sort: a menu of radios with one line of explanation each; the hidden #sort-order holds the value ---------
  function syncSort() {
    const value = $('sort-order').value;
    const radio = document.querySelector(`#sort-menu input[value="${value}"]`) || document.querySelector('#sort-menu input');
    document.querySelectorAll('#sort-menu input').forEach(item => { item.checked = item === radio; });
    $('sort-summary').textContent = radio.nextElementSibling.querySelector('.sort-name').textContent;
  }
  $('sort-menu').addEventListener('change', event => {
    $('sort-order').value = event.target.value;
    syncSort();
    $('sort-order').dispatchEvent(new Event('change', {bubbles: true}));
    $('sort-pop').open = false;
    $('sort-button').focus();
  });

  // ---- genres -----------------------------------------------------------------------------------
  function buildGenreMenu(genres) {
    $('genre-list').innerHTML = genres.map(genre => {
      const name = escapeHtml(genre);
      const excluded = state.genres.exclude.has(genre);
      return `<div class="genre-option${excluded ? ' is-excluded' : ''}"><label><input type="checkbox" value="${name}"${state.genres.include.has(genre) ? ' checked' : ''}> <span>${name}</span> <span class="option-count" data-genre-count="${name}"></span></label><button class="genre-exclude" type="button" data-genre="${name}" aria-pressed="${excluded}" aria-label="Exclude ${name}">No</button></div>`;
    }).join('') || '<p class="hint">Genres appear after the scan.</p>';
    updateGenreSummary();
  }
  function updateGenreSummary() {
    const included = [...state.genres.include];
    const excluded = [...state.genres.exclude];
    $('genre-summary').textContent = [included.length ? included.length === 1 ? included[0] : `${included.length}` : '', excluded.length ? `no ${excluded.length === 1 ? excluded[0] : excluded.length}` : ''].filter(Boolean).join(', ');
  }
  function setGenre(genre, mode) {
    state.genres.include.delete(genre);
    state.genres.exclude.delete(genre);
    if (mode) state.genres[mode].add(genre);
    const row = [...document.querySelectorAll('#genre-list .genre-option')].find(item => item.querySelector('input').value === genre);
    if (row) {
      row.querySelector('input').checked = mode === 'include';
      row.classList.toggle('is-excluded', mode === 'exclude');
      row.querySelector('.genre-exclude').setAttribute('aria-pressed', String(mode === 'exclude'));
    }
    updateGenreSummary();
    onChange();
  }
  $('genre-list').addEventListener('click', event => {
    const exclude = event.target.closest('.genre-exclude');
    if (exclude) { setGenre(exclude.dataset.genre, state.genres.exclude.has(exclude.dataset.genre) ? null : 'exclude'); return; }
    // Alt-click on a genre excludes it, as a shortcut for the "No" button.
    const label = event.target.closest('label');
    if (label && event.altKey) {
      event.preventDefault();
      const genre = label.querySelector('input').value;
      setGenre(genre, state.genres.exclude.has(genre) ? null : 'exclude');
    }
  });
  $('genre-list').addEventListener('change', event => {
    if (event.target.type === 'checkbox') setGenre(event.target.value, event.target.checked ? 'include' : null);
  });

  // ---- counts per option ------------------------------------------------------------------------
  // "What would I get if I picked this?": each control's counts leave that control itself out.
  function updateCounts(films, filters, context) {
    syncSort();
    const services = facetCounts(films, filters, context,
      (f, c) => [{...f, mode: 'any'}, {...c, selected: new Set(films.flatMap(film => Object.keys(film.providers || {})))}],
      film => Object.entries(film.providers || {}).filter(([, kinds]) => kinds.some(kind => costKinds(filters).includes(kind))).map(([name]) => name));
    document.querySelectorAll('[data-service-count]').forEach(element => {
      const count = services.get(element.dataset.serviceCount) || 0;
      element.textContent = count;
      element.closest('label').classList.toggle('is-empty', count === 0);
    });
    Object.entries(COST).forEach(([value, [availability, kind]]) => {
      const count = countVisible(films, {...filters, availability, kind}, context);
      const element = document.querySelector(`[data-cost-count="${value}"]`);
      element.textContent = count;
      element.closest('label').classList.toggle('is-empty', count === 0);
    });
    const genres = facetCounts(films, filters, context, (f, c) => [{...f, genres: {include: [], exclude: []}}, c], film => film.genres || []);
    document.querySelectorAll('[data-genre-count]').forEach(element => {
      const count = genres.get(element.dataset.genreCount) || 0;
      element.textContent = count;
      element.closest('.genre-option').classList.toggle('is-empty', count === 0);
    });
    const runtimes = facetCounts(films, filters, context, (f, c) => [{...f, maxRuntime: 0}, c],
      film => ['0', ...RUNTIME_STEPS.filter(step => film.runtime > 0 && film.runtime <= step).map(String)]);
    document.querySelectorAll('[data-runtime-count]').forEach(element => {
      const count = runtimes.get(element.dataset.runtimeCount) || 0;
      element.textContent = count;
      element.closest('label').classList.toggle('is-empty', count === 0);
    });
    const ratings = facetCounts(films, filters, context, (f, c) => [{...f, minRating: 0, minLetterboxd: 0}, c], film => [...$('rating-filter').options]
      .filter(option => {
        const [source, minimum] = option.value.split(':');
        return !option.value || (source === 'lb' ? Number(film.letterboxd_rating) >= Number(minimum) : Number(film.rating) >= Number(minimum));
      }).map(option => option.value));
    [...$('rating-filter').options].forEach(option => {
      option.dataset.label ??= option.textContent;
      option.textContent = `${option.dataset.label} (${ratings.get(option.value) || 0})`;
    });
  }

  // ---- chips ------------------------------------------------------------------------------------
  function updateChips() {
    const subscriptions = mySubscriptions();
    const ownSelection = state.selected.size === subscriptions.size && [...subscriptions].every(name => state.selected.has(name));
    const chip = (attributes, text) => `<button class="filter-chip" type="button" ${attributes} aria-label="Remove filter ${escapeHtml(text)}">${escapeHtml(text)} <i class="ti ti-x" aria-hidden="true"></i></button>`;
    const chips = [
      ...(ownSelection ? [] : [chip('data-services', `Services: ${[...state.selected].sort().slice(0, 3).join(', ') || 'none'}${state.selected.size > 3 ? ` +${state.selected.size - 3}` : ''}`)]),
      ...[...state.genres.include].map(genre => chip(`data-genre-include="${escapeHtml(genre)}"`, genre)),
      ...[...state.genres.exclude].map(genre => chip(`data-genre-exclude="${escapeHtml(genre)}"`, `No ${genre}`)),
      ...activeFilters(document).map(({id, label, text}) => chip(`data-filter-id="${id}"`, text ? `${label}: ${text}` : label)),
    ];
    if (chips.length) chips.push('<button class="filter-chip filter-reset" type="button" data-reset-filters>Reset all</button>');
    $('filter-chips').innerHTML = chips.join('');
    $('filter-chips').hidden = !chips.length;
    // Set filters inside "Filters" must not be forgotten: count them on its button.
    const inside = activeFilters(document).filter(({id}) => $(id).closest('#more-filters')).length;
    $('more-filters-count').textContent = inside ? `(${inside})` : '';
  }
  function resetAll() {
    resetFilters(document);
    state.genres = {include: new Set(), exclude: new Set()};
    state.selected = new Set(mySubscriptions());
    setCost('all', false);
    setRuntime(0, false);
    buildServicesMenu();
    buildGenreMenu([...document.querySelectorAll('#genre-list input')].map(input => input.value));
    onChange();
  }
  $('filter-chips').addEventListener('click', event => {
    const button = event.target.closest('.filter-chip');
    if (!button) return;
    if (button.hasAttribute('data-reset-filters')) { resetAll(); return; }
    if (button.hasAttribute('data-services')) { setServices(mySubscriptions()); return; }
    if (button.dataset.genreInclude || button.dataset.genreExclude) { setGenre(button.dataset.genreInclude || button.dataset.genreExclude, null); return; }
    const input = $(button.dataset.filterId);
    clearFilter(input);
    if (input.id === 'cost-filter') setCost('all', false);
    if (input.id === 'runtime-filter') setRuntime(0, false);
    onChange();
  });

  // ---- links --------------------------------------------------------------------------------------
  // Old links used availability=, kind=, runtime=short|medium|long, rating=<tmdb>, lb=, genre=<one>.
  function readUrl(params) {
    const oldCost = {Free: 'free', Paid: 'subscription'}[params.get('availability')] || {free: 'free', ads: 'free', flatrate: 'subscription', rent: 'rent'}[params.get('kind')];
    setCost(params.get('cost') || oldCost || 'all', false);
    if (['all', 'unavailable'].includes(params.get('availability'))) $('show-unavailable').checked = true;
    if (params.get('unavailable') === '1') $('show-unavailable').checked = true;
    const oldRuntime = {short: 90, medium: 120}[params.get('runtime')];
    setRuntime(params.get('max') || oldRuntime || 0, false);
    const rating = params.get('rating');
    const oldRating = rating && /^\d+(\.\d+)?$/.test(rating) && rating !== '0' ? `tmdb:${rating}` : null;
    const wanted = (rating && rating.includes(':') ? rating : null) || oldRating || (params.get('lb') && params.get('lb') !== '0' ? `lb:${params.get('lb')}` : '');
    $('rating-filter').value = [...$('rating-filter').options].some(option => option.value === wanted) ? wanted : '';
    const list = name => (params.get(name) || '').split(',').filter(value => value && value !== 'all');
    state.genres = {include: new Set(list('genre')), exclude: new Set(list('nogenre'))};
    state.matchMode = params.get('match') === 'all' ? 'all' : 'any';
  }
  function writeUrl(url) {
    const set = (name, value) => (value ? url.searchParams.set(name, value) : url.searchParams.delete(name));
    set('cost', $('cost-filter').value === 'all' ? '' : $('cost-filter').value);
    set('max', $('runtime-filter').value === '0' ? '' : $('runtime-filter').value);
    set('rating', $('rating-filter').value);
    set('genre', [...state.genres.include].join(','));
    set('nogenre', [...state.genres.exclude].join(','));
    set('unavailable', $('show-unavailable').checked ? '1' : '');
    set('match', state.matchMode === 'all' ? 'all' : '');
    ['availability', 'kind', 'runtime', 'lb'].forEach(name => url.searchParams.delete(name));
  }

  return {buildServicesMenu, buildGenreMenu, updateServicesButton, updateCounts, updateChips, resetAll, setServices, readUrl, writeUrl};
}

