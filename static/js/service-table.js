// Filter, sort and URL state of the stats page's service table. Pure functions, tested without a page.

export const TYPES = [
  ['sub-free', 'Subscription and free'], ['all', 'All'], ['sub', 'Subscription'], ['free', 'Free or ads'], ['store', 'Rent or buy'],
];
export const DEFAULTS = {q: '', type: 'sub-free', mine: false, exclusive: false, min: 1, sort: 'films', dir: 'desc', all: false};

const STATUS_ORDER = {own: 0, other: 1, free: 2, store: 3};
// Sort keys: how to read the value of a service; null sorts last in either direction.
const VALUE = {
  name: item => item.group.toLowerCase(),
  status: item => STATUS_ORDER[item.status],
  films: item => item.films,
  exclusive: item => item.exclusive,
  hours: item => item.hours,
  free: item => item.free,
  ads: item => item.ads,
  subscription: item => item.subscription,
  rent: item => item.rent,
  rating: item => item.averageRating,
  cost: item => item.costPerLostFilm,
};
export const SORT_KEYS = Object.keys(VALUE);

export function filterServices(services, filters) {
  const {q, type, mine, exclusive, min} = {...DEFAULTS, ...filters};
  const needle = q.trim().toLowerCase();
  return services.filter(item => {
    if (needle && ![item.group, ...item.plans].some(name => name.toLowerCase().includes(needle))) return false;
    if (type === 'sub-free' && item.status === 'store') return false;
    if (type === 'sub' && !item.subscription) return false;
    if (type === 'free' && !(item.free + item.ads)) return false;
    if (type === 'store' && item.status !== 'store') return false;
    if (mine && !item.own) return false;
    if (exclusive && !item.exclusive) return false;
    return item.films >= min;
  });
}

export function sortServices(services, sort = DEFAULTS.sort, dir = DEFAULTS.dir) {
  const read = VALUE[sort] || VALUE.films;
  const sign = dir === 'asc' ? 1 : -1;
  return [...services].sort((a, b) => {
    const x = read(a);
    const y = read(b);
    if ((x === null) !== (y === null)) return x === null ? 1 : -1;
    const order = x === y || x === null ? 0 : (x < y ? -1 : 1) * sign;
    return order || b.films - a.films || a.group.localeCompare(b.group);
  });
}

// ?svcq=net&svctype=all&mine=1&excl=1&min=3&sort=exclusive:desc&all=1; defaults are left out.
export function parseState(search) {
  const params = new URLSearchParams(search);
  const [sort, dir] = (params.get('sort') || '').split(':');
  const min = Number.parseInt(params.get('min'), 10);
  const key = SORT_KEYS.includes(sort) ? sort : DEFAULTS.sort;
  return {
    q: params.get('svcq') || DEFAULTS.q,
    type: TYPES.some(([value]) => value === params.get('svctype')) ? params.get('svctype') : DEFAULTS.type,
    mine: params.get('mine') === '1',
    exclusive: params.get('excl') === '1',
    min: min > 1 ? min : DEFAULTS.min,
    sort: key,
    dir: dir === 'asc' || dir === 'desc' ? dir : DEFAULTS.dir,
    all: params.get('all') === '1',
  };
}

export function stateToSearch(state, keep = '') {
  const params = new URLSearchParams(keep);
  ['svcq', 'svctype', 'mine', 'excl', 'min', 'sort', 'all'].forEach(key => params.delete(key));
  if (state.q) params.set('svcq', state.q);
  if (state.type !== DEFAULTS.type) params.set('svctype', state.type);
  if (state.mine) params.set('mine', '1');
  if (state.exclusive) params.set('excl', '1');
  if (state.min > 1) params.set('min', String(state.min));
  if (state.sort !== DEFAULTS.sort || state.dir !== DEFAULTS.dir) params.set('sort', `${state.sort}:${state.dir}`);
  if (state.all) params.set('all', '1');
  const text = params.toString();
  return text ? `?${text}` : '';
}

// How many filters differ from the default, for "Filters (n)".
export const activeFilters = state => [state.q, state.type !== DEFAULTS.type, state.mine, state.exclusive, state.min > 1].filter(Boolean).length;
