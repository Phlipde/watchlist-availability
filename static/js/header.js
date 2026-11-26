import './register-sw.js';
import './icons.js';
import {initPopovers} from './popovers.js';
import {initCountryPicker, switchCountryAway} from './country-picker.js';
// Pages without the film list (header and the settings page): a new country is saved, its scan starts
// and the watchlist opens to follow it.
initPopovers(document);
document.querySelectorAll('[data-country-picker]').forEach(root => initCountryPicker(root, {
  onPick: async code => {
    try {
      await switchCountryAway(code);
      return true;
    } catch (error) {
      const message = document.getElementById('settings-message');
      if (message) { message.textContent = error.message; message.classList.add('text-danger'); }
      return false;
    }
  },
}));
