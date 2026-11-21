// The film details drawer: pure functions that turn a film and a few facts about the user into HTML.
// No DOM access here (so node can test it); app.js wires the events.
import {escapeHtml, numberText} from './ui.js';
import {selectedChanges} from './filtering.js';

// Where "Report" opens a prefilled issue (nothing is sent until the user submits it there).
export const ISSUES_URL = 'https://github.com/Phlipde/watchlist-availability/issues/new';

const KIND_ORDER = ['free', 'ads', 'flatrate', 'rent', 'buy'];
const KIND_LABEL = {free: 'Free', ads: 'With ads', flatrate: 'Subscription', rent: 'Rent', buy: 'Buy'};
const WATCH = ['free', 'ads', 'flatrate'];
const PAY = ['rent', 'buy'];

// "HBO Max Amazon Channel" shows the same films as "HBO Max" (same rule as costs.catalog_name in Python).
export const catalogName = name => String(name).replace(/\s+Amazon channels?$/i, '');
const isChannel = name => catalogName(name) !== name;

// 148 → "2 h 28", 61 → "1 h 01", 58 → "58 min".
export function runtimeLong(minutes) {
  const total = Math.round(Number(minutes));
  if (!Number.isFinite(total) || total <= 0) return '';
  return total < 60 ? `${total} min` : `${Math.floor(total / 60)} h ${String(total % 60).padStart(2, '0')}`;
}

// The age rating the way people in that country say it: "FSK 12" in Germany, "rated 12" elsewhere.
export function certificationText(certification, country) {
  const text = String(certification ?? '').trim();
  if (!text) return '';
  return country === 'DE' ? `FSK ${text}` : text === '0' ? 'all ages' : `rated ${text}`;
}

export function metaLine(film, country) {
  return [numberText(film.year, ''), runtimeLong(film.runtime), certificationText(film.certification, country), (film.genres || []).join(', ')]
    .filter(Boolean).join(' · ');
}

// Country and place names are where a film comes from, not what it is about: they leave the keyword chips.
// `countryNames` is a Set of lower-case names (all ISO countries, from Intl.DisplayNames in the browser).
const PLACE_ALIASES = ['great britain', 'britain', 'england', 'scotland', 'wales', 'northern ireland', 'usa', 'u.s.', 'america', 'uk', 'soviet union', 'ussr'];
export function dedupeKeywords(keywords, countryNames = new Set()) {
  countryNames = new Set([...countryNames, ...PLACE_ALIASES]);
  const seen = new Set();
  const kept = [];
  for (const raw of keywords || []) {
    const word = String(raw).trim();
    const key = word.toLowerCase();
    if (!word || seen.has(key)) continue;
    seen.add(key);
    if (key.split(',').some(part => countryNames.has(part.trim()))) continue;
    kept.push(word);
  }
  return kept;
}

// {kind: [names]} → rows per offer type; "X" and "X Amazon Channel" are one row, the channel noted.
// Returns [{kind, label, rows: [{name, own, via}]}] in the order Free, With ads, Subscription, Rent, Buy.
export function catalogRows(providers, own) {
  const entries = Object.entries(providers || {});
  return KIND_ORDER.map(kind => {
    const byCatalog = new Map();
    for (const [name, kinds] of entries) {
      if (!kinds.includes(kind)) continue;
      const catalog = catalogName(name);
      const row = byCatalog.get(catalog) || {name: catalog, own: false, via: []};
      row.own = row.own || own.has(name) || own.has(catalog);
      if (isChannel(name)) row.via.push('Amazon Channel');
      byCatalog.set(catalog, row);
    }
    const rows = [...byCatalog.values()].sort((a, b) => Number(b.own) - Number(a.own) || a.name.localeCompare(b.name, undefined, {sensitivity: 'base'}));
    return {kind, label: KIND_LABEL[kind], rows};
  }).filter(group => group.rows.length);
}

// TMDB's watch page (JustWatch data); the JustWatch search when the film has no TMDB address (never an empty link).
export function watchUrl(film, country) {
  return film.tmdb_url ? `${film.tmdb_url}/watch?locale=${encodeURIComponent(country)}` : justWatchSearch(film, country);
}
const justWatchSearch = (film, country) => `https://www.justwatch.com/${encodeURIComponent(String(country).toLowerCase())}/search?q=${encodeURIComponent(film.title)}`;

// The one way to watch it that the main button shows, or why there is none. `primary` is true only for
// something watchable on an own service (that is the only gold button).
export function primaryAction(film, own, country, regionName = country) {
  const offers = Object.entries(film.providers || {});
  const best = (names, kinds) => offers
    .filter(([name, offered]) => names(name) && kinds.some(kind => offered.includes(kind)))
    .map(([name, offered]) => ({name: catalogName(name), kind: kinds.find(kind => offered.includes(kind))}))
    .sort((a, b) => kinds.indexOf(a.kind) - kinds.indexOf(b.kind) || a.name.localeCompare(b.name))[0];
  const mine = name => own.has(name) || own.has(catalogName(name));
  const href = watchUrl(film, country);
  let found = best(mine, WATCH);
  if (found) return {primary: true, text: `Watch on ${found.name} · ${KIND_LABEL[found.kind]}`, service: found.name, href};
  found = best(mine, PAY);
  if (found) return {primary: false, text: `${found.kind === 'buy' ? 'Buy' : 'Rent'} on ${found.name}`, service: found.name, href};
  found = best(() => true, WATCH);
  if (found) return {primary: false, text: `On ${found.name} (not your service)`, service: found.name, href};
  found = best(() => true, PAY);
  if (found) return {primary: false, text: `${found.kind === 'buy' ? 'Buy' : 'Rent'} on ${found.name}`, service: found.name, href};
  return {primary: false, text: `Not streaming in ${regionName}`, service: null, href: '', disabled: true};
}

// More own services that carry it for nothing extra, besides the one on the button.
export function alternatives(film, own, primaryService) {
  const names = new Map();
  for (const [name, offered] of Object.entries(film.providers || {})) {
    const catalog = catalogName(name);
    if (catalog === primaryService || !(own.has(name) || own.has(catalog))) continue;
    const kind = WATCH.find(item => offered.includes(item));
    if (kind && (!names.has(catalog) || WATCH.indexOf(kind) < WATCH.indexOf(names.get(catalog)))) names.set(catalog, kind);
  }
  return [...names].map(([name, kind]) => ({name, kind})).sort((a, b) => a.name.localeCompare(b.name));
}

// "12.11." from epoch seconds.
const shortDate = seconds => { const day = new Date(seconds * 1000); return `${day.getDate()}.${day.getMonth() + 1}.`; };

// "New on Netflix · since 12.11." / "No longer on Prime Video · since 14.11.", only for the services that count.
export function statusBadges(film, selected) {
  const {added, removed} = selectedChanges(film, selected);
  const since = film.provider_changes?.since;
  const when = since ? ` · since ${shortDate(since)}` : '';
  return [
    ...removed.map(name => ({tone: 'gone', text: `No longer on ${name}${when}`})),
    ...added.map(name => ({tone: 'new', text: `New on ${name}${when}`})),
  ];
}

// Letterboxd redirects /tmdb/<id> to the film page; the search is only the way out when there is no id.
export function letterboxdUrl(film) {
  return film.tmdb_id ? `https://letterboxd.com/tmdb/${encodeURIComponent(film.tmdb_id)}/` : `https://letterboxd.com/search/${encodeURIComponent(`${film.title} ${film.year || ''}`.trim())}/`;
}

export function linkChips(film, country) {
  const links = [
    ['Letterboxd', letterboxdUrl(film)],
    film.tmdb_url ? ['TMDB', film.tmdb_url] : null,
    /^tt\d+$/.test(film.imdb_id || '') ? ['IMDb', `https://www.imdb.com/title/${film.imdb_id}/`] : null,
    ['JustWatch', justWatchSearch(film, country)],
  ].filter(Boolean);
  return `<p class="film-modal-links">${links.map(([name, href]) => `<a class="link-chip" href="${escapeHtml(href)}" target="_blank" rel="noreferrer">${name} <i class="ti ti-arrow-up-right" aria-hidden="true"></i></a>`).join('')}</p>`;
}

export function reportUrl(film, country, service = '') {
  const title = `Wrong availability: ${film.title}${service ? ` on ${service}` : ''} (${country})`;
  const body = `Film: ${film.title}${film.year ? ` (${film.year})` : ''}\nTMDB id: ${film.tmdb_id ?? 'unknown'}\nCountry: ${country}${service ? `\nService: ${service}` : ''}\n\nWhat is wrong:\n`;
  return `${ISSUES_URL}?title=${encodeURIComponent(title)}&body=${encodeURIComponent(body)}`;
}

// ---- HTML pieces ----

const logoImg = (ctx, name, className = 'provider-logo') => {
  const path = ctx.logos[name] || ctx.logos[`${name} Amazon Channel`];
  return path ? `<img class="${className}" src="${escapeHtml(ctx.logoBaseUrl + path)}" alt="" loading="lazy">` : '';
};

function ratingsHtml(film) {
  const lb = numberText(film.letterboxd_rating) ? Number(film.letterboxd_rating).toFixed(1) : '';
  const tmdb = numberText(film.rating) ? Number(film.rating).toFixed(1) : '';
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

function otherServicesHtml(film, ctx, action) {
  const groups = catalogRows(film.providers, ctx.own);
  const others = new Set(groups.flatMap(group => group.rows.filter(row => !row.own).map(row => row.name)));
  const url = action.href || watchUrl(film, ctx.country);
  if (!groups.length || !others.size) return '';
  const rowHtml = row => `<li><a class="offer-row${row.own ? ' is-own' : ''}" href="${escapeHtml(url)}" target="_blank" rel="noreferrer">${row.own ? '<i class="ti ti-check own-check" aria-hidden="true"></i><span class="visually-hidden">Your service: </span>' : '<span class="own-check"></span>'}${logoImg(ctx, row.name)}<span class="offer-name">${escapeHtml(row.name)}</span>${row.via.length ? `<span class="offer-note">also via ${escapeHtml([...new Set(row.via)].join(', '))}</span>` : ''}<i class="ti ti-chevron-right offer-go" aria-hidden="true"></i></a></li>`;
  const groupHtml = group => {
    const body = `<h3 class="offer-heading">${group.label}</h3><ul class="offer-list">${group.rows.map(rowHtml).join('')}</ul>`;
    return group.kind === 'buy'
      ? `<details class="offer-group offer-buy" data-offer="buy"><summary class="offer-heading">Buy (${group.rows.length})</summary><ul class="offer-list">${group.rows.map(rowHtml).join('')}</ul></details>`
      : `<section class="offer-group" data-offer="${group.kind}">${body}</section>`;
  };
  return `<details class="other-services"><summary>Other services (${others.size})</summary>${groups.map(groupHtml).join('')}<p class="report-line">Something wrong? <a href="${escapeHtml(reportUrl(film, ctx.country, action.service || ''))}" target="_blank" rel="noreferrer">Report</a></p></details>`;
}

// A row of mini posters: the series (`current` marked) or the similar films, the service logo under each.
function posterRow(items, ctx, currentKey = '') {
  return `<ul class="mini-posters">${items.map(item => {
    const label = `${item.title}${item.year ? ` (${numberText(item.year)})` : ''}`;
    const service = ctx.serviceOf(item);
    const poster = item.poster_path ? `<img src="${ctx.imageBaseUrl}${escapeHtml(item.poster_path)}" alt="" loading="lazy">` : `<span class="no-poster" aria-hidden="true">${escapeHtml(item.title)}</span>`;
    const under = service ? `<span class="mini-service">${logoImg(ctx, service, 'mini-logo') || escapeHtml(service)}</span>` : '<span class="mini-service"></span>';
    const current = ctx.keyOf(item) === currentKey;
    return `<li${current ? ' class="is-current"' : ''}><button class="series-pick" type="button" data-key="${escapeHtml(ctx.keyOf(item))}" title="${escapeHtml(label)}" aria-label="${escapeHtml(label)}${service ? `, ${escapeHtml(service)}` : ''}"${current ? ' aria-current="true"' : ''}>${poster}${under}</button></li>`;
  }).join('')}</ul>`;
}

function toolButton(className, attrs, icon, label, fullName, pressed = null) {
  return `<button class="tool ${className}" type="button" ${attrs} title="${escapeHtml(fullName)}" aria-label="${escapeHtml(fullName)}"${pressed === null ? '' : ` aria-pressed="${pressed}"`}><i class="ti ${icon}" aria-hidden="true"></i><span class="tool-label">${label}</span></button>`;
}

// The complete content of the drawer. ctx: own (Set), country, regionName, logos, logoBaseUrl, imageBaseUrl,
// countryNames (Set), key, isFavorite, isSeen, isHidden, inCompare, series (films of the collection, oldest
// first, with this one), similar (films), watched (Set of keys), serviceOf(film), keyOf(film), releaseText,
// favoriteFields (HTML).
export function drawerHtml(film, ctx) {
  const key = ctx.key;
  const name = escapeHtml(film.title);
  const long = film.title.length > 30;
  const action = primaryAction(film, ctx.own, ctx.country, ctx.regionName);
  const badges = statusBadges(film, ctx.own).map(badge => `<p class="status-badge is-${badge.tone}">${escapeHtml(badge.text)}</p>`).join('');
  const alt = alternatives(film, ctx.own, action.service);
  const altKinds = alt.every(item => item.kind !== 'flatrate');
  const altLine = alt.length
    ? `<p class="alt-line">${altKinds ? 'Also free' : 'Also on'}: ${alt.map(item => `<a class="alt-chip" href="${escapeHtml(action.href || watchUrl(film, ctx.country))}" target="_blank" rel="noreferrer">${logoImg(ctx, item.name, 'provider-logo-sm')}${escapeHtml(item.name)} <i class="ti ti-chevron-right" aria-hidden="true"></i></a>`).join('')}</p>`
    : '';
  const backdrop = film.backdrop_path ? `<img class="film-hero-backdrop" src="${ctx.imageBaseUrl.replace('/w500', '/w780')}${escapeHtml(film.backdrop_path)}" alt="">` : '';
  const trailerId = film.trailer_url ? new URL(film.trailer_url).searchParams.get('v') : null;
  const play = trailerId && backdrop ? `<button class="hero-play trailer-link" data-trailer="${escapeHtml(trailerId)}" type="button"><i class="ti ti-player-play-filled" aria-hidden="true"></i> Trailer</button>` : '';
  const trailerFallback = trailerId && !backdrop ? `<p class="film-modal-trailer"><button class="hero-play-inline trailer-link" data-trailer="${escapeHtml(trailerId)}" type="button"><i class="ti ti-player-play-filled" aria-hidden="true"></i> Trailer</button></p>` : '';
  const poster = film.poster_path ? `<img class="film-hero-poster" src="${ctx.imageBaseUrl}${escapeHtml(film.poster_path)}" alt="Poster for ${name}">` : '<span class="film-hero-poster film-hero-nopic" aria-hidden="true"></span>';
  const original = film.original_title && film.original_title !== film.title ? `<p class="film-original-title">${escapeHtml(film.original_title)}</p>` : '';
  const hero = `<div class="film-hero${backdrop ? '' : ' no-backdrop'}">${backdrop}${play}</div><div class="film-hero-head">${poster}<div class="film-hero-text"><h2 class="film-hero-title${long ? ' is-long' : ''}" id="film-hero-title" title="${name}">${name}</h2>${original}<p class="film-modal-meta">${escapeHtml(metaLine(film, ctx.country))}</p></div></div>`;

  const seenName = ctx.isSeen ? 'Not watched after all' : 'Mark as watched';
  const hideName = ctx.isHidden ? 'Bring back' : 'Not now (30 days)';
  const compareName = ctx.inCompare ? 'Remove from comparison' : 'Add to comparison';
  const favName = ctx.isFavorite ? 'Remove favorite' : 'Add to favorites';
  const tools = `<div class="film-modal-toolbar" role="group" aria-label="Actions">${[
    toolButton('modal-favorite', `data-key="${escapeHtml(key)}"`, ctx.isFavorite ? 'ti-heart-filled' : 'ti-heart', 'Favorite', favName, String(ctx.isFavorite)),
    toolButton('modal-compare', `data-key="${escapeHtml(key)}"`, 'ti-layout-columns', 'Compare', compareName, String(ctx.inCompare)),
    toolButton('modal-flag', `data-flag="watched" data-key="${escapeHtml(key)}"`, ctx.isSeen ? 'ti-circle-check-filled' : 'ti-circle-check', 'Seen', seenName, String(ctx.isSeen)),
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

  return `${hero}<div class="film-modal-body">${ratingsHtml(film)}${badges}${mainButton(action)}${altLine}${otherServicesHtml(film, ctx, action)}<div id="film-abroad" class="film-abroad" hidden></div>${tools}${trailerFallback}<div class="film-modal-about"><div class="overview-box${clamp ? ' clamped' : ''}"><p class="film-modal-overview" id="film-overview">${escapeHtml(overview)}</p>${clamp ? '<button class="overview-more" type="button" aria-expanded="false" aria-controls="film-overview">more</button>' : ''}</div>${release}${credits}${collection}${similar}${keywords}${linkChips(film, ctx.country)}</div><div id="modal-favorite-fields" data-key="${escapeHtml(key)}">${ctx.favoriteFields}</div></div>`;
}

const personLink = person => `<a class="person-link" href="/watchlist?q=${encodeURIComponent(person)}">${escapeHtml(person)}</a>`;

// "Start with The Matrix (1999)" when an earlier part of the series is on the watchlist and not watched yet.
function firstUnseen(ctx, key) {
  const index = ctx.series.findIndex(item => ctx.keyOf(item) === key);
  const earlier = ctx.series.slice(0, Math.max(index, 0)).find(item => !ctx.watched.has(ctx.keyOf(item)));
  return earlier ? ` · Start with ${escapeHtml(earlier.title)}${earlier.year ? ` (${numberText(earlier.year)})` : ''}` : '';
}
