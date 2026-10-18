import {escapeHtml} from './ui.js';

const OFFER_TYPES = {
  free: ['Free', 'ti ti-gift'],
  ads: ['With ads', 'ti ti-ad-2'],
  flatrate: ['Subscription', 'ti ti-repeat'],
  rent: ['Rent', 'ti ti-ticket'],
};

export function offerBadges(kinds) {
  return [...new Set(kinds)].map(kind => {
    const [label, icon] = OFFER_TYPES[kind] || [kind, 'ti ti-circle'];
    return `<span class="badge offer-badge offer-${escapeHtml(kind)}"><i class="${icon}" aria-hidden="true"></i> ${escapeHtml(label)}</span>`;
  }).join('');
}

export function offerBadgesForProviders(providers) {
  return Object.entries(providers || {}).map(([provider, kinds]) =>
    `<li><span>${escapeHtml(provider)}</span><span class="provider-offers">${offerBadges(kinds)}</span></li>`
  ).join('');
}

export function unavailableCard(film) {
  const key = `${film.title}|${film.year}`;
  return `<article class="film unavailable-card" role="button" tabindex="0" aria-label="Open details for ${escapeHtml(film.title)}" data-key="${escapeHtml(key)}" data-title="${escapeHtml(String(film.title).toLowerCase())}" data-year="${film.year ?? ''}" data-rating="0" data-runtime="0" data-genres="" data-kinds="" data-section="Unavailable" data-providers="" data-provider-total="0" data-has-trailer="false" data-has-poster="${film.poster_path ? 'true' : 'false'}" data-changes="removed"><div class="film-info"><p class="film-title">${escapeHtml(film.title)}</p><span class="year">${film.year ?? 'Year unknown'} · <span class="badge offer-unavailable"><i class="ti ti-eye-off" aria-hidden="true"></i> Unavailable</span></span><button class="film-details-button" type="button" data-key="${escapeHtml(key)}"><i class="ti ti-info-circle"></i> Details</button></div></article>`;
}
