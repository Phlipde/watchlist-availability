// Title matches page: list uncertain matches, search TMDB and save a correction.
const config = window.MATCHES_PAGE;
const list = document.getElementById('match-list');
const showAll = document.getElementById('show-all');
const rescan = document.getElementById('rescan');
// After saving, the list is redrawn: keep the focus and the "saved" mark on the same film.
let focusKey = null;
let savedKey = null;

function element(tag, attributes = {}, ...children) {
  const node = document.createElement(tag);
  for (const [name, value] of Object.entries(attributes)) {
    if (value === undefined || value === null || value === false) continue;
    if (name === 'className') node.className = value;
    else if (name.startsWith('on')) node.addEventListener(name.slice(2), value);
    else node.setAttribute(name, value === true ? '' : value);
  }
  children.flat().forEach(child => {
    if (child !== null && child !== undefined && child !== false) node.append(child);
  });
  return node;
}

function show(text, failed = false) {
  const message = document.getElementById('matches-message');
  message.textContent = text;
  message.classList.toggle('text-danger', failed);
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || (response.status >= 500 ? 'The app reported an error. The Status page shows the last scans; reload and try again.' : `The app refused the request (${response.status}). Reload the page and try again.`));
  return data;
}

const withYear = (title, year) => (year ? `${title} (${year})` : title);
const matchUrl = key => `/api/matches/${encodeURIComponent(key)}`;

function poster(path, title) {
  if (!path) return element('div', {className: 'match-poster empty'}, element('i', {className: 'ti ti-movie', 'aria-hidden': 'true'}));
  return element('img', {className: 'match-poster', src: `${config.imageBaseUrl}${path}`, alt: '', loading: 'lazy'});
}

async function save(match, tmdbId, row) {
  show('Saving…');
  try {
    const result = await requestJson(matchUrl(match.film_key), {
      method: 'PUT',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({tmdb_id: tmdbId}),
    });
    show(`Saved: ${withYear(match.title, match.year)} → ${withYear(result.tmdb_title || `TMDB ${result.tmdb_id}`, result.tmdb_year)}.`);
    rescan.hidden = false;
    row.classList.add('match-saved');
    focusKey = savedKey = match.film_key;
    await load();
  } catch (error) {
    show(error.message, true);
  }
}

async function reset(match) {
  try {
    await requestJson(matchUrl(match.film_key), {method: 'DELETE'});
    show(`${match.title} will be looked up again at the next scan.`);
    rescan.hidden = false;
    focusKey = match.film_key;
    await load();
  } catch (error) {
    show(error.message, true);
  }
}

function correctionPanel(match, row) {
  const query = element('input', {className: 'form-control form-control-sm', type: 'search', value: match.title, 'aria-label': 'Title to search'});
  const year = element('input', {className: 'form-control form-control-sm match-year', type: 'number', value: match.year || '', placeholder: 'Year', 'aria-label': 'Year'});
  const results = element('ul', {className: 'candidate-list'});
  const reference = element('input', {className: 'form-control form-control-sm', placeholder: 'TMDB id or themoviedb.org link', 'aria-label': 'TMDB id or link'});

  async function search(event) {
    event?.preventDefault();
    results.replaceChildren(element('li', {className: 'meta'}, 'Searching…'));
    try {
      const params = new URLSearchParams({q: query.value});
      if (year.value) params.set('year', year.value);
      const found = await requestJson(`/api/matches/search?${params}`);
      results.replaceChildren(...(found.length ? found.map(candidate => element('li', {className: 'candidate'},
        poster(candidate.poster_path, candidate.title),
        element('div', {className: 'candidate-text'},
          element('strong', {}, withYear(candidate.title, candidate.year)),
          candidate.original_title && candidate.original_title !== candidate.title ? element('span', {className: 'meta'}, ` · ${candidate.original_title}`) : null,
          element('p', {className: 'candidate-overview'}, candidate.overview || '')),
        element('div', {className: 'candidate-actions'},
          element('a', {className: 'btn btn-sm btn-outline-secondary', href: `https://www.themoviedb.org/movie/${candidate.tmdb_id}`, target: '_blank', rel: 'noopener'}, 'TMDB'),
          element('button', {className: 'btn btn-sm btn-accent', type: 'button', onclick: () => save(match, candidate.tmdb_id, row)},
            candidate.tmdb_id === match.tmdb_id ? 'Keep this' : 'Use this'))))
        : [element('li', {className: 'meta'}, 'No film found. Try another title or the original title.')]));
    } catch (error) {
      results.replaceChildren(element('li', {className: 'text-danger'}, error.message));
    }
  }

  const panel = element('div', {className: 'match-correction'},
    element('form', {className: 'match-search', onsubmit: search}, query, year,
      element('button', {className: 'btn btn-sm btn-outline-secondary', type: 'submit'}, element('i', {className: 'ti ti-search', 'aria-hidden': 'true'}), ' Search TMDB')),
    results,
    element('form', {className: 'match-search', onsubmit: event => { event.preventDefault(); save(match, reference.value, row); }}, reference,
      element('button', {className: 'btn btn-sm btn-outline-secondary', type: 'submit'}, 'Use id')));
  search();
  return panel;
}

function matchRow(match) {
  const row = element('li', {className: 'match-row', 'data-film-key': match.film_key});
  const found = match.tmdb_id
    ? element('a', {href: match.tmdb_url, target: '_blank', rel: 'noopener'}, withYear(match.tmdb_title || `TMDB ${match.tmdb_id}`, match.tmdb_year))
    : element('span', {className: 'meta'}, 'no film');
  const sourceText = {letterboxd: 'from Letterboxd', search: 'title search', manual: 'set by you', missing: 'unknown id'}[match.source] || match.source || '';
  let panel = null;
  const correct = element('button', {className: 'btn btn-sm btn-outline-secondary', type: 'button', onclick: () => {
    if (panel) { panel.remove(); panel = null; return; }
    panel = correctionPanel(match, row);
    row.append(panel);
  }}, element('i', {className: 'ti ti-pencil', 'aria-hidden': 'true'}), ' Correct');
  row.append(
    element('div', {className: 'match-main'},
      poster(match.poster_path, match.title),
      element('div', {className: 'match-text'},
        element('strong', {}, withYear(match.title, match.year)),
        match.letterboxd_url ? element('a', {className: 'meta', href: match.letterboxd_url, target: '_blank', rel: 'noopener'}, ' Letterboxd') : null,
        element('div', {}, 'Matched to: ', found, element('span', {className: 'meta'}, ` · ${sourceText}`)),
        match.reason ? element('span', {className: `pill match-reason ${match.reason === 'not_found' ? 'pill-danger' : 'pill-warn'}`}, match.reason_text) : null),
      element('div', {className: 'match-actions'},
        match.reason && match.tmdb_id ? element('button', {className: 'btn btn-sm btn-outline-secondary', type: 'button', onclick: () => save(match, match.tmdb_id, row)}, element('i', {className: 'ti ti-check', 'aria-hidden': 'true'}), ' Looks right') : null,
        correct,
        match.source === 'manual' ? element('button', {className: 'btn btn-sm btn-outline-secondary', type: 'button', onclick: () => reset(match)}, 'Undo correction') : null)));
  return row;
}

async function load() {
  try {
    const matches = await requestJson(`/api/matches${showAll.checked ? '?all=1' : ''}`);
    list.replaceChildren(...matches.map(matchRow));
    document.getElementById('matches-empty').hidden = matches.length > 0;
    const row = key => key && list.querySelector(`[data-film-key="${CSS.escape(key)}"]`);
    row(savedKey)?.classList.add('match-saved');
    // A film that is no longer uncertain leaves the list: the message says what was saved.
    if (focusKey) (row(focusKey)?.querySelector('button') || document.getElementById('matches-message')).focus();
    focusKey = null;
  } catch (error) {
    show(error.message, true);
  }
}

rescan.addEventListener('click', async () => {
  try {
    await requestJson('/api/scan', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({country: config.country})});
    window.location.href = '/';
  } catch (error) {
    show(error.message, true);
  }
});

showAll.addEventListener('change', load);
load();
