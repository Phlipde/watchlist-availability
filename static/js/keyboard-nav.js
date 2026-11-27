// Arrow keys through the films (grid, compact grid, table and the Tonight rows: one tab stop each) and the key shortcuts.
import {NAV_KEYS, columnsFromTops, nextIndex, nextInRows} from './gridnav.js';
import {letterboxdUrl} from './drawer.js';
import {filmKey} from './filtering.js';

export function createKeyboardNav({state, results, view: VIEW, toggleFavorite, setFlag, setCompared, renderFilms}) {
  const CARD_CONTROLS = '.film-open, .favorite, .card-action, .best-way-link, .best-more, .lstack';
  let activeKey = null;  // the film that holds the tab stop (roving tabindex): one stop in the whole list
  const navItems = () => [...results.querySelectorAll('article.film[data-key], tr[data-key]')];
  function applyRoving() {
    const items = navItems();
    if (!items.length) return;
    // Until a film was chosen (focus or arrow keys) the first one holds the tab stop; a choice that was filtered away falls back to it.
    const current = items.find(item => item.dataset.key === activeKey) || items[0];
    for (const item of items) item.querySelectorAll(CARD_CONTROLS).forEach(control => { control.tabIndex = item === current ? 0 : -1; });
  }
  function focusItem(item) {
    activeKey = item.dataset.key;
    applyRoving();
    item.querySelector('.film-open')?.focus();
    item.scrollIntoView({block: 'nearest'});
  }
  results.addEventListener('focusin', event => {
    const item = event.target.closest('article.film[data-key], tr[data-key]');
    if (item && item.dataset.key !== activeKey) { activeKey = item.dataset.key; applyRoving(); }
  });
  document.addEventListener('keydown', event => {
    if (!NAV_KEYS.has(event.key) || event.ctrlKey || event.metaKey || event.altKey || event.shiftKey || event.isComposing) return;
    const item = event.target.closest?.('#results article.film[data-key], #results tr[data-key]');
    // Not in a text field, a menu or a dialog: the arrows keep their own meaning there.
    if (!item || event.target.closest('input, select, textarea, [contenteditable], dialog, details[open]') || document.querySelector('.modal.show')) return;
    const items = navItems();
    const columns = results.querySelector('table.film-table') ? 1 : columnsFromTops(items.map(card => card.getBoundingClientRect().top));
    const next = nextIndex(event.key, items.indexOf(item), columns, items.length);
    if (next === null) return;
    event.preventDefault();
    focusItem(items[next]);
  });
  // The Tonight rows: ←/→ along a row, ↑/↓ to the row above or below (same position as far as it reaches).
  let tonightSpot = [0, 0];  // [row, column] of the film that holds the tab stop
  const tonightGrid = () => [...document.querySelectorAll('#tonight-rows .film-row')].map(row => [...row.querySelectorAll('article.film[data-key]')]);
  function applyTonightRoving() {
    const grid = tonightGrid();
    if (!grid.length) return;
    const row = Math.min(tonightSpot[0], grid.length - 1);
    const col = Math.min(tonightSpot[1], Math.max(grid[row].length - 1, 0));
    grid.forEach((cards, r) => cards.forEach((card, c) => card.querySelectorAll(CARD_CONTROLS).forEach(control => { control.tabIndex = r === row && c === col ? 0 : -1; })));
  }
  document.getElementById('tonight-rows')?.addEventListener('focusin', event => {
    const card = event.target.closest('article.film[data-key]');
    const grid = tonightGrid();
    const row = grid.findIndex(cards => cards.includes(card));
    if (row >= 0) { tonightSpot = [row, grid[row].indexOf(card)]; applyTonightRoving(); }
  });
  document.addEventListener('keydown', event => {
    if (!NAV_KEYS.has(event.key) || event.ctrlKey || event.metaKey || event.altKey || event.shiftKey || event.isComposing) return;
    const card = event.target.closest?.('#tonight-rows article.film[data-key]');
    if (!card || event.target.closest('input, select, textarea, [contenteditable], dialog, details[open]') || document.querySelector('.modal.show')) return;
    const grid = tonightGrid();
    const row = grid.findIndex(cards => cards.includes(card));
    const next = nextInRows(event.key, row, grid[row].indexOf(card), grid.map(cards => cards.length));
    if (!next) return;
    event.preventDefault();
    tonightSpot = next;
    applyTonightRoving();
    const target = grid[next[0]][next[1]];
    target.querySelector('.film-open')?.focus();
    target.scrollIntoView({block: 'nearest', inline: 'nearest'});
  });
  // Keyboard shortcuts (outside text fields and dialogs): the film is the one in the open details, else the card in focus or under the pointer.
  let hoveredCard = null;
  document.addEventListener('pointerover', event => { hoveredCard = event.target.closest?.('article.film') || hoveredCard; });
  function filmInFocus() {
    const open = document.getElementById('film-details-modal').classList.contains('show');
    if (open) return {key: new URL(location.href).searchParams.get('film'), card: null};
    const card = document.activeElement?.closest?.('article.film') || (hoveredCard?.isConnected && hoveredCard.matches(':hover') ? hoveredCard : null);
    return {key: card?.dataset.key, card};
  }
  let goPending = false;
  document.addEventListener('keydown', event => {
    if (event.ctrlKey || event.metaKey || event.altKey || event.isComposing) return;
    if (event.target.closest?.('input, select, textarea, [contenteditable], dialog, .modal:not(#film-details-modal)')) return;
    if (document.querySelector('details.filter-pop[open]:not(.is-moved)')) return;  // a menu is open (not the filters moved into More filters, which stay open)
    const dialog = document.getElementById('shortcuts-dialog');
    if (event.key === '?') { dialog.showModal(); return; }
    if (goPending) {
      goPending = false;
      const target = {t: '/', w: '/watchlist', s: '/subscriptions'}[event.key];
      if (target) { event.preventDefault(); location.href = target; return; }
    }
    if (event.key === 'g') { goPending = true; setTimeout(() => { goPending = false; }, 1000); return; }
    if (event.key === '/' && VIEW !== 'tonight') { event.preventDefault(); document.getElementById('film-search').focus(); return; }
    if (event.key === 'R' && event.shiftKey) { document.getElementById('retry-scan')?.click(); return; }
    const {key, card} = filmInFocus();
    if (!key) return;
    if (event.key === 'f') {
      const button = (card || document).querySelector(card ? '.favorite' : '.modal-favorite');
      if (button) { event.preventDefault(); toggleFavorite(button); }
    } else if (event.key === 's') { event.preventDefault(); setFlag(key, 'watched'); }
    else if (event.key === 'n') { event.preventDefault(); setFlag(key, 'not_now'); }
    else if (event.key === 'l') {
      const film = [...state.films, ...state.unavailable].find(item => filmKey(item) === key);
      if (film) { event.preventDefault(); window.open(letterboxdUrl(film), '_blank', 'noopener'); }
    }
    else if (event.key === 'c') { event.preventDefault(); setCompared(key, !state.compareKeys.has(key)); renderFilms(); }
  });
  const setActiveKey = key => { activeKey = key; applyRoving(); };
  return {applyRoving, applyTonightRoving, navItems, activeKey: () => activeKey, setActiveKey};
}
