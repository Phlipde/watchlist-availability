// Arrow-key navigation through the films: grid, compact grid and table share it. Pure functions (node tests them);
// app.js reads the positions from the page and moves the focus.

// How many items sit in the first row: the leading items whose top is the same (a few pixels of tolerance).
export function columnsFromTops(tops, tolerance = 4) {
  if (!tops.length) return 1;
  let columns = 1;
  while (columns < tops.length && Math.abs(tops[columns] - tops[0]) <= tolerance) columns += 1;
  return columns;
}

// The index the key moves to, or null when the key does nothing there (the page may then scroll as usual).
// ↑/↓ keep the column; ↓ from a row above a shorter last row goes to the last item.
export function nextIndex(key, index, columns, count) {
  if (!count || index < 0) return null;
  const last = count - 1;
  let target = null;
  if (key === 'ArrowRight') target = Math.min(index + 1, last);
  else if (key === 'ArrowLeft') target = Math.max(index - 1, 0);
  else if (key === 'Home') target = 0;
  else if (key === 'End') target = last;
  else if (key === 'ArrowDown') target = index + columns <= last ? index + columns : (Math.floor(index / columns) < Math.floor(last / columns) ? last : index);
  else if (key === 'ArrowUp') target = index - columns >= 0 ? index - columns : index;
  return target === null || target === index ? null : target;
}

// Rows of different length (the Tonight page): [row, col] the key moves to, or null. ↑/↓ change the row and keep
// the column as far as the other row reaches.
export function nextInRows(key, row, col, lengths) {
  if (row < 0 || row >= lengths.length || col < 0) return null;
  const last = lengths[row] - 1;
  let target = null;
  if (key === 'ArrowRight') target = [row, Math.min(col + 1, last)];
  else if (key === 'ArrowLeft') target = [row, Math.max(col - 1, 0)];
  else if (key === 'Home') target = [row, 0];
  else if (key === 'End') target = [row, last];
  else if (key === 'ArrowDown' && row + 1 < lengths.length) target = [row + 1, Math.min(col, lengths[row + 1] - 1)];
  else if (key === 'ArrowUp' && row > 0) target = [row - 1, Math.min(col, lengths[row - 1] - 1)];
  return target === null || (target[0] === row && target[1] === col) ? null : target;
}

export const NAV_KEYS = new Set(['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', 'Home', 'End']);
