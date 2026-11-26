// The details drawer: its content, "Other services" and abroad, paging, the ?film= address and the trailer.
import {escapeHtml} from './ui.js';
import {similarOnServices} from './similar.js';
import {favoriteFields, filmHref} from './rendering.js';
import {filmKey} from './filtering.js';
import {abroadHtml, abroadRows} from './abroad.js';
import {drawerHtml, seriesOrder} from './drawer.js';

export function createFilmDetails({state, results, imageBaseUrl, openModal, modalOpeners, setDrawerKey, watchedKeys, hiddenKeys, includedOn, upcomingText, toggleFavorite, updateFavoriteField, setCompared, showToast, renderFilms}) {
  // "Abroad on your services": from stored scan data (no TMDB request); filled in when it arrives.
  async function showElsewhere(tmdbId, key, own) {
    let byCountry;
    try {
      const response = await fetch(`/api/films/${encodeURIComponent(tmdbId)}/countries`);
      if (!response.ok) return;
      byCountry = await response.json();
    } catch {
      return;
    }
    const target = document.getElementById('film-abroad');
    // The dialog may show another film by now.
    if (!target || document.getElementById('modal-favorite-fields')?.dataset.key !== key) return;
    const regions = new Intl.DisplayNames(['en'], {type: 'region'});
    const nameOf = code => regions.of(code) || code;
    const {providerLogos, logoBaseUrl} = window.WATCHLIST_CONFIG;
    const logoOf = (name, className = 'provider-logo') => (providerLogos[name] ? `<img class="${className}" src="${escapeHtml(logoBaseUrl + providerLogos[name])}" alt="" loading="lazy">` : '');
    const rows = abroadRows(byCountry, own, document.getElementById('country-select').value, nameOf);
    if (!rows.length) return;
    target.innerHTML = abroadHtml(rows, {nameOf, logoOf});
    target.hidden = false;
    // The block lives inside "Other services": show that, and say in its line how many countries there are.
    const more = document.getElementById('film-more');
    more.hidden = false;
    const total = new Set(rows.flatMap(row => row.countries)).size;
    more.querySelector('.os-abroad').textContent = ` · ${total} abroad`;
    revealMore();
  }
  document.getElementById('film-details-content').addEventListener('click', event => {
    const more = event.target.closest('.flag-more');
    if (!more) return;
    const grid = more.closest('.abroad-row').querySelector('.flag-grid');
    grid.hidden = !grid.hidden;
    more.setAttribute('aria-expanded', String(!grid.hidden));
  });
  // Every ISO country name in lower case (from the browser), to keep places out of the keyword chips.
  let countryNameSet = null;
  function allCountryNames() {
    if (countryNameSet) return countryNameSet;
    const names = new Intl.DisplayNames(['en'], {type: 'region'});
    countryNameSet = new Set();
    for (const a of 'ABCDEFGHIJKLMNOPQRSTUVWXYZ') for (const b of 'ABCDEFGHIJKLMNOPQRSTUVWXYZ') {
      try { const name = names.of(a + b); if (name && name !== a + b) countryNameSet.add(name.toLowerCase()); } catch { /* not a region code */ }
    }
    return countryNameSet;
  }
  // The title of the hero shows in the header once it scrolls out of sight.
  let heroTitleWatcher = null;
  function watchHeroTitle() {
    heroTitleWatcher?.disconnect();
    const header = document.querySelector('#film-details-modal .modal-header');
    header.classList.remove('show-title');
    const title = document.getElementById('film-hero-title');
    if (!title || !('IntersectionObserver' in window)) { header.classList.add('show-title'); return; }
    heroTitleWatcher = new IntersectionObserver(([entry]) => header.classList.toggle('show-title', !entry.isIntersecting), {root: document.getElementById('film-details-content')});
    heroTitleWatcher.observe(title);
  }
  function showFilmDetails(key, opener = document.activeElement) {
    const all = [...state.films, ...state.unavailable];
    const film = all.find(item => filmKey(item) === key);
    if (!film) return;
    document.getElementById('film-details-title').textContent = film.title;
    setDrawerKey(key);
    const country = document.getElementById('country-select').value;
    const regions = new Intl.DisplayNames(['en'], {type: 'region'});
    const own = state.selected;
    const saved = state.favorites.get(key);
    const watched = watchedKeys();
    const ctx = {
      own, country, key, watched,
      regionName: regions.of(country) || country,
      regionNames: code => regions.of(code) || code,
      logos: window.WATCHLIST_CONFIG.providerLogos, logoBaseUrl: window.WATCHLIST_CONFIG.logoBaseUrl, imageBaseUrl,
      countryNames: allCountryNames(),
      isFavorite: state.favorites.has(key),
      isSeen: state.flags.get(key)?.flag === 'watched' || saved?.status === 'watched',
      isHidden: hiddenKeys().has(key),
      inCompare: state.compareKeys.has(key),
      series: film.collection ? seriesOrder(all.filter(item => item.collection === film.collection)) : [],
      similar: similarOnServices(film, state.films, own, watched),
      serviceOf: item => includedOn(item, own).split(', ')[0],
      keyOf: filmKey,
      releaseText: upcomingText(film),
      scanAt: state.lastScan,
      favoriteFields: saved ? favoriteFields(key, film.title, saved) : '',
    };
    document.getElementById('film-details-content').innerHTML = drawerHtml(film, ctx);
    watchHeroTitle();
    if (film.tmdb_id) showElsewhere(film.tmdb_id, key, own);
    const detailsOpen = document.getElementById('film-details-modal').classList.contains('show');
    openModal('film-details-modal', opener);
    setFilmAddress(key, !detailsOpen);
  }
  // After "+N": scroll so "Other services" ends just above the bottom edge (or starts at the top when it is taller).
  // Called again when the abroad block has loaded into it, which makes the section taller.
  let pendingMore = false;
  const detailsModal = document.getElementById('film-details-modal');
  ['hidden.bs.modal', 'pointerdown'].forEach(type => detailsModal.addEventListener(type, () => { pendingMore = false; }));
  function revealMore() {
    const box = document.getElementById('film-more');
    const body = document.querySelector('#film-details-modal .modal-body');
    if (!pendingMore || !box || !body) return;
    const section = box.getBoundingClientRect();
    const view = body.getBoundingClientRect();
    const toBottom = section.bottom - (view.bottom - 16);
    const toTop = section.top - (view.top + 8);
    const smooth = !matchMedia('(prefers-reduced-motion: reduce)').matches;
    body.scrollTo({top: body.scrollTop + Math.min(toBottom, toTop), behavior: smooth ? 'smooth' : 'auto'});
  }
  // "+N" and "Abroad" on a card open the details at "Other services".
  document.addEventListener('click', event => {
    const more = event.target.closest('[data-open-more]');
    if (!more) return;
    event.preventDefault();
    // On a phone "+N" goes straight to the full-screen sheet: the list of services needs the room.
    document.getElementById('film-details-modal').classList.toggle('is-full', matchMedia('(max-width: 800px)').matches);
    showFilmDetails(more.dataset.key, more);
    const box = document.getElementById('film-more');
    if (box) box.open = true;
    pendingMore = true;
    const modal = document.getElementById('film-details-modal');
    if (modal.classList.contains('show')) revealMore();
    else modal.addEventListener('shown.bs.modal', revealMore, {once: true});
  });
  // Previous / next film of the list behind the drawer (the grid or the Tonight rows, as drawn); ← and → do the same.
  function neighbourFilm(step) {
    const keys = [...new Set([...document.querySelectorAll('#results article.film[data-key], #results tr[data-key], #tonight-rows article.film[data-key]')].map(card => card.dataset.key))];
    const current = new URL(location.href).searchParams.get('film');
    const next = keys[keys.indexOf(current) + step];
    if (next !== undefined && keys.indexOf(current) >= 0) showFilmDetails(next, modalOpeners.get('film-details-modal'));
  }
  document.getElementById('film-prev').addEventListener('click', () => neighbourFilm(-1));
  document.getElementById('film-next').addEventListener('click', () => neighbourFilm(1));
  document.addEventListener('keydown', event => {
    if (!document.getElementById('film-details-modal').classList.contains('show') || event.altKey || event.ctrlKey || event.metaKey) return;
    if (event.target.closest('input, select, textarea, [contenteditable]')) return;
    if (event.key === 'ArrowLeft') { event.preventDefault(); neighbourFilm(-1); }
    if (event.key === 'ArrowRight') { event.preventDefault(); neighbourFilm(1); }
  });
  // The details window has an address (?film=<key>): links open in a new tab, Back closes it, shared links open it.
  let filmPushed = false;  // opening added a history entry, so closing goes back instead of adding another
  function setFilmAddress(key, push = false) {
    const url = new URL(location.href);
    if ((url.searchParams.get('film') || null) === key) return;
    if (key) url.searchParams.set('film', key); else url.searchParams.delete('film');
    if (push) { history.pushState(history.state, '', url); filmPushed = true; } else history.replaceState(history.state, '', url);
  }
  document.getElementById('film-details-modal').addEventListener('hidden.bs.modal', () => {
    if (!new URL(location.href).searchParams.has('film')) return;
    if (filmPushed) { filmPushed = false; history.back(); } else setFilmAddress(null);
  });
  window.addEventListener('popstate', () => {
    filmPushed = false;
    const key = new URL(location.href).searchParams.get('film');
    if (key) showFilmDetails(key, results);
    else bootstrap.Modal.getInstance(document.getElementById('film-details-modal'))?.hide();
  });
  document.addEventListener('click', event => {
    const link = event.target.closest('a.film-open');
    // Middle, Ctrl, Cmd and Shift clicks keep the browser's own behaviour: a new tab or window.
    if (!link || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    showFilmDetails(link.dataset.key, link);
  });
  // Filters may have changed since the link was drawn; refresh it before the browser (or a screen reader) uses it.
  const refreshFilmLink = event => {
    const link = event.target.closest?.('a.film-open');
    if (link) link.href = filmHref(location.href, link.dataset.key);
  };
  document.addEventListener('pointerdown', refreshFilmLink);
  document.addEventListener('focusin', refreshFilmLink);
  // A shared ?film= link opens once the film is loaded; after the last data arrives a missing film gets a note.
  let pendingFilm = new URL(location.href).searchParams.get('film');
  function openPendingFilm(final = false) {
    if (!pendingFilm) return;
    const key = pendingFilm;
    if ([...state.films, ...state.unavailable].some(film => filmKey(film) === key)) {
      pendingFilm = null;
      // A link opened in a new tab (or the installed app) goes straight to the full-screen sheet on a phone.
      document.getElementById('film-details-modal').classList.toggle('is-full', matchMedia('(max-width: 800px)').matches);
      showFilmDetails(key, results);
    } else if (final) {
      pendingFilm = null;
      setFilmAddress(null);
      showToast('That film is not on this watchlist (or not in this country).', true);
    }
  }
  results.addEventListener('click', event => {
    if (event.target.closest('button, a, input, select, textarea, label, summary, .poster-actions')) return;
    const card = event.target.closest('.film');
    if (card) showFilmDetails(card.dataset.key);
  });
  document.getElementById('film-details-content').addEventListener('click', event => {
    const button = event.target.closest('.modal-favorite');
    if (button) {
      event.preventDefault();
      toggleFavorite(button);
    }
    const compareButton = event.target.closest('.modal-compare');
    if (compareButton) {
      const key = compareButton.dataset.key;
      setCompared(key, !state.compareKeys.has(key));
      const label = state.compareKeys.has(key) ? 'Remove from comparison' : 'Add to comparison';
      compareButton.innerHTML = '<i class="ti ti-layout-columns" aria-hidden="true"></i><span class="tool-label">Compare</span>';
      compareButton.title = label;
      compareButton.setAttribute('aria-label', label);
      compareButton.setAttribute('aria-pressed', String(state.compareKeys.has(key)));
    }
    if (event.target.closest('.modal-share')) {
      navigator.clipboard?.writeText(location.href).then(() => showToast('Link copied.'), () => showToast('Could not copy the link.', true));
    }
    const more = event.target.closest('.overview-more');
    // On a phone a tap on the cut-off text opens it as well (it only expands; "less" is the button).
    const tapped = matchMedia('(max-width: 800px)').matches && event.target.closest('.overview-box.clamped .film-modal-overview');
    if (more || tapped) {
      const box = (more || tapped).closest('.overview-box');
      const button = box.querySelector('.overview-more');
      const clamped = more ? box.classList.toggle('clamped') : (box.classList.remove('clamped'), false);
      button.textContent = clamped ? 'more' : 'less';
      button.setAttribute('aria-expanded', String(!clamped));
    }
    const extra = event.target.closest('.chip-more');
    if (extra) {
      extra.parentElement.querySelectorAll('.is-extra').forEach(chip => { chip.hidden = false; });
      extra.remove();
    }
  });
  function openTrailer(trailer, opener = trailer) {
    document.getElementById('trailer-frame').src = `https://www.youtube.com/embed/${encodeURIComponent(trailer.dataset.trailer)}?autoplay=1`;
    openModal('trailer-modal', opener);
  }
  results.addEventListener('click', event => { const trailer = event.target.closest('.trailer-link'); if (trailer) openTrailer(trailer); });
  document.getElementById('film-details-content').addEventListener('click', event => {
    const trailer = event.target.closest('.trailer-link');
    if (!trailer) return;
    // Bootstrap shows one modal at a time; left open, the details would cover the player.
    // After the trailer the focus goes back to what opened the details.
    const opener = modalOpeners.get('film-details-modal');
    modalOpeners.delete('film-details-modal');
    bootstrap.Modal.getInstance(document.getElementById('film-details-modal'))?.hide();
    openTrailer(trailer, opener);
  });
  document.getElementById('trailer-modal').addEventListener('hidden.bs.modal', () => { document.getElementById('trailer-frame').src = ''; });
  // Another film of the series replaces the content; the focus later still goes back to the first opener.
  document.getElementById('film-details-content').addEventListener('click', event => {
    const pick = event.target.closest('.series-pick');
    if (pick) showFilmDetails(pick.dataset.key, modalOpeners.get('film-details-modal'));
  });
  document.getElementById('film-details-content').addEventListener('change', event => { if (event.target.matches('.favorite-status, .favorite-note')) updateFavoriteField(event.target).then(renderFilms); });
  return {showFilmDetails, openPendingFilm};
}
