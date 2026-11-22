import {dateTime, escapeHtml, numberText} from './ui.js';
import {SECTION_KINDS, filmKey, sectionProviders, selectedChanges} from './filtering.js';
import {TYPE_ICON, bestWay, catalogues, wayText} from './bestway.js';

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

// The one line under a card: the logo of the best way and what it is in words, "+N" for the other services.
// The logos are no links (tap shows the name); "+N" opens the details at "Other services".
function wayLine(film, key, context) {
  const logos = context.providerLogos || {};
  const logo = (name, className = 'way-logo') => (logos[name] ? `<img class="${className}" src="${escapeHtml((context.logoBaseUrl || '') + logos[name])}" alt="" loading="lazy">` : '');
  // A film listed only because of the abroad switch has no way to watch it here: its best way is abroad.
  const way = film.abroadOnly
    ? bestWay({...film, providers: {}}, {own: context.selected, abroad: context.abroadFor ? context.abroadFor(film) : null})
    : bestWay(film, {own: context.selected});
  // Only the logo shows (the service's name when it has none); the words come in a bubble on hover, focus or tap.
  const logoOrName = name => logo(name) || `<span class="way-name">${escapeHtml(name || '')}</span>`;
  const text = escapeHtml(wayText(way));
  const title = escapeHtml(film.title);
  const none = `<div class="best-way is-muted"><span class="best-way-link is-static" tabindex="0"><i class="ti ti-ban way-none" aria-hidden="true"></i><span class="way-text">${text}</span></span></div>`;
  // A row of logos for your own services (best first), each marked with a small icon for its type in the logo's corner;
  // with the abroad switch on, your services abroad follow with the flag of their best country (dashed rim: needs a VPN).
  // "+N" counts the rest. With none of your services here, the one best way (a shop, or a service that is not yours).
  const WORDS = {free: 'Free', flatrate: 'Subscription', ads: 'With ads', rent: 'Rent', buy: 'Buy'};
  const rank = entry => (entry.name === way.service ? 0 : entry.own && ['free', 'flatrate', 'ads'].some(k => entry.kinds.has(k)) ? 1 : 2);
  // A film listed only because of the abroad switch has nothing to watch here: its offers are the abroad ones.
  const hereAll = film.abroadOnly ? [] : catalogues(film, context.selected).filter(entry => Object.keys(TYPE_ICON).some(k => entry.kinds.has(k))).sort((a, b) => rank(a) - rank(b) || a.name.localeCompare(b.name));
  const mine = hereAll.filter(entry => entry.own);
  const hereShown = (mine.length ? mine : hereAll.slice(0, 1)).slice(0, 4);
  const abroadRows = context.abroadList ? context.abroadList(film) : way.kind === 'abroad' ? [{service: way.service, countries: way.countries}] : [];
  const abroadNew = abroadRows.filter(row => !hereShown.some(entry => entry.name === row.service));
  const abroadShown = abroadNew.slice(0, 4 - hereShown.length);
  if (!hereShown.length && !abroadShown.length) return none;
  const tile = entry => {
    const kind = ['free', 'flatrate', 'ads', 'rent', 'buy'].find(k => entry.kinds.has(k));
    const dim = entry.own || kind === 'rent' || kind === 'buy' ? '' : ' is-dim';
    return `<span class="best-way-link${dim}" tabindex="0">${logoOrName(entry.name)}<span class="way-text">${escapeHtml(entry.name)} · ${WORDS[kind]}</span><span class="way-badge way-badge-${kind}" aria-hidden="true"><i class="ti ${TYPE_ICON[kind]}"></i></span></span>`;
  };
  const abroadTile = row => {
    const code = row.countries[0];
    const flag = code ? `<span class="way-badge way-badge-flag" aria-hidden="true"><img src="/static/flags/${escapeHtml(code.toLowerCase())}.svg" alt=""></span>` : '';
    const names = row.countries.map(c => (context.countryName ? context.countryName(c) : c)).join(', ');
    return `<button class="best-way-link is-abroad" type="button" data-open-more data-key="${escapeHtml(key)}">${logoOrName(row.service)}${flag}<span class="way-text">Abroad in ${escapeHtml(names)}, on ${escapeHtml(row.service)} · needs a VPN</span></button>`;
  };
  const rest = hereAll.length + abroadNew.length - hereShown.length - abroadShown.length;
  const extra = rest > 0
    ? `<button class="best-more" type="button" data-open-more data-key="${escapeHtml(key)}" aria-label="${rest} more ${rest === 1 ? 'service' : 'services'} for ${title}">+${rest}</button>`
    : '';
  return `<div class="best-way${way.muted ? ' is-muted' : ''}"><div class="way-row">${hereShown.map(tile).join('')}${abroadShown.map(abroadTile).join('')}</div>${extra}</div>`;
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
  return `<div class="film-actions"><select class="favorite-status" data-key="${escapeHtml(key)}" aria-label="Favorite status for ${name}">${option('plan', 'Plan')}${option('watching', 'Watching')}${option('watched', 'Hidden away')}</select><input class="favorite-note" data-key="${escapeHtml(key)}" aria-label="Note for ${name}" placeholder="Note" value="${escapeHtml(saved.notes || '')}"></div>`;
}

// TMDB serves a poster in several widths; the base url is w500 (the drawer's size).
const sized = (base, size) => base.replace('/w500', '/' + size);

// context: {imageBaseUrl, selected: Set, favorites: Map, compareKeys: Set, greyKeys: Set, favoritesOnly, pageHref}
export function filmCard(film, section, context) {
  const key = filmKey(film);
  const pageHref = context.pageHref || 'http://localhost/';
  // The title link below names the film, so the poster is decoration here (the details window keeps its alt text).
  const poster = film.poster_path ? `<img src="${sized(context.imageBaseUrl, 'w342')}${escapeHtml(film.poster_path)}" srcset="${['w185', 'w342', 'w500'].map(size => `${sized(context.imageBaseUrl, size)}${escapeHtml(film.poster_path)} ${size.slice(1)}w`).join(', ')}" sizes="(max-width: 800px) 45vw, 220px" alt="" loading="lazy">` : '<div class="no-poster" aria-hidden="true">No poster available</div>';
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
    ? '<span class="poster-badge">Hidden away</span>'
    : added.length ? `<span class="poster-badge poster-badge-new" title="New on ${escapeHtml(added.join(', '))}">New<span class="visually-hidden"> on ${escapeHtml(added.join(', '))}</span></span>`
      : removed.length ? `<span class="poster-badge poster-badge-gone" title="Gone from ${escapeHtml(removed.join(', '))}">Gone<span class="visually-hidden"> from ${escapeHtml(removed.join(', '))}</span></span>` : '';
  // Heart at the top right of the poster; compare, not now and grey out on a bar at its foot (hover, focus, long press).
  const act = (extra, icon, name) => `<button class="card-action" type="button" ${extra} title="${name}" aria-label="${name}"><i class="ti ${icon}" aria-hidden="true"></i></button>`;
  const bar = `<div class="poster-actions" role="group" aria-label="Actions: ${title}">${act(`data-compare="${escapeHtml(key)}"`, 'ti-layout-columns', context.compareKeys.has(key) ? 'Remove from comparison' : 'Add to comparison')}${act(`data-flag="not_now" data-key="${escapeHtml(key)}"`, 'ti-eye-off', hidden ? 'Bring back' : 'Not now (30 days)')}${act(`data-flag="watched" data-key="${escapeHtml(key)}"`, watched ? 'ti-circle-check-filled' : 'ti-circle-check', watched ? 'Remove grey-out' : 'Grey out')}</div>`;
  // The title comes first in the source (and for the keyboard); the CSS draws the poster on top. The title link covers
  // the whole card (see .film-open::after); the heart, the bar and the line sit above it.
  return `<article class="film${grey}${watched ? ' is-watched' : ''}" data-key="${escapeHtml(key)}" data-section="${section}"><div class="film-info"><h3 class="film-title">${filmLink(film, key, pageHref)}</h3><p class="year">${meta}</p><div class="card-foot">${wayLine(film, key, context)}</div>${favoriteControls}</div><div class="poster"><label class="comparison-toggle"><input class="comparison-check" type="checkbox" aria-label="Compare ${title}" ${compareChecked}><span aria-hidden="true">Compare</span></label>${badge}${favoriteButton}${poster}${bar}</div></article>`;
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
    const logos = context.providerLogos || {};
    const services = catalogues(film, context.selected)
      .sort((a, b) => Number(b.own) - Number(a.own) || a.name.localeCompare(b.name))
      .map(entry => {
        const kinds = [...entry.kinds].map(kind => (OFFER_TYPES[kind]?.[0] || (kind === 'buy' ? 'Buy' : kind)).toLowerCase()).join(', ');
        const tip = escapeHtml(`${entry.name}${entry.own ? ' (yours)' : ''}, ${kinds}`);
        return logos[entry.name]
          ? `<img class="table-logo${entry.own ? ' is-own' : ''}" src="${escapeHtml((context.logoBaseUrl || '') + logos[entry.name])}" alt="${tip}" title="${tip}" loading="lazy">`
          : `<span class="table-service" title="${tip}">${escapeHtml(entry.name)}</span>`;
      }).join('');
    const runtime = runtimeText(film.runtime);
    return `<tr data-key="${escapeHtml(key)}"><th scope="row"><span class="table-title">${film.poster_path ? `<img class="table-poster" src="${sized(context.imageBaseUrl, 'w92')}${escapeHtml(film.poster_path)}" alt="" loading="lazy" width="28" height="42">` : '<span class="table-poster" aria-hidden="true"></span>'}${filmLink(film, key, pageHref)}</span></th><td>${numberText(film.year, '')}</td><td>${runtime ? `<span aria-hidden="true">${runtime}</span><span class="visually-hidden">${runtimeSpoken(film.runtime)}</span>` : ''}</td><td>${rating}</td><td class="table-services">${services}</td></tr>`;
  }).join('');
  return `<div class="table-scroll"><table class="status-table film-table"><thead><tr><th scope="col">Title</th><th scope="col">Year</th><th scope="col">Runtime</th><th scope="col">Rating</th><th scope="col">Services</th></tr></thead><tbody>${rows}</tbody></table></div>`;
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

// Which of the values is best ("high" or "low" wins); a tie of all marks nobody, and fewer than two values prove nothing.
export function bestIndexes(values, prefer = 'high') {
  const numbers = values.map(value => (value === null || value === undefined || value === '' || !Number.isFinite(Number(value)) ? null : Number(value)));
  const known = numbers.filter(value => value !== null);
  if (known.length < 2) return [];
  const best = prefer === 'low' ? Math.min(...known) : Math.max(...known);
  if (known.every(value => value === best)) return [];
  return numbers.map((value, index) => (value === best ? index : -1)).filter(index => index >= 0);
}
