import {test} from 'node:test';
import assert from 'node:assert/strict';

import {eveningSuggestions, filterFilms, matchesSection, selectedChanges, selectedKinds, similarOnServices, sortFilms, ageMatches, sortRatings, comingSoon} from '../../static/js/filtering.js';

const baseFilters = {
  query: '', availability: 'all', kind: 'all', minRating: 0, minVotes: 0, genre: 'all', keyword: 'all', runtime: 'all', mode: 'any',
  yearFrom: 0, yearTo: 9999, media: 'all', change: 'all', minimumProviders: 0, favoriteStatus: 'all',
  sort: 'title', favoritesOnly: false,
};
const films = [
  {title: 'Alpha', director: 'Nolan', year: 2001, rating: 7.5, popularity: 12, vote_count: 1000, keywords: ['heist'], runtime: 100, genres: ['Drama'], providers: {Netflix: ['flatrate'], 'Apple TV Store': ['rent']}},
  {title: 'Beta', year: 1999, rating: 6, popularity: 30, vote_count: 100, runtime: 80, genres: ['Comedy'], providers: {Arte: ['free'], Netflix: ['flatrate']}},
  {title: 'Gamma', year: 2020, rating: 8, popularity: 20, vote_count: 10000, runtime: 130, genres: ['Drama'], providers: {'Apple TV Store': ['rent']}},
];
const unavailable = [{title: 'Delta', year: 2010}];
const context = (selected, favorites = new Map()) => ({selected: new Set(selected), favorites});
const titles = list => list.map(film => film.title);

test('films appear in each section with a selected provider', () => {
  const view = filterFilms(films, unavailable, baseFilters, context(['Netflix', 'Arte']));
  assert.deepEqual(titles(view.sections.Free), ['Beta']);
  assert.deepEqual(titles(view.sections.Paid), ['Alpha', 'Beta']);
});

test('visible count counts each available film once and skips unavailable films', () => {
  const view = filterFilms(films, unavailable, baseFilters, context(['Netflix', 'Arte']));
  assert.equal(view.visibleCount, 2);
  assert.deepEqual(titles(view.unavailable), ['Delta']);
});

test('offer type only counts offers from selected providers', () => {
  const rent = {...baseFilters, kind: 'rent'};
  assert.equal(filterFilms(films, [], rent, context(['Netflix'])).visibleCount, 0);
  assert.deepEqual(titles(filterFilms(films, [], rent, context(['Netflix', 'Apple TV Store'])).sections.Paid), ['Alpha', 'Gamma']);
  assert.deepEqual(selectedKinds(films[0], new Set(['Netflix'])), ['flatrate']);
});

test('offer type belongs to its section', () => {
  const free = {...baseFilters, kind: 'free'};
  assert.equal(matchesSection(films[1], 'Paid', free, context(['Arte', 'Netflix'])), false);
  assert.equal(matchesSection(films[1], 'Free', free, context(['Arte', 'Netflix'])), true);
});

test('unavailable films only show for matching availability and no offer type', () => {
  const ctx = context(['Netflix']);
  assert.equal(filterFilms(films, unavailable, {...baseFilters, availability: 'available'}, ctx).unavailable.length, 0);
  assert.equal(filterFilms(films, unavailable, {...baseFilters, availability: 'unavailable'}, ctx).unavailable.length, 1);
  assert.equal(filterFilms(films, unavailable, {...baseFilters, availability: 'unavailable'}, ctx).visibleCount, 0);
  assert.equal(filterFilms(films, unavailable, {...baseFilters, kind: 'flatrate'}, ctx).unavailable.length, 0);
});

test('match mode "all" needs every selected provider', () => {
  const all = {...baseFilters, mode: 'all'};
  assert.deepEqual(titles(filterFilms(films, [], all, context(['Netflix'])).sections.Paid), ['Alpha', 'Beta']);
  assert.equal(filterFilms(films, [], all, context(['Netflix', 'Apple TV Store'])).sections.Paid.length, 1);
  assert.equal(filterFilms(films, [], all, context([])).visibleCount, 0);
});

test('common filters', () => {
  const ctx = context(['Netflix', 'Arte', 'Apple TV Store']);
  const count = filters => filterFilms(films, [], {...baseFilters, ...filters}, ctx).visibleCount;
  assert.equal(count({query: 'alp'}), 1);
  assert.equal(count({minRating: 7}), 2);
  assert.equal(count({genre: 'Drama'}), 2);
  assert.equal(count({runtime: 'short'}), 1);
  assert.equal(count({runtime: 'long'}), 1);
  assert.equal(count({yearFrom: 2000, yearTo: 2010}), 1);
  assert.equal(count({minimumProviders: 2}), 2);
  assert.equal(count({minVotes: 1000}), 2);
  assert.equal(count({query: 'nolan'}), 1);
  assert.equal(count({keyword: 'heist'}), 1);
});

test('minimum providers only counts selected providers', () => {
  const count = (selected, minimumProviders) => filterFilms(films, [], {...baseFilters, minimumProviders}, context(selected)).visibleCount;
  // Alpha and Beta have two providers each, but only one of them is selected.
  assert.equal(count(['Netflix'], 2), 0);
  assert.equal(count(['Netflix', 'Arte'], 2), 1);
});

test('exclusive availability shows the films the server marked', () => {
  const marked = films.map((film, index) => ({...film, only_on_my_services: index === 0}));
  const view = filterFilms(marked, [], {...baseFilters, exclusive: true}, context(['Netflix', 'Arte']));
  assert.deepEqual(view.sections.Paid.map(film => film.title), ['Alpha']);
  assert.equal(view.visibleCount, 1);
});

test('favorites filter uses the status', () => {
  const favorites = new Map([['Alpha|2001', {status: 'watched'}], ['Beta|1999', {status: 'plan'}]]);
  const ctx = context(['Netflix', 'Arte'], favorites);
  const view = filterFilms(films, [], {...baseFilters, favoritesOnly: true, favoriteStatus: 'plan'}, ctx);
  assert.equal(view.visibleCount, 1);
  assert.deepEqual(titles(view.sections.Paid), ['Beta']);
});

test('change filter only counts changes on selected providers', () => {
  const changed = [{title: 'Alpha', year: 2001, providers: {Netflix: ['flatrate']}, provider_changes: {added: ['Netflix'], removed: ['MUBI']}}];
  const gone = [{title: 'Delta', year: 2010, providers: {}, provider_changes: {added: [], removed: ['Netflix']}}];
  const count = (change, selected) => {
    const view = filterFilms(changed, gone, {...baseFilters, change}, context(selected));
    return [view.visibleCount, view.unavailable.length];
  };
  assert.deepEqual(count('added', ['Netflix']), [1, 0]);
  assert.deepEqual(count('removed', ['Netflix']), [0, 1]);
  assert.deepEqual(count('removed', ['Netflix', 'MUBI']), [1, 1]);
  assert.deepEqual(selectedChanges(changed[0], new Set(['Arte'])), {added: [], removed: []});
  // Left the only selected provider but still runs elsewhere: shown under "removed" only.
  const moved = [{title: 'Moved', year: 2000, providers: {Arte: ['free']}, provider_changes: {added: [], removed: ['Netflix']}}];
  assert.equal(filterFilms(moved, [], baseFilters, context(['Netflix'])).visibleCount, 0);
  assert.equal(filterFilms(moved, [], {...baseFilters, change: 'removed'}, context(['Netflix'])).visibleCount, 1);
});

test('sorting breaks ties by title', () => {
  const list = [{title: 'b', year: 2000}, {title: 'a', year: 2000}, {title: 'c', year: 2010}];
  assert.deepEqual(titles(sortFilms(list, 'year-desc')), ['c', 'a', 'b']);
  assert.deepEqual(titles(sortFilms(list, 'title')), ['a', 'b', 'c']);
});

test('sorts by popularity and vote count', () => {
  assert.deepEqual(titles(sortFilms(films, 'popularity')), ['Beta', 'Gamma', 'Alpha']);
  assert.deepEqual(titles(sortFilms(films, 'votes')), ['Gamma', 'Alpha', 'Beta']);
});

test('evening mode picks up to three films that fit, on own services, best rated first', () => {
  const film = (title, rating, runtime, providers, genres = ['Drama']) => ({title, rating, runtime, providers, genres});
  const evening = [
    film('Long', 9, 150, {Netflix: ['flatrate']}),
    film('Rent only', 9, 90, {Netflix: ['rent']}),
    film('Elsewhere', 9, 90, {MUBI: ['flatrate']}),
    film('Comedy', 9, 90, {Netflix: ['flatrate']}, ['Comedy']),
    film('Exactly two hours', 6, 120, {Netflix: ['flatrate']}),
    film('Free', 8, 95, {Arte: ['free']}),
    film('Good', 7, 100, {Netflix: ['flatrate']}),
    film('Unknown runtime', 9.5, 0, {Netflix: ['flatrate']}),
    film('Fourth', 5, 80, {Netflix: ['flatrate']}),
  ];
  const picks = eveningSuggestions(evening, {maximum: 120, genre: 'Drama', subscriptions: new Set(['Netflix', 'Arte'])});
  assert.deepEqual(picks.map(f => f.title), ['Free', 'Good', 'Exactly two hours']);
  assert.equal(eveningSuggestions(evening, {maximum: 0, genre: 'all', subscriptions: new Set(['Netflix'])})[0].title, 'Unknown runtime');
});

test('years entered the wrong way round are swapped', async () => {
  const {readFilters} = await import('../../static/js/filters.js');
  const values = {'year-from': '2020', 'year-to': '2000'};
  const doc = {getElementById: id => ({value: values[id] ?? ''})};
  const filters = readFilters(doc, false);
  assert.equal(filters.yearFrom, 2000);
  assert.equal(filters.yearTo, 2020);
  values['year-to'] = '';
  assert.deepEqual([readFilters(doc, false).yearFrom, readFilters(doc, false).yearTo], [2020, 9999]);
});

test('every set filter gets a chip and reset clears them all', async () => {
  const {FILTER_CONTROLS, activeFilters, resetFilters} = await import('../../static/js/filters.js');
  const select = (value, values) => ({value, options: values.map(item => ({value: item, text: `Label ${item}`})), get selectedIndex() { return values.indexOf(this.value); }, dataset: {}});
  const controls = {
    'film-search': {value: 'heat', dataset: {}},
    'min-rating': select('7', ['0', '7']),
    'media-filter': select('trailer', ['all', 'trailer']),
    'provider-count-filter': select('2', ['0', '2']),
    'change-filter': select('all', ['all', 'added']),
    'exclusive-filter': {type: 'checkbox', checked: true, dataset: {}},
  };
  const doc = {getElementById: id => controls[id] ?? null};
  assert.equal(FILTER_CONTROLS.length, 15);
  assert.deepEqual(activeFilters(doc).map(chip => chip.label), ['Search', 'Rating', 'Media', 'Services', 'Only on one of my services']);
  assert.equal(activeFilters(doc).find(chip => chip.id === 'min-rating').text, 'Label 7');
  resetFilters(doc);
  assert.deepEqual(activeFilters(doc), []);
  assert.equal(controls['min-rating'].value, '0');
  assert.equal(controls['exclusive-filter'].checked, false);
});

test('evening mode skips watched films', () => {
  const films = [
    {key: '1', title: 'Seen', rating: 9, runtime: 100, providers: {Netflix: ['flatrate']}},
    {key: '2', title: 'New', rating: 7, runtime: 100, providers: {Netflix: ['flatrate']}},
  ];
  const picks = eveningSuggestions(films, {maximum: 120, genre: 'all', subscriptions: new Set(['Netflix']), skip: new Set(['1'])});
  assert.deepEqual(picks.map(film => film.title), ['New']);
});

test('the compare button counts the chosen films', async () => {
  const {compareButtonState} = await import('../../static/js/rendering.js');
  assert.deepEqual(compareButtonState(0), {text: 'Compare'});
  assert.deepEqual(compareButtonState(3), {text: 'Compare (3)'});
});

test('weighted sorts: rating per hour, longest on the watchlist, own services, series', () => {
  const list = [
    {title: 'Long', rating: 8, runtime: 180, watchlist_position: 0, providers: {Netflix: ['flatrate']}},
    {title: 'Short', rating: 7, runtime: 90, watchlist_position: 5, providers: {Netflix: ['flatrate'], Arte: ['free']}, collection: 'B Collection', year: 2001},
    {title: 'Unknown', providers: {}, collection: 'B Collection', year: 1999},
    {title: 'Alien', rating: 8, runtime: 117, watchlist_position: 2, providers: {}, collection: 'A Collection', year: 1979},
  ];
  assert.deepEqual(titles(sortFilms(list, 'rating-per-hour')), ['Short', 'Alien', 'Long', 'Unknown']);
  assert.deepEqual(titles(sortFilms(list, 'watchlist-oldest')), ['Short', 'Alien', 'Long', 'Unknown']);
  assert.deepEqual(titles(sortFilms(list, 'own-services', {subscriptions: new Set(['Netflix', 'Arte'])})), ['Short', 'Long', 'Alien', 'Unknown']);
  assert.deepEqual(titles(sortFilms(list, 'series')), ['Alien', 'Unknown', 'Short', 'Long']);
});

test('recently removed lists each film once, only for own services', async () => {
  const {recentlyRemoved} = await import('../../static/js/filtering.js');
  const changes = [
    {created: 10, film_key: '1', title: 'Heat', provider: 'Netflix', change: 'removed'},
    {created: 20, film_key: '1', title: 'Heat', provider: 'Arte', change: 'removed'},
    {created: 30, film_key: '2', title: 'Alien', provider: 'MUBI', change: 'removed'},
    {created: 40, film_key: '3', title: 'Up', provider: 'Netflix', change: 'added'},
  ];
  const removed = recentlyRemoved(changes, new Set(['Netflix', 'Arte']));
  assert.deepEqual(removed.map(item => [item.title, item.providers]), [['Heat', ['Arte', 'Netflix']]]);
});

test('similar films: only watchlist films on own services, in TMDB order, not watched', () => {
  const heat = {key: '949', title: 'Heat', similar_ids: [3, 2, 1, 4, 949], providers: {}};
  const films = [
    heat,
    {key: '1', title: 'One', providers: {Netflix: ['flatrate']}},
    {key: '2', title: 'Two', providers: {Netflix: ['rent']}},
    {key: '3', title: 'Three', providers: {Arte: ['free']}},
    {key: '4', title: 'Four', providers: {Netflix: ['flatrate']}},
  ];
  const titles = list => list.map(film => film.title);
  assert.deepEqual(titles(similarOnServices(heat, films, new Set(['Netflix', 'Arte']))), ['Three', 'One', 'Four']);
  assert.deepEqual(titles(similarOnServices(heat, films, new Set(['Netflix']), new Set(['1']))), ['Four']);
  assert.deepEqual(similarOnServices({key: 'x', title: 'Old scan'}, films, new Set(['Netflix'])), []);
});

test('age rating: up to a number, exact for other systems, unrated films out', () => {
  assert.equal(ageMatches('all', undefined), true);
  assert.equal(ageMatches(undefined, '18'), true);
  assert.equal(ageMatches('12', '6'), true);
  assert.equal(ageMatches('12', '16'), false);
  assert.equal(ageMatches('12', null), false);
  assert.equal(ageMatches('PG-13', 'PG-13'), true);
  assert.equal(ageMatches('PG-13', 'R'), false);
  assert.deepEqual(sortRatings(['16', 'PG', '6', null, '12', '6', 'G']), ['6', '12', '16', 'G', 'PG']);
});

test('coming soon: only future dates, soonest first', () => {
  const films = [
    {title: 'Out', cinema_date: '2025-01-01', home_date: '2025-05-01'},
    {title: 'Home later', cinema_date: '2026-01-01', home_date: '2026-12-01'},
    {title: 'Cinema soon', cinema_date: '2026-11-20'},
    {title: 'No dates'},
  ];
  assert.deepEqual(comingSoon(films, '2026-11-16').map(film => film.title), ['Cinema soon', 'Home later']);
});
