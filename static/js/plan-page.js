// The planner of the subscriptions page: the best services for a budget, what to book month by month, a what-if.
import {local} from './profile-storage.js';
import {bestCombinations, coverage, rotation} from './planner.js';

const data = window.PLAN_DATA;
const section = document.getElementById('planner');
if (data && section && Object.keys(data.services).length) {
  section.hidden = false;
  const money = value => value.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
  const escape = text => String(text).replace(/[&<>"']/g, char => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[char]));
  const KEY = 'candidatePrices';
  const stored = () => { try { return JSON.parse(local.getItem(KEY) || '{}'); } catch { return {}; } };
  const prices = () => ({...stored(), ...data.prices});  // a saved price of your own service wins
  const budget = document.getElementById('budget');
  const result = document.getElementById('budget-result');
  const now = coverage(data.owned, data);

  // Prices of every service that has none yet.
  const unpriced = Object.keys(data.services).filter(name => data.prices[name] === undefined);
  document.getElementById('candidate-prices').innerHTML = unpriced.map(name => `<label class="menu-field"><span>${escape(name)} per month</span><input class="form-control form-control-sm" data-price="${escape(name)}" inputmode="decimal" placeholder="€ / month" value="${stored()[name] ?? ''}"></label>`).join('');
  document.getElementById('candidate-prices').addEventListener('change', event => {
    const name = event.target.dataset.price;
    if (!name) return;
    const value = Number(event.target.value.replace(',', '.'));
    const next = stored();
    if (event.target.value.trim() === '' || Number.isNaN(value) || value < 0) delete next[name]; else next[name] = value;
    local.setItem(KEY, JSON.stringify(next));
    draw();
  });
  budget.value = String(Math.min(50, Math.max(5, Math.round(Object.values(data.prices).reduce((sum, price) => sum + price, 0) || 15))));
  budget.addEventListener('input', draw);

  function draw() {
    document.getElementById('budget-value').textContent = budget.value;
    const found = bestCombinations(data, prices(), Number(budget.value));
    result.innerHTML = found.length
      ? '<ol class="plan-options">' + found.map((item, index) => `<li><strong>${item.names.map(escape).join(' + ')}</strong> = € ${money(item.cost)} → ${item.percent} % of your watchlist${index === 0 ? ` (${item.percent - now.percent >= 0 ? '+' : ''}${item.percent - now.percent} % against now)` : ''}</li>`).join('') + '</ol>'
      : '<p class="hint">Nothing fits: enter prices above or raise the budget.</p>';
    const steps = rotation(data, 3, data.owned);
    document.getElementById('rotation').innerHTML = steps.length
      ? steps.map(step => `<li><strong>Month ${step.month}: ${escape(step.name)}</strong> adds ${step.films} film${step.films === 1 ? '' : 's'} (to ${step.percent} %)${prices()[step.name] ? `, € ${money(prices()[step.name])}` : ''}</li>`).join('')
      : '<li class="hint">Nothing more to add: your services cover everything the others have.</li>';
  }

  // What if: a checkbox per service, the coverage next to what you have now.
  const whatif = document.getElementById('whatif');
  const selected = new Set(data.owned);
  whatif.innerHTML = Object.keys(data.services).map(name => `<label class="check-field"><input type="checkbox" value="${escape(name)}"${selected.has(name) ? ' checked' : ''}> ${escape(name)}${data.owned.includes(name) ? ' <span class="pill pill-ok">yours</span>' : ''}</label>`).join('');
  function drawWhatIf() {
    const chosen = [...selected];
    const next = coverage(chosen, data);
    const cost = chosen.reduce((sum, name) => sum + (prices()[name] || 0), 0);
    const changed = chosen.length !== data.owned.length || chosen.some(name => !data.owned.includes(name));
    document.getElementById('whatif-result').textContent = changed
      ? `What-if, nothing saved: ${next.percent} % of your watchlist (now ${now.percent} %), € ${money(cost)} a month with the prices you entered.`
      : `As it is: ${now.percent} % of your watchlist.`;
    section.classList.toggle('is-whatif', changed);
  }
  whatif.addEventListener('change', event => {
    if (event.target.checked) selected.add(event.target.value); else selected.delete(event.target.value);
    drawWhatIf();
  });
  document.querySelectorAll('.try-it').forEach(button => button.addEventListener('click', () => {
    const box = [...whatif.querySelectorAll('input')].find(input => input.value === button.dataset.service);
    if (box) { box.checked = true; selected.add(box.value); drawWhatIf(); }
    section.scrollIntoView({behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth'});
    box?.focus();
  }));
  // Overlap: how many watchlist films two of your paid services share (a cell opens exactly those films).
  const mine = data.owned.filter(name => data.services[name]);
  if (mine.length > 1) {
    const shared = (a, b) => { const other = new Set(data.services[b]); return data.services[a].filter(key => other.has(key)).length; };
    const pairs = [];
    mine.forEach((a, i) => mine.slice(i + 1).forEach(b => pairs.push({a, b, count: shared(a, b)})));
    pairs.sort((x, y) => y.count - x.count);
    document.getElementById('overlap-text').textContent = pairs[0].count ? `${pairs[0].a} and ${pairs[0].b} share ${pairs[0].count} films.` : 'Your services share no film.';
    const link = (a, b) => `/watchlist?providers=${encodeURIComponent(a)}%2C${encodeURIComponent(b)}&match=all`;
    document.getElementById('overlap-table').innerHTML = `<thead><tr><th scope="col"></th>${mine.map(name => `<th scope="col">${escape(name)}</th>`).join('')}</tr></thead><tbody>${mine.map(a => `<tr><th scope="row">${escape(a)}</th>${mine.map(b => (a === b ? `<td class="num">${data.services[a].length}</td>` : `<td class="num"><a class="film-link" href="${link(a, b)}">${shared(a, b)}</a></td>`)).join('')}</tr>`).join('')}</tbody>`;
  } else {
    document.getElementById('overlap').hidden = true;
  }
  draw();
  drawWhatIf();
}
