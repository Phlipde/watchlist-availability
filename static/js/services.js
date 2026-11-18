// Settings -> My services: ticking saves at once; "Undo" puts the previous list back.
const root = document.getElementById('services-sections');
const country = root.dataset.country;
const boxes = () => [...root.querySelectorAll('input[type=checkbox]')];
const toast = document.getElementById('toast');
const toastText = document.getElementById('toast-text');
const undoButton = document.getElementById('toast-undo');
let saved = boxes().filter(box => box.checked).map(box => box.value);
let timer;

function say(text, undo) {
  toastText.textContent = text;
  undoButton.hidden = !undo;
  undoButton.onclick = undo || null;
  toast.hidden = false;
  clearTimeout(timer);
  timer = setTimeout(() => { toast.hidden = true; }, 6000);
}

async function save(names) {
  const response = await fetch('/api/settings', {
    method: 'PUT',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({subscriptions_country: country, subscriptions: names}),
  });
  if (!response.ok) throw new Error((await response.json().catch(() => ({}))).error || 'Could not save.');
}

root.addEventListener('change', async event => {
  const before = saved;
  const names = boxes().filter(box => box.checked).map(box => box.value);
  try {
    await save(names);
    saved = names;
    say('Saved', async () => {
      await save(before);
      saved = before;
      boxes().forEach(box => { box.checked = before.includes(box.value); });
      say('Undone');
    });
  } catch (error) {
    event.target.checked = !event.target.checked;  // the list on the page must match what is saved
    say(error instanceof TypeError ? 'Could not reach the app.' : error.message);
  }
});

document.getElementById('services-find').addEventListener('input', event => {
  const query = event.target.value.trim().toLowerCase();
  root.querySelectorAll('.service-list li').forEach(item => {
    item.hidden = Boolean(query) && !item.textContent.toLowerCase().includes(query);
  });
  root.querySelectorAll('details.settings-group').forEach(group => {
    const shown = [...group.querySelectorAll('li')].some(item => !item.hidden);
    group.hidden = !shown;
    if (query && shown) group.open = true;
  });
});
