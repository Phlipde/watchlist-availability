// Phones and touch: the filter sheet, the details drawer as a bottom sheet, long press and logo taps on the cards.
export function initPhoneSheet({results, filterBar}) {
  // Touch: the first tap on a card's logo shows what it is; a second tap goes to the service. A tap elsewhere closes it.
  document.addEventListener('click', event => {
    const link = event.target.closest('.best-way-link');
    const open = document.querySelector('.best-way-link.is-open');
    if (open && open !== link) open.classList.remove('is-open');
    if (!link || !matchMedia('(pointer: coarse)').matches) return;
    if (!link.classList.contains('is-open')) {
      event.preventDefault();
      event.stopImmediatePropagation();
      link.classList.add('is-open');
    }
  }, true);
  // Touch: a long press on a card shows its action bar (compare, not now, hide); a tap elsewhere hides it.
  let pressTimer = null;
  let swallowClick = false;
  results.addEventListener('pointerdown', event => {
    if (event.pointerType !== 'touch') return;
    const card = event.target.closest('article.film');
    if (!card || event.target.closest('button, a, input')) return;
    pressTimer = setTimeout(() => {
      results.querySelectorAll('.show-actions').forEach(other => other.classList.remove('show-actions'));
      card.classList.add('show-actions');
      swallowClick = true;
      navigator.vibrate?.(10);
    }, 500);
  });
  ['pointerup', 'pointercancel', 'pointermove'].forEach(type => results.addEventListener(type, () => clearTimeout(pressTimer)));
  results.addEventListener('click', event => {
    if (!swallowClick) return;
    swallowClick = false;
    event.stopImmediatePropagation();
    event.preventDefault();
  }, true);
  document.addEventListener('pointerdown', event => {
    if (!event.target.closest('.show-actions')) results.querySelectorAll('.show-actions').forEach(card => card.classList.remove('show-actions'));
  });
  // Phone sheet: opens at 80 %. Pulling the grip or the header up makes it full screen, pulling down shrinks it or
  // closes it, a tap on the grip toggles, and scrolling the content makes it full screen too (like a native sheet).
  (() => {
    const modal = document.getElementById('film-details-modal');
    const handles = [document.getElementById('sheet-grip'), modal.querySelector('.modal-header')];
    const dialog = modal.querySelector('.modal-dialog');
    let startY = null;
    let baseOffset = 0;
    handles.forEach(handle => {
      handle.addEventListener('pointerdown', event => {
        if (event.target.closest('button, a')) return;  // the arrows and the close button stay buttons
        startY = event.clientY;
        baseOffset = modal.classList.contains('is-full') ? 0 : innerHeight * 0.2;
        handle.setPointerCapture(event.pointerId);
      });
      // The sheet follows the finger (transform only); on release the classes decide where it settles.
      handle.addEventListener('pointermove', event => {
        if (startY === null) return;
        dialog.style.transition = 'none';
        dialog.style.transform = `translateY(${Math.max(0, baseOffset + event.clientY - startY)}px)`;
      });
      const release = () => { dialog.style.transition = ''; dialog.style.transform = ''; };
      handle.addEventListener('pointercancel', () => { startY = null; release(); });
      handle.addEventListener('pointerup', event => {
        if (startY === null) return;
        const moved = event.clientY - startY;
        startY = null;
        release();
        const full = modal.classList.contains('is-full');
        if (moved < -24) modal.classList.add('is-full');
        else if (moved > 48) { if (full) modal.classList.remove('is-full'); else modal.querySelector('.btn-close').click(); }
        else if (Math.abs(moved) < 8 && handle.id === 'sheet-grip') modal.classList.toggle('is-full', !full);
      });
    });
    modal.querySelector('.modal-body').addEventListener('scroll', event => {
      if (matchMedia('(max-width: 800px)').matches && event.target.scrollTop > 24) modal.classList.add('is-full');
    });
    modal.addEventListener('hidden.bs.modal', () => modal.classList.remove('is-full'));
  })();
  // Phones: "Filters" opens the bar as a sheet from the bottom, a modal dialog while open.
  // Phones keep the heart and the link inside the sheet; wider screens put them with the view switch in the tab row, so the bar stays one row.
  const phoneQuery = matchMedia('(max-width: 800px)');
  const placeViewTools = () => {
    const phone = phoneQuery.matches;
    const tabs = document.getElementById('tabs-view-slot');
    const home = document.getElementById(phone ? 'sheet-view-slot' : 'tabs-view-slot');
    ['favorites-view', 'share-button'].forEach(id => home.append(document.getElementById(id)));
    tabs.append(document.getElementById('view-switch'));
  };
  placeViewTools();
  phoneQuery.addEventListener('change', placeViewTools);
  const toolsToggle = document.getElementById('tools-toggle');
  const filterSheet = document.getElementById('film-filters');
  const behindSheet = () => [document.getElementById('app-header'), document.querySelector('.skip-link'), ...document.querySelectorAll('#watchlist-view > :not(.watch-bar), .watch-bar > :not(#film-filters)')].filter(Boolean);
  let sheetTimer = null;
  // Closing on a phone slides the sheet down first (`tools-closing`), then drops `tools-open`.
  function setSheet(open, instant = false) {
    clearTimeout(sheetTimer);
    const body = document.body;
    const slide = !open && !instant && body.classList.contains('tools-open') && phoneQuery.matches
      && !matchMedia('(prefers-reduced-motion: reduce)').matches;
    body.classList.toggle('tools-closing', slide);
    if (slide) sheetTimer = setTimeout(() => body.classList.remove('tools-open', 'tools-closing'), 230);
    else body.classList.toggle('tools-open', open);
    toolsToggle?.setAttribute('aria-expanded', String(open));
    filterSheet.setAttribute('role', open ? 'dialog' : 'search');
    if (open) filterSheet.setAttribute('aria-modal', 'true'); else filterSheet.removeAttribute('aria-modal');
    behindSheet().forEach(element => { element.inert = open; });
    // On a touch screen the search would raise the keyboard before anything is chosen: focus the close button instead.
    if (open) document.getElementById(matchMedia('(pointer: coarse)').matches ? 'filter-sheet-close' : 'film-search').focus();
    else toolsToggle?.focus();
  }
  toolsToggle?.addEventListener('click', () => setSheet(!document.body.classList.contains('tools-open')));
  // Pulling the sheet's header down follows the finger; past 80 px it slides out and closes.
  (() => {
    const head = filterSheet.querySelector('.sheet-head');
    let startY = null;
    head.addEventListener('pointerdown', event => {
      if (event.target.closest('button, a') || !phoneQuery.matches) return;
      startY = event.clientY;
      head.setPointerCapture(event.pointerId);
    });
    head.addEventListener('pointermove', event => {
      if (startY === null) return;
      filterSheet.style.transition = 'none';
      filterSheet.style.transform = `translateY(${Math.max(0, event.clientY - startY)}px)`;
    });
    const end = event => {
      if (startY === null) return;
      const far = event.type === 'pointerup' && event.clientY - startY > 80;
      startY = null;
      filterSheet.style.transition = 'transform .22s cubic-bezier(.2, .8, .2, 1)';
      filterSheet.style.transform = far ? 'translateY(100%)' : '';
      setTimeout(() => {
        filterSheet.style.transition = '';
        if (far) { setSheet(false, true); filterSheet.style.transform = ''; }
      }, 230);
    };
    head.addEventListener('pointerup', end);
    head.addEventListener('pointercancel', end);
  })();
  document.getElementById('filter-sheet-done').addEventListener('click', () => setSheet(false));
  document.getElementById('filter-sheet-close').addEventListener('click', () => setSheet(false));
  document.getElementById('filter-sheet-reset').addEventListener('click', () => filterBar.resetAll());
  // The dimmed page behind the sheet is the body's ::before: a tap on it closes the sheet.
  document.body.addEventListener('click', event => { if (event.target === document.body && document.body.classList.contains('tools-open')) setSheet(false); });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && document.body.classList.contains('tools-open') && !event.target.closest?.('details[open]')) setSheet(false);
  });
}
