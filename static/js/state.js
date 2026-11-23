// The single source of truth for the page: films, favorites and UI selections.
export function createAppState() {
  return {
    films: [],
    unavailable: [],
    changes: [],
    lastScan: null,
    favorites: new Map(),
    flags: new Map(),  // key -> {flag: 'watched' | 'not_now', until}
    favoritesOnly: false,
    link: {availability: [], person: '', collection: '', runtimeMin: 0},  // filters only links set, see link-filters.js
    compareKeys: new Set(),
    view: null,
  };
}

export function createScanState() {
  return {
    currentJob: undefined,
    pollDelay: 350,
    pollFailures: 0,
    lastPollSignature: '',
    rescanInProgress: false,
    resultsReceived: 0,
    pendingUnavailable: [],
  };
}
