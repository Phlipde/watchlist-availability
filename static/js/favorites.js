export function favoriteKey(movie) {
  return `${movie.title}|${movie.year}`;
}

export function favoriteLabel(isFavorite) {
  return isFavorite ? 'Remove favorite' : 'Add favorite';
}
