// Favorites and the Watched / Not now flags: loading, toggling with "Undo", and the status and note fields.
import {favoriteFields} from './rendering.js';
import {filmKey} from './filtering.js';

export function createFilmFlags({state, results, showToast, renderFilms}) {
  async function loadFavorites() {
    // Both requests at once: the page redraws when they are in, and a later redraw steals the keyboard focus.
    const [response, flags] = await Promise.all([
      fetch('/api/favorites'),
      fetch('/api/flags').then(answer => (answer.ok ? answer.json() : []), () => []),
    ]);
    const favorites = await response.json();
    state.favorites = new Map(favorites.map(movie => [movie.key, movie]));
    state.flags = new Map(flags.map(entry => [entry.key, entry]));
  }
  // Watched / Not now from the card menu, the details and the keys; "Undo" puts the film back for five seconds.
  async function setFlag(key, flag) {
    const before = state.flags.get(key);
    const turnOff = before?.flag === flag && (flag === 'watched' || before.until > Date.now() / 1000);
    const request = (target, kind) => (kind ? fetch(`/api/flags/${encodeURIComponent(target)}`, {method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({flag: kind})}) : fetch(`/api/flags/${encodeURIComponent(target)}`, {method: 'DELETE'}));
    const apply = async kind => {
      const response = await request(key, kind).catch(() => null);
      if (!response?.ok) { showToast('Could not save this. Reload the page and try again.', true); return false; }
      if (kind) state.flags.set(key, await response.json()); else state.flags.delete(key);
      return true;
    };
    if (!(await apply(turnOff ? null : flag))) return;
    const title = [...state.films, ...state.unavailable].find(film => filmKey(film) === key)?.title || 'Film';
    const message = turnOff ? `${title}: back on the list` : flag === 'watched' ? `${title}: hidden away` : `${title}: set aside for 30 days`;
    showToast(message, false, async () => { if (await apply(before?.flag ?? null)) renderFilms(); });
    renderFilms();
  }
  async function toggleFavorite(button) {
    const card = button.closest('.film');
    const key = card?.dataset.key || button.dataset.key;
    if (!key || button.disabled) return;
    const previous = state.favorites.get(key);
    const film = state.films.find(movie => filmKey(movie) === key);
    if (!previous && !film) return;
    // Disabling the button below takes the focus away, so remember it first.
    const hadFocus = document.activeElement === button && results.contains(button);
    button.disabled = true;
    let response;
    try {
      response = previous
        ? await fetch(`/api/favorites/${encodeURIComponent(key)}`, {method: 'DELETE'})
        : await fetch('/api/favorites', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({key, ...film})});
    } catch {
      response = null;
    }
    if (!response?.ok) {
      button.disabled = false;
      showToast('Could not save the favorite. Reload the page and try again.', true);
      return;
    }
    if (previous) state.favorites.delete(key);
    else state.favorites.set(key, {...film, key, status: 'plan', notes: ''});
    renderFilms();
    if (previous) showToast(`Removed “${previous.title || film?.title || 'film'}” from favorites.`, false, () => restoreFavorite(previous));
    const fields = document.getElementById('modal-favorite-fields');
    if (fields?.dataset.key === key) fields.innerHTML = state.favorites.has(key) ? favoriteFields(key, state.favorites.get(key).title || film?.title || '', state.favorites.get(key)) : '';
    // The redraw replaces the card: put the focus back on the same star.
    if (hadFocus) results.querySelector(`.film[data-key="${CSS.escape(key)}"] .favorite`)?.focus();
    document.querySelectorAll(`.modal-favorite[data-key="${CSS.escape(key)}"]`).forEach(modalButton => {
      const active = state.favorites.has(key);
      modalButton.innerHTML = `<i class="ti ${active ? 'ti-heart-filled' : 'ti-heart'}" aria-hidden="true"></i><span class="tool-label">Favorite</span>`;
      const label = active ? 'Remove favorite' : 'Add to favorites';
      modalButton.title = label;
      modalButton.setAttribute('aria-label', label);
      modalButton.setAttribute('aria-pressed', String(active));
      modalButton.disabled = false;
    });
    // The new heart blurs in: the swap's only motion (see .icon-swap).
    document.querySelectorAll(`.film[data-key="${CSS.escape(key)}"] .favorite i, .modal-favorite[data-key="${CSS.escape(key)}"] i`).forEach(icon => icon.classList.add('icon-swap'));
  }
  // Undo after removing: the favorite comes back with its status and note.
  async function restoreFavorite(previous) {
    try {
      const response = await fetch('/api/favorites', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(previous)});
      if (!response.ok) throw new Error();
    } catch {
      showToast('Could not restore the favorite.', true);
      return;
    }
    state.favorites.set(previous.key, previous);
    renderFilms();
    showToast(`“${previous.title}” is back in your favorites.`);
  }
  async function updateFavoriteField(control) {
    const key = control.dataset.key || control.closest('.film')?.dataset.key;
    const field = control.classList.contains('favorite-status') ? 'status' : 'notes';
    let response;
    try {
      response = await fetch(`/api/favorites/${encodeURIComponent(key)}`, {method: 'PATCH', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({[field]: control.value})});
    } catch {
      response = null;
    }
    // An unsaved note looks saved until the next redraw: mark the field until a retry works.
    control.classList.toggle('is-invalid', !response?.ok);
    if (!response?.ok) { showToast(`Could not save the ${field === 'notes' ? 'note' : 'status'}. It is still in the field; change it again to retry.`, true); return; }
    const saved = state.favorites.get(key) || {key}; saved[field] = control.value; state.favorites.set(key, saved);
  }
  results.addEventListener('click', event => { const favoriteButton = event.target.closest('.favorite'); if (favoriteButton) { event.preventDefault(); toggleFavorite(favoriteButton); } });
  results.addEventListener('change', event => { if (event.target.classList.contains('favorite-status')) updateFavoriteField(event.target); });
  results.addEventListener('change', event => { if (event.target.classList.contains('favorite-note')) updateFavoriteField(event.target); });
  return {loadFavorites, setFlag, toggleFavorite, updateFavoriteField};
}
