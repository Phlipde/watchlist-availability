// Popovers shared by every page (filter bar, header menus, the country picker).
// Popovers (<details>): one open at a time, closed by a click outside or Escape (focus back on its summary),
// arrow keys move through the controls inside. Bootstrap's dropdown toggles twice here (tabler.min.js
// brings a second Bootstrap), so these are plain <details>.
// A menu opens under its button; when that runs past the window edge, slide it back in.
export function keepInView(menu) {
  if (!menu) return;
  menu.style.translate = '';
  const {left, right} = menu.getBoundingClientRect();
  const margin = 8;
  const shift = right > innerWidth - margin ? innerWidth - margin - right : 0;
  menu.style.translate = `${Math.max(shift, margin - left)}px 0`;
}

const wired = new WeakSet();

export function initPopovers(doc = document) {
  // Listeners are per document: a second call (app.js and the country picker) must not add them twice.
  if (wired.has(doc)) return;
  wired.add(doc);
  // A control that moved into the "More filters" panel (.is-moved) stays open there and is left alone.
  const popovers = () => [...doc.querySelectorAll('details.filter-pop:not(.is-moved), details.sync, details.export-menu, details.card-menu')];
  doc.addEventListener('toggle', event => {
    if (!event.target.matches?.('details.filter-pop:not(.is-moved), details.sync, details.export-menu, details.card-menu') || !event.target.open) return;
    popovers().forEach(other => { if (other !== event.target) other.open = false; });
    keepInView(event.target.querySelector('.filter-menu, .sync-panel'));
  }, true);
  doc.addEventListener('click', event => {
    popovers().forEach(popover => { if (popover.open && !popover.contains(event.target)) popover.open = false; });
  });
  doc.addEventListener('keydown', event => {
    const popover = event.target.closest?.('details.filter-pop:not(.is-moved), details.sync, details.export-menu, details.card-menu');
    if (!popover?.open) return;
    if (event.key === 'Escape') {
      popover.open = false;
      popover.querySelector('summary').focus();
      event.stopPropagation();
      return;
    }
    if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') return;
    if (event.target.matches('select, input[type=range], input[type=number], input[type=radio]')) return;
    const items = [...popover.querySelectorAll('summary, .filter-menu input:not([type=hidden]), .filter-menu button, .filter-menu select, .filter-menu a[href]')]
      .filter(item => !item.closest('[hidden]'));
    const index = items.indexOf(event.target);
    if (index < 0) return;
    event.preventDefault();
    items[Math.max(0, Math.min(items.length - 1, index + (event.key === 'ArrowDown' ? 1 : -1)))].focus();
  });
}
