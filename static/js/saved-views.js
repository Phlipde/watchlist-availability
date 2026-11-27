// Saved views ("Movie night with Lea"): a name and the filters of the watchlist address, kept in this browser.
import {local, storageFor} from './profile-storage.js';
const KEY = 'savedViews';
const escape = text => String(text).replace(/[&<>"']/g, char => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[char]));

export function loadViews(storage = local) {
  try {
    const views = JSON.parse(storage.getItem(KEY) || '[]');
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

export function saveView(name, search, views = loadViews(), storage = local) {
  const clean = name.trim().slice(0, 40);
  if (!clean) return views;
  const next = [...views.filter(view => view.name !== clean), {name: clean, search: viewSearch(search)}].slice(-12);
  storage.setItem(KEY, JSON.stringify(next));
  return next;
}

// "Copy to profile …": the view joins the other profile's views on this device (same name: replaced).
export function copyView(view, storage) {
  return saveView(view.name, view.search, loadViews(storage), storage);
}

// The other profiles, as the header's profile menu lists them.
const otherProfiles = () => [...document.querySelectorAll('#profile-pop [data-profile-id]')]
  .map(button => ({id: button.dataset.profileId, name: button.textContent.trim()}));

export function removeView(name, views = loadViews()) {
  const next = views.filter(view => view.name !== name);
  local.setItem(KEY, JSON.stringify(next));
  return next;
}

// The "Save view" ghost button with its small popover (name and Save), shown only while filters are set.
export function saveViewHtml(search) {
  if (!viewSearch(search)) return '';
  return '<details class="filter-pop save-pop"><summary class="btn btn-sm btn-ghost">Save view</summary><div class="filter-menu menu"><form class="view-form"><label class="form-label small" for="view-name">Name of the view</label><input class="form-control form-control-sm" id="view-name" maxlength="40" placeholder="Name this view" autocomplete="off"><button class="btn btn-sm btn-accent" type="submit">Save this view</button></form></div></details>';
}

// The saved views as a list for the "Views" dropdown: each an address, with "Copy link", "Copy to profile"
// (only when there are other profiles) and delete.
export function viewsMenuHtml(views, others = []) {
  const options = others.map(profile => `<option value="${escape(profile.id)}">${escape(profile.name)}</option>`).join('');
  return views.map(view => {
    const name = escape(view.name);
    const copy = options ? `<select class="form-select form-select-sm view-copy" data-copy-view="${name}" aria-label="Copy the view ${name} to a profile"><option value="">Copy to…</option>${options}</select>` : '';
    return `<div class="menu-row"><a class="menu-item" href="/watchlist${escape(view.search)}">${name}</a><button class="btn btn-sm btn-ghost btn-icon" type="button" data-share-view="${name}" aria-label="Copy the link of the view ${name}"><i class="ti ti-link" aria-hidden="true"></i></button>${copy}<button class="btn btn-sm btn-ghost btn-icon" type="button" data-remove-view="${name}" aria-label="Delete the view ${name}"><i class="ti ti-x" aria-hidden="true"></i></button></div>`;
  }).join('');
}

// Tonight: the saved views as chips; the watchlist: "Save view" (row of the active filters) and the "Views" dropdown.
export function renderViews(container, {canSave = false, search = ''} = {}) {
  if (!container) return;
  const views = loadViews();
  if (canSave) {
    const save = saveViewHtml(search);
    container.innerHTML = save;
    container.hidden = !save;
    const pop = document.getElementById('views-pop');
    if (pop) {
      document.getElementById('views-menu').innerHTML = viewsMenuHtml(views, otherProfiles());
      pop.hidden = views.length === 0;
    }
    return;
  }
  const chips = views.map(view => `<span class="filter-chip saved-view"><a class="chip-open" href="/watchlist${escape(view.search)}">${escape(view.name)}</a><button class="chip-remove" type="button" data-remove-view="${escape(view.name)}" aria-label="Delete the view ${escape(view.name)}"><i class="ti ti-x" aria-hidden="true"></i></button></span>`).join('');
  container.innerHTML = chips ? `<span class="views-label">Views</span>${chips}` : '';
  container.hidden = !chips;
}

export function wireViews(container, getSearch, onChange, showToast = () => {}) {
  const find = name => loadViews().find(view => view.name === name);
  container?.addEventListener('submit', event => {
    event.preventDefault();
    saveView(container.querySelector('input').value, getSearch());
    onChange();
  });
  container?.addEventListener('click', async event => {
    const share = event.target.closest('[data-share-view]');
    if (share) {
      const link = `${location.origin}/watchlist${find(share.dataset.shareView)?.search || ''}`;
      try {
        await navigator.clipboard.writeText(link);
        showToast('Link copied.');
      } catch {
        window.prompt('Copy this link:', link);  // no clipboard over plain http in the home network
      }
      return;
    }
    const button = event.target.closest('[data-remove-view]');
    if (!button) return;
    removeView(button.dataset.removeView);
    onChange();
  });
  container?.addEventListener('change', event => {
    const select = event.target.closest('[data-copy-view]');
    const view = select && find(select.dataset.copyView);
    if (!view || !select.value) return;
    copyView(view, storageFor(localStorage, select.value));
    showToast(`Copied to ${select.selectedOptions[0].textContent}.`);
    select.value = '';
  });
}
