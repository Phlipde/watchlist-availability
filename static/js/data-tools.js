// Settings -> Data: the grey-outs (count and reset).
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
