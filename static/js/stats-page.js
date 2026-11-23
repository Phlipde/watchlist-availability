import {computeStats} from './stats-compute.js';
import {mountServiceTable} from './service-table-view.js';
import {changes, distribution, head, nextUp, people, subscriptions, wirePeople} from './stats-sections.js';

const config = window.STATS_PAGE;
const root = document.getElementById('stats-root');
const languageName = new Intl.DisplayNames(['en'], {type: 'language'});
const countryName = new Intl.DisplayNames(['en'], {type: 'region'});
const named = (names, code) => { try { return names.of(code) || code; } catch { return code; } };
const WEEK = 7 * 24 * 3600;

function render(stats, scan) {
  const day = seconds => new Date(seconds * 1000).toLocaleDateString([], {dateStyle: 'medium'});
  document.getElementById('stats-meta').textContent = `Watchlist scan of ${day(scan.created)} · ${config.country}`;
  const old = Date.now() / 1000 - scan.created > WEEK
    ? `<p class="state-note">The data is from ${day(scan.created)}. Open the <a href="/watchlist">Watchlist</a> to scan again.</p>` : '';
  const ageNote = `Ratings for ${config.country}. A film can have only one.`;
  root.innerHTML = `${old}
    <section class="stats-section"><h2>What can I watch now?</h2>${head(stats)}</section>
    ${subscriptions(stats, config)}
    ${nextUp(stats, config)}
    ${distribution(stats, {nameOfLanguage: code => named(languageName, code), nameOfCountry: code => named(countryName, code), ageNote})}
    ${people(stats)}
    ${changes(stats)}
    <section class="stats-section" id="services-section"></section>`;
  wirePeople(stats, root.querySelector('#people'));
  mountServiceTable(document.getElementById('services-section'), stats.serviceValue, {total: stats.overview.total, imageBaseUrl: config.imageBaseUrl});
  root.setAttribute('aria-busy', 'false');
  // A link like ?svcq=Disney%2B#services-section scrolls once the table exists.
  if (location.hash) document.getElementById(location.hash.slice(1))?.scrollIntoView();
}

async function load() {
  try {
    const [scan, favorites] = await Promise.all([
      fetch(`/api/latest?country=${encodeURIComponent(config.country)}`).then(response => response.json()),
      fetch('/api/favorites').then(response => (response.ok ? response.json() : [])),
    ]);
    if (!scan.available) {
      root.innerHTML = '<p class="empty">No scan yet. Open the <a href="/watchlist">Watchlist</a> to run the first one.</p>';
      root.setAttribute('aria-busy', 'false');
      return;
    }
    render(computeStats(scan, {subscriptions: config.subscriptions, prices: config.prices, favorites}), scan);
  } catch {
    root.innerHTML = '<p class="error">The statistics could not be loaded. Reload the page to try again.</p>';
    root.setAttribute('aria-busy', 'false');
  }
}
load();
