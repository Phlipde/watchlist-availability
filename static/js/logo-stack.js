// LogoStack: the first (best) logo free, up to three more overlapping, then "+N". A click fans them out in place;
// with more than LIST_FROM logos it opens a list instead (popover, a bottom sheet on a phone).
import {escapeHtml} from './ui.js';

export const WORDS = {free: 'Free', flatrate: 'Subscription', ads: 'With ads', rent: 'Rent', buy: 'Buy', abroad: 'Subscription'};
export const WIDE = 3;         // the first logos (your services) sit side by side
export const OVERLAP_MAX = 2;  // then this many overlap, then "+N"
export const LIST_FROM = 9;    // more than 8 logos: list instead of fan

// item: {name, kind, logo (url or ''), country ('Italy' for a service abroad), flag (country code), badge (html)}
export const itemText = item => [item.name, WORDS[item.kind] || '', item.country || ''].filter(Boolean).join(' · ');
export const stackLabel = items => `${items.length} service${items.length === 1 ? '' : 's'}: ${items.map(item => item.name).join(', ')}`;
export const stackMode = items => (items.length >= LIST_FROM ? 'list' : 'fan');
export const hiddenCount = items => Math.max(items.length - WIDE - OVERLAP_MAX, 0);

const logoHtml = item => (item.logo
  ? `<img class="lstack-logo" src="${escapeHtml(item.logo)}" alt="" loading="lazy">`
  : `<span class="lstack-logo lstack-name">${escapeHtml(item.name)}</span>`);
const flagHtml = item => (item.flag ? `<span class="way-badge way-badge-flag" aria-hidden="true"><img src="/static/flags/${escapeHtml(item.flag.toLowerCase())}.svg" alt=""></span>` : '');

// interactive:false gives a plain row (the services chip), no click.
export function logoStackHtml(items, {interactive = true} = {}) {
  if (!items.length) return '';
  const hidden = hiddenCount(items);
  const cells = items.map((item, index) => `<span class="lstack-item${index === 0 ? ' is-first' : ''}${index < WIDE ? ' is-wide' : ''}${index >= WIDE + OVERLAP_MAX ? ' is-extra' : ''}"${items.length === 1 && interactive ? ' tabindex="0"' : ''} data-tip="${escapeHtml(itemText(item))}">${logoHtml(item)}${index === 0 ? item.badge || '' : ''}${flagHtml(item)}</span>`).join('');
  const more = hidden ? `<span class="lstack-more">+${hidden}</span>` : '';
  if (!interactive) return `<span class="lstack" role="img" aria-label="${escapeHtml(stackLabel(items))}">${cells}${more}</span>`;
  const list = stackMode(items) === 'list'
    ? `<ul class="lstack-list" hidden>${items.map(item => `<li>${logoHtml(item)}<span>${escapeHtml(item.name)}</span><span class="muted">${escapeHtml(WORDS[item.kind] || '')}</span>${item.flag ? flagHtml(item) : ''}</li>`).join('')}</ul>`
    : '';
  const names = escapeHtml(items.map(item => itemText(item)).join('\n'));
  return `<div class="lstack${items.length > 1 ? ' is-multi' : ''}" data-mode="${stackMode(items)}" title="${names}"><div class="lstack-row">${cells}${more}</div>`
    + (items.length > 1 ? `<button class="lstack-toggle" type="button" aria-expanded="false" aria-label="${escapeHtml(stackLabel(items))}"></button>` : '')
    + `${list}</div>`;
}

// One delegated handler for every stack on the page.
export function initLogoStacks(root = document) {
  const closeAll = except => root.querySelectorAll('.lstack.is-open').forEach(stack => {
    if (stack === except) return;
    stack.classList.remove('is-open');
    stack.querySelector('.lstack-toggle')?.setAttribute('aria-expanded', 'false');
    const list = stack.querySelector('.lstack-list');
    if (list) list.hidden = true;
  });
  const set = (stack, open) => {
    stack.classList.toggle('is-open', open);
    stack.querySelector('.lstack-toggle').setAttribute('aria-expanded', String(open));
    const list = stack.querySelector('.lstack-list');
    if (list) list.hidden = !open;
    stack.querySelectorAll('.is-tip').forEach(tip => tip.classList.remove('is-tip'));
  };
  root.addEventListener('click', event => {
    const stack = event.target.closest('.lstack.is-multi');
    closeAll(stack);
    if (!stack) return;
    const item = event.target.closest('.lstack-item');
    if (stack.classList.contains('is-open') && item) {
      const on = !item.classList.contains('is-tip');
      stack.querySelectorAll('.is-tip').forEach(tip => tip.classList.remove('is-tip'));
      item.classList.toggle('is-tip', on);
      return;
    }
    if (event.target.closest('.lstack-list')) return;
    event.preventDefault();
    set(stack, !stack.classList.contains('is-open'));
  });
  root.addEventListener('keydown', event => {
    if (event.key !== 'Escape') return;
    const open = root.querySelector('.lstack.is-open');
    if (!open) return;
    set(open, false);
    open.querySelector('.lstack-toggle').focus();
  });
}
