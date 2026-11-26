// Settings page: save watchlist and schedule through the API and handle backup restore.
// The country has its own picker (header.js): it saves, scans and opens the watchlist.
const form = document.getElementById('settings-form');
function show(id, text, failed = false) {
  const element = document.getElementById(id);
  element.textContent = text;
  element.classList.toggle('text-danger', failed);
}

// Every field saves on its own when it changes (text fields when they lose focus); a toast offers Undo.
// A new Letterboxd name needs a new scan: the toast offers it.
const fields = () => ({
  letterboxd_username: document.getElementById('letterboxd-username').value,
  scan_interval_hours: Number(document.getElementById('scan-interval').value),
  weekly_hours: Number(document.getElementById('weekly-hours').value),
  notify_kind: document.getElementById('notify-kind').value,
  notify_url: document.getElementById('notify-url').value,
  notify_events: Object.fromEntries([...document.querySelectorAll('input[name=notify_event]')].map(box => [box.value, box.checked])),
});
function fill(values) {
  document.getElementById('letterboxd-username').value = values.letterboxd_username;
  document.getElementById('scan-interval').value = String(values.scan_interval_hours);
  document.getElementById('weekly-hours').value = String(values.weekly_hours);
  document.getElementById('notify-kind').value = values.notify_kind;
  document.getElementById('notify-url').value = values.notify_url;
  document.querySelectorAll('input[name=notify_event]').forEach(box => { box.checked = Boolean(values.notify_events[box.value]); });
}
async function save(values) {
  try {
    const token = document.getElementById('notify-token');
    const response = await fetch('/api/settings', {
      method: 'PUT',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({...values, notify_token: token.value}),  // an empty token keeps the saved one
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) { show('settings-message', data.error || 'Could not save the settings.', true); return false; }
    token.value = '';
    show('settings-message', '');
    return true;
  } catch {
    show('settings-message', 'Could not reach the app.', true);
    return false;
  }
}

const toast = document.getElementById('toast');
let toastTimer;
let undo = null;
function showToast(text, onUndo, rescan) {
  document.getElementById('toast-text').textContent = text;
  undo = onUndo;
  document.getElementById('toast-undo').hidden = !onUndo;
  document.getElementById('toast-rescan').hidden = !rescan;
  toast.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { toast.hidden = true; }, rescan ? 10000 : 5000);
}
document.getElementById('toast-undo').addEventListener('click', () => { toast.hidden = true; undo?.(); });
document.getElementById('toast-rescan').addEventListener('click', async () => {
  toast.hidden = true;
  const response = await fetch('/api/scan', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({})});
  const data = await response.json().catch(() => ({}));
  if (response.ok && data.job_id) location.href = `/watchlist?scan=${encodeURIComponent(data.job_id)}`;
  else show('settings-message', data.error || 'Could not start the scan.', true);
});

let saved = fields();
form.addEventListener('submit', event => event.preventDefault());
form.addEventListener('change', async event => {
  if (!event.target.name || event.target.name === 'notify_token' && !event.target.value) return;
  const before = saved;
  const now = fields();
  if (!await save(now)) return;
  saved = now;
  const rescan = event.target.name === 'letterboxd_username';
  showToast(rescan ? 'Saved · Rescan now?' : 'Saved', async () => {
    fill(before);
    if (await save(before)) { saved = before; showToast('Change undone', null, false); }
  }, rescan);
});

document.getElementById('tmdb-test').addEventListener('click', async () => {
  show('tmdb-message', 'Asking TMDB…');
  try {
    const response = await fetch('/api/tmdb/test', {method: 'POST'});
    const data = await response.json().catch(() => ({}));
    show('tmdb-message', response.ok ? 'The key works.' : data.error || 'TMDB did not answer.', !response.ok);
  } catch {
    show('tmdb-message', 'Could not reach the app.', true);
  }
});

// "Send a test message" uses what is saved, so it saves the form first.
document.getElementById('notify-test').addEventListener('click', async () => {
  show('notify-message', 'Saving and sending…');
  form.requestSubmit();
  await new Promise(resolve => setTimeout(resolve, 600));
  try {
    const response = await fetch('/api/notify/test', {method: 'POST'});
    const data = await response.json().catch(() => ({}));
    show('notify-message', response.ok ? 'Sent. Look for the message.' : data.error || 'Could not send.', !response.ok);
  } catch {
    show('notify-message', 'Could not reach the app.', true);
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
