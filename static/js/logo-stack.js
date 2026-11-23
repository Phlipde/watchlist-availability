// LogoStack: the first logos side by side, then a few overlapping, then "+N". Names come as a bubble on hover/tap.
// On a card the whole stack opens the film's details at "Other services" (data-open-more, handled in app.js).
import {escapeHtml} from './ui.js';

export const WORDS = {free: 'Free', flatrate: 'Subscription', ads: 'With ads', rent: 'Rent', buy: 'Buy', abroad: 'Subscription'};
export const WIDE = 3;         // the first logos (your services) sit side by side
export const OVERLAP_MAX = 2;  // then this many overlap, then "+N"

// item: {name, kind, logo (url or ''), country ('Italy' for a service abroad), flag (country code), badge (html)}
export const itemText = item => [item.name, WORDS[item.kind] || '', item.country || ''].filter(Boolean).join(' · ');
export const stackLabel = items => `${items.length} service${items.length === 1 ? '' : 's'}: ${items.map(item => item.name).join(', ')}`;
export const hiddenCount = items => Math.max(items.length - WIDE - OVERLAP_MAX, 0);

const logoHtml = item => (item.logo
  ? `<img class="lstack-logo" src="${escapeHtml(item.logo)}" alt="" loading="lazy">`
  : `<span class="lstack-logo lstack-name">${escapeHtml(item.name)}</span>`);
const flagHtml = item => (item.flag ? `<span class="way-badge way-badge-flag" aria-hidden="true"><img src="/static/flags/${escapeHtml(item.flag.toLowerCase())}.svg" alt=""></span>` : '');

// key: the film's key; with it the stack is a button that opens the details. Without it a plain row (the services chip).
export function logoStackHtml(items, {key = ''} = {}) {
  if (!items.length) return '';
  const hidden = hiddenCount(items);
  const cells = items.slice(0, WIDE + OVERLAP_MAX).map((item, index) => `<span class="lstack-item${index < WIDE ? ' is-wide' : ''}" data-tip="${escapeHtml(itemText(item))}">${logoHtml(item)}${item.badge || ''}${flagHtml(item)}</span>`).join('');
  const more = hidden ? `<span class="lstack-more">+${hidden}</span>` : '';
  if (!key) return `<span class="lstack" role="img" aria-label="${escapeHtml(stackLabel(items))}">${cells}${more}</span>`;
  return `<div class="lstack" data-open-more data-key="${escapeHtml(key)}"><div class="lstack-row">${cells}${more}</div>`
    + `<button class="lstack-toggle" type="button" aria-label="${escapeHtml(stackLabel(items))} · details"></button></div>`;
}
