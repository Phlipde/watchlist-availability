import {dateTime, escapeHtml, numberText} from './ui.js';
import {SECTION_KINDS, filmKey, sectionProviders, selectedChanges} from './filtering.js';
import {TYPE_ICON, bestWay, catalogues, wayText} from './bestway.js';
import {logoStackHtml} from './logo-stack.js';

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
  // A film listed only because of the abroad switch has no way to watch it here: its best way is abroad.
  const way = film.abroadOnly
    ? bestWay({...film, providers: {}}, {own: context.selected, abroad: context.abroadFor ? context.abroadFor(film) : null})
    : bestWay(film, {own: context.selected});
  const text = escapeHtml(wayText(way));
  const none = `<div class="best-way is-muted"><span class="best-way-link is-static" tabindex="0"><i class="ti ti-ban way-none" aria-hidden="true"></i><span class="way-text">${text}</span></span></div>`;
  // A row of logos for your own services (best first), each marked with a small icon for its type in the logo's corner;
  // with the abroad switch on, your services abroad follow with the flag of their best country (dashed rim: needs a VPN).
  // "+N" counts the rest. With none of your services here, the one best way (a shop, or a service that is not yours).
  const rank = entry => (entry.name === way.service ? 0 : entry.own && ['free', 'flatrate', 'ads'].some(k => entry.kinds.has(k)) ? 1 : 2);
  // A film listed only because of the abroad switch has nothing to watch here: its offers are the abroad ones.
  const hereAll = film.abroadOnly ? [] : catalogues(film, context.selected).filter(entry => Object.keys(TYPE_ICON).some(k => entry.kinds.has(k))).sort((a, b) => rank(a) - rank(b) || a.name.localeCompare(b.name));
  // Rent and buy are not on the card (they live in the details); only free, subscription and ads are.
  const streaming = hereAll.filter(entry => ['free', 'flatrate', 'ads'].some(k => entry.kinds.has(k)) && entry.own);
  const freeElsewhere = hereAll.filter(entry => !entry.own && ['free', 'ads'].some(k => entry.kinds.has(k)));
  const abroadRows = context.abroadList ? context.abroadList(film) : way.kind === 'abroad' ? [{service: way.service, countries: way.countries}] : [];
  const abroadNew = abroadRows.filter(row => !streaming.some(entry => entry.name === row.service));
  const url = name => (logos[name] ? (context.logoBaseUrl || '') + logos[name] : '');
  const items = [
    ...streaming.map(entry => {
      const kind = ['free', 'flatrate', 'ads'].find(k => entry.kinds.has(k));
      return {name: entry.name, kind, logo: url(entry.name), badge: `<span class="way-badge way-badge-${kind}" aria-hidden="true"><i class="ti ${TYPE_ICON[kind]}"></i></span>`};
    }),
    ...freeElsewhere.map(entry => {
      const kind = entry.kinds.has('free') ? 'free' : 'ads';
      return {name: entry.name, kind, logo: url(entry.name), badge: `<span class="way-badge way-badge-${kind}" aria-hidden="true"><i class="ti ${TYPE_ICON[kind]}"></i></span>`};
    }),
    ...abroadNew.map(row => ({name: row.service, kind: 'abroad', logo: url(row.service), flag: row.countries[0], country: `${context.countryName ? context.countryName(row.countries[0]) : row.countries[0]}${row.countries.length > 1 ? ` +${row.countries.length - 1} more` : ''}`})),
  ];
  if (!items.length) return none;
  // Together: whose service each logo is, in the bubble; one owner's initial also in the top corner (a shared one has none).
  if (context.ownersOf) items.forEach(item => {
    const {owners, text} = context.ownersOf(item.name);
    item.owner = text;
    if (owners.length === 1) item.ownerBadge = `<span class="way-badge way-badge-owner" aria-hidden="true">${escapeHtml(owners[0].initial)}</span>`;
  });
  return `<div class="best-way${way.muted ? ' is-muted' : ''}">${logoStackHtml(items, {key})}</div>`;
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
  return `<div class="film-actions"><select class="favorite-status" data-key="${escapeHtml(key)}" aria-label="Favorite status for ${name}">${option('plan', 'Plan')}${option('watching', 'Watching')}${option('watched', 'Hidden')}</select><input class="favorite-note" data-key="${escapeHtml(key)}" aria-label="Note for ${name}" placeholder="Note" value="${escapeHtml(saved.notes || '')}"></div>`;
}

// TMDB serves a poster in several widths; the base url is w500 (the drawer's size).
const sized = (base, size) => base.replace('/w500', '/' + size);

// context: {imageBaseUrl, selected: Set, favorites: Map, compareKeys: Set, greyKeys: Set, favoritesOnly, pageHref}
export function filmCard(film, section, context) {
  const key = filmKey(film);
  const pageHref = context.pageHref || 'http://localhost/';
  // The title link below names the film, so the poster is decoration here (the details window keeps its alt text).
  const poster = film.poster_path ? `<img src="${sized(context.imageBaseUrl, 'w342')}${escapeHtml(film.poster_path)}" srcset="${['w185', 'w342', 'w500'].map(size => `${sized(context.imageBaseUrl, size)}${escapeHtml(film.poster_path)} ${size.slice(1)}w`).join(', ')}" sizes="(max-width: 800px) 45vw, 220px" alt="" loading="lazy">` : `<div class="no-poster" aria-hidden="true"><span class="no-poster-title">${escapeHtml(film.title)}</span>${film.year ? `<span class="no-poster-year">${escapeHtml(String(film.year))}</span>` : ''}</div>`;
  // Letterboxd first (the community the watchlist comes from), TMDB when Letterboxd has no value yet.
  const rating = numberText(film.letterboxd_rating)
    ? `<span aria-hidden="true">★</span><span class="visually-hidden">Letterboxd</span> ${Number(film.letterboxd_rating).toFixed(1)}`
    : Number(film.rating) > 0 ? `TMDB ${Number(film.rating).toFixed(1)}` : '';
  // Only the essentials on the card; runtime, director and genres are in the details.
  const meta = [numberText(film.year, 'Year unknown'), rating].filter(Boolean).join(' · ');
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
    ? '<span class="poster-badge">Hidden</span>'
    : added.length ? `<span class="poster-badge poster-badge-new" title="New on ${escapeHtml(added.join(', '))}">New<span class="visually-hidden"> on ${escapeHtml(added.join(', '))}</span></span>`
      : removed.length ? `<span class="poster-badge poster-badge-gone" title="Gone from ${escapeHtml(removed.join(', '))}">Gone<span class="visually-hidden"> from ${escapeHtml(removed.join(', '))}</span></span>` : '';
  // Heart at the top right of the poster; compare, not now and hide on a bar at its foot (hover, focus, long press).
  const act = (extra, icon, name) => `<button class="card-action" type="button" ${extra} title="${name}" aria-label="${name}"><i class="ti ${icon}" aria-hidden="true"></i></button>`;
  const bar = `<div class="poster-actions" role="group" aria-label="Actions: ${title}">${act(`data-compare="${escapeHtml(key)}"`, 'ti-layout-columns', context.compareKeys.has(key) ? 'Remove from comparison' : 'Add to comparison')}${act(`data-flag="not_now" data-key="${escapeHtml(key)}"`, 'ti-eye-off', hidden ? 'Bring back' : 'Not now: off Tonight and suggestions for 30 days')}${act(`data-flag="watched" data-key="${escapeHtml(key)}"`, 'ti-archive', watched ? 'Unhide' : 'Hide: stays hidden until you unhide it')}</div>`;
  // The title comes first in the source (and for the keyboard); the CSS draws the poster on top. The title link covers
  // the whole card (see .film-open::after); the heart, the bar and the line sit above it.
  return `<article class="film${grey}${watched ? ' is-watched' : ''}" data-key="${escapeHtml(key)}" data-section="${section}"><div class="film-info"><h3 class="film-title">${filmLink(film, key, pageHref)}</h3><p class="year">${meta}</p><div class="card-foot">${wayLine(film, key, context)}</div>${favoriteControls}</div><div class="poster"><label class="comparison-toggle"><input class="comparison-check" type="checkbox" aria-label="Compare ${title}" ${compareChecked}><span aria-hidden="true">Compare</span></label>${badge}${favoriteButton}${poster}${bar}</div></article>`;
}

export function unavailableCard(film, selected, pageHref = 'http://localhost/') {
  const key = filmKey(film);
  const changeBadges = changeBadgesFor(film, selected);
  return `<article class="film unavailable-card" data-key="${escapeHtml(key)}" data-section="Unavailable"><div class="film-info"><h3 class="film-title">${filmLink(film, key, pageHref)}</h3><span class="year">${numberText(film.year, 'Year unknown')}</span>${changeBadges ? `<p class="provider-changes">${changeBadges}</p>` : ''}</div></article>`;
}

// The table view: one row per film, the title is the link to the details.
export function filmTable(films, context) {
  const pageHref = context.pageHref || 'http://localhost/';
  const rows = films.map(film => {
    const key = filmKey(film);
    const rating = numberText(film.letterboxd_rating) ? `★ ${Number(film.letterboxd_rating).toFixed(1)}` : numberText(film.rating) ? `TMDB ${Number(film.rating).toFixed(1)}` : '';
    const logos = context.providerLogos || {};
    const url = name => (logos[name] ? (context.logoBaseUrl || '') + logos[name] : '');
    const items = catalogues(film, context.selected)
      .sort((a, b) => Number(b.own) - Number(a.own) || a.name.localeCompare(b.name))
      .map(entry => ({name: entry.name, kind: ['free', 'flatrate', 'ads', 'rent', 'buy'].find(k => entry.kinds.has(k)), logo: url(entry.name)}))
      .filter(item => item.kind);
    const services = logoStackHtml(items, {key});
    const runtime = runtimeText(film.runtime);
    return `<tr data-key="${escapeHtml(key)}"><th scope="row"><span class="table-title">${film.poster_path ? `<img class="table-poster" src="${sized(context.imageBaseUrl, 'w92')}${escapeHtml(film.poster_path)}" alt="" loading="lazy" width="28" height="42">` : '<span class="table-poster" aria-hidden="true"></span>'}${filmLink(film, key, pageHref)}</span></th><td class="col-year">${numberText(film.year, '')}</td><td>${runtime ? `<span aria-hidden="true">${runtime}</span><span class="visually-hidden">${runtimeSpoken(film.runtime)}</span>` : ''}</td><td>${rating}</td><td class="table-services">${services}</td></tr>`;
  }).join('');
  return `<div class="table-scroll"><table class="status-table film-table"><thead><tr><th scope="col">Title</th><th scope="col" class="col-year">Year</th><th scope="col">Runtime</th><th scope="col">Rating</th><th scope="col">Services</th></tr></thead><tbody>${rows}</tbody></table></div>`;
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
