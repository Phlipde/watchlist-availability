// Subscriptions page: prices and dates save when you leave the field; totals follow at once.
import {showDeadlines} from './deadlines.js';
const page = document.getElementById('subscriptions-page');
const country = page.dataset.country;
const table = document.getElementById('subscriptions-table');
const state = document.getElementById('save-state');
const money = value => value.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
const dayText = iso => (iso ? new Date(`${iso}T12:00:00`).toLocaleDateString(undefined, {day: '2-digit', month: '2-digit', year: 'numeric'}) : 'Set date');
const number = text => Number(String(text).replace(',', '.'));
let timer;

// The banner for dates within a week; "Not interested" hides a recommendation for 30 days (this browser only).
const banner = document.getElementById('deadline-banner');
showDeadlines(banner, banner ? JSON.parse(banner.dataset.deadlines || '[]') : []);
const HIDE_KEY = 'hiddenRecommendations';
const hidden = () => { try { return JSON.parse(localStorage.getItem(HIDE_KEY) || '{}'); } catch { return {}; } };
document.querySelectorAll('.rec').forEach(card => { if (hidden()[card.dataset.rec] > Date.now()) card.hidden = true; });
document.querySelectorAll('.rec-hide').forEach(button => button.addEventListener('click', () => {
  const card = button.closest('.rec');
  localStorage.setItem(HIDE_KEY, JSON.stringify({...hidden(), [card.dataset.rec]: Date.now() + 30 * 86400000}));
  card.hidden = true;
}));
document.querySelectorAll('.set-reminder').forEach(button => button.addEventListener('click', () => {
  const row = [...document.querySelectorAll('tr[data-service]')].find(item => item.dataset.service === button.dataset.service);
  row?.querySelector('.date-button')?.click();
}));

function rows() { return table ? [...table.querySelectorAll('tbody tr[data-service]')] : []; }
const priceOf = row => {
  const text = row.querySelector('[name=price]').value.trim();
  return text === '' || Number.isNaN(number(text)) ? null : number(text);
};

// Numbers and dates follow the browser's language (21.11.2026 in Germany).
document.querySelectorAll('[data-money]').forEach(element => { element.textContent = money(number(element.textContent)); });
rows().forEach(row => {
  const button = row.querySelector('.date-button');
  button.textContent = dayText(row.querySelector('[name=remind_on]').value);
});
function markSoon() {
  rows().forEach(row => {
    const iso = row.querySelector('[name=remind_on]').value;
    const days = iso ? (new Date(`${iso}T12:00:00`) - Date.now()) / 86400000 : Infinity;
    row.querySelector('.date-button').classList.toggle('is-soon', days <= 7);
  });
}

const details = new Map(rows().map(row => [row.dataset.service, JSON.parse(row.dataset.detail || '{}')]));

// Totals and the price per film follow the prices without a reload.
function recalc() {
  let total = 0;
  rows().forEach(row => {
    // A shared account (set in the drawer) splits the price.
    const full = priceOf(row);
    const price = full === null ? null : full / (details.get(row.dataset.service)?.shared || 1);
    total += price || 0;
    const cell = row.querySelector('.per-film');
    const only = Number(row.dataset.only);
    if (price && only) cell.innerHTML = `<span data-money>${money(price / only)}</span>`;
    else if (only) cell.innerHTML = '<button class="film-link add-price" type="button">add price</button>';
  });
  if (table) {
    document.getElementById('total-month').textContent = money(total);
    document.getElementById('total-year').textContent = money(total * 12);
    document.getElementById('price-hint').hidden = rows().some(row => priceOf(row) !== null);
  }
}

// What the drawer edits per service (shared with n people, notice days, trial date, note, cancellation link).
const extraOf = name => {
  const detail = details.get(name) || {};
  return {shared: detail.shared > 1 ? detail.shared : '', notice_days: detail.notice_days ?? '', trial_on: detail.trial_on || '', note: detail.note || '', cancel_url: detail.cancel_url || ''};
};

async function save() {
  const costs = {};
  rows().forEach(row => {
    costs[row.dataset.service] = {price: priceOf(row) ?? '', remind_on: row.querySelector('[name=remind_on]').value, ...extraOf(row.dataset.service)};
  });
  state.textContent = 'Saving…';
  try {
    const response = await fetch('/api/settings', {
      method: 'PUT',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({subscriptions_country: country, costs}),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || 'Could not save.');
    state.textContent = 'Saved';
    state.classList.remove('text-danger');
    clearTimeout(timer);
    timer = setTimeout(() => { state.textContent = ''; }, 3000);
  } catch (error) {
    state.textContent = error instanceof TypeError ? 'Could not reach the app.' : error.message;
    state.classList.add('text-danger');
  }
}

if (table) {
  table.addEventListener('change', event => {
    if (event.target.name === 'remind_on') {
      event.target.closest('tr').querySelector('.date-button').textContent = dayText(event.target.value);
      markSoon();
    }
    if (event.target.name === 'price') {
      const price = priceOf(event.target.closest('tr'));
      if (event.target.value.trim() !== '' && price === null) { state.textContent = 'The price must be a number.'; state.classList.add('text-danger'); return; }
      if (price !== null) event.target.value = String(price);
    }
    recalc();
    save();
  });
  table.addEventListener('click', event => {
    const date = event.target.closest('.date-button');
    if (date) {
      const input = date.parentElement.querySelector('.date-input');
      if (input.showPicker) input.showPicker(); else input.focus();
    }
    const head = event.target.closest('.sort-head');
    if (head) sortBy(head);
  });
  document.addEventListener('click', event => {
    if (!event.target.closest('.add-price')) return;
    const empty = rows().map(row => row.querySelector('[name=price]')).find(input => input.value.trim() === '');
    (empty || rows()[0]?.querySelector('[name=price]'))?.focus();
  });
  // Sorting by a column header; the table starts sorted by "Only here".
  function sortBy(head) {
    const key = head.dataset.sort;
    const descending = head.getAttribute('aria-sort') !== 'descending' && key !== 'name' && key !== 'remind' ? true : head.getAttribute('aria-sort') === 'ascending';
    const value = row => {
      if (key === 'name') return row.dataset.service.toLowerCase();
      if (key === 'price') return priceOf(row) ?? -1;
      if (key === 'remind') return row.querySelector('[name=remind_on]').value || '9999';
      if (key === 'perfilm') return priceOf(row) && Number(row.dataset.only) ? priceOf(row) / Number(row.dataset.only) : -1;
      return Number(row.dataset[key]);
    };
    const sorted = rows().sort((a, b) => (value(a) > value(b) ? 1 : value(a) < value(b) ? -1 : 0) * (descending ? -1 : 1));
    sorted.forEach(row => table.tBodies[0].append(row));
    table.querySelectorAll('.sort-head').forEach(button => button.removeAttribute('aria-sort'));
    head.setAttribute('aria-sort', descending ? 'descending' : 'ascending');
  }
  recalc();
  markSoon();
}

// ---- the drawer of one service: the numbers, the films only here, what you keep elsewhere, and your own notes ----
const drawer = document.getElementById('service-drawer');
const escape = text => String(text ?? '').replace(/[&<>"']/g, char => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[char]));
const filmLinks = films => films.map(film => `<li><a href="/watchlist?film=${encodeURIComponent(film.key || '')}">${film.poster_path ? `<img src="${window.IMAGE_BASE_URL || ''}${escape(film.poster_path)}" alt="" loading="lazy">` : '<span class="no-poster" aria-hidden="true">No poster</span>'}<span>${escape(film.title)}${film.year ? ` (${escape(film.year)})` : ''}</span></a></li>`).join('');
function openDrawer(name, opener) {
  const detail = details.get(name);
  if (!detail || !drawer) return;
  document.getElementById('service-drawer-title').textContent = name;
  const only = detail.only_here || [];
  const elsewhere = detail.elsewhere || [];
  const weeks = detail.hours && window.WEEKLY_HOURS ? detail.hours / window.WEEKLY_HOURS : 0;
  const pace = !weeks ? '–' : weeks >= 4.345 ? `≈ ${Math.round(weeks / 4.345)} mo` : `≈ ${Math.max(1, Math.round(weeks))} wk`;
  const field = (id, label, type, value, extra = '') => `<label class="menu-field"><span>${label}</span><input class="form-control form-control-sm" id="drawer-${id}" name="${id}" type="${type}" value="${escape(value)}" ${extra}></label>`;
  document.getElementById('service-drawer-body').innerHTML = `
    <dl class="figures"><div><dt>Watchlist</dt><dd>${detail.films}</dd></div><div><dt>Only here</dt><dd>${only.length}${detail.favorites ? ` <span class="fav-count"><i class="ti ti-heart-filled" aria-hidden="true"></i> ${detail.favorites}</span>` : ''}</dd></div><div><dt>Value</dt><dd>${detail.value}</dd></div><div><dt>Hours</dt><dd>${detail.hours} h</dd></div><div><dt>Your pace</dt><dd>${pace}</dd></div><div><dt>€ / film</dt><dd>${detail.per_film != null ? money(detail.per_film) : '–'}</dd></div></dl>
    <h3>Only here <span class="row-count">${only.length}</span></h3>
    ${only.length ? `<ul class="poster-grid">${filmLinks(only.slice(0, 36))}</ul>${only.length > 36 ? `<p class="hint">and ${only.length - 36} more: <a href="/watchlist?providers=${encodeURIComponent(name)}&only=1&cost=subscription">see them all</a></p>` : ''}` : '<p class="hint">Nothing: cancelling loses no film you cannot watch elsewhere.</p>'}
    <h3>Also elsewhere <span class="row-count">${elsewhere.length}</span></h3>
    <p class="hint">${elsewhere.length ? `These stay available on another service of yours or for free when you cancel: ${elsewhere.slice(0, 8).map(film => escape(film.title)).join(', ')}${elsewhere.length > 8 ? ' …' : ''}.` : 'Every film here is only on this service.'}</p>
    <h3>Your notes</h3>
    <div class="drawer-fields">
      ${field('shared', 'Shared with (people, splits the price)', 'number', detail.shared > 1 ? detail.shared : '', 'min="1" max="20" step="1" placeholder="1"')}
      ${field('notice_days', 'Notice period (days)', 'number', detail.notice_days ?? '', 'min="0" max="365" step="1"')}
      ${field('trial_on', 'Trial used on', 'date', detail.trial_on || '')}
      ${field('cancel_url', 'Cancellation page', 'url', detail.cancel_url || '', 'placeholder="https://…"')}
      <label class="menu-field"><span>Note</span><textarea class="form-control form-control-sm" id="drawer-note" name="note" rows="2" maxlength="300">${escape(detail.note || '')}</textarea></label>
    </div>
    ${detail.cancel_url ? `<p><a class="film-link" href="${escape(detail.cancel_url)}" target="_blank" rel="noreferrer noopener">Open the cancellation page ↗</a></p>` : ''}`;
  drawer.dataset.service = name;
  drawer.opener = opener;
  drawer.showModal();
}
const openFrom = event => {
  const button = event.target.closest('.service-open');
  if (button) openDrawer(button.dataset.service, button);
};
table?.addEventListener('click', openFrom);
document.getElementById('service-drawer-close')?.addEventListener('click', () => drawer.close());
drawer?.addEventListener('click', event => { if (event.target === drawer) drawer.close(); });  // a click on the dimmed page closes it
drawer?.addEventListener('close', () => drawer.opener?.focus());
drawer?.addEventListener('change', event => {
  const name = drawer.dataset.service;
  const detail = details.get(name);
  if (!detail || !event.target.name) return;
  const value = event.target.value.trim();
  if (event.target.name === 'shared') detail.shared = value ? Number(value) : 1;
  else if (event.target.name === 'notice_days') detail.notice_days = value === '' ? null : Number(value);
  else detail[event.target.name] = value;
  recalc();
  save();
});
