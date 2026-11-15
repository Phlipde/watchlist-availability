// Settings page: save the form through the API and handle backup restore.
const form = document.getElementById('settings-form');
const country = document.getElementById('country');
const boxes = [...form.querySelectorAll('input[name="subscriptions"]')];
const subscriptions = window.SETTINGS_PAGE.subscriptions;

function show(id, text, failed = false) {
  const element = document.getElementById(id);
  element.textContent = text;
  element.classList.toggle('text-danger', failed);
}

function updateCount() {
  document.getElementById('subscription-count').textContent = boxes.filter(box => box.checked).length;
}

// Subscriptions are saved per country: show the list of the chosen country.
function showSubscriptions() {
  const chosen = new Set(subscriptions[country.value] || []);
  boxes.forEach(box => { box.checked = chosen.has(box.value); });
  updateCount();
}

country.addEventListener('change', showSubscriptions);
boxes.forEach(box => box.addEventListener('change', updateCount));
showSubscriptions();

form.addEventListener('submit', async event => {
  event.preventDefault();
  const chosen = boxes.filter(box => box.checked).map(box => box.value);
  const response = await fetch('/api/settings', {
    method: 'PUT',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      letterboxd_username: document.getElementById('letterboxd-username').value,
      country: country.value,
      scan_interval_hours: Number(document.getElementById('scan-interval').value),
      subscriptions: chosen,
    }),
  });
  const data = await response.json();
  if (!response.ok) return show('settings-message', data.error || 'Could not save the settings.', true);
  subscriptions[country.value] = chosen;
  show('settings-message', 'Saved.');
});

document.getElementById('backup-file').addEventListener('change', async event => {
  const file = event.target.files[0];
  if (!file) return;
  if (!window.confirm(`Restore from "${file.name}"? Settings and favorites in the file replace the current ones.`)) {
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
