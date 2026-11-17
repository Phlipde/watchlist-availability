// Settings page: save watchlist, country and schedule through the API and handle backup restore.
const form = document.getElementById('settings-form');
const country = document.getElementById('country');
function show(id, text, failed = false) {
  const element = document.getElementById(id);
  element.textContent = text;
  element.classList.toggle('text-danger', failed);
}

form.addEventListener('submit', async event => {
  event.preventDefault();
  const button = document.getElementById('settings-save');
  button.disabled = true;
  try {
    const response = await fetch('/api/settings', {
      method: 'PUT',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        letterboxd_username: document.getElementById('letterboxd-username').value,
        country: country.value,
        scan_interval_hours: Number(document.getElementById('scan-interval').value),
      }),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) return show('settings-message', data.error || 'Could not save the settings.', true);
    show('settings-message', 'Saved.');
  } catch {
    show('settings-message', 'Could not reach the app.', true);
  } finally {
    button.disabled = false;
  }
});

document.getElementById('backup-file').addEventListener('change', async event => {
  const file = event.target.files[0];
  if (!file) return;
  if (!window.confirm(`Restore from “${file.name}”? Settings and favorites in the file replace the current ones.`)) {
    event.target.value = '';
    return;
  }
  const body = new FormData();
  body.append('backup', file);
  const response = await fetch('/api/backup', {method: 'POST', body});
  const data = await response.json();
  event.target.value = '';
  if (!response.ok) return show('backup-message', data.error || 'Could not restore the backup.', true);
  const counts = data.imported;
  const skipped = counts.skipped ? ` ${counts.skipped} unusable entries were skipped.` : '';
  show('backup-message', `Restored: ${counts.favorites} favorites, ${counts.changes} changes, ${counts.scans} scans.${skipped} Reloading…`);
  setTimeout(() => location.reload(), 1200);
});
