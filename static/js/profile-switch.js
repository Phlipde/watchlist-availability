// Switching the profile (header menu and /settings/profiles): the server sets the cookie, the service worker
// forgets the old profile's saved pages, then the page loads again. Imported by header.js, app.js and profiles.js.
import {clearPages} from './register-sw.js';

export async function switchProfile(id) {
  const response = await fetch('/api/profiles/active', {
    method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({id}),
  });
  if (!response.ok) throw new Error((await response.json().catch(() => ({}))).error || 'The profile could not be switched.');
  await clearPages();
  // ?profile= beats the cookie: drop it, or the page would open the old profile again.
  const url = new URL(location.href);
  if (!url.searchParams.has('profile')) { location.reload(); return; }
  url.searchParams.delete('profile');
  location.replace(url);
}

document.addEventListener('click', async event => {
  const button = event.target.closest?.('[data-profile-id]');
  if (!button) return;
  button.disabled = true;
  try {
    await switchProfile(Number(button.dataset.profileId));
  } catch (error) {
    button.disabled = false;
    const menu = button.closest('.profile-menu');
    menu?.querySelector('.profile-error')?.remove();
    menu?.insertAdjacentHTML('beforeend', '<p class="hint error profile-error" role="alert"></p>');
    if (menu) menu.lastElementChild.textContent = error.message;
  }
});
