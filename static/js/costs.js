// Costs page: save prices and reminder dates, then reload so the per-film costs update.
const form = document.getElementById('costs-form');

form?.addEventListener('submit', async event => {
  event.preventDefault();
  const costs = {};
  form.querySelectorAll('tr[data-service]').forEach(row => {
    costs[row.dataset.service] = {
      price: row.querySelector('[name="price"]').value,
      remind_on: row.querySelector('[name="remind_on"]').value,
    };
  });
  const message = document.getElementById('costs-message');
  const response = await fetch('/api/settings', {
    method: 'PUT',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({costs}),
  });
  const data = await response.json();
  message.classList.toggle('text-danger', !response.ok);
  if (!response.ok) {
    message.textContent = data.error || 'Could not save the prices.';
    return;
  }
  message.textContent = 'Saved.';
  location.reload();
});
