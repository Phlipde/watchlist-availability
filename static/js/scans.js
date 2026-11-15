import {escapeHtml} from './ui.js';

export function updateScanFeedback(job) {
  const phase = document.getElementById('scan-phase');
  const scanStats = document.getElementById('scan-live-stats');
  if (phase) phase.textContent = job.phase || 'Scanning';
  if (scanStats) {
    scanStats.textContent = `${job.completed || 0} checked · ${(job.results || []).length} available · ${(job.unavailable || []).length} unavailable · ${(job.failed || []).length} failed`;
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
