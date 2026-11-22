import './register-sw.js';
// Header of the pages without the film list: choosing another country makes it the app's country.
document.getElementById('country-select')?.addEventListener('change', async event => {
  event.target.disabled = true;
  const response = await fetch('/api/settings', {method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({country: event.target.value})});
  if (response.ok) location.href = '/watchlist'; else { event.target.disabled = false; location.reload(); }
});
