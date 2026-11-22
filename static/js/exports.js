// Export and import of the films and the favorites (Settings -> Data). Pure functions; node tests them.
const cell = value => `"${String(value ?? '').replaceAll('"', '""')}"`;

export const filmsCsv = films => ['Title,Year,Services', ...films.map(film => [film.title, film.year, Object.keys(film.providers || {}).join('; ')].map(cell).join(','))].join('\n');

export const favoritesCsv = favorites => ['Title,Year,Status,Notes,Key', ...favorites.map(favorite => [favorite.title, favorite.year, favorite.status || 'plan', favorite.notes || '', favorite.key].map(cell).join(','))].join('\n');

export function parseFavoriteCsv(text) {
  const lines = text.split(/\r?\n/).filter(Boolean);
  if (lines.length < 2) return [];
  const headers = lines.shift().split(',').map(value => value.trim().toLowerCase());
  return lines.map(line => {
    const values = line.match(/(?:"([^"]*(?:""[^"]*)*)"|([^,]*))(?:,|$)/g)?.map(value => value.replace(/,$/, '').replace(/^"|"$/g, '').replaceAll('""', '"')) || [];
    const record = Object.fromEntries(headers.map((header, index) => [header, values[index] || '']));
    return {key: record.key || `${record.title}|${record.year}`, title: record.title, year: record.year, status: record.status, notes: record.notes};
  });
}

// A file's records: JSON (a list) or CSV, by the file name. Throws a message a person can read.
export function parseFavorites(text, fileName) {
  const records = fileName.toLowerCase().endsWith('.json') ? JSON.parse(text) : parseFavoriteCsv(text);
  if (!Array.isArray(records)) throw new Error('The import must contain a list of favorites.');
  return records;
}

// What an import would do: how many favorites are in the file, how many are set already, how many are new.
export function importPreview(records, existingKeys) {
  const valid = records.filter(record => record && record.title && record.key);
  const already = valid.filter(record => existingKeys.has(String(record.key))).length;
  return {valid, found: valid.length, already, fresh: valid.length - already};
}

export const importLine = ({found, already, fresh}) => `${found} favorite${found === 1 ? '' : 's'} found · ${already} already set · ${fresh} new`;
