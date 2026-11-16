// My subscriptions page: save services, prices and reminders together, then reload with the new numbers.
const form = document.getElementById('subscriptions-form');
const country = form.dataset.country;
const boxes = [...form.querySelectorAll('input[name="subscriptions"]')];
const saveButton = document.getElementById('subscriptions-save');
const message = document.getElementById('subscriptions-message');
let dirty = false;

form.addEventListener('input', () => { dirty = true; });
boxes.forEach(box => box.addEventListener('change', () => {
  document.getElementById('subscription-count').textContent = boxes.filter(item => item.checked).length;
}));

document.getElementById('subscriptions-country').addEventListener('change', event => {
  if (dirty && !window.confirm('Leave without saving your changes?')) {
    event.target.value = country;
    return;
  }
  dirty = false;
  location.href = `/subscriptions?country=${encodeURIComponent(event.target.value)}`;
});

form.addEventListener('submit', async event => {
  event.preventDefault();
  const chosen = boxes.filter(box => box.checked).map(box => box.value);
  const costs = {};
  // Prices of unticked services are dropped by the server; free services have no fields.
  form.querySelectorAll('tr[data-service]').forEach(row => {
    if (!chosen.includes(row.dataset.service) || !row.querySelector('[name="price"]')) return;
    costs[row.dataset.service] = {
      price: row.querySelector('[name="price"]').value,
      remind_on: row.querySelector('[name="remind_on"]').value,
    };
  });
  saveButton.disabled = true;
  message.classList.remove('text-danger');
  message.textContent = 'Saving…';
  try {
    const response = await fetch('/api/settings', {
      method: 'PUT',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({subscriptions_country: country, subscriptions: chosen, costs}),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || 'Could not reach the app.');
    dirty = false;
    location.href = `/subscriptions?country=${encodeURIComponent(country)}&saved=1`;
  } catch (error) {
    // fetch itself fails with a TypeError when the app is not running.
    message.textContent = error instanceof TypeError ? 'Could not reach the app.' : error.message;
    message.classList.add('text-danger');
    saveButton.disabled = false;
  }
});

window.addEventListener('beforeunload', event => { if (dirty) event.preventDefault(); });
