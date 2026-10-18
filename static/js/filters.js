export function selectedProviders(inputs) {
  return new Set([...inputs].filter(input => input.checked).map(input => input.value));
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
    const input = label?.querySelector('input[type="checkbox"]');
    element.textContent = count;
    if (label) label.dataset.providerAvailable = count > 0 ? 'true' : 'false';
    if (count === 0 && input) {
      input.checked = false;
      label.hidden = true;
    } else if (label) {
      label.hidden = false;
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
