// The watchlist grid in Together (/watchlist?together=2,3): your list merged with the other profiles' lists
// (/api/together), the members' services ticked, whose each service is on the logos. "Back to my list" leaves it.
import {ownerText, ownersOf, whose} from './owners.js';
import {escapeHtml} from './ui.js';

// The ids from ?together=, or [] (only positive whole numbers count).
export function togetherIdsFrom(search) {
  const value = new URLSearchParams(search).get('together') || '';
  return [...new Set(value.split(',').filter(id => /^[1-9]\d{0,8}$/.test(id)).map(Number))];
}

// The address without ?together= (and without the ticked services, which were the members' services).
export function myListHref(href) {
  const url = new URL(href);
  url.searchParams.delete('together');
  url.searchParams.delete('providers');
  return url.pathname + url.search;
}

export function createTogetherGrid({state, view, filterBar, populateGenres, renderFilms, showToast}) {
  let ids = view === 'watchlist' ? togetherIdsFrom(location.search) : [];
  let data = null;        // the answer of /api/together
  let loadedFor = null;   // the time of your scan it belongs to
  const members = () => data?.together?.members || [];
  const owners = service => ownersOf(service, data.together.service_owners, members());
  const country = () => document.getElementById('country-select').value;

  function note() {
    let element = document.getElementById('together-grid-note');
    if (!element) {
      element = document.createElement('p');
      element.className = 'meta together-grid-note';
      element.id = 'together-grid-note';
      document.getElementById('result-meta').insertAdjacentElement('afterend', element);
    }
    const others = members().slice(1);
    const missing = others.filter(member => (data.missing || []).includes(member.id));
    element.innerHTML = `Together with ${escapeHtml(others.map(member => member.name).join(', '))} · <a class="film-link" href="${escapeHtml(myListHref(location.href))}">Back to my list</a>`
      + missing.map(member => ` · ${escapeHtml(member.name)} has no recent scan for ${escapeHtml(country())} — their list may be out of date.`).join('');
  }
  function apply() {
    state.films = data.results;
    state.unavailable = data.unavailable;
    // "My subscriptions" in the services menu are everybody's services while Together is on (not saved).
    window.WATCHLIST_CONFIG.subscriptions = {...window.WATCHLIST_CONFIG.subscriptions, [country()]: data.subscriptions};
    populateGenres();
    note();
    if (new URLSearchParams(location.search).has('providers')) renderFilms();  // a link's services win
    else filterBar.setServices(data.subscriptions);
  }
  function leave(message) {
    ids = [];
    showToast(message, true);
    populateGenres();
    renderFilms();
  }
  // Called when your own films arrive (page load, finished scan): true when Together takes over the drawing.
  function show() {
    if (!ids.length) return false;
    if (data && loadedFor === state.lastScan) { apply(); return true; }
    const wanted = state.lastScan;
    loadedFor = wanted;
    fetch(`/api/together?with=${ids.join(',')}`)
      .then(response => (response.ok ? response.json() : Promise.reject(new Error(String(response.status)))))
      .then(answer => {
        if (loadedFor !== wanted || !ids.length) return;
        if (!answer.available) { leave('Your list has no scan yet. Showing your list.'); return; }
        data = answer;
        apply();
      }, () => { if (loadedFor === wanted) leave('Together could not load. Showing your list.'); });
    return true;
  }
  const on = () => ids.length > 0 && data !== null;
  return {
    show,
    // For the cards: whose each service is (undefined outside Together).
    ownersOf: () => (on() ? service => { const list = owners(service); return {owners: list, text: ownerText(list, members()[0]?.id)}; } : undefined),
    // For the drawer, like togetherMode on Tonight (the films are already in state.films).
    mode: () => (on() ? {films: [], own: new Set(data.subscriptions), whose: service => whose(owners(service), members()[0]?.id)} : null),
  };
}
