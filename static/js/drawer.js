// The film details drawer: pure functions that turn a film and a few facts about the user into HTML.
// No DOM access here (so node can test it); app.js wires the events.
import {escapeHtml, initials, numberText} from './ui.js';
import {
  alternatives, catalogRows, dedupeKeywords, isReleased, justWatchSearch, letterboxdUrl, metaLine, primaryAction,
  sourceText, statusBadges, watchUrl,
} from './film-meta.js';
export {
  alternatives, catalogName, catalogRows, certificationText, dedupeKeywords, isReleased, letterboxdUrl, metaLine,
  primaryAction, runtimeLong, seriesOrder, sourceText, statusBadges, watchUrl,
} from './film-meta.js';

export function linkChips(film, country) {
  const links = [
    ['Letterboxd', letterboxdUrl(film), 'Open on Letterboxd'],
    film.tmdb_url ? ['TMDB', film.tmdb_url] : null,
    /^tt\d+$/.test(film.imdb_id || '') ? ['IMDb', `https://www.imdb.com/title/${film.imdb_id}/`] : null,
    ['JustWatch', justWatchSearch(film, country)],
  ].filter(Boolean);
  return `<p class="film-modal-links">${links.map(([name, href, tip]) => `<a class="link-chip" href="${escapeHtml(href)}" target="_blank" rel="noreferrer"${tip ? ` title="${escapeHtml(tip)}"` : ''}>${name}</a>`).join('')}</p>`;
}

// ---- HTML pieces ----

const logoImg = (ctx, name, className = 'provider-logo') => {
  const path = ctx.logos[name] || ctx.logos[`${name} Amazon Channel`];
  return path ? `<img class="${className}" src="${escapeHtml(ctx.logoBaseUrl + path)}" alt="" loading="lazy">` : '';
};
// The logo, or a neutral tile with the initials (the name itself is only in the tooltip).
const logoTile = (ctx, name, className) => logoImg(ctx, name, className)
  || `<span class="${className} logo-fallback" aria-hidden="true">${escapeHtml(initials(name))}</span>`;

function ratingsHtml(film) {
  const lb = Number(film.letterboxd_rating) > 0 ? Number(film.letterboxd_rating).toFixed(1) : '';
  const tmdb = Number(film.rating) > 0 ? Number(film.rating).toFixed(1) : '';  // TMDB gives unreleased films 0.0
  if (!lb && !tmdb) return '';
  // Tap or focus shows the vote count (a native title does not appear on a phone).
  const votes = film.vote_count ? `${Number(film.vote_count).toLocaleString()} votes` : '';
  const letterboxd = lb ? `<span class="rating"><svg class="rating-logo" viewBox="0 0 30 16" role="img" aria-label="Letterboxd"><circle cx="8" cy="8" r="6" fill="#00e054"/><circle cx="15" cy="8" r="6" fill="#ff8000" fill-opacity=".9"/><circle cx="22" cy="8" r="6" fill="#40bcf4" fill-opacity=".9"/></svg>★ ${lb}</span>` : '';
  const tmdbHtml = tmdb ? `<button class="rating" type="button" data-tip="${escapeHtml(votes)}" aria-label="TMDB ${tmdb}${votes ? `, ${escapeHtml(votes)}` : ''}"><span class="rating-logo rating-tmdb" aria-hidden="true">TMDB</span>${tmdb}</button>` : '';
  return `<p class="film-modal-ratings">${letterboxd}${tmdbHtml}</p>`;
}


function mainButton(action) {
  const attrs = action.disabled ? 'aria-disabled="true"' : `href="${escapeHtml(action.href)}" target="_blank" rel="noreferrer"`;
  const tag = action.disabled ? 'span' : 'a';
  const tone = action.primary ? 'btn-accent' : 'btn-outline-secondary';
  const icon = action.disabled ? '' : '<i class="ti ti-player-play" aria-hidden="true"></i> ';
  return `<${tag} class="btn ${tone} film-modal-primary${action.disabled ? ' disabled' : ''}" ${attrs}>${icon}<span>${escapeHtml(action.text)}</span></${tag}>`;
}

// One folded block: the services by offer type as a row of logos (names on hover or focus), the countries
// abroad below (filled in later by app.js), and one link for all of it instead of one per service.
function otherServicesHtml(film, ctx, action) {
  const groups = catalogRows(film.providers, ctx.own);
  const others = new Set(groups.flatMap(group => group.rows.filter(row => !row.own).map(row => row.name)));
  const url = action.href || watchUrl(film, ctx.country);
  const chip = row => {
    const owner = ctx.whose ? ctx.whose(row.name) || 'shared' : 'your';  // Together names whose it is
    const tip = `${row.name}${row.own ? ` · ${owner} service` : ''}${row.via.length ? ` · also via ${[...new Set(row.via)].join(', ')}` : ''}`;
    return `<li class="svc${row.own ? ' is-own' : ''}" tabindex="0" role="img" aria-label="${escapeHtml(tip)}" data-tip="${escapeHtml(tip)}">${logoTile(ctx, row.name, 'svc-logo')}${row.own ? '<i class="ti ti-check own-badge" aria-hidden="true"></i>' : ''}</li>`;
  };
  const groupHtml = group => (group.kind === 'buy'
    ? `<details class="offer-group offer-buy" data-offer="buy"><summary class="offer-heading">Buy (${group.rows.length})</summary><ul class="svc-list">${group.rows.map(chip).join('')}</ul></details>`
    : `<section class="offer-group" data-offer="${group.kind}"><h3 class="offer-heading">${group.label}</h3><ul class="svc-list">${group.rows.map(chip).join('')}</ul></section>`);
  const visible = groups.length && others.size;
  return `<details class="other-services" id="film-more"${visible ? '' : ' hidden'}><summary><span>Other services</span> <span class="os-count">${others.size ? `(${others.size})` : ''}</span><span class="os-abroad"></span></summary>${groups.map(groupHtml).join('')}<div id="film-abroad" class="film-abroad" hidden></div><p class="report-line">${url ? `<a href="${escapeHtml(url)}" target="_blank" rel="noreferrer">All offers</a>` : ''}<span class="info source-info" tabindex="0" role="note" data-tip="${escapeHtml(sourceText(ctx.country, ctx.scanAt))}" aria-label="${escapeHtml(sourceText(ctx.country, ctx.scanAt))}"><i class="ti ti-info-circle" aria-hidden="true"></i></span></p></details>`;
}

// A row of mini posters: the series (`current` marked) or the similar films, the service logo under each.
function posterRow(items, ctx, currentKey = '') {
  return `<ul class="mini-posters">${items.map(item => {
    const label = `${item.title}${item.year ? ` (${numberText(item.year)})` : ''}`;
    const service = ctx.serviceOf(item);
    const poster = item.poster_path ? `<img src="${ctx.imageBaseUrl}${escapeHtml(item.poster_path)}" alt="">` : `<span class="no-poster" aria-hidden="true">${escapeHtml(item.title)}</span>`;
    const badge = service ? `<span class="mini-service">${logoImg(ctx, service, 'mini-logo') || escapeHtml(service.slice(0, 2))}</span>` : '';
    const under = `${badge}<span class="mini-year">${item.year ? numberText(item.year) : ''}</span>`;
    const current = ctx.keyOf(item) === currentKey;
    const unreleased = !isReleased(item, ctx.today);
    return `<li class="${[current && 'is-current', unreleased && 'is-unreleased'].filter(Boolean).join(' ')}"><button class="series-pick" type="button" data-key="${escapeHtml(ctx.keyOf(item))}" title="${escapeHtml(label)}" aria-label="${escapeHtml(label)}${service ? `, ${escapeHtml(service)}` : ''}"${current ? ' aria-current="true"' : ''}>${poster}${under}</button></li>`;
  }).join('')}</ul>`;
}

function toolButton(className, attrs, icon, label, fullName, pressed = null) {
  return `<button class="tool ${className}" type="button" ${attrs} title="${escapeHtml(fullName)}" aria-label="${escapeHtml(fullName)}"${pressed === null ? '' : ` aria-pressed="${pressed}"`}><i class="ti ${icon}" aria-hidden="true"></i><span class="tool-label">${label}</span></button>`;
}

// The complete content of the drawer. ctx: own (Set), country, regionName, logos, logoBaseUrl, imageBaseUrl,
// countryNames (Set), key, isFavorite, isSeen, isHidden, inCompare, series (films of the collection, oldest
// first, with this one), similar (films), watched (Set of keys), serviceOf(film), keyOf(film), releaseText,
// favoriteFields (HTML), whose(service) (Together only: 'your', "Anna's" or '' for a shared service).
export function drawerHtml(film, ctx) {
  const key = ctx.key;
  const name = escapeHtml(film.title);
  const long = film.title.length > 30;
  const action = primaryAction(film, ctx.own, ctx.country, ctx.regionName, ctx.today);
  const owner = action.primary && ctx.whose ? ctx.whose(action.service) : '';
  if (owner) action.text = action.text.replace(`Watch on ${action.service}`, `Watch on ${owner} ${action.service}`);
  const badges = statusBadges(film, ctx.own).map(badge => `<p class="status-badge is-${badge.tone}">${escapeHtml(badge.text)}</p>`).join('');
  const alt = alternatives(film, ctx.own, action.service);
  const altKinds = alt.every(item => item.kind !== 'flatrate');
  const altLine = alt.length
    ? `<p class="alt-line">${altKinds ? 'Also free' : 'Also on'}: ${alt.map(item => `<a class="alt-chip" href="${escapeHtml(action.href || watchUrl(film, ctx.country))}" target="_blank" rel="noreferrer" aria-label="${escapeHtml(item.name)}" data-tip="${escapeHtml(item.name)}">${logoTile(ctx, item.name, 'provider-logo-sm')}</a>`).join('')}</p>`
    : '';
  const backdrop = film.backdrop_path ? `<img class="film-hero-backdrop" src="${ctx.imageBaseUrl.replace('/w500', '/w780')}${escapeHtml(film.backdrop_path)}" alt="">` : '';
  const trailerId = film.trailer_url ? new URL(film.trailer_url).searchParams.get('v') : null;
  const play = trailerId && backdrop ? `<button class="hero-play trailer-link" data-trailer="${escapeHtml(trailerId)}" type="button"><i class="ti ti-player-play-filled" aria-hidden="true"></i> Trailer</button>` : '';
  const trailerFallback = trailerId && !backdrop ? `<p class="film-modal-trailer"><button class="hero-play-inline trailer-link" data-trailer="${escapeHtml(trailerId)}" type="button"><i class="ti ti-player-play-filled" aria-hidden="true"></i> Trailer</button></p>` : '';
  const poster = film.poster_path ? `<img class="film-hero-poster" src="${ctx.imageBaseUrl}${escapeHtml(film.poster_path)}" alt="Poster for ${name}">` : '<span class="film-hero-poster film-hero-nopic" aria-hidden="true"></span>';
  const original = film.original_title && film.original_title !== film.title ? `<p class="film-original-title">${escapeHtml(film.original_title)}</p>` : '';
  const hero = `<div class="film-hero${backdrop ? '' : ' no-backdrop'}">${backdrop}${play}</div><div class="film-hero-head">${poster}<div class="film-hero-text"><h2 class="film-hero-title${long ? ' is-long' : ''}" id="film-hero-title" title="${name}">${name}</h2>${original}<p class="film-modal-meta">${escapeHtml(metaLine(film, ctx.country))}</p></div></div>`;

  const seenName = ctx.isSeen ? 'Unhide this film' : 'Hide this film: stays hidden until you unhide it';
  const hideName = ctx.isHidden ? 'Bring back' : 'Not now: off Tonight and suggestions for 30 days';
  const compareName = ctx.inCompare ? 'Remove from comparison' : 'Add to comparison';
  const favName = ctx.isFavorite ? 'Remove favorite' : 'Add to favorites';
  const tools = `<div class="film-modal-toolbar" role="group" aria-label="Actions">${[
    toolButton('modal-favorite', `data-key="${escapeHtml(key)}"`, ctx.isFavorite ? 'ti-heart-filled' : 'ti-heart', 'Favorite', favName, String(ctx.isFavorite)),
    toolButton('modal-compare', `data-key="${escapeHtml(key)}"`, 'ti-layout-columns', 'Compare', compareName, String(ctx.inCompare)),
    toolButton('modal-flag', `data-flag="watched" data-key="${escapeHtml(key)}"`, 'ti-archive', 'Hide', seenName, String(ctx.isSeen)),
    toolButton('modal-flag', `data-flag="not_now" data-key="${escapeHtml(key)}"`, 'ti-eye-off', 'Not now', hideName, String(ctx.isHidden)),
    toolButton('modal-share', '', 'ti-share', 'Share', 'Copy the link to this film'),
  ].join('')}</div>`;

  const overview = film.overview || 'No description available.';
  const clamp = overview.length > 220;
  const credits = film.director || (film.cast || []).length
    ? `<p class="film-modal-credits">${film.director ? `Directed by ${personLink(film.director)}` : ''}${film.director && film.cast?.length ? ' · ' : ''}${film.cast?.length ? `Cast: ${film.cast.slice(0, 5).map(personLink).join(', ')}` : ''}</p>` : '';
  const collection = ctx.series.length > 1
    ? `<div class="film-modal-series"><p>Part of ${escapeHtml(film.collection)}${firstUnseen(ctx, key)}</p>${posterRow(ctx.series, ctx, key)}</div>` : '';
  const similar = ctx.similar.length ? `<div class="film-modal-similar"><p>Similar on your services</p>${posterRow(ctx.similar.slice(0, 6), ctx)}</div>` : '';
  const regionNames = ctx.regionNames || ((code) => code);
  const origin = (film.origin_countries || []).slice(0, 3);
  const words = dedupeKeywords(film.keywords, new Set([...(ctx.countryNames || []), ...origin.map(code => String(regionNames(code)).toLowerCase())]));
  const chip = word => `<a class="chip-link" href="/watchlist?keyword=${encodeURIComponent(word)}">${escapeHtml(word)}</a>`;
  const keywords = words.length
    ? `<p class="film-modal-chips">${words.slice(0, 8).map(chip).join('')}${words.slice(8).map(word => chip(word).replace('class="chip-link"', 'class="chip-link is-extra" hidden')).join('')}${words.length > 8 ? `<button class="chip-link chip-more" type="button" aria-expanded="false">+${words.length - 8}</button>` : ''}</p>` : '';
  const release = ctx.releaseText ? `<p class="film-modal-release">Coming ${escapeHtml(ctx.releaseText)}</p>` : '';

  return `${hero}<div class="film-modal-body">${ratingsHtml(film)}${badges}${mainButton(action)}${altLine}${otherServicesHtml(film, ctx, action)}${tools}${trailerFallback}<div class="film-modal-about"><div class="overview-box${clamp ? ' clamped' : ''}"><p class="film-modal-overview" id="film-overview">${escapeHtml(overview)}</p>${clamp ? '<button class="overview-more" type="button" aria-expanded="false" aria-controls="film-overview">more</button>' : ''}</div>${release}${credits}${collection}${similar}${keywords}${linkChips(film, ctx.country)}</div><div id="modal-favorite-fields" data-key="${escapeHtml(key)}">${ctx.favoriteFields}</div></div>`;
}

const personLink = person => `<a class="person-link" href="/watchlist?q=${encodeURIComponent(person)}">${escapeHtml(person)}</a>`;

// "Start with The Matrix (1999)" when an earlier part of the series is on the watchlist and not watched yet.
function firstUnseen(ctx, key) {
  const index = ctx.series.findIndex(item => ctx.keyOf(item) === key);
  const earlier = ctx.series.slice(0, Math.max(index, 0)).find(item => isReleased(item, ctx.today) && !ctx.watched.has(ctx.keyOf(item)));
  return earlier ? ` · Start with ${escapeHtml(earlier.title)}${earlier.year ? ` (${numberText(earlier.year)})` : ''}` : '';
}
