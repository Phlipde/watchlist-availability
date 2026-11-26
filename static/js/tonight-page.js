// Tonight (the start page): rows of films, a context line, quick chips, "Pick for me" and the films that just left.
import {ago, escapeHtml, numberText} from './ui.js';
import {showDeadlines} from './deadlines.js';
import {TONIGHT_CHIPS, nowOnText, pickFilm, pickReason, recentlyGone, tonightRows} from './events.js';
import {filmCard, filmHref} from './rendering.js';
import {filmKey, sortFilms} from './filtering.js';

export function createTonightPage({state, imageBaseUrl, view: VIEW, regionLabel, drawViews, ensureAbroad, abroadOnFor, abroadCandidates, abroadFor, abroadList, watchedKeys, hiddenKeys, includedOn, applyTonightRoving, showFilmDetails, showToast, detailsOpener}) {
  const tonightChips = new Set(JSON.parse(localStorage.getItem('tonightChips') || '[]'));
  const picked = new Set(JSON.parse(sessionStorage.getItem('pickedFilms') || '[]'));
  let tonightAvailable = [];
  function renderTonightPage() {
    drawViews();
    showDeadlines(document.getElementById('deadline-banner'), window.WATCHLIST_CONFIG.deadlines, {link: true});
    const {rows, available} = tonightRows(state.films, {services: state.selected, favorites: state.favorites, skip: new Set([...watchedKeys(), ...hiddenKeys()]), chips: tonightChips, now: Date.now() / 1000});
    tonightAvailable = available;
    // With the abroad switch on (remembered in this browser) a last row lists what your services have abroad.
    ensureAbroad();
    if (abroadOnFor()) {
      const shown = new Set([...available.map(filmKey), ...watchedKeys(), ...hiddenKeys()]);
      const checks = TONIGHT_CHIPS.filter(([id, , check]) => tonightChips.has(id) && check).map(([, , check]) => check);
      const list = sortFilms(abroadCandidates(shown).filter(film => checks.every(check => check(film))), 'priority', {favorites: state.favorites});
      if (list.length) rows.push({id: 'abroad', title: 'On your services abroad', films: list, href: '/watchlist?where=abroad'});
    }
    document.getElementById('context-text').innerHTML = `${available.length} films available on <a href="/subscriptions">${state.selected.size} services</a>${state.lastScan ? ` · synced ${ago(state.lastScan)}` : ''}`;
    document.querySelectorAll('.quick-chip').forEach(chip => chip.setAttribute('aria-pressed', String(tonightChips.has(chip.dataset.chip))));
    const context = {imageBaseUrl, providerLogos: window.WATCHLIST_CONFIG.providerLogos, logoBaseUrl: window.WATCHLIST_CONFIG.logoBaseUrl, selected: state.selected, favorites: state.favorites, compareKeys: state.compareKeys, greyKeys: new Set(), favoritesOnly: false, pageHref: location.href, country: document.getElementById('country-select').value, countryName: code => regionLabel.of(code) || code, abroadFor, abroadList};
    const section = (row, film) => (row.id === 'free' || (row.id === 'new' && !Object.values(film.providers || {}).flat().includes('flatrate')) ? 'Free' : 'Paid');
    document.getElementById('tonight-rows').innerHTML = rows.map(row => `<section class="film-row" aria-labelledby="row-${escapeHtml(row.id)}"><div class="film-row-head"><h2 id="row-${escapeHtml(row.id)}">${escapeHtml(row.title)} <span class="row-count">${row.films.length}</span></h2><a class="film-link" href="${escapeHtml(row.href)}">See all</a></div><div class="row-scroller"><button class="row-arrow row-prev" type="button" aria-label="Scroll ${escapeHtml(row.title)} back" tabindex="-1"><i class="ti ti-chevron-left" aria-hidden="true"></i></button><div class="row-track films">${row.films.slice(0, 24).map(film => filmCard(film, section(row, film), context)).join('')}</div><button class="row-arrow row-next" type="button" aria-label="Scroll ${escapeHtml(row.title)} on" tabindex="-1"><i class="ti ti-chevron-right" aria-hidden="true"></i></button></div></section>`).join('')
      || '<p class="empty">No film fits. Tick more services or turn a quick filter off.</p>';
    applyTonightRoving();
    const gone = recentlyGone(state.changes, [...state.films, ...state.unavailable], state.selected, Date.now() / 1000);
    document.getElementById('tonight-gone').hidden = gone.length === 0;
    document.getElementById('tonight-gone-count').textContent = gone.length;
    document.getElementById('tonight-gone-list').innerHTML = gone.map(entry => {
      const title = escapeHtml(entry.title) + (entry.year ? ` (${numberText(entry.year)})` : '');
      const name = entry.film ? `<a class="film-link film-open" href="${escapeHtml(filmHref(location.href, entry.key))}" data-key="${escapeHtml(entry.key)}">${title}</a>` : title;
      return `<li>${name} · gone from ${escapeHtml(entry.providers.join(', '))} ${new Date(entry.created * 1000).toLocaleDateString([], {dateStyle: 'medium'})} · ${escapeHtml(nowOnText(entry))}</li>`;
    }).join('');
  }
  document.querySelector('.tonight-chips')?.addEventListener('click', event => {
    const chip = event.target.closest('.quick-chip');
    if (!chip) return;
    if (tonightChips.has(chip.dataset.chip)) tonightChips.delete(chip.dataset.chip); else tonightChips.add(chip.dataset.chip);
    localStorage.setItem('tonightChips', JSON.stringify([...tonightChips]));
    renderTonightPage();
  });
  // Rows scroll sideways; the arrows move one screen of cards.
  document.getElementById('tonight-rows')?.addEventListener('click', event => {
    const arrow = event.target.closest('.row-arrow');
    if (!arrow) return;
    const track = arrow.parentElement.querySelector('.row-track');
    track.scrollBy({left: (arrow.classList.contains('row-next') ? 1 : -1) * track.clientWidth * 0.9, behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth'});
  });
  function pickForMe(opener) {
    const film = pickFilm(tonightAvailable, picked);
    if (!film) { showToast('No film fits the quick filters.', true); return; }
    picked.add(filmKey(film));
    sessionStorage.setItem('pickedFilms', JSON.stringify([...picked]));
    document.getElementById('pick-for-me').innerHTML = '<i class="ti ti-dice-5" aria-hidden="true"></i> Again';
    showFilmDetails(filmKey(film), opener);
    // The drawer covers the button, so the reason and "Pick another" sit inside it.
    const where = includedOn(film, state.selected);
    const reason = pickReason(film, where ? `on ${where}` : '');
    document.getElementById('film-details-content').insertAdjacentHTML('afterbegin', `<p class="pick-reason"><span>Picked for you${reason ? `: ${escapeHtml(reason)}` : ''}</span><button class="film-link pick-again" type="button"><i class="ti ti-dice-5" aria-hidden="true"></i> Pick another</button></p>`);
  }
  document.getElementById('film-details-content').addEventListener('click', event => {
    if (event.target.closest('.pick-again')) pickForMe(detailsOpener());
  });
  document.getElementById('pick-for-me')?.addEventListener('click', event => pickForMe(event.currentTarget));
  // "r" picks a film; only outside text fields and dialogs.
  document.addEventListener('keydown', event => {
    if (VIEW !== 'tonight' || event.key !== 'r' || event.ctrlKey || event.metaKey || event.altKey) return;
    if (event.target.closest('input, select, textarea, [contenteditable], .modal')) return;
    pickForMe(document.getElementById('pick-for-me'));
  });
  return {renderTonightPage};
}
