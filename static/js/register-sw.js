// Registers the service worker (offline use and installing the app). It needs https or localhost; elsewhere it is skipped.
if ('serviceWorker' in navigator && (location.protocol === 'https:' || ['localhost', '127.0.0.1'].includes(location.hostname))) {
  navigator.serviceWorker.register('/sw.js').catch(() => {});
}

// Asks the worker to forget the saved pages and data (another profile sees other data under the same URLs).
// Waits for its answer, at most a second: an older worker without the handler never answers.
export async function clearPages(timeout = 1000) {
  const worker = navigator.serviceWorker?.controller;
  if (!worker) return;
  const channel = new MessageChannel();
  const answered = new Promise(resolve => { channel.port1.onmessage = resolve; });
  worker.postMessage({type: 'clear-pages'}, [channel.port2]);
  await Promise.race([answered, new Promise(resolve => setTimeout(resolve, timeout))]);
}
