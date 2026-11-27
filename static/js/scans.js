import {escapeHtml} from './ui.js';
import {serviceGroup} from './catalog.js';

export function updateScanFeedback(job) {
  const phase = document.getElementById('scan-phase');
  const scanStats = document.getElementById('scan-live-stats');
  if (phase) phase.textContent = job.phase || 'Scanning';
  if (scanStats) {
    scanStats.textContent = `${job.completed || 0} checked · ${job.stats?.total ?? (job.results || []).length} available · ${(job.unavailable || []).length} unavailable · ${(job.failed || []).length} failed`;
  }
  const failurePanel = document.getElementById('scan-failures');
  const failureList = document.getElementById('failed-list');
  if (failurePanel && failureList) {
    const failures = job.failed || [];
    failurePanel.hidden = failures.length === 0;
    document.getElementById('failed-count').textContent = failures.length;
    failureList.innerHTML = failures.map(failure => `<li>${escapeHtml(failure.title)} (${escapeHtml(failure.year || 'unknown year')}): ${escapeHtml(failure.message || 'Lookup failed')}</li>`).join('');
  }
}

// The toast after a scan: how many films this scan found new on your services (plans and channels count as the service).
export function scanResultText(job, subscriptions) {
  const own = new Set([...subscriptions].map(serviceGroup));
  const since = job.started_at ?? Infinity;
  const films = new Set((job.changes || [])
    .filter(change => change.change === 'added' && change.created >= since && own.has(serviceGroup(change.provider)))
    .map(change => change.film_key));
  return films.size ? `Scan complete: ${films.size} new on your services.` : 'Watchlist scan complete.';
}
