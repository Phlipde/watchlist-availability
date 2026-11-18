// Saved views ("Movie night with Lea"): a name and the filters of the watchlist address, kept in this browser.
const KEY = 'savedViews';
const escape = text => String(text).replace(/[&<>"']/g, char => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[char]));

export function loadViews() {
  try {
    const views = JSON.parse(localStorage.getItem(KEY) || '[]');
    return Array.isArray(views) ? views.filter(view => typeof view?.name === 'string' && typeof view?.search === 'string') : [];
  } catch {
    return [];
  }
}

// The filters of an address without the film that is open and the scan job.
export function viewSearch(search) {
  const params = new URLSearchParams(search);
  params.delete('film');
  params.delete('scan');
  const text = params.toString();
  return text ? `?${text}` : '';
}

export function saveView(name, search, views = loadViews()) {
  const clean = name.trim().slice(0, 40);
  if (!clean) return views;
  const next = [...views.filter(view => view.name !== clean), {name: clean, search: viewSearch(search)}].slice(-12);
  localStorage.setItem(KEY, JSON.stringify(next));
  return next;
}

export function removeView(name, views = loadViews()) {
  const next = views.filter(view => view.name !== name);
  localStorage.setItem(KEY, JSON.stringify(next));
  return next;
}

// Draws the saved views as chips into `container`; `canSave` adds "Save this view" (used on the watchlist).
export function renderViews(container, {canSave = false, search = ''} = {}) {
  if (!container) return;
  const views = loadViews();
  const chips = views.map(view => `<span class="filter-chip saved-view"><a class="chip-open" href="/watchlist${escape(view.search)}">${escape(view.name)}</a><button class="chip-remove" type="button" data-remove-view="${escape(view.name)}" aria-label="Delete the view ${escape(view.name)}"><i class="ti ti-x" aria-hidden="true"></i></button></span>`).join('');
  const save = canSave && viewSearch(search)
    ? '<form class="view-form"><label class="visually-hidden" for="view-name">Name of the view</label><input class="form-control form-control-sm" id="view-name" maxlength="40" placeholder="Name this view" autocomplete="off"><button class="btn btn-sm btn-outline-secondary" type="submit">Save view</button></form>'
    : '';
  container.innerHTML = chips || save ? `<span class="views-label">Views</span>${chips}${save}` : '';
  container.hidden = !(chips || save);
}

export function wireViews(container, getSearch, onChange) {
  container?.addEventListener('submit', event => {
    event.preventDefault();
    saveView(container.querySelector('input').value, getSearch());
    onChange();
  });
  container?.addEventListener('click', event => {
    const button = event.target.closest('[data-remove-view]');
    if (!button) return;
    removeView(button.dataset.removeView);
    onChange();
  });
}
