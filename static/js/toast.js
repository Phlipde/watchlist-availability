// The toast at the bottom of the page: one message at a time; errors stay longer, a change can offer "Undo".
export function createToast() {
  const toastElement = document.getElementById('app-toast');
  const toast = window.bootstrap ? bootstrap.Toast.getOrCreateInstance(toastElement, {autohide: false}) : {show() {}, hide() {}};
  let toastTimer;
  let toastUndo = null;
  // An error must not look like routine feedback: red border, announced at once, shown longer.
  // With `undo` the toast offers "Undo" for about five seconds.
  function showToast(message, error = false, undo = null) {
    document.getElementById('toast-message').textContent = message;
    toastElement.classList.toggle('toast-error', error);
    toastElement.setAttribute('role', error ? 'alert' : 'status');
    toastUndo = undo;
    document.getElementById('toast-undo').hidden = !undo;
    clearTimeout(toastTimer);
    toast.show();
    toastTimer = setTimeout(() => { toastUndo = null; toast.hide(); }, error ? 6000 : undo ? 5000 : 2400);
  }
  document.getElementById('toast-undo').addEventListener('click', () => {
    const undo = toastUndo;
    toastUndo = null;
    toast.hide();
    undo?.();
  });
  return {showToast};
}
