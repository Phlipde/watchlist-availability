// Values kept in this browser (saved views, Tonight chips, ...) belong to the active profile: each key gets the
// profile id from <body data-profile>, so "savedViews" is stored as "p2:savedViews".
const activeProfile = () => globalThis.document?.body?.dataset.profile || '1';

export const profileKey = (name, id = activeProfile()) => `p${id}:${name}`;

// A localStorage-like object for one profile. Profile 1 takes over a value saved before profiles had keys
// (the old key without a prefix) on the first read, so nothing is lost.
export function storageFor(storage, id) {
  return {
    getItem(name) {
      const key = profileKey(name, id);
      const value = storage.getItem(key);
      if (value !== null || String(id) !== '1') return value;
      const old = storage.getItem(name);
      if (old === null) return null;
      storage.setItem(key, old);
      storage.removeItem(name);
      return old;
    },
    setItem: (name, value) => storage.setItem(profileKey(name, id), value),
    removeItem: name => storage.removeItem(profileKey(name, id)),
  };
}

// The browser's localStorage for the active profile; looked up on each call, so importing this needs no browser.
export const local = {
  getItem: name => storageFor(localStorage, activeProfile()).getItem(name),
  setItem: (name, value) => storageFor(localStorage, activeProfile()).setItem(name, value),
  removeItem: name => storageFor(localStorage, activeProfile()).removeItem(name),
};
