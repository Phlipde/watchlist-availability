// The single source of truth for the page: films, favorites and UI selections.
export function createAppState() {
  return {
    films: [],
    unavailable: [],
    changes: [],
    lastScan: null,
    favorites: new Map(),
    favoritesOnly: false,
    compareKeys: new Set(),
    view: null,
  };
}

export function createScanState() {
  return {
    currentJob: undefined,
    pollDelay: 350,
    lastPollSignature: '',
    rescanInProgress: false,
    pendingResults: [],
    pendingUnavailable: [],
  };
}
