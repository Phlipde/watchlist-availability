// Closing by a swipe: past 28 % of the sheet (or panel) or a quick flick of at least 24 px; else it springs back.
export const swipeCloses = (moved, ms, size) => moved > size * 0.28 || (moved >= 24 && moved / Math.max(ms, 1) > 0.6);

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
    let startTime = 0;
    let baseOffset = 0;
    handles.forEach(handle => {
      handle.addEventListener('pointerdown', event => {
        if (event.target.closest('button, a')) return;  // the arrows and the close button stay buttons
        startY = event.clientY;
        startTime = performance.now();
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
        else if (full && moved > 48) modal.classList.remove('is-full');
        else if (!full && swipeCloses(moved, performance.now() - startTime, dialog.offsetHeight)) closeBySwipe('y');
        else if (Math.abs(moved) < 8 && handle.id === 'sheet-grip') modal.classList.toggle('is-full', !full);
      });
    });
    // Touch: pulling down from the top of the content (phone sheet) or right anywhere in the side panel (tablet)
    // follows the finger; past 28 % or with a quick flick it closes, else it springs back. Horizontal rows of posters
    // keep their own scrolling, and the gesture starts in the panel, never at the screen edge (Safari's back swipe).
    function closeBySwipe(axis) {
      dialog.style.transition = 'transform .2s ease-in';
      dialog.style.transform = axis === 'x' ? 'translateX(100%)' : 'translateY(100%)';
      setTimeout(() => modal.querySelector('.btn-close').click(), 180);
    }
    const scrollsSideways = node => {
      for (let element = node; element && element !== dialog; element = element.parentElement) {
        if (element.scrollWidth > element.clientWidth + 1 && /(auto|scroll)/.test(getComputedStyle(element).overflowX)) return true;
      }
      return false;
    };
    const body = modal.querySelector('.modal-body');
    let touch = null;
    modal.addEventListener('touchstart', event => {
      touch = null;
      if (event.touches.length !== 1 || !dialog.contains(event.target) || event.target.closest('iframe, input, select, textarea')) return;
      const phone = matchMedia('(max-width: 800px)').matches;
      if (phone && !body.contains(event.target)) return;  // the grip and the header have their own drag above
      if (!phone && scrollsSideways(event.target)) return;
      const {clientX: x, clientY: y} = event.touches[0];
      touch = {x, y, time: performance.now(), phone, axis: null, base: phone && !modal.classList.contains('is-full') ? innerHeight * 0.2 : 0};
    }, {passive: true});
    modal.addEventListener('touchmove', event => {
      if (!touch) return;
      const dx = event.touches[0].clientX - touch.x;
      const dy = event.touches[0].clientY - touch.y;
      if (!touch.axis) {
        if (Math.abs(dx) + Math.abs(dy) < 8) return;
        if (touch.phone && dy > 0 && dy > Math.abs(dx) && body.scrollTop <= 0) touch.axis = 'y';
        else if (!touch.phone && dx > 0 && dx > Math.abs(dy) * 1.2) touch.axis = 'x';
        else { touch = null; return; }
      }
      event.preventDefault();
      dialog.style.transition = 'none';
      dialog.style.transform = touch.axis === 'x' ? `translateX(${Math.max(0, dx)}px)` : `translateY(${touch.base + Math.max(0, dy)}px)`;
    }, {passive: false});
    const endTouch = event => {
      if (!touch?.axis) { touch = null; return; }
      const point = event.changedTouches[0];
      const moved = touch.axis === 'x' ? point.clientX - touch.x : point.clientY - touch.y;
      const size = touch.axis === 'x' ? dialog.offsetWidth : dialog.offsetHeight;
      const {axis, time} = touch;
      touch = null;
      if (event.type === 'touchend' && swipeCloses(moved, performance.now() - time, size)) { closeBySwipe(axis); return; }
      dialog.style.transition = 'transform .25s cubic-bezier(.2, .8, .2, 1)';
      dialog.style.transform = '';
      setTimeout(() => { dialog.style.transition = ''; }, 260);
    };
    modal.addEventListener('touchend', endTouch);
    modal.addEventListener('touchcancel', endTouch);
    modal.addEventListener('hidden.bs.modal', () => { dialog.style.transition = ''; dialog.style.transform = ''; });
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
