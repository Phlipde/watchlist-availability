export function selectedProviders(inputs) {
  return new Set([...inputs].filter(input => input.checked).map(input => input.value));
}

// Reads the filter controls into a plain object for filtering.js.
export function readFilters(doc, favoritesOnly) {
  const value = id => doc.getElementById(id).value;
  // "Year from 2020, to 2000" means the same range as the other way round.
  const years = [Number(value('year-from')) || 0, Number(value('year-to')) || 9999].sort((a, b) => a - b);
  return {
    query: value('film-search').toLowerCase().trim(),
    availability: value('availability-filter'),
    kind: value('kind-filter'),
    minRating: Number(value('min-rating')) || 0,
    minVotes: Number(value('min-votes')) || 0,
    genre: value('genre-filter'),
    keyword: value('keyword-filter'),
    runtime: value('runtime-filter'),
    mode: value('match-mode'),
    yearFrom: years[0],
    yearTo: years[1],
    media: value('media-filter'),
    change: value('change-filter'),
    minimumProviders: Number(value('provider-count-filter')) || 0,
    favoriteStatus: value('favorite-status-filter'),
    sort: value('sort-order'),
    favoritesOnly,
  };
}

export function updateProviderCount(inputs, target) {
  target.textContent = `${[...inputs].filter(input => input.checked).length}/${inputs.length}`;
}

export function updateProviderFilmCounts(films, countElements) {
  const counts = new Map();
  films.forEach(film => Object.keys(film.providers || {}).forEach(provider => {
    counts.set(provider, (counts.get(provider) || 0) + 1);
  }));
  countElements.forEach(element => {
    const count = counts.get(element.dataset.providerCount) || 0;
    const label = element.closest('label');
    element.textContent = count;
    if (label) {
      // Hide providers without films, but keep their selection (e.g. after a country switch).
      label.dataset.providerAvailable = count > 0 ? 'true' : 'false';
      label.hidden = count === 0;
    }
  });
  document.querySelectorAll('.provider-list').forEach(list => {
    list.hidden = !list.querySelector('label:not([hidden])');
    const heading = list.previousElementSibling;
    if (heading?.classList.contains('subgroup')) heading.hidden = list.hidden;
  });
  document.querySelectorAll('.channel-dropdown').forEach(dropdown => {
    dropdown.hidden = !dropdown.querySelector('label:not([hidden])');
  });
}
