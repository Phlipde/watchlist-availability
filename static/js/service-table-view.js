// The stats page's service table: filter bar, sortable columns, an open row with the best films, state in the URL.
import {escapeHtml} from './ui.js';
import {TYPES, activeFilters, DEFAULTS, filterServices, parseState, sortServices, stateToSearch} from './service-table.js';

const STATUS = {own: ['Your subscription', 'pill-ok'], other: ['Not subscribed', 'pill-neutral'], free: ['Free', 'pill-ok'], store: ['Rent or buy', 'pill-neutral']};
const ROWS = 15;
const dash = count => (count ? String(count) : '–');
const money = value => (value === null ? '–' : `${value.toFixed(2)} €`);
const poster = (base, path) => (path ? `<img src="${escapeHtml(base.replace('/w500', '/w92'))}${escapeHtml(path)}" alt="" width="40" height="60" loading="lazy">` : '<span class="svc-no-poster" aria-hidden="true"></span>');

export function mountServiceTable(root, services, {total, imageBaseUrl}) {
  const state = parseState(location.search);
  const hasPrices = services.some(item => item.costPerLostFilm !== null);
  const columns = [
    ['name', 'Service'], ['status', 'Status'], ['films', 'Films'], ['exclusive', 'Nowhere else', 'Films no other service streams: not free, not with ads, not by subscription'],
    ['hours', 'Hours'], ['free', 'Free'], ['ads', 'Ads'], ['subscription', 'Subscr.'], ['rent', 'Rent'], ['rating', 'Ø rating', 'Average Letterboxd rating of its films'],
    ...(hasPrices ? [['cost', '€ per film you would lose', 'Your monthly price divided by the films only here: none of your other services has them and none is free elsewhere (as on Subscriptions)']] : []),
  ];
  const max = Math.max(...services.map(item => item.films), 1);
  const open = new Set();

  root.innerHTML = `<h2 class="h4 mt-4" id="svc-title">Services</h2>
    <p class="hint">Every service with a film from the watchlist. Click a row for its best films.</p>
    <details class="svc-filters" id="svc-filters"><summary id="svc-filters-summary">Filters</summary>
      <div class="svc-bar" role="search" aria-label="Filter services">
        <input class="form-control" id="svc-q" type="search" placeholder="Search services…" aria-label="Search services">
        <label class="svc-field">Type <select class="form-select form-select-sm" id="svc-type">${TYPES.map(([value, label]) => `<option value="${value}">${label}</option>`).join('')}</select></label>
        <label class="svc-switch"><input type="checkbox" role="switch" id="svc-mine"> Only my subscriptions</label>
        <label class="svc-switch"><input type="checkbox" role="switch" id="svc-excl"> Only with films nowhere else</label>
        <label class="svc-field">At least <input class="form-control" id="svc-min" type="number" min="1" step="1" inputmode="numeric"> films</label>
        <button class="btn btn-sm btn-ghost" id="svc-reset" type="button" hidden>Reset filters</button>
      </div>
    </details>
    <p class="hint" id="svc-count" aria-live="polite"></p>
    <div class="svc-wrap"><table class="status-table stats-table svc-table" id="svc-table"></table></div>
    <button class="btn btn-sm btn-outline-secondary" id="svc-all" type="button" hidden></button>`;
  const $ = id => root.querySelector(`#${id}`);

  const header = () => `<thead><tr>${columns.map(([key, label, hint]) => {
    const active = state.sort === key;
    const arrow = active ? `<i class="ti ti-arrow-${state.dir === 'asc' ? 'up' : 'down'}" aria-hidden="true"></i>` : '';
    return `<th scope="col" aria-sort="${active ? (state.dir === 'asc' ? 'ascending' : 'descending') : 'none'}"${hint ? ` title="${escapeHtml(hint)}"` : ''}><button class="svc-sort" type="button" data-sort="${key}">${escapeHtml(label)}${arrow}</button></th>`;
  }).join('')}</tr></thead>`;

  const detail = item => {
    const films = item.topFilms.map(film => `<li><a href="/watchlist?film=${encodeURIComponent(film.key)}">${poster(imageBaseUrl, film.poster_path)}<span>${escapeHtml(film.title)}${film.year ? ` <span class="muted">(${escapeHtml(String(film.year))})</span>` : ''}</span></a></li>`).join('');
    const plans = item.plans.length > 1 ? `<p class="hint">Plans: ${escapeHtml(item.plans.join(', '))}</p>` : '';
    return `${plans}${films ? `<ol class="svc-top">${films}</ol>` : ''}<a href="/watchlist?providers=${encodeURIComponent(item.plans.join(','))}">All ${item.films} films on the watchlist</a>`;
  };

  const row = item => {
    const [label, tone] = STATUS[item.status];
    const id = `svc-${item.group.replace(/\W+/g, '-')}`;
    const cell = (name, content, cls = 'num') => `<td class="${cls}" data-label="${name}">${content}</td>`;
    return `<tr class="svc-row${item.own ? ' own-service' : ''}${open.has(item.group) ? ' open' : ''}" data-group="${escapeHtml(item.group)}">
      <th scope="row"><button class="svc-name" type="button" aria-expanded="${open.has(item.group)}" aria-controls="${id}">${escapeHtml(item.group)}</button></th>
      ${cell('Status', `<span class="pill ${tone}">${label}</span>`, 'svc-status')}
      ${cell('Films', `<span class="bar-track inline" aria-hidden="true"><span class="bar" style="width:${item.films / max * 100}%"></span></span>${item.films} <span class="muted">(${Math.round(item.films / total * 100)}%)</span>`)}
      ${cell('Nowhere else', dash(item.exclusive))}${cell('Hours', dash(item.hours))}${cell('Free', dash(item.free))}${cell('Ads', dash(item.ads))}
      ${cell('Subscr.', dash(item.subscription))}${cell('Rent', dash(item.rent))}${cell('Ø rating', item.averageRating === null ? '–' : item.averageRating.toFixed(2))}
      ${hasPrices ? cell('€ per film you would lose', money(item.costPerLostFilm)) : ''}
    </tr>
    <tr class="svc-detail" id="${id}"${open.has(item.group) ? '' : ' hidden'}><td colspan="${columns.length}">${detail(item)}</td></tr>`;
  };

  function renderTable() {
    const found = sortServices(filterServices(services, state), state.sort, state.dir);
    const shown = state.all ? found : found.slice(0, ROWS);
    $('svc-count').textContent = `${found.length} of ${services.length} services`;
    $('svc-table').innerHTML = found.length
      ? `${header()}<tbody>${shown.map(row).join('')}</tbody>`
      : '<tbody><tr><td class="svc-empty">No service matches these filters. <button class="btn btn-sm btn-outline-secondary" type="button" data-reset>Reset filters</button></td></tr></tbody>';
    const more = $('svc-all');
    more.hidden = found.length <= ROWS;
    more.textContent = state.all ? `Show the first ${ROWS}` : `Show all ${found.length} services`;
    const count = activeFilters(state);
    $('svc-filters-summary').textContent = count ? `Filters (${count} active)` : 'Filters';
    $('svc-reset').hidden = !count;
    history.replaceState(history.state, '', `${location.pathname}${stateToSearch(state, location.search)}${location.hash}`);
  }

  const fillControls = () => {
    $('svc-q').value = state.q;
    $('svc-type').value = state.type;
    $('svc-mine').checked = state.mine;
    $('svc-excl').checked = state.exclusive;
    $('svc-min').value = state.min;
  };
  const change = patch => { Object.assign(state, patch); renderTable(); };
  const reset = () => { Object.assign(state, {...DEFAULTS, sort: state.sort, dir: state.dir, all: state.all}); fillControls(); renderTable(); };

  let timer;
  $('svc-q').addEventListener('input', event => { clearTimeout(timer); timer = setTimeout(() => change({q: event.target.value}), 150); });
  $('svc-type').addEventListener('change', event => change({type: event.target.value}));
  $('svc-mine').addEventListener('change', event => change({mine: event.target.checked}));
  $('svc-excl').addEventListener('change', event => change({exclusive: event.target.checked}));
  $('svc-min').addEventListener('input', event => change({min: Math.max(1, Number.parseInt(event.target.value, 10) || 1)}));
  $('svc-reset').addEventListener('click', reset);
  $('svc-all').addEventListener('click', () => change({all: !state.all}));
  $('svc-table').addEventListener('click', event => {
    if (event.target.closest('[data-reset]')) { reset(); return; }
    const sort = event.target.closest('[data-sort]');
    if (sort) {
      const key = sort.dataset.sort;
      change({sort: key, dir: state.sort === key ? (state.dir === 'desc' ? 'asc' : 'desc') : (key === 'name' ? 'asc' : 'desc')});
      $('svc-table').querySelector(`[data-sort="${key}"]`)?.focus();
      return;
    }
    const rowElement = event.target.closest('.svc-row');
    if (!rowElement || event.target.closest('a')) return;
    const group = rowElement.dataset.group;
    const isOpen = !open.has(group);
    if (isOpen) open.add(group); else open.delete(group);
    rowElement.classList.toggle('open', isOpen);
    rowElement.querySelector('.svc-name').setAttribute('aria-expanded', String(isOpen));
    rowElement.nextElementSibling.hidden = !isOpen;
  });

  fillControls();
  // A phone starts with the filters folded away unless some are active.
  $('svc-filters').open = !matchMedia('(max-width: 800px)').matches || activeFilters(state) > 0;
  renderTable();
}
