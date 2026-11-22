// Settings -> Data: export, import with a preview, and the grey-outs (count and reset).
import {favoritesCsv, filmsCsv, importLine, importPreview, parseFavorites} from './exports.js';

function download(name, data, type) {
  const link = document.createElement('a');
  link.href = URL.createObjectURL(new Blob([data], {type}));
  link.download = name;
  link.click();
  URL.revokeObjectURL(link.href);
}
const getJson = async url => {
  const response = await fetch(url);
  if (!response.ok) throw new Error('Could not load the data.');
  return response.json();
};

document.querySelectorAll('[data-export]').forEach(button => button.addEventListener('click', async () => {
  const what = button.dataset.export;
  try {
    if (what.startsWith('films')) {
      const snapshot = await getJson('/api/latest');
      const films = snapshot.results || [];
      if (what === 'films-json') download('watchlist.json', JSON.stringify(films, null, 2), 'application/json');
      else download('watchlist.csv', filmsCsv(films), 'text/csv');
    } else {
      const favorites = await getJson('/api/favorites');
      if (what === 'favorites-json') download('favorites.json', JSON.stringify(favorites, null, 2), 'application/json');
      else download('favorites.csv', favoritesCsv(favorites), 'text/csv');
    }
  } catch (error) {
    document.getElementById('import-preview').textContent = error.message;
    document.getElementById('import-preview').hidden = false;
  }
}));

// Import: read the file, say what would happen, and change nothing until "Import" is pressed.
let pending = [];
const previewText = document.getElementById('import-preview');
const goButton = document.getElementById('import-go');
document.getElementById('import-favorites')?.addEventListener('change', async event => {
  const file = event.target.files[0];
  if (!file) return;
  try {
    const records = parseFavorites(await file.text(), file.name);
    const existing = new Set((await getJson('/api/favorites')).map(favorite => String(favorite.key)));
    const preview = importPreview(records, existing);
    if (!preview.found) throw new Error('No valid favorites found in this file.');
    pending = preview.valid;
    previewText.textContent = importLine(preview);
    goButton.hidden = false;
  } catch (error) {
    pending = [];
    previewText.textContent = error.message || 'Could not read this file.';
    goButton.hidden = true;
  }
  previewText.hidden = false;
  event.target.value = '';
});
goButton?.addEventListener('click', async () => {
  goButton.disabled = true;
  try {
    for (const movie of pending) {
      const status = ['plan', 'watching', 'watched'].includes(movie.status) ? movie.status : 'plan';
      const response = await fetch('/api/favorites', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({...movie, status, notes: String(movie.notes || '')})});
      if (!response.ok) throw new Error(`Could not import “${movie.title}”.`);
    }
    previewText.textContent = `Imported ${pending.length} favorite${pending.length === 1 ? '' : 's'}.`;
    pending = [];
    goButton.hidden = true;
  } catch (error) {
    previewText.textContent = error.message;
  }
  goButton.disabled = false;
});

const text = document.getElementById('greyouts-text');
const button = document.getElementById('greyouts-reset');

async function refresh() {
  const response = await fetch('/api/greyouts');
  if (!response.ok) return;
  const {flags, favorites} = await response.json();
  const total = flags + favorites;
  button.disabled = total === 0;
  text.textContent = total
    ? `${total} ${total === 1 ? 'film is' : 'films are'} greyed out${favorites ? ` (${favorites} as favorites)` : ''}. They stay in the list, only paler.`
    : 'No film is greyed out. Letterboxd is where you log what you watched.';
}

button?.addEventListener('click', async () => {
  const response = await fetch('/api/greyouts/reset', {method: 'POST'});
  if (response.ok) {
    const done = await response.json();
    text.textContent = `Reset: ${done.flags} grey-outs removed${done.favorites ? `, ${done.favorites} favorites set back to Plan` : ''}.`;
    button.disabled = true;
  }
});

refresh();
