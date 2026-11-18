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

// Totals and the price per film follow the prices without a reload.
function recalc() {
  let total = 0;
  rows().forEach(row => {
    const price = priceOf(row);
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

async function save() {
  const costs = {};
  rows().forEach(row => {
    costs[row.dataset.service] = {price: priceOf(row) ?? '', remind_on: row.querySelector('[name=remind_on]').value};
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
