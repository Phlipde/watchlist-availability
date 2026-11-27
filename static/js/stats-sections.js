// The sections of the stats page, one function each. They only draw what computeStats returned; nothing is calculated here.
import {escapeHtml as esc} from './ui.js';
import {AVAILABILITY_LABEL} from './statistics.js';

const number = value => Number(value).toLocaleString('en');
const percent = (part, whole) => (whole ? Math.round(part / whole * 100) : 0);
const plural = (count, word) => `${number(count)} ${word}${count === 1 ? '' : 's'}`;
export const watchlistHref = params => `/watchlist?${new URLSearchParams(params)}`;
const posterOf = (base, path) => (path ? `<img src="${esc(base.replace('/w500', '/w92'))}${esc(path)}" alt="" width="40" height="60" loading="lazy">` : '<span class="film-row-poster" aria-hidden="true"></span>');
const section = (title, hint, body, id = '') => `<section class="stats-section"${id ? ` id="${id}"` : ''}><h2>${esc(title)}</h2>${hint ? `<p class="hint">${hint}</p>` : ''}${body}</section>`;

// ---- 3.1 what can I watch now -------------------------------------------------------------------

function tile(value, label, {sub = '', href = ''} = {}) {
  const inner = `<strong>${esc(String(value))}</strong><span>${esc(label)}</span>${sub ? `<small>${esc(sub)}</small>` : ''}`;
  return href ? `<a class="stat-tile" href="${esc(href)}">${inner}</a>` : `<div class="stat-tile">${inner}</div>`;
}

export function head(stats) {
  const o = stats.overview;
  const free = o.availability.free + o.availability.ads;
  const tip = stats.rotationSuggestion;
  // One base set on every page (base.py, baseCounts): released films; coming soon is counted apart.
  const rows = stats.availabilityBreakdown.filter(item => item.films && item.kind !== 'coming_soon');
  const watchlist = o.total - o.comingSoon;
  const tiles = [
    tile(number(o.availability.own_subscription), 'films on your services (incl. your free ones)', {sub: `${number(stats.availabilityBreakdown[0].hours)} h`, href: watchlistHref({availability: 'own_subscription'})}),
    tile(number(free), 'free elsewhere (not your services)', {sub: `${number(stats.availabilityBreakdown[1].hours + stats.availabilityBreakdown[2].hours)} h`, href: watchlistHref({availability: 'free,ads'})}),
    tip ? tile(number(tip.films), `more films with ${tip.group}`, {sub: 'a subscription you do not have', href: `?svcq=${encodeURIComponent(tip.group)}&svctype=all#services-section`})
      : tile('–', 'more films with another subscription', {sub: 'nothing to add'}),
    tile(number(watchlist), 'films on the watchlist', {sub: `${number(rows.reduce((sum, item) => sum + item.hours, 0))} h in total${o.comingSoon ? ` · +${number(o.comingSoon)} coming soon` : ''}`, href: '/watchlist'}),
  ].join('');
  const segments = rows.map(item => `<a class="avail-seg avail-${item.kind}" style="flex:${item.films}" href="${esc(watchlistHref({availability: item.kind}))}" title="${esc(AVAILABILITY_LABEL[item.kind])}: ${item.films} films (${percent(item.films, watchlist)}%)" aria-label="${esc(AVAILABILITY_LABEL[item.kind])}: ${item.films} films"></a>`).join('');
  const legend = rows.map(item => `<li><a href="${esc(watchlistHref({availability: item.kind}))}"><i class="swatch avail-${item.kind}" aria-hidden="true"></i>${esc(AVAILABILITY_LABEL[item.kind])} <strong>${number(item.films)}</strong> <span class="muted">${percent(item.films, watchlist)}%</span></a></li>`).join('');
  const foot = stats.withoutRuntime ? `<p class="hint">${plural(stats.withoutRuntime, 'film')} without a runtime are counted, but not in the hours.</p>` : '';
  return `<div class="stat-tiles">${tiles}</div>
    <div class="avail" role="group" aria-label="Where the films of your watchlist can be watched">
      <div class="avail-bar">${segments}</div><ul class="avail-legend">${legend}</ul></div>${foot}`;
}

// ---- 3.2 are my subscriptions worth it ------------------------------------------------------------

const euro = value => `${value.toFixed(2)} €`;
const serviceLink = group => `?svcq=${encodeURIComponent(group)}&svctype=all#services-section`;

function valueRow({group, films, exclusive, text, badge = '', tone = 'own', max}) {
  const wide = Math.max(films / max * 100, films ? 2 : 0);
  return `<li class="val-row"><a href="${esc(serviceLink(group))}"><span class="val-name">${esc(group)}</span>
    <span class="val-bar" aria-hidden="true"><span class="val-${tone}" style="width:${wide}%"><span class="val-strong" style="width:${films ? exclusive / films * 100 : 0}%"></span></span></span>
    <span class="val-text">${text}</span></a>${badge}</li>`;
}

export function subscriptions(stats, {subscriptions: owned, prices}) {
  const own = stats.serviceValue.filter(item => item.own).sort((a, b) => b.onlyHere - a.onlyHere || b.films - a.films);
  const ownMax = Math.max(...own.map(item => item.films), 1);
  const rows = own.map(item => valueRow({
    group: item.group, films: item.films, exclusive: item.onlyHere, max: ownMax,
    text: `<strong>${number(item.onlyHere)}</strong> only here · ${number(item.films)} films${item.costPerLostFilm !== null ? ` · ${euro(item.costPerLostFilm)} per film you would lose` : ''}`,
    badge: item.price && item.films && !item.onlyHere ? '<span class="pill pill-warn">Cancel candidate</span>' : '',
  })).join('');
  const seen = new Set(own.map(item => item.group));
  const empty = [...new Set(owned)].filter(name => ![...seen].some(group => group === name || stats.serviceValue.find(item => item.group === group)?.plans.includes(name))).sort();
  const none = empty.length ? `<p class="hint">No films from your watchlist: ${esc(empty.join(', '))}.</p>` : '';
  const noPrices = own.length && !Object.keys(prices).length ? '<p class="hint">Set your monthly prices on <a href="/subscriptions">Subscriptions</a> to see the cost per film.</p>' : '';

  const gain = stats.gainIfSubscribed.slice(0, 8);
  const gainMax = Math.max(...gain.map(item => item.films), 1);
  const tip = stats.rotationSuggestion;
  const tipCard = tip ? `<p class="stats-tip"><strong>Tip:</strong> one month of ${esc(tip.group)} would add ${plural(tip.films, 'film')} (${number(tip.hours)} h), ${number(tip.onlyThere)} of them nowhere else.</p>` : '';
  const more = gain.map(item => valueRow({
    group: item.group, films: item.films, exclusive: item.onlyThere, max: gainMax, tone: 'other',
    text: `would add <strong>${number(item.films)}</strong> films · ${number(item.hours)} h · ${number(item.onlyThere)} nowhere else`,
  })).join('');

  return section('Are my subscriptions worth it?', 'The bright part of a bar is what you would lose by cancelling ("only here", as on Subscriptions): films none of your other services has and no service shows for free.',
    `${own.length ? `<ul class="val-list">${rows}</ul>` : '<p class="empty">No subscriptions saved. Set them on the <a href="/subscriptions">Subscriptions</a> page.</p>'}${none}${noPrices}
    ${gain.length ? `<h3 class="stats-sub">Subscriptions you do not have</h3>${tipCard}<ul class="val-list val-muted">${more}</ul>` : ''}`);
}

// ---- 3.3 what is worth watching next ----------------------------------------------------------------

function filmRows(films, noteOf, base) {
  if (!films.length) return '<p class="empty">Nothing yet.</p>';
  return `<ol class="film-rows">${films.slice(0, 8).map(film => `<li><a href="/watchlist?film=${encodeURIComponent(film.key)}">${posterOf(base, film.poster_path)}<span class="film-row-text"><span class="film-row-title">${esc(film.title)}${film.year ? ` <span class="muted">(${esc(String(film.year))})</span>` : ''}</span><span class="muted">${esc(noteOf(film))}</span></span></a></li>`).join('')}</ol>`;
}
const ratingNote = film => [film.letterboxd_rating ? `★ ${Number(film.letterboxd_rating).toFixed(1)}` : '', film.runtime ? `${Math.floor(film.runtime / 60)} h ${String(film.runtime % 60).padStart(2, '0')}` : ''].filter(Boolean).join(' · ');

export function nextUp(stats, {imageBaseUrl}) {
  const series = stats.collectionsPlanner.slice(0, 8).map(item => `<li><a href="${esc(watchlistHref({collection: item.name}))}"><span class="film-row-text"><span class="film-row-title">${esc(item.name)}</span><span class="muted">${item.films} films · ${number(item.hours)} h · ${item.inOwn === item.films ? 'all' : `${item.inOwn} of ${item.films}`} on your subscriptions</span></span></a></li>`).join('');
  const list = (title, body, href) => `<div class="stats-list"><h3 class="stats-sub">${esc(title)}</h3>${body}${href ? `<a class="stats-all" href="${esc(href)}">Show all</a>` : ''}</div>`;
  return section('What is worth watching next?', '',
    `<div class="stats-lists">
      ${list('Best rated on your subscriptions', filmRows(stats.bestOnOwnSubs, ratingNote, imageBaseUrl), watchlistHref({availability: 'own_subscription', sort: 'letterboxd'}))}
      ${list('Waiting the longest', filmRows(stats.waitingLongest, film => `#${film.watchlist_position} on your Letterboxd watchlist`, imageBaseUrl), watchlistHref({availability: 'own_subscription', sort: 'oldest'}))}
      ${list('Worth renting', filmRows(stats.worthRenting, ratingNote, imageBaseUrl), watchlistHref({availability: 'rent_buy', rating: 'lb:4', sort: 'letterboxd'}))}
      ${list('Film series', series ? `<ol class="film-rows">${series}</ol>` : '<p class="empty">No series with two films.</p>', '')}
    </div>`);
}

// ---- 3.4 what does my list look like ------------------------------------------------------------------

// One series, one colour; the value is written next to the bar. With hrefOf a row opens the watchlist for it.
function bars(rows, total, {limit = 8, nameOf = name => name, hrefOf = null, noun = 'films'} = {}) {
  if (!rows.length) return '<p class="empty">No data yet.</p>';
  const max = Math.max(...rows.map(([, count]) => count), 1);
  const row = ([name, count]) => {
    const label = esc(nameOf(name));
    const inner = `<span class="bar-label">${label}</span><span class="bar-track" aria-hidden="true"><span class="bar" style="width:${Math.max(count / max * 100, count ? 2 : 0)}%"></span></span><span class="bar-value">${number(count)}</span>`;
    return `<li title="${label}: ${count} of ${total} ${noun} (${percent(count, total)}%)">${hrefOf ? `<a href="${esc(hrefOf(name))}">${inner}</a>` : inner}</li>`;
  };
  const rest = rows.slice(limit);
  return `<ol class="bars">${rows.slice(0, limit).map(row).join('')}</ol>${rest.length ? `<details class="bars-more"><summary>Show ${rest.length} more</summary><ol class="bars">${rest.map(row).join('')}</ol></details>` : ''}`;
}

function histogram({bins, average}, {unit, hrefOf}) {
  const peak = Math.max(...bins.map(bin => bin.count), 1);
  const middle = bins.find(bin => average !== null && average >= bin.from && average < bin.to);
  const columns = bins.map(bin => `<li${bin === middle ? ' class="is-average"' : ''}><a href="${esc(hrefOf(bin))}" title="${esc(bin.label)}: ${bin.count} films"><span class="histo-bar" style="height:${bin.count / peak * 100}%"></span><span class="histo-label" aria-hidden="true">${esc(bin.label.replace(' min', '').replace('Under ', '<').split('–')[0].replace(/(\.\d)0$/, '$1'))}</span><span class="visually-hidden">${esc(bin.label)}: ${bin.count} films</span></a></li>`).join('');
  return `<p class="hint">${average === null ? 'No data.' : `Average ${unit(average)}`}</p><ol class="histo${bins.length > 8 ? ' is-dense' : ''}">${columns}</ol>`;
}

const sentence = (rows, total, nameOf) => {
  if (!rows.length) return '<p class="empty">No data yet.</p>';
  const [[first, count], ...rest] = rows;
  const named = rest.slice(0, 4).map(([name, n]) => `${esc(nameOf(name))} (${n})`).join(', ');
  const all = rest.length > 4 ? `<details class="bars-more"><summary>All ${rows.length}</summary><p>${rows.map(([name, n]) => `${esc(nameOf(name))} (${n})`).join(', ')}</p></details>` : '';
  return `<p class="stats-sentence"><strong>${percent(count, total)}%</strong> ${esc(nameOf(first))}${named ? `, also ${named}` : ''}.</p>${all}`;
};

export function distribution(stats, {nameOfLanguage, nameOfCountry, ageNote}) {
  const o = stats.overview;
  const card = (title, body, note = '') => `<div class="stats-card"><h3>${esc(title)}</h3>${note ? `<p class="hint">${note}</p>` : ''}${body}</div>`;
  const decadeNote = o.unknownYears ? `${plural(o.unknownYears, 'film')} without a confirmed release year are left out.` : '';
  const keywords = stats.keywords.slice(0, 15);
  const gaps = list => list.map(item => `<li><a href="/watchlist?film=${encodeURIComponent(item.film.key)}">${esc(item.film.title)}</a> <span class="muted">★ ${Number(item.film.letterboxd_rating).toFixed(1)} · TMDB ${Number(item.film.rating).toFixed(1)}</span></li>`).join('');
  // The tiles count released films; these charts count every film on the list, coming soon included.
  const base = `All ${number(o.total)} films on the list${o.comingSoon ? `, the ${number(o.comingSoon)} coming soon included` : ''}. Click a bar to open those films.`;
  return section('What does my list look like?', base,
    `<div class="stats-grid">
      ${card('Genres', bars(stats.genres.map(genre => [genre.name, genre.total]), o.total, {hrefOf: name => watchlistHref({genre: name})}), 'A film can have several genres.')}
      ${card('Decades', bars(stats.decades, o.total, {limit: 20, hrefOf: name => watchlistHref({from: String(name).slice(0, 4), to: Number(String(name).slice(0, 4)) + 9})}), decadeNote)}
      ${card('Runtime', histogram(stats.runtimeHistogram, {unit: value => `${Math.round(value)} min`, hrefOf: bin => watchlistHref({...(bin.from ? {runtimeMin: bin.from} : {}), ...(Number.isFinite(bin.to) ? {max: bin.to - 1} : {})})}))}
      ${card('Letterboxd rating', histogram(stats.ratingHistogram, {unit: value => value.toFixed(2), hrefOf: bin => watchlistHref({rating: `lb:${bin.from}`})}), stats.withoutRating ? `${plural(stats.withoutRating, 'film')} without a rating are not counted.` : '')}
      ${card('Age rating', bars(stats.ageRatings, o.total, {hrefOf: name => watchlistHref({ages: name})}), ageNote)}
      ${card('Language and country', `${sentence(stats.languages, o.total, nameOfLanguage)}${sentence(stats.countries, o.total, nameOfCountry)}`)}
      ${card('Critics against crowd', `<p class="hint">Letterboxd compared with TMDB, both out of 10.</p><h4 class="stats-sub">Letterboxd likes more</h4><ul class="plain-list">${gaps(stats.ratingGap.positive)}</ul><h4 class="stats-sub">TMDB likes more</h4><ul class="plain-list">${gaps(stats.ratingGap.negative)}</ul>`)}
    </div>
    ${keywords.length ? `<details class="bars-more"><summary>Keywords</summary><ul class="tag-cloud">${keywords.map(([word, count]) => `<li><a href="${esc(watchlistHref({keyword: word}))}">${esc(word)} <span class="muted">${count}</span></a></li>`).join('')}</ul></details>` : ''}`);
}

// ---- 3.5 who and what ---------------------------------------------------------------------------------------

const PEOPLE = [['directors', 'Directors', 'person'], ['actors', 'Actors', 'person'], ['collections', 'Series', 'collection']];

export function people(stats) {
  return section('Who and what?', 'Only names with more than one film on the watchlist.',
    `<div class="tabs-small" role="tablist" aria-label="People and series">${PEOPLE.map(([key, label], index) => `<button type="button" role="tab" id="people-tab-${key}" aria-selected="${index === 0}" aria-controls="people-list" tabindex="${index === 0 ? 0 : -1}" data-people="${key}">${label}</button>`).join('')}</div>
    <input class="form-control" id="people-q" type="search" placeholder="Search in this list…" aria-label="Search in this list">
    <div id="people-list" role="tabpanel" aria-live="polite"></div><button class="btn btn-sm btn-outline-secondary" id="people-more" type="button" hidden>Show 20 more</button>`, 'people');
}

// Tabs, search and "show more" of the people section. Returns nothing; it only wires the elements above.
export function wirePeople(stats, root) {
  const state = {key: 'directors', shown: 10, q: ''};
  const draw = () => {
    const [, , param] = PEOPLE.find(([key]) => key === state.key);
    const needle = state.q.trim().toLowerCase();
    const found = stats[state.key].filter(([name]) => !needle || String(name).toLowerCase().includes(needle));
    root.querySelector('#people-list').innerHTML = found.length
      ? `<ol class="bars">${found.slice(0, state.shown).map(([name, count]) => `<li><a href="${esc(watchlistHref({[param]: name}))}"><span class="bar-label">${esc(name)}</span><span class="bar-track" aria-hidden="true"><span class="bar" style="width:${count / found[0][1] * 100}%"></span></span><span class="bar-value">${count}</span></a></li>`).join('')}</ol>`
      : '<p class="empty">No name matches.</p>';
    root.querySelector('#people-more').hidden = found.length <= state.shown;
    root.querySelectorAll('[data-people]').forEach(tab => {
      tab.setAttribute('aria-selected', String(tab.dataset.people === state.key));
      tab.tabIndex = tab.dataset.people === state.key ? 0 : -1;
    });
    root.querySelector('#people-list').setAttribute('aria-labelledby', `people-tab-${state.key}`);
  };
  root.querySelector('.tabs-small').addEventListener('click', event => {
    const tab = event.target.closest('[data-people]');
    if (tab) { Object.assign(state, {key: tab.dataset.people, shown: 10}); draw(); }
  });
  // Arrow keys move between the tabs, as in any tab list.
  root.querySelector('.tabs-small').addEventListener('keydown', event => {
    const step = {ArrowRight: 1, ArrowLeft: -1}[event.key];
    if (!step) return;
    const tabs = [...root.querySelectorAll('[data-people]')];
    const next = tabs[(tabs.findIndex(tab => tab.dataset.people === state.key) + step + tabs.length) % tabs.length];
    Object.assign(state, {key: next.dataset.people, shown: 10});
    draw();
    next.focus();
    event.preventDefault();
  });
  root.querySelector('#people-q').addEventListener('input', event => { Object.assign(state, {q: event.target.value, shown: 10}); draw(); });
  root.querySelector('#people-more').addEventListener('click', () => { state.shown += 20; draw(); });
  draw();
}

// ---- 3.6 what has changed ------------------------------------------------------------------------------------

export function changes(stats, now) {
  const c = stats.changes;
  const day = seconds => new Date(seconds * 1000).toLocaleDateString([], {dateStyle: 'medium'});
  if (!c.added30 && !c.removed30 && !c.weeks.some(week => week.added || week.removed) && !stats.recentChanges.length) {
    return section('What has changed?', '', '<p class="empty">No changes recorded yet. After the next scans you will see here which films are new on your services or gone from them. A film counts as gone only after two scans in a row without it.</p>');
  }
  const peak = Math.max(...c.weeks.flatMap(week => [week.added, week.removed]), 1);
  const weeks = [...c.weeks].reverse().map(week => `<li title="Week from ${day(week.start)}: ${week.added} new, ${week.removed} gone"><span class="wk-up" style="height:${week.added / peak * 100}%"></span><span class="wk-down" style="height:${week.removed / peak * 100}%"></span><span class="visually-hidden">Week from ${day(week.start)}: ${week.added} new, ${week.removed} gone</span></li>`).join('');
  const events = stats.recentChanges.map(change => `<li><a href="/watchlist?film=${encodeURIComponent(change.film_key)}">${esc(change.title || change.film_key)}</a> <span class="muted">${change.change === 'added' ? 'new on' : 'gone from'} ${esc(change.provider)} · ${day(change.created)}</span></li>`).join('');
  return section('What has changed?', 'The last 30 days.',
    `<div class="stat-tiles stat-tiles-two">${tile(number(c.added30), 'new on a service', {href: watchlistHref({changes: 'added'})})}${tile(number(c.removed30), 'gone from a service', {href: watchlistHref({changes: 'removed'})})}</div>
    <ol class="weeks" aria-label="New above, gone below, per week">${weeks}</ol>
    ${events ? `<ul class="plain-list">${events}</ul>` : ''}`, 'changes');
}
