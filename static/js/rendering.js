import {dateTime, escapeHtml, numberText} from './ui.js';
import {SECTION_KINDS, filmKey, sectionProviders, selectedChanges} from './filtering.js';

// "Free" alone was read three ways; the section says what it holds.

const OFFER_TYPES = {
  free: ['Free', 'ti ti-gift'],
  ads: ['With ads', 'ti ti-ad-2'],
  flatrate: ['Subscription', 'ti ti-repeat'],
  rent: ['Rent', 'ti ti-ticket'],
};

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

// Runtime on the card as hours and minutes: 154 → "2h 34m", 58 → "58m", 120 → "2h".
export function runtimeText(minutes) {
  const total = Math.round(Number(minutes));
  if (!Number.isFinite(total) || total <= 0) return '';
  const hours = Math.floor(total / 60);
  const rest = total % 60;
  return [hours ? `${hours}h` : '', rest ? `${rest}m` : ''].filter(Boolean).join(' ');
}

// Address of a film's details: the current page plus film=<key>, so a new tab keeps country and filters.
export function filmHref(pageHref, key) {
  const url = new URL(pageHref);
  url.searchParams.delete('scan');  // a finished scan job in a new tab would start a new scan
  url.searchParams.set('film', key);
  return url.pathname + url.search;
}

// What a screen reader says for the runtime: "1 hour 47 minutes".
function runtimeSpoken(minutes) {
  const total = Math.round(Number(minutes));
  const hours = Math.floor(total / 60);
  const rest = total % 60;
  return [hours ? `${hours} hour${hours === 1 ? '' : 's'}` : '', rest ? `${rest} minute${rest === 1 ? '' : 's'}` : ''].filter(Boolean).join(' ');
}

function filmLink(film, key, pageHref, className = 'film-open') {
  return `<a class="${className}" href="${escapeHtml(filmHref(pageHref, key))}" data-key="${escapeHtml(key)}" title="${escapeHtml(film.title)}">${escapeHtml(film.title)}</a>`;
}

// Mark on a service logo for the offer type in the card's section; a subscription is the usual case and has none.
const SERVICE_MARKS = {free: '<i class="ti ti-gift"></i>', ads: 'Ad', rent: '€'};

// Every ticked service the film runs on in this section, sorted by name so a service keeps its place across cards.
function serviceList(film, section, context) {
  const sectionKinds = section === 'All' ? ['free', 'ads', 'flatrate', 'rent'] : SECTION_KINDS[section] || [];
  const logos = context.providerLogos || {};
  const offered = section === 'All' ? Object.keys(film.providers || {}) : sectionProviders(film, section);
  return offered.filter(provider => context.selected.has(provider))
    .sort((a, b) => a.localeCompare(b, undefined, {sensitivity: 'base'}))
    .map(provider => {
      const kinds = film.providers[provider] || [];
      const kind = sectionKinds.find(item => kinds.includes(item));
      const offers = kinds.map(item => (OFFER_TYPES[item]?.[0] || item).toLowerCase()).join(', ');
      const name = escapeHtml(provider);
      const mark = SERVICE_MARKS[kind] ? `<span class="service-mark service-mark-${kind}" aria-hidden="true">${SERVICE_MARKS[kind]}</span>` : '';
      const label = logos[provider]
        ? `<img class="service-logo" src="${escapeHtml((context.logoBaseUrl || '') + logos[provider])}" alt="${name}, ${escapeHtml(offers)}" title="${name}, ${escapeHtml(offers)}" loading="lazy">`
        : `<span class="pill pill-service" title="${name}, ${escapeHtml(offers)}">${name}<span class="visually-hidden">, ${escapeHtml(offers)}</span></span>`;
      return `<li class="service" data-provider="${name}">${label}${mark}</li>`;
    }).join('');
}

export function changeBadgesFor(film, selected) {
  const changes = selectedChanges(film, selected);
  return [
    ...changes.added.map(provider => `<span class="pill pill-ok me-1">New on ${escapeHtml(provider)}</span>`),
    ...changes.removed.map(provider => `<span class="pill pill-neutral me-1">No longer on ${escapeHtml(provider)}</span>`),
  ].join('');
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

// context: {imageBaseUrl, selected: Set, favorites: Map, compareKeys: Set, greyKeys: Set, favoritesOnly, pageHref}
export function filmCard(film, section, context) {
  const key = filmKey(film);
  const pageHref = context.pageHref || 'http://localhost/';
  // The title link below names the film, so the poster is decoration here (the details window keeps its alt text).
  const poster = film.poster_path ? `<img src="${context.imageBaseUrl}${escapeHtml(film.poster_path)}" alt="" loading="lazy">` : '<div class="no-poster" aria-hidden="true">No poster available</div>';
  // Letterboxd first (the community the watchlist comes from), TMDB when Letterboxd has no value yet.
  const rating = numberText(film.letterboxd_rating)
    ? `<span aria-hidden="true">★</span><span class="visually-hidden">Letterboxd</span> ${Number(film.letterboxd_rating).toFixed(1)}`
    : numberText(film.rating) ? `TMDB ${Number(film.rating).toFixed(1)}` : '';
  const runtime = runtimeText(film.runtime) && `<span aria-hidden="true">${runtimeText(film.runtime)}</span><span class="visually-hidden">${runtimeSpoken(film.runtime)}</span>`;
  const meta = [numberText(film.year, 'Year unknown'), runtime, rating].filter(Boolean).join(' · ');
  const favorite = context.favorites.has(key);
  const savedFavorite = context.favorites.get(key) || {};
  const title = escapeHtml(film.title);
  const favoriteButton = `<button class="favorite" type="button" aria-label="Favorite: ${title}" aria-pressed="${favorite}" data-favorite="${favorite ? 'true' : 'false'}"><i class="ti ${favorite ? 'ti-heart-filled' : 'ti-heart'}" aria-hidden="true"></i></button>`;
  const compareChecked = context.compareKeys.has(key) ? 'checked' : '';
  const grey = context.greyKeys.has(key) ? ' rescan-unavailable' : '';
  // Status and note only in the favorites view (and in the details), so the cards do not jump.
  const favoriteControls = favorite && context.favoritesOnly ? favoriteFields(key, film.title, savedFavorite) : '';
  // At most one status on the poster, as text: watched beats new.
  const {added, removed} = selectedChanges(film, context.selected);
  const watched = savedFavorite.status === 'watched' || Boolean(context.watched?.has(key));
  const hidden = Boolean(context.hiddenKeys?.has(key));
  const badge = watched
    ? '<span class="poster-badge">Watched</span>'
    : added.length ? `<span class="poster-badge poster-badge-new" title="New on ${escapeHtml(added.join(', '))}">New<span class="visually-hidden"> on ${escapeHtml(added.join(', '))}</span></span>`
      : removed.length ? `<span class="poster-badge poster-badge-gone" title="Gone from ${escapeHtml(removed.join(', '))}">Gone<span class="visually-hidden"> from ${escapeHtml(removed.join(', '))}</span></span>` : '';
  const services = serviceList(film, section, context);
  // The "..." menu: watched, not now, compare. The summary is the third tab stop of a card, after the title and the heart.
  const menu = `<details class="card-menu"><summary class="card-more" aria-label="More actions: ${title}"><i class="ti ti-dots" aria-hidden="true"></i></summary><div class="card-menu-items"><button type="button" data-flag="watched" data-key="${escapeHtml(key)}">${watched ? 'Not watched after all' : 'Mark as watched'}</button><button type="button" data-flag="not_now" data-key="${escapeHtml(key)}">${hidden ? 'Bring back' : 'Not now (30 days)'}</button><button type="button" data-compare="${escapeHtml(key)}">${context.compareKeys.has(key) ? 'Remove from comparison' : 'Add to comparison'}</button></div></details>`;
  // The title link covers the whole card (see .film-open::after); the star sits above it. Two tab stops per card.
  return `<article class="film${grey}" data-key="${escapeHtml(key)}" data-section="${section}"><div class="poster"><label class="comparison-toggle"><input class="comparison-check" type="checkbox" aria-label="Compare ${title}" ${compareChecked}><span aria-hidden="true">Compare</span></label>${badge}${poster}</div><div class="film-info"><h3 class="film-title">${filmLink(film, key, pageHref)}</h3><p class="year">${meta}</p><div class="card-foot">${services ? `<ul class="services">${services}</ul>` : '<span></span>'}<span class="card-actions">${favoriteButton}${menu}</span></div>${favoriteControls}</div></article>`;
}

export function unavailableCard(film, selected, pageHref = 'http://localhost/') {
  const key = filmKey(film);
  const changeBadges = changeBadgesFor(film, selected);
  return `<article class="film unavailable-card" data-key="${escapeHtml(key)}" data-section="Unavailable"><div class="film-info"><h3 class="film-title">${filmLink(film, key, pageHref)}</h3><span class="year">${numberText(film.year, 'Year unknown')} · <span class="pill pill-neutral"><i class="ti ti-eye-off" aria-hidden="true"></i> Unavailable</span></span>${changeBadges ? `<p class="provider-changes">${changeBadges}</p>` : ''}</div></article>`;
}

// The table view: one row per film, the title is the link to the details.
export function filmTable(films, context) {
  const pageHref = context.pageHref || 'http://localhost/';
  const rows = films.map(film => {
    const key = filmKey(film);
    const rating = numberText(film.letterboxd_rating) ? `★ ${Number(film.letterboxd_rating).toFixed(1)}` : numberText(film.rating) ? `TMDB ${Number(film.rating).toFixed(1)}` : '';
    const services = Object.entries(film.providers || {}).filter(([name]) => context.selected.has(name)).map(([name]) => name).sort((a, b) => a.localeCompare(b)).join(', ');
    const runtime = runtimeText(film.runtime);
    return `<tr data-key="${escapeHtml(key)}"><th scope="row">${filmLink(film, key, pageHref)}</th><td>${numberText(film.year, '')}</td><td>${runtime ? `<span aria-hidden="true">${runtime}</span><span class="visually-hidden">${runtimeSpoken(film.runtime)}</span>` : ''}</td><td>${rating}</td><td>${escapeHtml(services)}</td></tr>`;
  }).join('');
  return `<div class="table-scroll"><table class="status-table film-table"><thead><tr><th scope="col">Title</th><th scope="col">Year</th><th scope="col">Runtime</th><th scope="col">Rating</th><th scope="col">On your services</th></tr></thead><tbody>${rows}</tbody></table></div>`;
}

// Draws the films (as cards, compact cards or a table) and the unavailable list from the result of filterFilms().
export function renderResults(view, containers, context) {
  const mode = context.viewMode || 'grid';
  containers.results.dataset.mode = mode;
  containers.results.innerHTML = !view.films.length ? ''
    : mode === 'table' ? filmTable(view.films, context)
      : `<div class="films">${view.films.map(film => filmCard(film, view.sectionOf.get(filmKey(film)), context)).join('')}</div>`;
  containers.unavailableResults.innerHTML = view.unavailable.map(film => unavailableCard(film, context.selected, context.pageHref)).join('');
}
