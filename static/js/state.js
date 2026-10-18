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
