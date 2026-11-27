// Tonight (the start page): rows of films, a context line, quick chips, "Pick for me" and the films that just left.
import {local} from './profile-storage.js';
import {ago, escapeHtml, numberText} from './ui.js';
import {showDeadlines} from './deadlines.js';
import {TONIGHT_CHIPS, nowOnText, pickFilm, pickReason, recentlyGone, togetherRows, tonightRows} from './events.js';
import {ownerText, ownersOf, whose} from './owners.js';
import {filmCard, filmHref} from './rendering.js';
import {filmKey, sortFilms} from './filtering.js';

export function createTonightPage({state, imageBaseUrl, view: VIEW, regionLabel, drawViews, ensureAbroad, abroadOnFor, abroadCandidates, abroadFor, abroadList, watchedKeys, hiddenKeys, includedOn, applyTonightRoving, showFilmDetails, showToast, detailsOpener}) {
  const tonightChips = new Set(JSON.parse(local.getItem('tonightChips') || '[]'));
  const picked = new Set(JSON.parse(sessionStorage.getItem('pickedFilms') || '[]'));
  let tonightAvailable = [];
  // ---- Together: the lists of other profiles merged with yours (/api/together), remembered in this browser ----
  const TOGETHER_KEY = 'togetherWith';  // per profile, see profile-storage.js
  const picks = () => [...document.querySelectorAll('.together-pick')];
  const togetherIds = () => picks().filter(box => box.checked).map(box => Number(box.value));
  const savedIds = new Set(JSON.parse(local.getItem(TOGETHER_KEY) || '[]'));
  picks().forEach(box => { box.checked = savedIds.has(Number(box.value)); });  // ids of deleted profiles drop out
  let together = null;    // the answer of /api/together for `togetherFor`
  let togetherFor = '';   // "2,3|<time of your last scan>": a new scan of yours loads it again
  function loadTogether() {
    const ids = togetherIds();
    const wanted = ids.length ? `${ids.join(',')}|${state.lastScan}` : '';
    if (wanted === togetherFor) return;
    togetherFor = wanted;
    together = null;
    if (!wanted) return;
    fetch(`/api/together?with=${ids.join(',')}`)
      .then(response => (response.ok ? response.json() : Promise.reject(new Error(String(response.status)))))
      .then(data => { if (togetherFor === wanted) { together = data; renderTonightPage(); } }, () => {
        if (togetherFor !== wanted) return;
        setTogether([]);
        showToast('Together could not load. Showing your list.', true);
      });
  }
  function setTogether(ids) {
    picks().forEach(box => { box.checked = ids.includes(Number(box.value)); });
    local.setItem(TOGETHER_KEY, JSON.stringify(ids));
    renderTonightPage();
  }
  const members = () => together?.together?.members || [];
  const ownersFor = service => ownersOf(service, together.together.service_owners, members());
  // For the drawer and "Pick for me" while Together is on (and loaded): the partners' films, everybody's services.
  function togetherMode() {
    if (!togetherIds().length || !together?.available) return null;
    return {films: [...together.results, ...together.unavailable], own: new Set(together.subscriptions), whose: service => whose(ownersFor(service), members()[0]?.id)};
  }
  function showTogetherControls(on) {
    if (!document.getElementById('together-pop')) return;
    const names = picks().filter(box => box.checked).map(box => box.dataset.name);
    document.getElementById('together-label').textContent = on ? `Together with ${names.join(', ')}` : 'Watch together';
    document.getElementById('together-pop').toggleAttribute('data-active', on);
    document.getElementById('together-off').hidden = !on;
    const missing = members().filter(member => (together?.missing || []).includes(member.id));
    const country = document.getElementById('country-select').value;
    const note = document.getElementById('together-note');
    note.textContent = on ? missing.map(member => `${member.name} has no recent scan for ${country} — their list may be out of date.`).join(' ') : '';
    note.hidden = !note.textContent;
  }
  const rowHtml = (row, card) => `<section class="film-row" aria-labelledby="row-${escapeHtml(row.id)}"><div class="film-row-head"><h2 id="row-${escapeHtml(row.id)}">${escapeHtml(row.title)} <span class="row-count">${row.films.length}</span></h2>${row.href ? `<a class="film-link" href="${escapeHtml(row.href)}">See all</a>` : ''}</div><div class="row-scroller"><button class="row-arrow row-prev" type="button" aria-label="Scroll ${escapeHtml(row.title)} back" tabindex="-1"><i class="ti ti-chevron-left" aria-hidden="true"></i></button><div class="row-track films">${row.films.slice(0, 24).map(card).join('')}</div><button class="row-arrow row-next" type="button" aria-label="Scroll ${escapeHtml(row.title)} on" tabindex="-1"><i class="ti ti-chevron-right" aria-hidden="true"></i></button></div></section>`;
  // Together replaces the rows with "On both lists" and "One of you, unseen"; abroad and "Recently gone" are yours alone.
  function renderTogether(context) {
    const box = document.getElementById('tonight-rows');
    document.getElementById('tonight-gone').hidden = true;
    tonightAvailable = [];
    if (!together) { box.innerHTML = '<p class="empty" role="status">Loading your lists…</p>'; return; }
    if (!together.available) { box.innerHTML = '<p class="empty">Your list has no scan yet. Once it has synced, Together shows your films.</p>'; return; }
    const services = new Set(together.subscriptions);
    const everyone = members().length > 2;
    const {rows: [both, one], available} = togetherRows(together.results, {services, members: members().length, favorites: state.favorites, skip: new Set([...watchedKeys(), ...hiddenKeys()]), chips: tonightChips, now: Date.now() / 1000});
    tonightAvailable = available;
    both.href = one.href = `/watchlist?together=${togetherIds().join(',')}`;  // the grid in Together
    document.getElementById('context-text').innerHTML = `${available.length} films available on the <a href="/subscriptions">${services.size} services</a> you have between you`;
    const cardContext = {...context, selected: services, whose: togetherMode()?.whose, ownersOf: service => { const owners = ownersFor(service); return {owners, text: ownerText(owners, members()[0]?.id)}; }};
    const card = film => filmCard(film, 'Paid', cardContext);
    const lists = everyone ? "everyone's list" : 'both lists';
    const empty = together.together.groups.both.length
      ? `No film on ${lists} fits: none runs on your services, or the quick filters keep them out.`
      : `No film is on ${lists}.`;
    box.innerHTML = (both.films.length ? rowHtml(both, card) : `<p class="empty together-empty">${empty}</p>`) + (one.films.length ? rowHtml(one, card) : '');
    applyTonightRoving();
  }
  function renderTonightPage() {
    drawViews();
    showDeadlines(document.getElementById('deadline-banner'), window.WATCHLIST_CONFIG.deadlines, {link: true});
    loadTogether();
    const togetherOn = togetherIds().length > 0;
    showTogetherControls(togetherOn);
    document.querySelectorAll('.quick-chip').forEach(chip => chip.setAttribute('aria-pressed', String(tonightChips.has(chip.dataset.chip))));
    const context = {imageBaseUrl, providerLogos: window.WATCHLIST_CONFIG.providerLogos, logoBaseUrl: window.WATCHLIST_CONFIG.logoBaseUrl, selected: state.selected, favorites: state.favorites, compareKeys: state.compareKeys, greyKeys: new Set(), favoritesOnly: false, pageHref: location.href, country: document.getElementById('country-select').value, countryName: code => regionLabel.of(code) || code, abroadFor, abroadList};
    if (togetherOn) { renderTogether({...context, abroadList: () => []}); return; }
    const {rows, available} = tonightRows(state.films, {services: state.selected, favorites: state.favorites, skip: new Set([...watchedKeys(), ...hiddenKeys()]), chips: tonightChips, now: Date.now() / 1000});
    tonightAvailable = available;
    // With the abroad switch on (remembered in this browser) a last row lists what your services have abroad.
    ensureAbroad();
    if (abroadOnFor()) {
      const shown = new Set([...available.map(filmKey), ...watchedKeys(), ...hiddenKeys()]);
      const checks = TONIGHT_CHIPS.filter(([id, , check]) => tonightChips.has(id) && check).map(([, , check]) => check);
      const list = sortFilms(abroadCandidates(shown).filter(film => checks.every(check => check(film, {services: state.selected, now: Date.now() / 1000}))), 'priority', {favorites: state.favorites});
      if (list.length) rows.push({id: 'abroad', title: 'On your services abroad', films: list, href: '/watchlist?where=abroad'});
    }
    document.getElementById('context-text').innerHTML = `${available.length} films available on <a href="/subscriptions">${state.selected.size} services</a>${state.lastScan ? ` · synced ${ago(state.lastScan)}` : ''}`;
    const section = (row, film) => (row.id === 'free' || (row.id === 'new' && !Object.values(film.providers || {}).flat().includes('flatrate')) ? 'Free' : 'Paid');
    document.getElementById('tonight-rows').innerHTML = rows.map(row => rowHtml(row, film => filmCard(film, section(row, film), context))).join('')
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
    local.setItem('tonightChips', JSON.stringify([...tonightChips]));
    renderTonightPage();
  });
  document.getElementById('together-pop')?.addEventListener('change', event => {
    setTogether(togetherIds());
    // With one other profile there is nothing more to choose: close the menu so it does not cover the chips.
    if (picks().length === 1) { event.currentTarget.open = false; event.currentTarget.querySelector('summary').focus(); }
  });
  document.getElementById('together-off')?.addEventListener('click', () => {
    setTogether([]);
    document.querySelector('#together-pop > summary').focus();  // the button itself hides
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
    const where = includedOn(film, togetherMode()?.own || state.selected);
    const reason = pickReason(film, where ? `on ${where}` : '', members().length > 2 ? "On everyone's list" : undefined);
    document.getElementById('film-details-content').insertAdjacentHTML('afterbegin', `<p class="pick-reason"><span>Picked for you${reason ? `: ${escapeHtml(reason)}` : ''}</span><button class="film-link pick-again" type="button"><i class="ti ti-dice-5" aria-hidden="true"></i> Pick another</button></p>`);
  }
  document.getElementById('film-details-content').addEventListener('click', event => {
    if (event.target.closest('.pick-again')) pickForMe(detailsOpener());
  });
  document.getElementById('pick-for-me')?.addEventListener('click', event => pickForMe(event.currentTarget));
  // "r" picks a film; only outside text fields and dialogs.
  document.addEventListener('keydown', event => {
    if (VIEW !== 'tonight' || event.key !== 'r' || event.ctrlKey || event.metaKey || event.altKey) return;
    // Not while typing or while a menu (country, profile, Together, filters) is open.
    if (event.target.closest('input, select, textarea, [contenteditable], .modal') || document.querySelector('details.filter-pop[open]')) return;
    pickForMe(document.getElementById('pick-for-me'));
  });
  return {renderTonightPage, togetherMode};
}
