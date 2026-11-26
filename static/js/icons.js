// Logos and flags carry their names only as a tooltip: one bubble for every [data-tip], shown on mouse hover,
// keyboard focus and touch tap (a tap on a card's logo shows its name and opens nothing). Only the first bubble waits;
// the next ones within a moment show at once. A logo or flag that fails to load becomes a neutral tile.
import {initials} from './ui.js';

const DELAY = 400;  // ms before the first bubble
const WARM = 700;   // ms after a bubble closes in which the next one needs no delay

let tip = null;
let current = null;
let timer = 0;
let warmUntil = 0;


function bubble() {
  if (!tip) {
    tip = document.createElement('div');
    tip.className = 'tip';
    tip.setAttribute('role', 'tooltip');
    tip.hidden = true;
    document.body.append(tip);
  }
  return tip;
}

function place(target) {
  const box = bubble();
  box.textContent = target.dataset.tip;
  box.hidden = false;
  const rect = target.getBoundingClientRect();
  const {width, height} = box.getBoundingClientRect();
  const above = rect.top - height - 6;
  box.style.top = `${above >= 4 ? above : rect.bottom + 6}px`;
  box.style.left = `${Math.min(Math.max(rect.left + rect.width / 2 - width / 2, 4), innerWidth - width - 4)}px`;
  current = target;
}

function show(target, now = false) {
  clearTimeout(timer);
  if (!target.dataset.tip) return hide();
  if (now || current || Date.now() < warmUntil) place(target);
  else timer = setTimeout(() => place(target), DELAY);
}

export function hide() {
  clearTimeout(timer);
  if (current) warmUntil = Date.now() + WARM;
  current = null;
  if (tip) tip.hidden = true;
}

const tipOf = node => node?.closest?.('[data-tip]') || null;

document.addEventListener('pointerover', event => {
  if (event.pointerType !== 'mouse') return;
  const target = tipOf(event.target);
  if (target) { if (target !== current) show(target); } else if (current || timer) hide();
});
document.addEventListener('focusin', event => { const target = tipOf(event.target); if (target) show(target); else hide(); });
document.addEventListener('focusout', hide);
document.addEventListener('pointerup', event => {
  if (event.pointerType === 'mouse') return;
  const target = tipOf(event.target);
  if (!target || (target.closest('[data-open-more]') && !target.matches('.lstack-item'))) return hide();
  if (target === current) hide(); else show(target, true);
});
document.addEventListener('keydown', event => { if (event.key === 'Escape') hide(); });
// Scrolling moves the bubble with a focused element (focus itself scrolls it into view) and closes it otherwise.
addEventListener('scroll', () => {
  if (current?.contains(document.activeElement)) place(current); else if (current) hide();
}, {capture: true, passive: true});

const LOGOS = '.lstack-logo, .svc-logo, .provider-logo, .provider-logo-sm, .table-logo, .mini-logo';
document.addEventListener('error', event => {
  const img = event.target;
  if (img.tagName !== 'IMG') return;
  if (img.matches('.flag img, .way-badge-flag img')) { img.classList.add('is-missing'); img.removeAttribute('src'); return; }
  if (!img.matches(LOGOS)) return;
  const name = img.closest('[data-tip]')?.dataset.tip?.split(' · ')[0] || img.closest('[aria-label]')?.getAttribute('aria-label') || '';
  const tile = document.createElement('span');
  tile.className = `${img.className} logo-fallback`;
  tile.setAttribute('aria-hidden', 'true');
  tile.textContent = initials(name);
  img.replaceWith(tile);
}, true);
