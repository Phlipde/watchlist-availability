// /settings/profiles: add, rename, set the e-mail, delete (second click confirms) and use a profile.
// Every change reloads the page, so the list and the header come from the server; the message survives the reload.
import {switchProfile} from './profile-switch.js';
import {clearPages} from './register-sw.js';

const message = document.getElementById('profiles-message');
const NOTE = 'profiles-message';

function say(text, isError = false) {
  message.textContent = text;
  message.classList.toggle('text-danger', isError);
  message.focus();
}

const saved = sessionStorage.getItem(NOTE);
if (saved) { sessionStorage.removeItem(NOTE); say(saved); }

async function send(method, url, body, done) {
  try {
    const response = await fetch(url, {method, headers: {'Content-Type': 'application/json'}, body: body && JSON.stringify(body)});
    const answer = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(answer.error || 'That did not work.');
    sessionStorage.setItem(NOTE, done);
    await clearPages();  // saved pages show the old names (or a deleted active profile) offline
    location.reload();
  } catch (error) {
    say(error.message, true);
  }
}

const fields = form => ({name: form.elements.name.value, email: form.elements.email.value.trim() || null});

document.getElementById('profile-add').addEventListener('submit', event => {
  event.preventDefault();
  const profile = fields(event.target);
  send('POST', '/api/profiles', profile, `${profile.name.trim()} added.`);
});

document.querySelectorAll('form[data-profile]').forEach(form => {
  const {profile: id, name} = form.dataset;
  const remove = form.querySelector('[data-delete]');
  const disarm = () => {
    delete remove.dataset.armed;
    remove.textContent = 'Delete';
    remove.setAttribute('aria-label', `Delete ${name}`);
    remove.classList.replace('btn-danger', 'btn-outline-secondary');
  };
  form.addEventListener('submit', event => {
    event.preventDefault();
    send('PUT', `/api/profiles/${id}`, fields(form), 'Changes saved.');
  });
  form.querySelector('[data-use]')?.addEventListener('click', () => switchProfile(Number(id)).catch(error => say(error.message, true)));
  remove.addEventListener('click', () => {
    if (!remove.dataset.armed) {
      remove.dataset.armed = '1';
      remove.textContent = `Delete ${name}?`;
      remove.setAttribute('aria-label', `Delete ${name}? Press again to delete it and all its data.`);
      remove.classList.replace('btn-outline-secondary', 'btn-danger');
      return;
    }
    // Deleting the active profile: the server falls back to another one on the reload.
    send('DELETE', `/api/profiles/${id}`, null, `${name} deleted.`);
  });
  remove.addEventListener('blur', disarm);
  remove.addEventListener('keydown', event => { if (event.key === 'Escape') disarm(); });
});
