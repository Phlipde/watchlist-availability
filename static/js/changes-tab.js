// The Changes tab of the watchlist (every stored change, newest first, filterable) and the Films | Changes tabs.
import {escapeHtml, numberText} from './ui.js';
import {filmHref} from './rendering.js';
import {filmKey} from './filtering.js';

export function createChangesTab({state}) {
  function renderChanges() {
    const service = document.getElementById('changes-service');
    const kind = document.getElementById('changes-kind').value;
    const mine = document.getElementById('changes-mine').checked;
    const all = (state.changes || []).filter(change => !mine || state.selected.has(change.provider));
    const services = [...new Set(all.map(change => change.provider))].sort();
    const wanted = services.includes(service.value) ? service.value : '';
    service.innerHTML = '<option value="">All services</option>' + services.map(name => `<option value="${escapeHtml(name)}">${escapeHtml(name)}</option>`).join('');
    service.value = wanted;
    // The search box above works here too (on the titles); the other filters belong to the films.
    const query = (document.getElementById('film-search')?.value || '').trim().toLowerCase();
    const rows = all.filter(change => (!wanted || change.provider === wanted) && (!kind || change.change === kind) && (!query || String(change.title).toLowerCase().includes(query)));
    const known = new Set([...state.films, ...state.unavailable].map(filmKey));
    document.getElementById('changes-body').innerHTML = rows.map(change => {
      const title = escapeHtml(change.title) + (change.year ? ` (${numberText(change.year)})` : '');
      const film = known.has(change.film_key) ? `<a class="film-link film-open" href="${escapeHtml(filmHref(location.href, change.film_key))}" data-key="${escapeHtml(change.film_key)}">${title}</a>` : title;
      const event = change.change === 'added' ? '<span class="pill pill-ok">New</span>' : '<span class="pill pill-gone">Gone</span>';
      return `<tr><td>${new Date(change.created * 1000).toLocaleDateString('en-GB', {dateStyle: 'medium'})}</td><td>${film}</td><td>${escapeHtml(change.provider)}</td><td>${event}</td></tr>`;
    }).join('') || `<tr><td colspan="4" class="empty">${query ? 'No change matches the search.' : 'No changes in the last 30 days.'}</td></tr>`;
    document.getElementById('tab-changes-count').textContent = rows.length;
  }
  ['changes-service', 'changes-kind', 'changes-mine'].forEach(id => document.getElementById(id)?.addEventListener('change', renderChanges));
  // Films | Changes: a tab list; arrow keys move between the tabs.
  function showTab(name) {
    ['films', 'changes'].forEach(tab => {
      const button = document.getElementById(`tab-${tab}`);
      button.setAttribute('aria-selected', String(tab === name));
      button.tabIndex = tab === name ? 0 : -1;
      document.getElementById(`${tab}-panel`).hidden = tab !== name;
    });
    // The film count, the view switch and "Save view" are about the films: away while Changes is open.
    document.body.classList.toggle('changes-open', name === 'changes');
  }
  document.querySelector('.view-tabs')?.addEventListener('click', event => {
    const tab = event.target.closest('[role=tab]');
    if (tab) showTab(tab.id.replace('tab-', ''));
  });
  document.querySelector('.view-tabs')?.addEventListener('keydown', event => {
    if (event.key !== 'ArrowRight' && event.key !== 'ArrowLeft') return;
    const next = document.getElementById(event.target.id === 'tab-films' ? 'tab-changes' : 'tab-films');
    next.focus();
    showTab(next.id.replace('tab-', ''));
  });
  return {renderChanges};
}
