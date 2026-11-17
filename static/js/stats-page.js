import {escapeHtml} from './ui.js';
import {watchlistStats} from './statistics.js';

const config = window.STATS_PAGE;
const root = document.getElementById('stats-root');
const languageName = new Intl.DisplayNames(['en'], {type: 'language'});
const countryName = new Intl.DisplayNames(['en'], {type: 'region'});
const named = (names, code) => { try { return names.of(code) || code; } catch { return code; } };
const one = (value, digits = 1) => (value === null ? '–' : value.toFixed(digits));
const percent = (part, whole) => (whole ? Math.round(part / whole * 100) : 0);

function tile(value, label, note = '') {
  return `<div class="stat-tile"><strong>${escapeHtml(String(value))}</strong><span>${escapeHtml(label)}</span>${note ? `<small>${escapeHtml(note)}</small>` : ''}</div>`;
}

// One series per list: one colour, the value written next to each bar, the share in the tooltip.
function bars(rows, total, {limit = 10, nameOf = name => name} = {}) {
  if (!rows.length) return '<p class="empty">No data yet.</p>';
  const max = Math.max(...rows.map(([, count]) => count), 1);
  const row = ([name, count]) => {
    const label = escapeHtml(nameOf(name));
    return `<li title="${label}: ${count} of ${total} films (${percent(count, total)}%)"><span class="bar-label">${label}</span><span class="bar-track" aria-hidden="true"><span class="bar" style="width:${Math.max(count / max * 100, count ? 2 : 0)}%"></span></span><span class="bar-value">${count}</span></li>`;
  };
  const shown = rows.slice(0, limit).map(row).join('');
  const rest = rows.slice(limit);
  return `<ol class="bars">${shown}</ol>${rest.length ? `<details class="bars-more"><summary>Show ${rest.length} more</summary><ol class="bars">${rest.map(row).join('')}</ol></details>` : ''}`;
}

function card(title, body, note = '') {
  return `<section class="stats-card"><h2>${escapeHtml(title)}</h2>${note ? `<p class="hint">${escapeHtml(note)}</p>` : ''}${body}</section>`;
}

function filmList(films, extra) {
  if (!films.length) return '<p class="empty">None.</p>';
  return `<ol class="stats-films">${films.map(film => `<li><a href="/?film=${encodeURIComponent(film.key)}">${escapeHtml(film.title)}</a>${film.year ? ` <span class="muted">(${escapeHtml(String(film.year))})</span>` : ''} · ${escapeHtml(extra(film))}</li>`).join('')}</ol>`;
}

function servicesTable(services, total) {
  const max = Math.max(...services.map(service => service.films), 1);
  const row = service => `<tr${service.own ? ' class="own-service"' : ''}><th scope="row">${escapeHtml(service.name)}${service.own ? ' <span class="pill pill-ok">Yours</span>' : ''}</th><td class="num"><span class="bar-track inline" aria-hidden="true"><span class="bar" style="width:${service.films / max * 100}%"></span></span>${service.films} <span class="muted">(${percent(service.films, total)}%)</span></td><td class="num">${service.exclusive}</td><td class="num">${service.hours}</td><td class="num">${service.free}</td><td class="num">${service.ads}</td><td class="num">${service.subscription}</td><td class="num">${service.rent}</td></tr>`;
  const head = '<thead><tr><th scope="col">Service</th><th scope="col">Films</th><th scope="col" title="Films no other service shows without paying per film">Only here</th><th scope="col">Hours</th><th scope="col">Free</th><th scope="col">Ads</th><th scope="col">Subscr.</th><th scope="col">Rent</th></tr></thead>';
  const table = list => `<div class="table-scroll"><table class="status-table stats-table">${head}<tbody>${list.map(row).join('')}</tbody></table></div>`;
  return table(services.slice(0, 15)) + (services.length > 15 ? `<details class="bars-more"><summary>Show all ${services.length} services</summary>${table(services.slice(15))}</details>` : '');
}

function render(stats, scan) {
  const o = stats.overview;
  const day = seconds => new Date(seconds * 1000).toLocaleDateString([], {dateStyle: 'medium'});
  document.getElementById('stats-meta').textContent = `Watchlist scan of ${day(scan.created)} · ${config.country}`;
  const tiles = [
    tile(o.total, 'films on the watchlist'),
    tile(o.available, 'available somewhere', `${percent(o.available, o.total)}%`),
    tile(o.onSubscriptions, 'on your subscriptions', `${percent(o.onSubscriptions, o.total)}% · ${o.hoursOnSubscriptions} h`),
    tile(o.free, 'free or with ads'),
    tile(o.subscription, 'in a subscription'),
    tile(o.rentOnly, 'rent only'),
    tile(o.unavailable, 'not available'),
    tile(o.comingSoon, 'coming soon'),
    tile(`${o.hoursAvailable} h`, 'to watch in total'),
    tile(o.averageRuntime === null ? '–' : `${Math.round(o.averageRuntime)} min`, 'average runtime'),
    tile(one(o.averageLetterboxd, 2), 'average Letterboxd'),
    tile(one(o.averageTmdb), 'average TMDB'),
    tile(o.oldestYear && o.newestYear ? `${o.oldestYear}–${o.newestYear}` : '–', 'release years'),
    tile(o.favorites, 'favorites', `${o.watched} watched`),
    tile(stats.changes.added30, 'newly available', 'last 30 days'),
    tile(stats.changes.removed30, 'gone from a service', 'last 30 days'),
  ].join('');
  const weeks = stats.changes.weeks.map(week => `<tr><th scope="row">${day(week.start)}</th><td class="num">${week.added}</td><td class="num">${week.removed}</td></tr>`).join('');
  root.innerHTML = `<div class="stat-tiles">${tiles}</div>
    <div class="stats-grid">
      ${card('Your subscriptions', stats.ownServices.length ? `<div class="table-scroll"><table class="status-table stats-table"><thead><tr><th scope="col">Service</th><th scope="col">Films</th><th scope="col" title="Films none of your other subscriptions has">Only in this one</th></tr></thead><tbody>${stats.ownServices.map(service => `<tr><th scope="row">${escapeHtml(service.name)}</th><td class="num">${service.films}</td><td class="num">${service.onlyHere}</td></tr>`).join('')}</tbody></table></div>` : '<p class="empty">No subscriptions saved. Set them on the <a href="/subscriptions">Subscriptions</a> page.</p>', '“Only in this one” is what you would lose by cancelling it.')}
      ${card('Offer types', bars(stats.offerTypes, o.available), 'Available films; a film can have several.')}
      ${card('Genres', bars(stats.genres.map(genre => [genre.name, genre.total]), o.total, {limit: 12}))}
      ${card('Decades', bars(stats.decades, o.total, {limit: 20}))}
      ${card('Runtime', bars(stats.runtimes, o.total))}
      ${card('Letterboxd rating', bars(stats.letterboxdRatings, o.total))}
      ${card('TMDB rating', bars(stats.tmdbRatings, o.total))}
      ${card('Original language', bars(stats.languages, o.total, {nameOf: code => named(languageName, code)}))}
      ${card('Country of origin', bars(stats.countries, o.total, {nameOf: code => named(countryName, code)}))}
      ${card('Age rating', bars(stats.ageRatings, o.total), `Ratings for ${config.country}.`)}
      ${card('Directors', bars(stats.directors, o.total), 'With more than one film on the watchlist.')}
      ${card('Actors', bars(stats.actors, o.total), 'With more than one film on the watchlist.')}
      ${card('Film series', bars(stats.collections, o.total), 'With more than one film on the watchlist.')}
      ${card('Keywords', bars(stats.keywords, o.total, {limit: 12}))}
      ${card('Changes per service', bars(stats.changes.byService, stats.changes.added30 + stats.changes.removed30), 'New and gone, last 30 days.')}
      ${card('Changes per week', `<div class="table-scroll"><table class="status-table stats-table"><thead><tr><th scope="col">Week from</th><th scope="col">New</th><th scope="col">Gone</th></tr></thead><tbody>${weeks}</tbody></table></div>`)}
      ${card('Waiting longest', filmList(stats.longestWaiting, film => `#${film.watchlist_position} on the watchlist`), 'On your subscriptions, longest on the watchlist.')}
      ${card('Best rated on your subscriptions', filmList(stats.bestOnSubscriptions, film => (film.letterboxd_rating ? `★ ${Number(film.letterboxd_rating).toFixed(1)}` : `TMDB ${Number(film.rating || 0).toFixed(1)}`)))}
    </div>
    <h2 class="h4 mt-4">Services</h2>
    <p class="hint">Every service with at least one film from the watchlist. “Only here” counts films no other service shows without paying per film.</p>
    ${servicesTable(stats.services, o.available)}`;
  root.setAttribute('aria-busy', 'false');
}

async function load() {
  try {
    const [scan, favorites] = await Promise.all([
      fetch(`/api/latest?country=${encodeURIComponent(config.country)}`).then(response => response.json()),
      fetch('/api/favorites').then(response => (response.ok ? response.json() : [])),
    ]);
    if (!scan.available) {
      root.innerHTML = '<p class="empty">No scan yet. Open the <a href="/">Watchlist</a> to run the first one.</p>';
      root.setAttribute('aria-busy', 'false');
      return;
    }
    render(watchlistStats(scan, {subscriptions: config.subscriptions, favorites}), scan);
  } catch {
    root.innerHTML = '<p class="error">The statistics could not be loaded. Reload the page to try again.</p>';
    root.setAttribute('aria-busy', 'false');
  }
}
load();
