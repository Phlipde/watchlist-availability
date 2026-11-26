// Compare 2 to 4 films: the tick boxes on the posters, the bar at the bottom and the table in a dialog.
import {escapeHtml, numberText} from './ui.js';
import {bestIndexes} from './rendering.js';
import {filmKey} from './filtering.js';

export function createCompare({state, results, imageBaseUrl, showToast, openModal, renderFilms}) {
  // The tick boxes on the posters only show while choosing films to compare.
  // The bar at the bottom appears with the first chosen film; the boxes on the posters show while it is there.
  function setCompareMode(on) {
    document.body.classList.toggle('compare-mode', on);
  }
  function compareFilms() {
    const films = state.films.filter(film => state.compareKeys.has(filmKey(film)));
    if (films.length < 2 || films.length > 4) return showToast('Choose 2 to 4 films to compare.');
    const providers = [...new Set(films.flatMap(film => Object.keys(film.providers || {})))].sort();
    const offerCell = film => Object.entries(film.providers || {}).map(([provider, kinds]) => `${escapeHtml(provider)}: ${escapeHtml(kinds.join(', '))}`).join('<br>') || '-';
    const providerRows = providers.map(provider => `<tr><th>${escapeHtml(provider)}</th>${films.map(film => `<td>${escapeHtml((film.providers?.[provider] || []).join(', ') || '—')}</td>`).join('')}</tr>`).join('');
    // The best value of a row is marked (rating: highest, runtime: shortest, own services: most).
    const row = (label, values, show, prefer) => {
      const best = prefer ? bestIndexes(values, prefer) : [];
      return `<tr><th>${label}</th>${values.map((value, index) => `<td${best.includes(index) ? ' class="best"' : ''}>${show(value)}${best.includes(index) ? '<span class="visually-hidden"> (best)</span>' : ''}</td>`).join('')}</tr>`;
    };
    const ownCount = film => Object.keys(film.providers || {}).filter(name => state.selected.has(name)).length;
    document.getElementById('compare-table').innerHTML = `<thead><tr><th>Metric</th>${films.map(film => `<th>${escapeHtml(film.title)}</th>`).join('')}</tr></thead><tbody>${row('Year', films.map(film => film.year), value => numberText(value, '-'))}${row('Letterboxd', films.map(film => film.letterboxd_rating), value => (numberText(value) ? Number(value).toFixed(1) : '-'), 'high')}${row('TMDB', films.map(film => film.rating), value => (numberText(value) ? Number(value).toFixed(1) : '-'), 'high')}${row('Runtime', films.map(film => film.runtime), value => (numberText(value) ? `${numberText(value)} min` : '-'), 'low')}${row('On your services', films.map(ownCount), value => String(value), 'high')}<tr><th>Genres</th>${films.map(film => `<td>${escapeHtml((film.genres || []).join(', ') || '-')}</td>`).join('')}</tr><tr><th>Offers</th>${films.map(film => `<td>${offerCell(film)}</td>`).join('')}</tr>${providerRows}</tbody>`;
    openModal('compare-modal');
  }
  function updateCompareButton() {
    const count = state.compareKeys.size;
    setCompareMode(count > 0);
    const bar = document.getElementById('compare-bar');
    bar.hidden = count === 0;
    const countText = document.getElementById('compare-count');
    countText.textContent = count === 1 ? 'Pick one more' : count > 4 ? `${count} chosen: at most 4` : `${count} to compare`;
    countText.dataset.hint = String(count < 2 || count > 4);
    document.getElementById('compare-thumbs').innerHTML = state.films.filter(film => state.compareKeys.has(filmKey(film)) && film.poster_path).map(film => `<img src="${imageBaseUrl.replace("/w500", "/w92")}${escapeHtml(film.poster_path)}" alt="${escapeHtml(film.title)}">`).join('');
    document.getElementById('compare-go').disabled = count < 2 || count > 4;
  }
  function setCompared(key, checked) {
    if (checked) state.compareKeys.add(key);
    else state.compareKeys.delete(key);
    document.querySelectorAll(`.film[data-key="${CSS.escape(key)}"] .comparison-check`).forEach(check => { check.checked = checked; });
    updateCompareButton();
  }
  document.getElementById('clear-compare').addEventListener('click', () => {
    [...state.compareKeys].forEach(key => setCompared(key, false));
    setCompareMode(false);
    bootstrap.Modal.getInstance(document.getElementById('compare-modal'))?.hide();
  });
  results.addEventListener('change', event => {
    const check = event.target.closest('.comparison-check');
    if (check) setCompared(check.closest('.film').dataset.key, check.checked);
  });
  document.getElementById('compare-go').addEventListener('click', compareFilms);
  document.getElementById('compare-bar-clear').addEventListener('click', () => { [...state.compareKeys].forEach(key => setCompared(key, false)); renderFilms(); });
  updateCompareButton();
  return {setCompared};
}
