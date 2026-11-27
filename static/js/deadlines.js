// The banner for a renewal or cancellation date that is at most a week away (dates the user entered).
// "Remind me tomorrow" and "Dismiss" are remembered in this browser only.
import {local} from './profile-storage.js';
const KEY = 'deadlineSnooze';
const read = () => { try { return JSON.parse(local.getItem(KEY) || '{}'); } catch { return {}; } };

export function dayText(iso) {
  return new Date(`${iso}T12:00:00`).toLocaleDateString('en-GB', {dateStyle: 'medium'});
}

export function whenText(days) {
  return days === 0 ? 'today' : days === 1 ? 'tomorrow' : `in ${days} days`;
}

// deadlines: [{name, date, days}] from the server, soonest first; `link` adds a way to the subscriptions page.
export function showDeadlines(container, deadlines, {link = false, now = Date.now()} = {}) {
  if (!container) return;
  const snoozed = read();
  const visible = (deadlines || []).filter(item => !(snoozed[`${item.name}|${item.date}`] > now));
  container.hidden = visible.length === 0;
  if (!visible.length) return;
  const first = visible[0];
  const more = visible.length > 1 ? ` (and ${visible.length - 1} more)` : '';
  container.innerHTML = '';
  const text = document.createElement('p');
  text.textContent = `${first.name}: renewal or cancellation date ${whenText(first.days)} (${dayText(first.date)})${more}.`;
  const buttons = document.createElement('div');
  buttons.className = 'banner-actions';
  const add = (label, onClick) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'film-link';
    button.textContent = label;
    button.addEventListener('click', onClick);
    buttons.append(button);
  };
  const hide = until => {
    const stored = read();
    visible.forEach(item => { stored[`${item.name}|${item.date}`] = until; });
    local.setItem(KEY, JSON.stringify(stored));
    showDeadlines(container, deadlines, {link, now: Date.now()});
  };
  add('Remind me tomorrow', () => hide(Date.now() + 20 * 3600 * 1000));
  add('Dismiss', () => hide(new Date(`${first.date}T23:59:59`).getTime()));
  if (link) {
    const anchor = document.createElement('a');
    anchor.className = 'film-link';
    anchor.href = '/subscriptions';
    anchor.textContent = 'Open subscriptions';
    buttons.append(anchor);
  }
  container.append(text, buttons);
}
