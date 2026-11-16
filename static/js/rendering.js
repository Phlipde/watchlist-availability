import {dateTime, escapeHtml, numberText} from './ui.js';
import {filmKey, sectionProviders, selectedChanges, selectedKinds} from './filtering.js';

// "Free" alone was read three ways; the section says what it holds.
const SECTION_TITLES = {Free: 'Free & with ads', Paid: 'Paid'};

const OFFER_TYPES = {
  free: ['Free', 'ti ti-gift'],
  ads: ['With ads', 'ti ti-ad-2'],
  flatrate: ['Subscription', 'ti ti-repeat'],
  rent: ['Rent', 'ti ti-ticket'],
};

export function offerBadges(kinds) {
  return [...new Set(kinds)].map(kind => {
    const [label, icon] = OFFER_TYPES[kind] || [kind, 'ti ti-circle'];
    return `<span class="pill offer-badge offer-${escapeHtml(kind)}"><i class="${icon}" aria-hidden="true"></i> ${escapeHtml(label)}</span>`;
  }).join('');
}

// Availability in the details window: one group per offer type (Free, With ads, Subscription,
// Rent). The user's own services come first and are marked, the rest in alphabetical order,
// each with its logo when TMDB has one.
export function availabilityByOffer(providers, logos = {}, logoBaseUrl = '', own = new Set()) {
  const entries = Object.entries(providers || {});
  return Object.entries(OFFER_TYPES).map(([kind, [label, icon]]) => {
    const names = entries.filter(([, kinds]) => kinds.includes(kind)).map(([name]) => name)
      .sort((a, b) => Number(own.has(b)) - Number(own.has(a)) || a.localeCompare(b, undefined, {sensitivity: 'base'}));
    if (!names.length) return '';
    const rows = names.map(name => {
      const logo = logos[name] ? `<img class="provider-logo" src="${escapeHtml(logoBaseUrl + logos[name])}" alt="" loading="lazy">` : '';
      const mine = own.has(name) ? ' <span class="pill pill-ok">Your service</span>' : '';
      return `<li${own.has(name) ? ' class="own-service"' : ''}>${logo}<span>${escapeHtml(name)}</span>${mine}</li>`;
    }).join('');
    return `<section class="film-offer-group" data-offer="${kind}"><h6 class="film-offer-heading"><i class="${icon}" aria-hidden="true"></i> ${label}</h6><ul class="film-provider-list">${rows}</ul></section>`;
  }).join('');
}

function changeBadgesFor(film, selected) {
  const changes = selectedChanges(film, selected);
  return [
    ...changes.added.map(provider => `<span class="badge text-bg-success me-1">New on ${escapeHtml(provider)}</span>`),
    ...changes.removed.map(provider => `<span class="badge text-bg-secondary me-1">No longer on ${escapeHtml(provider)}</span>`),
  ].join('');
}

// The "Scan changes" box: stored changes of the last two weeks for the selected providers.
export function changeSummary(changes, selected, lastScan) {
  const relevant = (changes || []).filter(change => selected.has(change.provider));
  const added = relevant.filter(change => change.change === 'added').length;
  const day = seconds => new Date(seconds * 1000).toLocaleDateString();
  const rows = relevant.slice(0, 60).map(change =>
    `<li>${day(change.created)} · ${escapeHtml(change.title)}: ${change.change === 'added' ? 'new on' : 'no longer on'} ${escapeHtml(change.provider)}</li>`
  ).join('');
  return (lastScan ? `<p>Last successful scan: ${dateTime(lastScan)}.</p>` : '')
    + `<p>Last 14 days on your selected services: ${added} new, ${relevant.length - added} no longer available.</p>`
    + (rows ? `<ul class="change-list">${rows}</ul>` : '')
    + (relevant.length > 60 ? `<p>… and ${relevant.length - 60} more.</p>` : '');
}

// Status and note of a favorite; data-key lets the same fields work on the card and in the details.
export function favoriteFields(key, title, saved = {}) {
  const name = escapeHtml(title);
  const option = (value, label) => `<option value="${value}" ${saved.status === value ? 'selected' : ''}>${label}</option>`;
  return `<div class="film-actions"><select class="favorite-status" data-key="${escapeHtml(key)}" aria-label="Favorite status for ${name}">${option('plan', 'Plan')}${option('watching', 'Watching')}${option('watched', 'Watched')}</select><input class="favorite-note" data-key="${escapeHtml(key)}" aria-label="Note for ${name}" placeholder="Note" value="${escapeHtml(saved.notes || '')}"></div>`;
}

// The compare button says how many films are chosen.
export function compareButtonState(count) {
  return {text: count ? `Compare (${count})` : 'Compare'};
}

// context: {imageBaseUrl, selected: Set, favorites: Map, compareKeys: Set, greyKeys: Set, favoritesOnly}
export function filmCard(film, section, context) {
  const key = filmKey(film);
  const providers = sectionProviders(film, section).filter(provider => context.selected.has(provider));
  const kinds = selectedKinds(film, context.selected);
  const poster = film.poster_path ? `<img src="${context.imageBaseUrl}${escapeHtml(film.poster_path)}" alt="Poster for ${escapeHtml(film.title)}" loading="lazy">` : '<div class="no-poster">No poster available</div>';
  const rating = numberText(film.rating) ? `TMDB ${Number(film.rating).toFixed(1)}/10` : 'No rating';
  const trailerId = film.trailer_url ? new URL(film.trailer_url).searchParams.get('v') : null;
  const links = `${film.tmdb_url ? `<a class="film-link" href="${escapeHtml(film.tmdb_url)}" target="_blank" rel="noreferrer">TMDB</a>` : ''}${trailerId ? ` · <button class="film-link trailer-link" data-trailer="${escapeHtml(trailerId)}" type="button">Trailer</button>` : ''}`;
  const favorite = context.favorites.has(key);
  const savedFavorite = context.favorites.get(key) || {};
  const providerBadges = providers.map(provider => `<span class="pill pill-service me-1 mb-1" data-provider="${escapeHtml(provider)}">${escapeHtml(provider)}</span>`).join('');
  const changeBadges = changeBadgesFor(film, context.selected);
  const title = escapeHtml(film.title);
  const favoriteButton = `<button class="favorite" type="button" aria-label="Favorite: ${title}" aria-pressed="${favorite}" data-favorite="${favorite ? 'true' : 'false'}"><span aria-hidden="true">${favorite ? '★' : '☆'}</span></button>`;
  const compareChecked = context.compareKeys.has(key) ? 'checked' : '';
  const grey = context.greyKeys.has(key) ? ' rescan-unavailable' : '';
  // Status and note only in the favorites view (and in the details), so the cards do not jump.
  const favoriteControls = favorite && context.favoritesOnly ? favoriteFields(key, film.title, savedFavorite) : '';
  const watched = savedFavorite.status === 'watched' ? ' <span class="pill pill-neutral">Watched</span>' : '';
  // The card is clickable with the mouse; keyboard users reach the details through the "Details" button.
  return `<article class="film${grey}" data-key="${escapeHtml(key)}" data-section="${section}"><div class="poster"><label class="comparison-toggle"><input class="comparison-check" type="checkbox" aria-label="Compare ${title}" ${compareChecked}><span aria-hidden="true">Compare</span></label>${poster}${favoriteButton}</div><div class="film-info"><h3 class="film-title">${title}${watched}</h3><span class="year">${numberText(film.year, 'Year unknown')} · ${rating}${numberText(film.runtime) ? ` · ${numberText(film.runtime)} min` : ''}</span><p class="providers">${providerBadges}</p><div class="offer-badges">${offerBadges(kinds)}</div>${links ? `<p class="film-links">${links}</p>` : ''}${changeBadges ? `<p class="provider-changes">${changeBadges}</p>` : ''}<button class="btn btn-sm btn-outline-secondary film-details-button" type="button" data-key="${escapeHtml(key)}" aria-label="Details: ${title}"><i class="ti ti-info-circle" aria-hidden="true"></i> Details</button>${favoriteControls}</div></article>`;
}

export function unavailableCard(film, selected) {
  const key = filmKey(film);
  const changeBadges = changeBadgesFor(film, selected);
  return `<article class="film unavailable-card" data-key="${escapeHtml(key)}" data-section="Unavailable"><div class="film-info"><h3 class="film-title">${escapeHtml(film.title)}</h3><span class="year">${numberText(film.year, 'Year unknown')} · <span class="pill pill-neutral"><i class="ti ti-eye-off" aria-hidden="true"></i> Unavailable</span></span>${changeBadges ? `<p class="provider-changes">${changeBadges}</p>` : ''}<button class="btn btn-sm btn-outline-secondary film-details-button" type="button" data-key="${escapeHtml(key)}" aria-label="Details: ${escapeHtml(film.title)}"><i class="ti ti-info-circle" aria-hidden="true"></i> Details</button></div></article>`;
}

// Draws the Free/Paid sections and the unavailable list from the result of filterFilms().
export function renderResults(view, containers, context) {
  containers.results.innerHTML = Object.entries(view.sections)
    .filter(([, films]) => films.length)
    .map(([section, films]) => `<div class="result-section" data-section="${section}"><h2>${SECTION_TITLES[section] || section}</h2><div class="films">${films.map(film => filmCard(film, section, context)).join('')}</div></div>`)
    .join('');
  containers.unavailableResults.innerHTML = view.unavailable.map(film => unavailableCard(film, context.selected)).join('');
}
