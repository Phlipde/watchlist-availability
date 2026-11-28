// The filter bar on one row: Year, Runtime and Rating give way to the "More filters" panel when it does not fit.
// Split out of filterbar.js; `onFit` runs after each fit (the chips list the moved filters).
export function createBarFit({onFit}) {
  const $ = id => document.getElementById(id);
  // ---- a bar that does not fit one row gives Year, then Runtime, then Rating to the "More filters" panel ----------
  // The same element moves (nothing is copied), so the filters, the chips and the URL keep working unchanged.
  // To let another control give way too, add its pop's id to GIVE_WAY (first in the list goes first).
  const GIVE_WAY = ['year-pop', 'runtime-pop', 'rating-pop'];
  const markers = new Map();
  function moveIn(pop) {
    if (markers.has(pop)) return;
    const marker = document.createComment(pop.id);
    pop.before(marker);
    markers.set(pop, marker);
    $('moved-slot').append(pop);
    pop.classList.add('is-moved');
    pop.open = true;
    pop.querySelector('summary').tabIndex = -1;
    $('moved-section').hidden = false;
  }
  function moveBack(pop) {
    const marker = markers.get(pop);
    if (!marker) return;
    pop.classList.remove('is-moved');
    pop.open = false;
    pop.querySelector('summary').removeAttribute('tabindex');
    marker.replaceWith(pop);
    markers.delete(pop);
    $('moved-section').hidden = !markers.size;
  }
  // Closing a moved control (its summary is not clickable, but Enter on it would) opens it again.
  document.addEventListener('toggle', event => { if (event.target.classList?.contains('is-moved') && !event.target.open) event.target.open = true; }, true);
  // The bar and the page tools are one flex row (".watch-bar"; the bar itself is display: contents), so look at all of its items.
  const wrapped = row => {
    const search = $('film-search');
    const floor = search.offsetTop + search.offsetHeight;
    const items = [...row.children].flatMap(child => (getComputedStyle(child).display === 'contents' ? [...child.children] : [child]));
    return items.some(item => item.offsetParent !== null && item.offsetTop >= floor);
  };
  // A bar that still takes two rows (a tablet) gets the heart, the link and the view switch into the gap of its
  // second row, so the row of tabs below stays one line. Wider screens keep them beside the tabs.
  const VIEW_TOOLS = ['favorites-view', 'share-button', 'view-switch'];
  function fitBar() {
    const row = $('film-filters').parentElement;
    const pops = GIVE_WAY.map($);
    pops.forEach(moveBack);
    if (matchMedia('(max-width: 800px)').matches || $('film-search').offsetParent === null) return;  // phones have their own sheet
    VIEW_TOOLS.forEach(id => $('tabs-view-slot').append($(id)));
    for (const pop of pops) {
      if (!wrapped(row)) break;
      moveIn(pop);
    }
    if (wrapped(row)) VIEW_TOOLS.forEach(id => $('bar-view-slot').append($(id)));
    onFit();
  }
  // The row's own size does not change when a control gives way, so also look again after fonts load, on resize and after each draw.
  new ResizeObserver(fitBar).observe($('film-filters').parentElement);
  addEventListener('resize', fitBar);
  document.fonts?.ready.then(fitBar);
  return fitBar;
}
