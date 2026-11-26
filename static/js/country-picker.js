// The country picker (partials/country-picker.html): a menu with a search field and one flag per country.
// countryMatches is pure (tested in node); the rest runs only when a page calls it.

const plain = text => text.normalize('NFD').replace(/\p{M}/gu, '').toLowerCase();

// "pl" finds PL by its code, "ivo" or "cote" finds Côte d'Ivoire by its name.
// 0: by the code (listed first, so "fr" puts France above Central African Republic), 1: by the name, null: no match.
export function countryRank(code, name, query) {
  const wanted = plain(query.trim());
  if (!wanted || code.toLowerCase().startsWith(wanted)) return 0;
  return plain(name || '').includes(wanted) ? 1 : null;
}
export const countryMatches = (code, name, query) => countryRank(code, name, query) !== null;

const jsonRequest = (method, body) => ({method, headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});

// Makes `code` the app's country; returns the saved settings (with the country's services) or throws.
export async function saveCountry(code) {
  const response = await fetch('/api/settings', jsonRequest('PUT', {country: code}));
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || 'Could not save the country.');
  return data;
}

// Pages without the film list: save, start the country's scan and follow it on the watchlist.
// A scan that cannot start (no TMDB key) still lands on the watchlist, which says why.
export async function switchCountryAway(code) {
  await saveCountry(code);
  let job = null;
  try {
    const response = await fetch('/api/scan', jsonRequest('POST', {country: code}));
    job = response.ok ? (await response.json()).job_id : null;
  } catch { /* the watchlist shows the state */ }
  location.href = job ? `/watchlist?scan=${encodeURIComponent(job)}` : '/watchlist';
}

// onPick(code) may return a promise: further picks wait until it settles (no two saves in flight);
// false puts the previous country back.
export function initCountryPicker(root, {onPick}) {
  const names = new Intl.DisplayNames(['en'], {type: 'region'});
  const search = root.querySelector('.country-search');
  const options = [...root.querySelectorAll('.country-option')];
  const none = root.querySelector('.country-none');
  for (const option of options) {
    let name = '';
    try { name = names.of(option.dataset.code) || ''; } catch { /* unknown to this browser */ }
    option.dataset.name = name === option.dataset.code ? '' : name;
    option.querySelector('.country-name').textContent = option.dataset.name;
  }
  let busy = false;
  const set = code => {
    root.dataset.current = code;
    const summary = root.querySelector('summary');
    summary.querySelector('img').src = `/static/flags/${code.toLowerCase()}.svg`;
    summary.querySelector('.country-code').textContent = code;
    summary.setAttribute('aria-label', `Country: ${names.of(code) || code}. Change country`);
    options.forEach(option => option.setAttribute('aria-pressed', String(option.dataset.code === code)));
  };
  const list = root.querySelector('.country-list');
  const filter = () => {
    const ranked = [[], []];
    for (const option of options) {
      const rank = countryRank(option.dataset.code, option.dataset.name, search.value);
      option.hidden = rank === null;
      if (rank !== null) ranked[rank].push(option);
    }
    // Code hits first in the DOM too: the arrow keys follow the DOM order.
    list.append(...ranked[0], ...ranked[1], ...options.filter(option => option.hidden));
    none.hidden = ranked[0].length + ranked[1].length > 0;
  };
  async function pick(code) {
    root.open = false;
    root.querySelector('summary').focus();
    if (busy || code === root.dataset.current) return;
    const before = root.dataset.current;
    set(code);
    busy = true;
    root.setAttribute('aria-busy', 'true');
    try {
      if (await onPick(code) === false) set(before);
    } finally {
      busy = false;
      root.removeAttribute('aria-busy');
    }
  }
  search.addEventListener('input', filter);
  search.addEventListener('keydown', event => {
    if (event.key !== 'Enter') return;
    event.preventDefault();
    // "de" picks DE, not Denmark (DK starts with D too).
    const first = options.find(option => option.dataset.code === search.value.trim().toUpperCase()) || list.querySelector('.country-option:not([hidden])');
    if (first) pick(first.dataset.code);
  });
  root.addEventListener('click', event => {
    const option = event.target.closest('.country-option');
    if (option) pick(option.dataset.code);
  });
  root.addEventListener('toggle', () => {
    if (!root.open) return;
    search.value = '';
    filter();
    options.find(option => option.dataset.code === root.dataset.current)?.scrollIntoView({block: 'nearest'});
    // On a touch screen the keyboard would cover the list: the search field waits for a tap.
    if (!matchMedia('(pointer: coarse)').matches) search.focus();
  });
  set(root.dataset.current);
  return {set};
}
