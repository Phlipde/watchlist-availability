// The filter bar of the watchlist page: services menu, cost, genres, runtime, rating, chips and counts.
// Pure counting lives in filtering.js; this module only reads and writes the bar's DOM.
import {escapeHtml} from './ui.js';
import {logoStackHtml} from './logo-stack.js';
import {COST, FILTER_CONTROLS, activeFilters, clearFilter, durationText, resetFilters} from './filters.js';
import {SECTION_KINDS, countVisible, facetCounts} from './filtering.js';
import {clearLink, emptyLink, linkChips, needsUnavailable, parseLink, writeLink} from './link-filters.js';

const ALL_KINDS = ['free', 'ads', 'flatrate', 'rent'];
const RUNTIME_STEPS = [90, 120, 150];
const runtimeText = minutes => (Number(minutes) ? `Up to ${durationText(minutes)}` : 'Any length');

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
  // A control that moved into the "More filters" panel (.is-moved) stays open there and is left alone.
  const popovers = () => [...doc.querySelectorAll('details.filter-pop:not(.is-moved), details.sync, details.export-menu, details.card-menu')];
  doc.addEventListener('toggle', event => {
    if (!event.target.matches?.('details.filter-pop:not(.is-moved), details.sync, details.export-menu, details.card-menu') || !event.target.open) return;
    popovers().forEach(other => { if (other !== event.target) other.open = false; });
    keepInView(event.target.querySelector('.filter-menu, .sync-panel'));
  }, true);
  doc.addEventListener('click', event => {
    popovers().forEach(popover => { if (popover.open && !popover.contains(event.target)) popover.open = false; });
  });
  doc.addEventListener('keydown', event => {
    const popover = event.target.closest?.('details.filter-pop:not(.is-moved), details.sync, details.export-menu, details.card-menu');
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
    const rest = take(Object.keys(logos));  // every other service TMDB knows, found by search or the switch
    return [['My subscriptions', mine], ['Free', free], ['Rental shops', rental], ['Other', other], ['All others', rest]].filter(([, names]) => names.length);
  }
  // "Only my services" (on by default) hides the long list of all others; a search looks through everything.
  function applyServicesView() {
    const query = $('services-search').value.trim().toLowerCase();
    const onlyMine = $('services-only-mine').checked;
    document.querySelectorAll('#services-menu .services-group').forEach(group => {
      let shown = 0;
      group.querySelectorAll('.service-option').forEach(option => {
        const match = !query || option.dataset.providerLabel.toLowerCase().includes(query);
        option.hidden = !match;
        if (match) shown += 1;
      });
      group.hidden = !shown || (group.dataset.group === 'All others' && onlyMine && !query);
    });
  }
  function buildServicesMenu() {
    $('services-list').innerHTML = groups().map(([title, names]) => `<section class="services-group" data-group="${escapeHtml(title)}"><div class="services-group-head"><h3>${escapeHtml(title)}</h3><button class="film-link" type="button" data-group-toggle>All</button></div>${names.map(name => `<label class="service-option" data-provider-label="${escapeHtml(name)}"><input type="checkbox" value="${escapeHtml(name)}"${state.selected.has(name) ? ' checked' : ''}>${logo(name)}<span class="provider-name">${escapeHtml(name)}${freeServices.has(name) ? '<span class="free-tag pill pill-ok">Mostly free</span>' : ''}</span><span class="option-count" data-service-count="${escapeHtml(name)}"></span></label>`).join('')}</section>`).join('')
      + `<div class="services-foot"><select class="form-select form-select-sm" id="match-mode" aria-label="How the ticked services are combined"><option value="any">Films on any ticked service</option><option value="all">Films on all ticked services</option></select><button class="btn btn-sm btn-outline-secondary" type="button" id="clear-providers">Clear</button><a class="film-link" href="/subscriptions">Edit my subscriptions</a></div>`
      + '<p class="hint">Changing services filters the list; it does not start a scan.</p>';
    $('match-mode').value = state.matchMode || 'any';
    applyServicesView();
    updateServicesButton();
  }
  $('services-search').addEventListener('input', applyServicesView);
  $('services-only-mine').addEventListener('change', applyServicesView);
  function updateServicesButton() {
    const chosen = [...state.selected].sort((a, b) => Number(Boolean(logos[b])) - Number(Boolean(logos[a])) || a.localeCompare(b));
    const withLogo = chosen.filter(name => logos[name]);
    $('services-logos').innerHTML = logoStackHtml(withLogo.map(name => ({name, kind: '', logo: (config.logoBaseUrl || '') + logos[name]})));
    $('services-label').textContent = chosen.length ? (withLogo.length ? String(chosen.length) : `${chosen.length} services`) : 'No services';
    $('services-button').setAttribute('aria-label', `Services: ${chosen.length} ticked`);
  }
  $('services-menu').addEventListener('change', event => {
    if (!event.target.closest('#services-list')) return;  // the search and the switch are no services
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
    $('runtime-summary').textContent = value ? `≤ ${durationText(value)}` : '';
    const radio = document.querySelector(`#runtime-pop input[name=runtime][value="${value}"]`);
    document.querySelectorAll('#runtime-pop input[name=runtime]').forEach(item => { item.checked = item === radio; });
    if (value) { $('runtime-slider').value = String(value); $('runtime-slider-value').textContent = runtimeText(value); }
    if (notify) onChange();
  }
  $('runtime-pop').addEventListener('change', event => {
    if (event.target.name === 'runtime') setRuntime(event.target.value);
  });
  $('runtime-slider').addEventListener('input', event => setRuntime(event.target.value));

  // ---- year, rating and votes: quick chips plus a slider; hidden inputs hold the values ------------------------
  const YEAR_MIN = 1920;
  const YEAR_MAX = new Date().getFullYear() + 1;
  let ratingSource = 'lb';
  let chipsOpen = false;
  $('year-min').max = $('year-max').max = String(YEAR_MAX);
  $('year-max').value = String(YEAR_MAX);
  function setYears(from, to, notify = true) {
    $('year-from').value = from ? String(from) : '';
    $('year-to').value = to ? String(to) : '';
    if (notify) onChange();
  }
  function setRating(value, notify = true) {
    const input = $('rating-filter');
    input.value = value;
    const [source, minimum] = value.split(':');
    input.dataset.text = value ? `${source === 'lb' ? 'Letterboxd' : 'TMDB'} ${minimum}+` : '';
    if (value) ratingSource = source;
    if (notify) onChange();
  }
  function setVotes(value, notify = true) {
    const input = $('min-votes');
    input.value = value;
    const chip = document.querySelector(`#votes-chips [data-votes="${value}"]`);
    input.dataset.text = value === '0' ? '' : chip ? chip.textContent.trim() : `${value}+`;
    if (notify) onChange();
  }
  // The panels show what the hidden inputs say; this runs after every change, link and reset.
  function syncRanges() {
    const from = Number($('year-from').value) || 0;
    const to = Number($('year-to').value) || 0;
    $('year-min').value = String(from || YEAR_MIN);
    $('year-max').value = String(to || YEAR_MAX);
    $('year-text').textContent = from || to ? `${from || 'Any'} – ${to || 'now'}` : 'Any year';
    $('year-summary').textContent = from || to ? `${from || ''}–${to || ''}` : '';
    $('year-reset').hidden = !(from || to);
    document.querySelectorAll('#year-chips .chip').forEach(chip => chip.setAttribute('aria-pressed', String((Number(chip.dataset.from) || 0) === from && Number(chip.dataset.to) === to)));
    const [source, minimum] = $('rating-filter').value.split(':');
    const active = source || ratingSource;
    document.querySelector(`input[name=rating-source][value="${active}"]`).checked = true;
    $('rating-chips-lb').hidden = active !== 'lb';
    $('rating-chips-tmdb').hidden = active !== 'tmdb';
    document.querySelectorAll('[data-rating]').forEach(chip => chip.setAttribute('aria-pressed', String(chip.dataset.rating === $('rating-filter').value)));
    $('rating-slider').max = active === 'lb' ? '5' : '10';
    $('rating-slider').value = minimum || '0';
    $('rating-slider-value').textContent = Number(minimum) ? `${minimum}+` : 'any';
    const votes = $('min-votes').value;
    const votesChip = document.querySelector(`#votes-chips [data-votes="${votes}"]`);
    $('min-votes').dataset.text = votes === '0' ? '' : votesChip ? votesChip.textContent.trim() : `${votes}+`;
    $('rating-filter').dataset.text = minimum ? `${source === 'lb' ? 'Letterboxd' : 'TMDB'} ${minimum}+` : '';
    document.querySelectorAll('#votes-chips .chip').forEach(chip => chip.setAttribute('aria-pressed', String(chip.dataset.votes === votes)));
    $('rating-summary').textContent = minimum ? `${source === 'lb' ? 'Letterboxd' : 'TMDB'} ${minimum}+` : '';
    $('rating-reset').hidden = !minimum && votes === '0';
  }
  $('year-chips').addEventListener('click', event => {
    const chip = event.target.closest('.chip');
    if (!chip) return;
    const same = chip.getAttribute('aria-pressed') === 'true';
    setYears(same ? '' : chip.dataset.from, same ? '' : chip.dataset.to);
  });
  ['year-min', 'year-max'].forEach(id => $(id).addEventListener('input', () => {
    // The handles cannot cross: the one being moved pushes the other.
    let low = Number($('year-min').value);
    let high = Number($('year-max').value);
    if (low > high) { if (id === 'year-min') high = low; else low = high; }
    setYears(low > YEAR_MIN ? low : '', high < YEAR_MAX ? high : '');
  }));
  $('year-reset').addEventListener('click', () => setYears('', ''));
  $('rating-pop').addEventListener('change', event => {
    if (event.target.name !== 'rating-source') return;
    ratingSource = event.target.value;
    const hadValue = Boolean($('rating-filter').value);
    setRating('');  // the two scales differ: a number from one is no limit on the other
    $('rating-note').hidden = !hadValue;
  });
  $('rating-pop').addEventListener('click', event => {
    const chip = event.target.closest('.chip');
    if (!chip) return;
    if (chip.dataset.votes !== undefined) setVotes(chip.dataset.votes);
    else setRating(chip.getAttribute('aria-pressed') === 'true' ? '' : chip.dataset.rating);
    $('rating-note').hidden = true;
  });
  $('rating-slider').addEventListener('input', event => setRating(Number(event.target.value) ? `${ratingSource}:${event.target.value}` : ''));
  $('rating-reset').addEventListener('click', () => { setRating('', false); setVotes('0'); });
  // Letterboxd ratings arrive with the first scan after an update; until then only TMDB can be used.
  function setRatingAvailability(rated) {
    document.querySelector('input[name=rating-source][value="lb"]').disabled = !rated;
    document.querySelectorAll('#rating-chips-lb .chip').forEach(chip => { chip.disabled = !rated; });
    if (!rated) { ratingSource = 'tmdb'; if ($('rating-filter').value.startsWith('lb:')) setRating('', false); }
  }

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

  // ---- age rating: chips, several can be chosen; the hidden #age-filter holds "all" or "6,12" -----------------
  const ageValues = () => ($('age-filter').value === 'all' ? [] : $('age-filter').value.split(','));
  function setAges(values, notify = true) {
    const input = $('age-filter');
    input.value = values.length ? values.join(',') : 'all';
    input.dataset.text = values.join(', ');
    document.querySelectorAll('#age-chips .chip').forEach(chip => chip.setAttribute('aria-pressed', String(values.includes(chip.dataset.age))));
    if (notify) onChange();
  }
  // `values` come from the films, sorted young to old.
  function buildAgeChips(values) {
    $('age-label').textContent = $('country-select')?.value === 'DE' ? 'FSK' : 'Age rating';
    $('age-chips').innerHTML = values.map(value => `<button class="chip" type="button" data-age="${escapeHtml(value)}" aria-pressed="false">${escapeHtml(value)} <span class="option-count" data-age-count="${escapeHtml(value)}"></span></button>`).join('') || '<span class="hint">Appears after the scan.</span>';
    setAges(ageValues().filter(value => values.includes(value)), false);
  }
  $('age-chips').addEventListener('click', event => {
    const chip = event.target.closest('.chip');
    if (!chip) return;
    const current = ageValues();
    setAges(current.includes(chip.dataset.age) ? current.filter(value => value !== chip.dataset.age) : [...document.querySelectorAll('#age-chips .chip')].map(item => item.dataset.age).filter(value => value === chip.dataset.age || current.includes(value)));
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
      const label = element.closest('label');
      const input = label.querySelector('input');
      // An option without films is switched off, except the one that is chosen (it must stay changeable).
      input.disabled = count === 0 && !input.checked;
      label.title = value === 'rent' && rentalShops.size === 0 ? 'No rental shops selected. Add them in Settings > Services.'
        : input.disabled ? 'No films with the current filters' : value === 'all' ? 'Films can be in several groups' : '';
      label.classList.toggle('is-empty', count === 0);
    });
    const genres = facetCounts(films, filters, context, (f, c) => [{...f, genres: {include: [], exclude: []}}, c], film => film.genres || []);
    document.querySelectorAll('[data-genre-count]').forEach(element => {
      const count = genres.get(element.dataset.genreCount) || 0;
      element.textContent = count;
      element.closest('.genre-option').classList.toggle('is-empty', count === 0);
    });
    const ages = facetCounts(films, filters, context, (f, c) => [{...f, age: 'all'}, c], film => (film.certification ? [film.certification] : []));
    document.querySelectorAll('[data-age-count]').forEach(element => { element.textContent = ages.get(element.dataset.ageCount) || 0; });
    const runtimes = facetCounts(films, filters, context, (f, c) => [{...f, maxRuntime: 0}, c],
      film => ['0', ...RUNTIME_STEPS.filter(step => film.runtime > 0 && film.runtime <= step).map(String)]);
    document.querySelectorAll('[data-runtime-count]').forEach(element => {
      const count = runtimes.get(element.dataset.runtimeCount) || 0;
      element.textContent = count;
      element.closest('label').classList.toggle('is-empty', count === 0);
    });
    const ratingKeys = [...document.querySelectorAll('[data-rating]')].map(chip => chip.dataset.rating);
    const ratings = facetCounts(films, filters, context, (f, c) => [{...f, minRating: 0, minLetterboxd: 0}, c], film => ratingKeys
      .filter(key => { const [source, minimum] = key.split(':'); return source === 'lb' ? Number(film.letterboxd_rating) >= Number(minimum) : Number(film.rating) >= Number(minimum); }));
    document.querySelectorAll('[data-rating-count]').forEach(element => { element.textContent = ratings.get(element.dataset.ratingCount) || 0; });
    syncRanges();
  }

  // ---- chips ------------------------------------------------------------------------------------
  // Which panel holds a filter; every other one sits behind "Filters".
  const PANELS = {'runtime-filter': 'runtime-pop', 'rating-filter': 'rating-pop', 'min-votes': 'rating-pop', 'year-from': 'year-pop', 'year-to': 'year-pop', 'film-search': 'film-search', 'cost-filter': 'cost-options'};
  const insidePanel = id => Boolean($(id).closest('#more-filters') || $(PANELS[id])?.classList.contains('is-moved'));
  function openPanel(id) {
    let element = $(id);
    if (element.classList?.contains('is-moved')) element = $('more-filters');
    if (element.tagName === 'DETAILS') { element.open = true; element.querySelector('summary').focus(); return; }
    (element.querySelector?.('input:checked') || element).focus();
  }
  function updateChips() {
    const subscriptions = mySubscriptions();
    const ownSelection = state.selected.size === subscriptions.size && [...subscriptions].every(name => state.selected.has(name));
    // The text opens the panel the filter lives in; the x removes just this filter.
    const chip = (attributes, text, panel) => `<span class="filter-chip" ${attributes}><button class="chip-open" type="button" data-panel="${panel}" aria-label="Change filter ${escapeHtml(text)}">${escapeHtml(text)}</button><button class="chip-remove" type="button" aria-label="Remove filter ${escapeHtml(text)}"><i class="ti ti-x" aria-hidden="true"></i></button></span>`;
    const chips = [
      ...(ownSelection ? [] : [chip('data-services', `Services: ${[...state.selected].sort().slice(0, 3).join(', ') || 'none'}${state.selected.size > 3 ? ` +${state.selected.size - 3}` : ''}`, 'services-pop')]),
      ...[...state.genres.include].map(genre => chip(`data-genre-include="${escapeHtml(genre)}"`, genre, 'genre-pop')),
      ...[...state.genres.exclude].map(genre => chip(`data-genre-exclude="${escapeHtml(genre)}"`, `No ${genre}`, 'genre-pop')),
      ...activeFilters(document).map(({id, label, text}) => chip(`data-filter-id="${id}"`, text ? `${label}: ${text}` : label, PANELS[id] || 'more-filters')),
      ...linkChips(state.link).map(({key, text}) => chip(`data-link="${key}"`, text, 'more-filters')),
    ];
    $('tools-count').textContent = chips.length ? ` · ${chips.length}` : '';
    // From five chips on, only three show; the rest sit behind "+n more".
    const total = chips.length;
    if (total >= 5 && !chipsOpen) chips.splice(3, total - 3, `<button class="filter-chip chips-more" type="button" data-chips-more aria-expanded="false">+${total - 3} more</button>`);
    else if (total >= 5) chips.push('<button class="filter-chip chips-more" type="button" data-chips-more aria-expanded="true">Fewer</button>');
    if (total) chips.push('<button class="filter-chip filter-reset" type="button" data-reset-filters>Reset all</button>');
    $('filter-chips').innerHTML = chips.join('');
    $('filter-chips').hidden = !chips.length;
    // Set filters inside "Filters" must not be forgotten: count them on its button.
    const inside = activeFilters(document).filter(({id}) => insidePanel(id)).length;
    $('more-filters-count').textContent = inside ? `· ${inside}` : '';
    $('more-reset').hidden = !inside;
    const setIds = new Set(activeFilters(document).map(({id}) => id));
    document.querySelectorAll('.field-clear').forEach(button => { button.hidden = !setIds.has(button.dataset.clears); });
  }
  // A small × beside each dropdown in the panel clears just that field.
  document.querySelectorAll('.more-filters-grid select').forEach(select => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'field-clear';
    button.hidden = true;
    button.dataset.clears = select.id;
    button.setAttribute('aria-label', `Clear ${select.getAttribute('aria-label') || 'field'}`);
    button.innerHTML = '<i class="ti ti-x" aria-hidden="true"></i>';
    button.addEventListener('click', () => { clearFilter(select); onChange(); });
    select.closest('label').append(button);
  });
  function resetAll() {
    resetFilters(document);
    state.genres = {include: new Set(), exclude: new Set()};
    state.link = emptyLink();
    state.selected = new Set(mySubscriptions());
    setCost('all', false);
    setRuntime(0, false);
    setRating('', false);
    setVotes('0', false);
    buildServicesMenu();
    buildGenreMenu([...document.querySelectorAll('#genre-list input')].map(input => input.value));
    onChange();
  }
  // "Reset" in the panel clears only what is set inside it.
  $('more-reset').addEventListener('click', () => {
    activeFilters(document).filter(({id}) => insidePanel(id)).forEach(({id}) => clearFilter($(id)));
    setAges([], false);
    onChange();
  });
  $('filter-chips').addEventListener('click', event => {
    const open = event.target.closest('.chip-open');
    if (open) { event.stopPropagation(); openPanel(open.dataset.panel); return; }  // else the outside-click rule closes it again
    if (event.target.closest('[data-chips-more]')) { chipsOpen = !chipsOpen; updateChips(); return; }
    if (event.target.closest('[data-reset-filters]')) { resetAll(); return; }
    const button = event.target.closest('.chip-remove')?.closest('.filter-chip');
    if (!button) return;
    if (button.hasAttribute('data-services')) { setServices(mySubscriptions()); return; }
    if (button.dataset.link) { state.link = clearLink(state.link, button.dataset.link); onChange(); return; }
    if (button.dataset.genreInclude || button.dataset.genreExclude) { setGenre(button.dataset.genreInclude || button.dataset.genreExclude, null); return; }
    const input = $(button.dataset.filterId);
    clearFilter(input);
    if (input.id === 'cost-filter') setCost('all', false);
    if (input.id === 'runtime-filter') setRuntime(0, false);
    onChange();
  });

  // ---- links --------------------------------------------------------------------------------------
  function readUrl(params) {
    setCost(params.get('cost') || 'all', false);
    if (params.get('unavailable') === '1') $('show-unavailable').checked = true;
    setRuntime(params.get('max') || 0, false);
    const rating = params.get('rating') || '';
    setRating(/^(lb|tmdb):\d+(\.\d+)?$/.test(rating) ? rating : '', false);
    const list = name => (params.get(name) || '').split(',').filter(value => value && value !== 'all');
    state.genres = {include: new Set(list('genre')), exclude: new Set(list('nogenre'))};
    state.matchMode = params.get('match') === 'all' ? 'all' : 'any';
    state.link = parseLink(params);
    // Films that are nowhere to watch show only on request.
    if (needsUnavailable(state.link)) $('show-unavailable').checked = true;
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
    writeLink(state.link, url.searchParams);
  }

  // ---- a bar that does not fit one row gives Year, then Runtime, then Rating to the "More filters" panel ----------
  // The same element moves (nothing is copied), so the filters, the chips and the URL keep working unchanged.
  // To let another control give way too, add its pop's id to GIVE_WAY (first in the list goes first).
  const GIVE_WAY = ['year-pop', 'runtime-pop', 'rating-pop'];
  const markers = new Map();
  function moveIn(pop) {
    if (markers.has(pop)) return;
    const marker = document.createComment(pop.id);
    pop.before(marker);
    markers.set(pop, marker);
    $('moved-slot').append(pop);
    pop.classList.add('is-moved');
    pop.open = true;
    pop.querySelector('summary').tabIndex = -1;
    $('moved-section').hidden = false;
  }
  function moveBack(pop) {
    const marker = markers.get(pop);
    if (!marker) return;
    pop.classList.remove('is-moved');
    pop.open = false;
    pop.querySelector('summary').removeAttribute('tabindex');
    marker.replaceWith(pop);
    markers.delete(pop);
    $('moved-section').hidden = !markers.size;
  }
  // Closing a moved control (its summary is not clickable, but Enter on it would) opens it again.
  document.addEventListener('toggle', event => { if (event.target.classList?.contains('is-moved') && !event.target.open) event.target.open = true; }, true);
  // The bar and the page tools are one flex row (".watch-bar"; the bar itself is display: contents), so look at all of its items.
  const wrapped = row => {
    const search = $('film-search');
    const floor = search.offsetTop + search.offsetHeight;
    const items = [...row.children].flatMap(child => (getComputedStyle(child).display === 'contents' ? [...child.children] : [child]));
    return items.some(item => item.offsetParent !== null && item.offsetTop >= floor);
  };
  function fitBar() {
    const row = $('film-filters').parentElement;
    const pops = GIVE_WAY.map($);
    pops.forEach(moveBack);
    if (matchMedia('(max-width: 800px)').matches || $('film-search').offsetParent === null) return;  // phones have their own sheet
    for (const pop of pops) {
      if (!wrapped(row)) break;
      moveIn(pop);
    }
    updateChips();
  }
  // The row's own size does not change when a control gives way, so also look again after fonts load, on resize and after each draw.
  new ResizeObserver(fitBar).observe($('film-filters').parentElement);
  addEventListener('resize', fitBar);
  document.fonts?.ready.then(fitBar);
  return {fitBar, buildServicesMenu, buildGenreMenu, buildAgeChips, setAges, setRatingAvailability, updateServicesButton, updateCounts, updateChips, resetAll, setServices, readUrl, writeUrl};
}

