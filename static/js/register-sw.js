// Registers the service worker (offline use and installing the app). It needs https or localhost; elsewhere it is skipped.
if ('serviceWorker' in navigator && (location.protocol === 'https:' || ['localhost', '127.0.0.1'].includes(location.hostname))) {
  navigator.serviceWorker.register('/sw.js').catch(() => {});
}
